from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand
)
from locales import t


def lang_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🇺🇿 O'zbek (lotin)")],
        [KeyboardButton(text="🇺🇿 Ўзбек (кирилл)")],
        [KeyboardButton(text="🇷🇺 Русский")],
    ], resize_keyboard=True, one_time_keyboard=True)


def role_keyboard(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("btn_client", lang)), KeyboardButton(text=t("btn_driver", lang))],
    ], resize_keyboard=True, one_time_keyboard=True)


def cancel_keyboard(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("btn_cancel", lang))]
    ], resize_keyboard=True, one_time_keyboard=True)


def share_phone_keyboard(lang):
    """Telefon: inline tugma yoki matn bilan kiritish."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("btn_share_phone", lang), request_contact=True)],
        [KeyboardButton(text=t("btn_cancel", lang))],
    ], resize_keyboard=True, one_time_keyboard=True)


def client_main_keyboard(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("btn_order_ride", lang))],
        [KeyboardButton(text=t("btn_my_orders", lang)), KeyboardButton(text=t("btn_cancel_order", lang))],
        [KeyboardButton(text=t("btn_profile", lang))],
    ], resize_keyboard=True)


def driver_main_keyboard(lang, status="offline"):
    toggle = t("btn_go_offline", lang) if status == "online" else t("btn_go_online", lang)
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=toggle)],
        [KeyboardButton(text=t("btn_my_stats", lang)), KeyboardButton(text=t("btn_profile", lang))],
    ], resize_keyboard=True)


def from_location_keyboard(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("loc_toshkent", lang))],
        [KeyboardButton(text=t("loc_andijon", lang)), KeyboardButton(text=t("loc_xonabod", lang))],
        [KeyboardButton(text="📍 " + t("btn_send_location", lang), request_location=True)],
        [KeyboardButton(text=t("btn_cancel", lang))],
    ], resize_keyboard=True, one_time_keyboard=True)


def to_location_keyboard(lang, exclude=None):
    locs = [t("loc_toshkent", lang), t("loc_andijon", lang), t("loc_xonabod", lang)]
    buttons = [[KeyboardButton(text=l)] for l in locs if l != exclude]
    buttons.append([KeyboardButton(text="📍 " + t("btn_send_location", lang), request_location=True)])
    buttons.append([KeyboardButton(text=t("btn_cancel", lang))])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def people_count_keyboard(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="1"), KeyboardButton(text="2"),
         KeyboardButton(text="3"), KeyboardButton(text="4")],
        [KeyboardButton(text=t("btn_cancel", lang))],
    ], resize_keyboard=True, one_time_keyboard=True)


def order_action_keyboard(order_id, lang):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_accept_order", lang), callback_data=f"accept:{order_id}"),
        InlineKeyboardButton(text=t("btn_reject_order", lang), callback_data=f"reject:{order_id}"),
    ]])


def complete_order_keyboard(order_id, lang):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_complete_order", lang), callback_data=f"complete:{order_id}")
    ]])


def client_edit_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_edit_name", lang),  callback_data="edit_client:name")],
        [InlineKeyboardButton(text=t("btn_edit_phone", lang), callback_data="edit_client:phone")],
        [InlineKeyboardButton(text=t("btn_cancel", lang),     callback_data="edit_client:cancel")],
    ])


def driver_edit_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_edit_name", lang),       callback_data="edit_driver:name")],
        [InlineKeyboardButton(text=t("btn_edit_phone", lang),      callback_data="edit_driver:phone")],
        [InlineKeyboardButton(text=t("btn_edit_car_number", lang), callback_data="edit_driver:car_number")],
        [InlineKeyboardButton(text=t("btn_edit_car_model", lang),  callback_data="edit_driver:car_model")],
        [InlineKeyboardButton(text=t("btn_edit_car_color", lang),  callback_data="edit_driver:car_color")],
        [InlineKeyboardButton(text=t("btn_cancel", lang),          callback_data="edit_driver:cancel")],
    ])


def driver_contact_keyboard(driver_name: str, phone: str, username: str | None, lang: str):
    """
    Haydovchi ma'lumotlari — mijozga yuboriladi.
    Telegram username bo'lsa profil havolasi, telefon matn ko'rinishida.
    """
    rows = []
    if username:
        rows.append([InlineKeyboardButton(
            text=f"✉️ {driver_name} (Telegram)",
            url=f"https://t.me/{username.lstrip('@')}"
        )])
    # tel: Telegram da ishlamaydi — raqamni faqat matn sifatida xabarda ko'rsatamiz
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def client_contact_keyboard(client_name: str, phone: str, username: str | None, lang: str):
    """
    Mijoz ma'lumotlari — haydovchiga yuboriladi.
    """
    rows = []
    if username:
        rows.append([InlineKeyboardButton(
            text=f"✉️ {client_name} (Telegram)",
            url=f"https://t.me/{username.lstrip('@')}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


MENU_COMMANDS = [
    BotCommand(command="start",   description="🔄 Botni boshlash / Запустить бота"),
    BotCommand(command="lang",    description="🌐 Tilni o'zgartirish / Сменить язык"),
    BotCommand(command="menu",    description="🏠 Asosiy menyu / Главное меню"),
    BotCommand(command="profile", description="👤 Profil / Профиль"),
    BotCommand(command="help",    description="❓ Yordam / Помощь"),
    BotCommand(command="cancel",  description="❌ Bekor qilish / Отмена"),
]
