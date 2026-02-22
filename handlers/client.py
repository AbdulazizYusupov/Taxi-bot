import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import (
    get_client, create_client, get_client_by_id,
    update_client, create_order, update_order_status,
    get_client_active_order, get_online_drivers_sorted,
    add_rejected_driver, parse_rejected_ids, get_order
)
from keyboards.keyboards import (
    client_main_keyboard, cancel_keyboard, share_phone_keyboard,
    from_location_keyboard, to_location_keyboard,
    people_count_keyboard, client_edit_keyboard
)
from locales import t
from states import ClientRegState, OrderState, ClientEditState

logger = logging.getLogger(__name__)
router = Router()

ALL_LOCS = [
    "🏙 Toshkent", "🏙 Andijon", "🏙 Xonabod",
    "🏙 Тошкент", "🏙 Андижон", "🏙 Хонобод",
    "🏙 Ташкент", "🏙 Андижан", "🏙 Ханабад",
]


def is_cancel(text, lang):
    return (text or "") == t("btn_cancel", lang)


def norm_loc(text, lang):
    lo = (text or "").lower()
    if any(w in lo for w in ["toshkent", "ташкент", "тошкент"]): return t("loc_toshkent", lang)
    if any(w in lo for w in ["andijon", "андижан", "андижон"]):   return t("loc_andijon", lang)
    if any(w in lo for w in ["xonabod", "ханабад", "хонобод"]):   return t("loc_xonabod", lang)
    return text


def map_link(lat, lon, lang):
    labels = {"uz": "🗺 Xaritada ko'rish", "kr": "🗺 Кўриш", "ru": "🗺 На карте"}
    return f'\n<a href="https://maps.google.com/?q={lat},{lon}">{labels.get(lang, labels["uz"])}</a>'


def build_driver_keyboard(order_id, client_name, phone, username, lang):
    rows = [[
        InlineKeyboardButton(
            text=t("btn_accept_order", lang), callback_data=f"accept:{order_id}"
        ),
        InlineKeyboardButton(
            text=t("btn_reject_order", lang), callback_data=f"reject:{order_id}"
        ),
    ]]
    if username:
        rows.append([InlineKeyboardButton(
            text=f"✉️ {client_name} (Telegram)",
            url=f"https://t.me/{username.lstrip('@')}"
        )])
    # tel: protokoli Telegram da ishlamaydi — callback orqali raqamni ko'rsatamiz
    if phone and phone != "—":
        rows.append([InlineKeyboardButton(
            text=f"📞 {phone}",
            callback_data=f"show_phone:{order_id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_order_to_driver(bot: Bot, order_id: int):
    """
    Order uchun keyingi bo'sh driverga yuboradi.
    - Online driverlarni balance ASC tartibda oladi
    - Allaqachon rad etganlarni chiqarib tashlaydi
    - Birinchi mos kelgan driverga yuboradi va to'xtaydi
    """
    order = await get_order(order_id)
    if not order:
        logger.warning(f"send_order: order #{order_id} topilmadi")
        return

    if order["status"] != "pending":
        logger.info(f"send_order: order #{order_id} status={order['status']}, skip")
        return

    # Rad etgan driverlar ro'yxati
    try:
        rejected_ids = parse_rejected_ids(order["rejected_driver_ids"] or "")
    except (IndexError, KeyError):
        rejected_ids = []
    logger.info(f"Order #{order_id}: rejected_ids={rejected_ids}")

    # Online driverlar (rad etganlarni chiqarib)
    available = await get_online_drivers_sorted(exclude_ids=rejected_ids)
    logger.info(f"Order #{order_id}: available drivers={len(available)}")

    if not available:
        # Online driver yo'q yoki hammasi rad etdi
        client = await get_client_by_id(order["client_id"])
        if client:
            if rejected_ids:
                msg_key = "order_no_more_drivers"
            else:
                msg_key = "no_drivers_online"
            try:
                await bot.send_message(
                    chat_id=client["telegram_id"],
                    text=t(msg_key, client["lang"])
                )
            except Exception as e:
                logger.error(f"Mijozga xabar yuborib bo'lmadi: {e}")
        await update_order_status(order_id, "cancelled")
        return

    # Faqat birinchi driverga yuboramiz
    driver = available[0]
    client = await get_client_by_id(order["client_id"])
    dlang = driver["lang"]

    from_link = map_link(order["from_lat"], order["from_lon"], dlang) \
                if order["from_lat"] and order["from_lon"] else ""
    to_link   = map_link(order["to_lat"], order["to_lon"], dlang) \
                if order["to_lat"] and order["to_lon"] else ""

    text = t("new_order_for_driver", dlang,
             order_id=order_id,
             client_name=client["full_name"] if client else "—",
             client_phone=client["phone_number"] if client and client["phone_number"] else "—",
             count=order["count_of_people"],
             from_loc=order["from_location"], from_link=from_link,
             to_loc=order["to_location"],     to_link=to_link)

    kb = build_driver_keyboard(
        order_id=order_id,
        client_name=client["full_name"] if client else "—",
        phone=client["phone_number"] if client else "",
        username=client["username"] if client else "",
        lang=dlang
    )

    try:
        await bot.send_message(
            chat_id=driver["telegram_id"],
            text=text,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info(
            f"✅ Order #{order_id} -> driver '{driver['full_name']}' "
            f"(tg_id={driver['telegram_id']}, balance={driver['balance']})"
        )
    except Exception as e:
        logger.warning(
            f"❌ Driver '{driver['full_name']}' (tg_id={driver['telegram_id']}) "
            f"ga yuborib bo'lmadi: {e}"
        )
        # Driver botni bloklagan — uni rad etganlar ro'yxatiga qo'shamiz
        await add_rejected_driver(order_id, driver["id"])
        # Keyingi driverga o'tamiz (recursive emas — yangi chaqiriq)
        await send_order_to_driver(bot, order_id)


# ── MIJOZ RO'YXATDAN O'TISH ───────────────────────────────────────────────────

@router.message(ClientRegState.name)
async def client_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang))
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer(t("ask_client_name", lang), parse_mode="HTML")
        return
    await state.update_data(client_name=name)
    await message.answer(
        t("ask_client_phone", lang),
        parse_mode="HTML",
        reply_markup=share_phone_keyboard(lang)
    )
    await state.set_state(ClientRegState.phone)


@router.message(ClientRegState.phone)
async def client_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang))
        return
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"): phone = "+" + phone
    elif message.text:
        phone = message.text.strip()
    else:
        await message.answer(
            t("ask_client_phone", lang),
            parse_mode="HTML",
            reply_markup=share_phone_keyboard(lang)
        )
        return
    name = data["client_name"]
    username = message.from_user.username
    await create_client(name, message.from_user.id, phone, lang, username)
    await state.clear()
    await message.answer(
        t("client_registered", lang, name=name, phone=phone),
        parse_mode="HTML",
        reply_markup=client_main_keyboard(lang)
    )


# ── PROFIL ────────────────────────────────────────────────────────────────────

async def show_client_profile(message: Message):
    """Faqat mijoz uchun — driver.py universal handler ichidan chaqiriladi."""
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer(t("not_registered", "uz"))
        return
    lang = client["lang"]
    await message.answer(
        t("profile_client", lang,
          name=client["full_name"],
          phone=client["phone_number"] or "—"),
        reply_markup=client_edit_keyboard(lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("edit_client:"))
async def edit_client_cb(callback: CallbackQuery, state: FSMContext):
    client = await get_client(callback.from_user.id)
    if not client:
        await callback.answer()
        return
    lang = client["lang"]
    field = callback.data.split(":")[1]
    if field == "cancel":
        await callback.message.delete()
        await callback.answer()
        return
    state_map = {
        "name":  ClientEditState.editing_name,
        "phone": ClientEditState.editing_phone
    }
    await state.update_data(lang=lang)
    if field == "phone":
        await callback.message.answer(
            t("ask_client_phone", lang),
            parse_mode="HTML",
            reply_markup=share_phone_keyboard(lang)
        )
    else:
        await callback.message.answer(
            t("enter_new_value", lang),
            reply_markup=cancel_keyboard(lang)
        )
    await state.set_state(state_map[field])
    await callback.answer()


@router.message(ClientEditState.editing_name)
async def client_edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang))
        return
    await update_client(message.from_user.id, full_name=(message.text or "").strip())
    await state.clear()
    await message.answer(t("profile_updated", lang), reply_markup=client_main_keyboard(lang))


@router.message(ClientEditState.editing_phone)
async def client_edit_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang))
        return
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"): phone = "+" + phone
    else:
        phone = (message.text or "").strip()
    await update_client(message.from_user.id, phone_number=phone)
    await state.clear()
    await message.answer(t("profile_updated", lang), reply_markup=client_main_keyboard(lang))


# ── BUYURTMA ──────────────────────────────────────────────────────────────────

@router.message(F.text.func(lambda txt: any(
    w in (txt or "").lower() for w in [
        "yo'l buyurtma", "йўл буюртма", "заказать поездку", "yol buyurtma"
    ]
)))
async def order_ride(message: Message, state: FSMContext):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer(t("not_registered", "uz"))
        return
    lang = client["lang"]
    active = await get_client_active_order(client["id"])
    if active:
        await message.answer(
            t("order_created", lang,
              from_loc=active["from_location"],
              to_loc=active["to_location"],
              count=active["count_of_people"]),
            parse_mode="HTML"
        )
        return
    await state.update_data(lang=lang, client_id=client["id"])
    await message.answer(t("ask_from_location", lang), reply_markup=from_location_keyboard(lang))
    await state.set_state(OrderState.from_location)


@router.message(OrderState.from_location)
async def order_from(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=client_main_keyboard(lang))
        return
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        await state.update_data(
            from_location=f"GPS ({lat:.5f}, {lon:.5f})",
            from_lat=lat, from_lon=lon
        )
        await message.answer(
            f"✅ {t('location_received', lang)}\n\n{t('ask_to_location', lang)}",
            reply_markup=to_location_keyboard(lang)
        )
        await state.set_state(OrderState.to_location)
        return
    if (message.text or "") not in ALL_LOCS:
        await message.answer(t("ask_from_location", lang), reply_markup=from_location_keyboard(lang))
        return
    loc = norm_loc(message.text, lang)
    await state.update_data(from_location=loc, from_lat=None, from_lon=None)
    await message.answer(t("ask_to_location", lang), reply_markup=to_location_keyboard(lang, exclude=loc))
    await state.set_state(OrderState.to_location)


@router.message(OrderState.to_location)
async def order_to(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    from_loc = data.get("from_location", "")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=client_main_keyboard(lang))
        return
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        await state.update_data(
            to_location=f"GPS ({lat:.5f}, {lon:.5f})",
            to_lat=lat, to_lon=lon
        )
        await message.answer(
            f"✅ {t('location_received', lang)}\n\n{t('ask_people_count', lang)}",
            parse_mode="HTML",
            reply_markup=people_count_keyboard(lang)
        )
        await state.set_state(OrderState.people_count)
        return
    if (message.text or "") not in ALL_LOCS:
        await message.answer(t("ask_to_location", lang),
                             reply_markup=to_location_keyboard(lang, exclude=from_loc))
        return
    loc = norm_loc(message.text, lang)
    if loc == from_loc:
        await message.answer(t("ask_to_location", lang),
                             reply_markup=to_location_keyboard(lang, exclude=from_loc))
        return
    await state.update_data(to_location=loc, to_lat=None, to_lon=None)
    await message.answer(t("ask_people_count", lang), parse_mode="HTML",
                         reply_markup=people_count_keyboard(lang))
    await state.set_state(OrderState.people_count)


@router.message(OrderState.people_count)
async def order_people(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if is_cancel(message.text, lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=client_main_keyboard(lang))
        return
    try:
        count = int(message.text or "")
        if not 1 <= count <= 4: raise ValueError
    except ValueError:
        await message.answer(t("invalid_people_count", lang),
                             reply_markup=people_count_keyboard(lang))
        return

    from_loc = data["from_location"]
    to_loc   = data["to_location"]
    from_lat = data.get("from_lat")
    from_lon = data.get("from_lon")
    to_lat   = data.get("to_lat")
    to_lon   = data.get("to_lon")

    # Username yangilash
    await update_client(message.from_user.id, username=message.from_user.username)

    order_id = await create_order(
        data["client_id"], count, from_loc, to_loc,
        from_lat, from_lon, to_lat, to_lon
    )
    await state.clear()

    logger.info(f"Yangi order #{order_id} yaratildi, client_id={data['client_id']}")

    await message.answer(
        t("order_created", lang, from_loc=from_loc, to_loc=to_loc, count=count),
        parse_mode="HTML",
        reply_markup=client_main_keyboard(lang)
    )

    # Bitta driverga yuborish
    await send_order_to_driver(bot, order_id)


# ── TELEFON RAQAM KO'RSATISH ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("show_phone:"))
async def show_phone_callback(callback: CallbackQuery):
    """Driver mijoz raqamini ko'rish uchun tugmani bosganda."""
    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    client = await get_client_by_id(order["client_id"])
    if client and client["phone_number"]:
        await callback.answer(f"📞 {client['phone_number']}", show_alert=True)
    else:
        await callback.answer("Raqam topilmadi", show_alert=True)


# ── BEKOR QILISH / BUYURTMALARIM ─────────────────────────────────────────────

@router.message(F.text.func(lambda txt: any(
    w in (txt or "").lower() for w in ["buyurtmani bekor", "буюртмани бекор", "отменить заказ"]
)))
async def cancel_active_order(message: Message, bot: Bot):
    client = await get_client(message.from_user.id)
    if not client: return
    lang = client["lang"]
    active = await get_client_active_order(client["id"])
    if not active:
        await message.answer(t("no_active_order", lang))
        return

    order_id = active["id"]
    driver_id = active["driver_id"]  # qabul qilgan driver (agar bo'lsa)

    await update_order_status(order_id, "cancelled")
    await message.answer(t("order_cancelled_by_client", lang))

    # Agar driver qabul qilgan bo'lsa — unga xabar yuboramiz
    if driver_id:
        from database.db import get_driver_by_id
        driver = await get_driver_by_id(driver_id)
        if driver:
            try:
                await bot.send_message(
                    chat_id=driver["telegram_id"],
                    text=t("order_cancelled_by_client_notify", driver["lang"])
                )
            except Exception:
                pass


@router.message(F.text.func(lambda txt: any(
    w in (txt or "").lower() for w in ["mening buyurtmalarim", "менинг буюртмаларим", "мои заказы"]
)))
async def my_orders(message: Message):
    client = await get_client(message.from_user.id)
    if not client: return
    lang = client["lang"]
    active = await get_client_active_order(client["id"])
    if not active:
        await message.answer(t("no_active_order", lang))
        return
    await message.answer(
        t("order_created", lang,
          from_loc=active["from_location"],
          to_loc=active["to_location"],
          count=active["count_of_people"]),
        parse_mode="HTML"
    )
