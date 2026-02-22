from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import (
    get_driver, create_driver, get_client_by_id,
    update_driver, update_driver_status, get_order,
    update_order_status, increment_driver_balance,
    add_rejected_driver
)
from keyboards.keyboards import (
    driver_main_keyboard, cancel_keyboard, share_phone_keyboard,
    complete_order_keyboard, driver_edit_keyboard,
    driver_contact_keyboard
)
from locales import t
from states import DriverRegState, DriverEditState

router = Router()


def is_cancel(text, lang):
    return (text or "") == t("btn_cancel", lang)


# ── RO'YXATDAN O'TISH ────────────────────────────────────────────────────────

@router.message(DriverRegState.name)
async def drv_name(message: Message, state: FSMContext):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang): await state.clear(); await message.answer(t("cancelled", lang)); return
    await state.update_data(driver_name=(message.text or "").strip())
    await message.answer(t("ask_driver_age", lang), parse_mode="HTML")
    await state.set_state(DriverRegState.age)


@router.message(DriverRegState.age)
async def drv_age(message: Message, state: FSMContext):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang): await state.clear(); await message.answer(t("cancelled", lang)); return
    try:
        age = int(message.text or "")
        if not 18 <= age <= 70: raise ValueError
    except ValueError:
        await message.answer(t("invalid_age", lang), parse_mode="HTML"); return
    await state.update_data(driver_age=age)
    await message.answer(t("ask_driver_phone", lang), parse_mode="HTML",
                         reply_markup=share_phone_keyboard(lang))
    await state.set_state(DriverRegState.phone)


@router.message(DriverRegState.phone)
async def drv_phone(message: Message, state: FSMContext):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang): await state.clear(); await message.answer(t("cancelled", lang)); return

    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"): phone = "+" + phone
    elif message.text:
        phone = message.text.strip()
    else:
        await message.answer(t("ask_driver_phone", lang), parse_mode="HTML",
                             reply_markup=share_phone_keyboard(lang)); return

    await state.update_data(driver_phone=phone)
    await message.answer(t("ask_car_number", lang), parse_mode="HTML")
    await state.set_state(DriverRegState.car_number)


@router.message(DriverRegState.car_number)
async def drv_car_number(message: Message, state: FSMContext):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang): await state.clear(); await message.answer(t("cancelled", lang)); return
    await state.update_data(car_number=(message.text or "").strip().upper())
    await message.answer(t("ask_car_model", lang), parse_mode="HTML")
    await state.set_state(DriverRegState.car_model)


@router.message(DriverRegState.car_model)
async def drv_car_model(message: Message, state: FSMContext):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang): await state.clear(); await message.answer(t("cancelled", lang)); return
    await state.update_data(car_model=(message.text or "").strip())
    await message.answer(t("ask_car_color", lang), parse_mode="HTML")
    await state.set_state(DriverRegState.car_color)


@router.message(DriverRegState.car_color)
async def drv_car_color(message: Message, state: FSMContext):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang): await state.clear(); await message.answer(t("cancelled", lang)); return
    car_color = (message.text or "").strip()
    data = await state.get_data()
    username = message.from_user.username
    await create_driver(
        data["driver_name"], data["driver_age"], message.from_user.id,
        data["car_number"], data["driver_phone"],
        data["car_model"], car_color, lang, username
    )
    await state.clear()
    await message.answer(
        t("driver_registered", lang, name=data["driver_name"], phone=data["driver_phone"],
          model=data["car_model"], color=car_color, car_number=data["car_number"]),
        parse_mode="HTML", reply_markup=driver_main_keyboard(lang, "offline")
    )


# ── PROFIL ────────────────────────────────────────────────────────────────────

@router.message(F.text.func(lambda txt: any(
    w in (txt or "").lower() for w in ["profil", "профил", "профиль"]
)))
async def show_profile(message: Message):
    """Driver bo'lsa — driver profili, client bo'lsa — client profili."""
    driver = await get_driver(message.from_user.id)
    if driver:
        lang = driver["lang"]
        status_text = t("status_online", lang) if driver["status"] == "online" else t("status_offline", lang)
        await message.answer(
            t("profile_driver", lang,
              name=driver["full_name"], phone=driver["phone_number"] or "—",
              model=driver["car_model"] or "—", color=driver["car_color"] or "—",
              car_number=driver["car_number"] or "—",
              balance=driver["balance"], status=status_text),
            reply_markup=driver_edit_keyboard(lang),
            parse_mode="HTML"
        )
        return
    # Client bo'lsa
    from handlers.client import show_client_profile
    await show_client_profile(message)


@router.callback_query(F.data.startswith("edit_driver:"))
async def edit_driver_cb(callback: CallbackQuery, state: FSMContext):
    driver = await get_driver(callback.from_user.id)
    if not driver: await callback.answer(); return
    lang = driver["lang"]
    field = callback.data.split(":")[1]
    if field == "cancel":
        await callback.message.delete(); await callback.answer(); return
    state_map = {
        "name":       DriverEditState.editing_name,
        "phone":      DriverEditState.editing_phone,
        "car_number": DriverEditState.editing_car_number,
        "car_model":  DriverEditState.editing_car_model,
        "car_color":  DriverEditState.editing_car_color,
    }
    await state.update_data(lang=lang, edit_field=field)
    if field == "phone":
        await callback.message.answer(t("ask_driver_phone", lang), parse_mode="HTML",
                                      reply_markup=share_phone_keyboard(lang))
    else:
        await callback.message.answer(t("enter_new_value", lang), reply_markup=cancel_keyboard(lang))
    await state.set_state(state_map[field])
    await callback.answer()


async def _save_driver(message: Message, state: FSMContext, field: str):
    data = await state.get_data(); lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear(); await message.answer(t("cancelled", lang)); return
    if message.contact:
        val = message.contact.phone_number
        if not val.startswith("+"): val = "+" + val
    else:
        val = (message.text or "").strip()
    if field == "car_number": val = val.upper()
    await update_driver(message.from_user.id, **{field: val})
    await state.clear()
    driver = await get_driver(message.from_user.id)
    await message.answer(t("profile_updated", lang),
                         reply_markup=driver_main_keyboard(lang, driver["status"] if driver else "offline"))


@router.message(DriverEditState.editing_name)
async def drv_edit_name(message: Message, state: FSMContext):
    await _save_driver(message, state, "full_name")

@router.message(DriverEditState.editing_phone)
async def drv_edit_phone(message: Message, state: FSMContext):
    await _save_driver(message, state, "phone_number")

@router.message(DriverEditState.editing_car_number)
async def drv_edit_car_number(message: Message, state: FSMContext):
    await _save_driver(message, state, "car_number")

@router.message(DriverEditState.editing_car_model)
async def drv_edit_car_model(message: Message, state: FSMContext):
    await _save_driver(message, state, "car_model")

@router.message(DriverEditState.editing_car_color)
async def drv_edit_car_color(message: Message, state: FSMContext):
    await _save_driver(message, state, "car_color")


# ── ONLINE / OFFLINE ──────────────────────────────────────────────────────────

@router.message(F.text.func(lambda txt: any(
    w in (txt or "").lower() for w in [
        "online bo'lish","онлайн бўлиш","выйти онлайн",
        "offline bo'lish","оффлайн бўлиш","выйти оффлайн",
        "online bo`lish","offline bo`lish",
    ]
)))
async def toggle_status(message: Message):
    driver = await get_driver(message.from_user.id)
    if not driver: await message.answer(t("not_registered", "uz")); return
    lang = driver["lang"]
    new_status = "offline" if driver["status"] == "online" else "online"
    await update_driver_status(message.from_user.id, new_status)
    # Username ni yangilab qo'yamiz
    await update_driver(message.from_user.id, username=message.from_user.username)
    key = "driver_online" if new_status == "online" else "driver_offline"
    await message.answer(t(key, lang), reply_markup=driver_main_keyboard(lang, new_status))


# ── STATISTIKA ────────────────────────────────────────────────────────────────

@router.message(F.text.func(lambda txt: any(
    w in (txt or "").lower() for w in ["statistika", "статистика", "📊"]
)))
async def my_stats(message: Message):
    driver = await get_driver(message.from_user.id)
    if not driver: return
    lang = driver["lang"]
    await message.answer(
        t("driver_stats", lang, name=driver["full_name"], balance=driver["balance"],
          model=driver["car_model"] or "—", color=driver["car_color"] or "—",
          car_number=driver["car_number"] or "—"),
        parse_mode="HTML"
    )


# ── BUYURTMA QABUL ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("accept:"))
async def accept_order(callback: CallbackQuery, bot: Bot):
    driver = await get_driver(callback.from_user.id)
    if not driver: await callback.answer(); return
    lang = driver["lang"]

    if driver["status"] != "online":
        await callback.answer(t("must_be_online", lang), show_alert=True); return

    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)

    if not order or order["status"] != "pending":
        await callback.answer(t("order_already_taken", lang), show_alert=True)
        try: await callback.message.delete()
        except: pass
        return

    await update_order_status(order_id, "accepted", driver["id"])
    await callback.message.edit_text(t("order_accepted_driver", lang))
    await callback.message.answer(
        t("order_accepted_driver", lang),
        reply_markup=complete_order_keyboard(order_id, lang)
    )

    # Mijozga haydovchi ma'lumotlari + kontakt tugmalari (tel + telegram)
    client = await get_client_by_id(order["client_id"])
    if client:
        client_lang = client["lang"]
        # Haydovchi username ni yangilash
        await update_driver(callback.from_user.id, username=callback.from_user.username)
        driver = await get_driver(callback.from_user.id)  # yangilangan
        # Telegram username havolasi (faqat username bo'lsa)
        kb = driver_contact_keyboard(
            driver_name=driver["full_name"],
            phone=driver["phone_number"] or "—",
            username=driver["username"],
            lang=client_lang
        )
        try:
            await bot.send_message(
                chat_id=client["telegram_id"],
                text=t("order_accepted_by_driver", client_lang,
                       driver_name=driver["full_name"],
                       phone=driver["phone_number"] or "—",
                       car_model=driver["car_model"] or "—",
                       car_color=driver["car_color"] or "—",
                       car_number=driver["car_number"] or "—"),
                reply_markup=kb if kb else None,
                parse_mode="HTML"
            )
        except Exception:
            pass
    await callback.answer()


# ── BUYURTMA RAD ETISH ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject:"))
async def reject_order(callback: CallbackQuery, bot: Bot):
    driver = await get_driver(callback.from_user.id)
    lang = driver["lang"] if driver else "uz"
    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)
    await callback.message.edit_text(t("order_rejected", lang))
    await callback.answer()
    if driver and order and order["status"] == "pending":
        await add_rejected_driver(order_id, driver["id"])
        from handlers.client import send_order_to_driver
        await send_order_to_driver(bot, order_id)


# ── BUYURTMA YAKUNLASH ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("complete:"))
async def complete_order(callback: CallbackQuery, bot: Bot):
    driver = await get_driver(callback.from_user.id)
    if not driver: await callback.answer(); return
    lang = driver["lang"]
    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)
    if not order or order["status"] != "accepted": await callback.answer(); return
    await update_order_status(order_id, "completed")
    await increment_driver_balance(driver["id"])
    await callback.message.edit_text(t("order_completed", lang))
    client = await get_client_by_id(order["client_id"])
    if client:
        try:
            await bot.send_message(chat_id=client["telegram_id"],
                                   text=t("order_completed", client["lang"]))
        except: pass
    await callback.answer()
