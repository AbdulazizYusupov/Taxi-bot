from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import get_client, get_driver, update_client_lang, update_driver_lang
from keyboards.keyboards import lang_keyboard, role_keyboard, client_main_keyboard, driver_main_keyboard
from locales import t
from states import LangState, RoleState, ClientRegState, DriverRegState

router = Router()


def get_lang_from_text(text: str) -> str:
    text = (text or "").lower()
    if "кирилл" in text or "ўзбек" in text: return "kr"
    if "русский" in text or "рус" in text:  return "ru"
    return "uz"


async def get_user_lang(telegram_id: int) -> str:
    client = await get_client(telegram_id)
    if client: return client["lang"]
    driver = await get_driver(telegram_id)
    if driver: return driver["lang"]
    return "uz"


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    client = await get_client(message.from_user.id)
    driver = await get_driver(message.from_user.id)
    if client:
        lang = client["lang"]
        await message.answer(t("already_registered", lang), reply_markup=client_main_keyboard(lang)); return
    if driver:
        lang = driver["lang"]
        await message.answer(t("already_registered", lang), reply_markup=driver_main_keyboard(lang, driver["status"])); return
    await message.answer(t("choose_lang", "uz"), reply_markup=lang_keyboard())
    await state.set_state(LangState.choosing)


@router.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    await message.answer(t("choose_lang", lang), reply_markup=lang_keyboard())
    await state.set_state(LangState.choosing)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    client = await get_client(message.from_user.id)
    if client:
        lang = client["lang"]
        await message.answer(t("client_menu", lang), reply_markup=client_main_keyboard(lang)); return
    driver = await get_driver(message.from_user.id)
    if driver:
        lang = driver["lang"]
        status_text = t("status_online",lang) if driver["status"]=="online" else t("status_offline",lang)
        await message.answer(t("driver_menu", lang, status=status_text),
                             reply_markup=driver_main_keyboard(lang, driver["status"])); return
    await message.answer(t("not_registered", "uz"))


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Profile commandini client/driver handlerlari ushlaydi — bu yerda redirect."""
    driver = await get_driver(message.from_user.id)
    if driver:
        from handlers.driver import show_profile
        await show_profile(message)
        return
    client = await get_client(message.from_user.id)
    if client:
        from handlers.client import show_client_profile
        await show_client_profile(message)
        return
    await message.answer(t("not_registered", "uz"))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    await state.clear()
    await message.answer(t("cancelled", lang))


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(t("help_text", lang))


@router.message(Command("about"))
async def cmd_about(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(t("about_text", lang))


# ── Til tanlash ───────────────────────────────────────────────────────────────

@router.message(LangState.choosing)
async def process_lang_choice(message: Message, state: FSMContext):
    lang = get_lang_from_text(message.text or "")
    client = await get_client(message.from_user.id)
    driver = await get_driver(message.from_user.id)
    if client:
        await update_client_lang(message.from_user.id, lang)
        await state.clear()
        await message.answer(t("lang_set", lang), reply_markup=client_main_keyboard(lang)); return
    if driver:
        await update_driver_lang(message.from_user.id, lang)
        await state.clear()
        await message.answer(t("lang_set", lang), reply_markup=driver_main_keyboard(lang, driver["status"])); return
    await state.update_data(lang=lang)
    await message.answer(t("lang_set", lang))
    await message.answer(t("welcome", lang), reply_markup=role_keyboard(lang))
    await state.set_state(RoleState.choosing)


# ── Rol tanlash ───────────────────────────────────────────────────────────────

@router.message(RoleState.choosing)
async def process_role_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = (message.text or "").lower()
    if any(w in text for w in ["mijoz", "клиент", "мижоз"]):
        await message.answer(t("ask_client_name", lang), parse_mode="HTML")
        await state.set_state(ClientRegState.name)
    elif any(w in text for w in ["haydovchi", "ҳайдовчи", "водитель"]):
        await message.answer(t("ask_driver_name", lang), parse_mode="HTML")
        await state.set_state(DriverRegState.name)
    else:
        await message.answer(t("welcome", lang), reply_markup=role_keyboard(lang))
