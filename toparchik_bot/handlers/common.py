from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from toparchik_bot import config

router = Router()

# --- Keyboards ---
def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📥 Media"))
    builder.add(types.KeyboardButton(text="📄 Word<->Pdf"))
    builder.add(types.KeyboardButton(text="🎤 Artistlar"))
    builder.add(types.KeyboardButton(text="🆘 Help"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# --- Prompts and Constants ---
BOT_LINK = "@toparchik_bot"
PROMO_TEXT = f"\n\n🔥 <i>Eng sara musiqalar va aqlli AI xizmatlari faqat bizda: {BOT_LINK}</i>"

WELCOME_TEXT = (
    "<b>✨ TOPARCHIK AI - Universal Media App</b>\n\n"
    "Web App interfeysini ochish uchun pastdagi <b>🚀 Open</b> tugmasini bosing.\n"
    "Bu sizga Telegram ichida alohida sahifada kanalga yuklangan qo‘shiqlarni, top yo‘llanmalarni va platforma bo‘yicha toifalarni ko‘rish imkonini beradi.\n\n"
    "<b>🎯 Nimalar kutishingiz mumkin:</b>\n"
    "• <b>Top yuklanganlar</b> va eng so‘nggi qo‘shiqlar.\n"
    "• <b>YouTube / Instagram / TikTok</b> bo‘limlari.\n"
    "• <b>Artistlar</b> va <b>Barchasi</b> bo‘limi.\n"
    "• <b>Oddiy, tezkor</b> media va musiqani eshitish imkoniyati.\n\n"
    "<i>Bot ichidan o‘ziga xos app ochiladi, keyin alohida sahifada tinglash va tanlash mumkin.</i>" + PROMO_TEXT
)

HELP_TEXT = (
    "<b>🆘 Botdan foydalanish bo'yicha qo'llanma:</b>\n\n"
    "1️⃣ <b>📥 Media:</b> YouTube, Instagram yoki TikTok linkini yuboring.\n"
    "2️⃣ <b>📄 Hujjatlar:</b> PDF yoki Word fayl yuboring.\n"
    "3️⃣ <b>🎤 Artistlar:</b> sevimli ijrochilaringizni tez orada toping.\n\n"
    "<b>📌 Eslatma:</b> Har bir bo‘limni tezda tanlash uchun menyudan foydalaning.\n\n"
    "💎 <i>Botimiz 24/7 xizmatingizda!</i>" + PROMO_TEXT
)

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")

@router.message(F.text == "🆘 Help")
async def help_button_handler(message: types.Message):
    await cmd_help(message)
