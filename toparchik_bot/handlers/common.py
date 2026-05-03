from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, WebAppInfo

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

def webapp_inline_button():
    """Web App ochish uchun inline tugma."""
    if config.WEB_APP_URL:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="🚀 Ilovani Ochish",
            web_app=WebAppInfo(url=config.WEB_APP_URL)
        ))
        return builder.as_markup()
    return None

# --- Prompts and Constants ---
BOT_LINK = "@toparchik_bot"
PROMO_TEXT = f"\n\n🔥 <i>Eng sara musiqalar va aqlli AI xizmatlari faqat bizda: {BOT_LINK}</i>"

WELCOME_TEXT = (
    "<b>✨ TOPARCHIK AI - Universal Media App</b>\n\n"
    "Xush kelibsiz! Men sizga quyidagi xizmatlarni taqdim etaman:\n\n"
    "<b>🎯 Imkoniyatlar:</b>\n"
    "• <b>Top yuklanganlar</b> va eng so'nggi qo'shiqlar.\n"
    "• <b>YouTube / Instagram / TikTok</b> media yuklash.\n"
    "• <b>Artistlar</b> bo'yicha qidirish.\n"
    "• <b>PDF ↔ Word</b> konvertatsiya.\n"
    "• <b>AI yordamchi</b> — musiqa haqida istalgan savol.\n\n"
    "<i>Boshlash uchun quyidagi menyudan foydalaning yoki to'g'ridan-to'g'ri qo'shiq nomini yozing.</i>" + PROMO_TEXT
)

HELP_TEXT = (
    "<b>🆘 Botdan foydalanish bo'yicha qo'llanma:</b>\n\n"
    "1️⃣ <b>📥 Media:</b> YouTube, Instagram yoki TikTok linkini yuboring.\n"
    "2️⃣ <b>📄 Hujjatlar:</b> PDF yoki Word (.docx) fayl yuboring.\n"
    "3️⃣ <b>🎤 Artistlar:</b> sevimli ijrochilaringizni tez orada toping.\n"
    "4️⃣ <b>🔍 Qidirish:</b> Qo'shiq nomini yozing — topamiz!\n"
    "5️⃣ <b>🤖 AI:</b> Agar qo'shiq topilmasa, AI javob beradi.\n\n"
    "<b>📌 Eslatma:</b> Har bir bo'limni tezda tanlash uchun menyudan foydalaning.\n\n"
    "💎 <i>Botimiz 24/7 xizmatingizda!</i>" + PROMO_TEXT
)

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    markup = webapp_inline_button()
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    # Web App tugmasini alohida yuborish (agar sozlangan bo'lsa)
    if markup:
        await message.answer(
            "👇 <b>Web ilovani ochish uchun tugmani bosing:</b>",
            reply_markup=markup,
            parse_mode="HTML"
        )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")

@router.message(F.text == "🆘 Help")
async def help_button_handler(message: types.Message):
    await cmd_help(message)
