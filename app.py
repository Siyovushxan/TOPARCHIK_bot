import asyncio
import logging
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, FSInputFile, Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

import config
from services.gemini import ask_gemini
from services.youtube import search_youtube, download_media
from services.archive import archive_service
from services.whisper import transcribe_audio
from services.docs import convert_pdf_to_docx, run_conversion

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot initialization
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- Keyboards ---
def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📥 Media"))
    builder.add(KeyboardButton(text="📄 Word<->Pdf"))
    builder.add(KeyboardButton(text="🎙 Ovozli Tahlil"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def ad_inline_markup():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="💎 Hamkorlik", url="https://t.me/erpaiapp"))
    builder.add(InlineKeyboardButton(text="📊 Batafsil", callback_data="ad_more"))
    return builder.as_markup()

# --- Handlers ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Toparchik AI Universal Bot (v2.0)** ga xush kelibsiz!\n\n"
        "Men sizga media yuklash, hujjatlarni aylantirish va ovozli xabarlarni tahlil qilishda yordam beraman.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({"Musiqa qidirish", "AI savol-javob", "PPT yaratish", "Word yaratish", "Asosiy menyu", "📄 Hujjatlar"}))
async def old_menu_handler(message: types.Message):
    await message.answer(
        "ℹ️ **Bot yangilandi!**\n\n"
        "Iltimos, yangi menyuni ishga tushirish uchun /start ni bosing.",
        reply_markup=types.ReplyKeyboardRemove()
    )

# --- Prompts and Constants ---
BOT_LINK = "@toparchik_bot"
PROMO_TEXT = f"\n\n🔥 <i>Eng sara musiqalar va aqlli AI xizmatlari faqat bizda: {BOT_LINK}</i>"
WELCOME_TEXT = (
    "<b>👋 Xush kelibsiz! Men TOPARCHIK AI Universal Botman.</b>\n\n"
    "✨ <b>Asosiy imkoniyatlarim:</b>\n"
    "🎵 <b>Musiqa:</b> Dunyo bo'ylab istalgan qo'shiqni topish.\n"
    "📹 <b>Video:</b> Ijtimoiy tarmoqlardan (YT, IG, TT) media yuklash.\n"
    "🔄 <b>Konvertatsiya:</b> PDF <-> Word fayllarni aylantirish.\n"
    "🎙 <b>AI Tahlil:</b> Ovozli xabarlarni matnga o'girish (tez orada).\n\n"
    "⚡️ <i>Quyidagi menyu orqali botni boshqarishingiz mumkin:</i>" + PROMO_TEXT
)
HELP_TEXT = (
    "<b>🆘 Botdan foydalanish bo'yicha qo'llanma:</b>\n\n"
    "1️⃣ <b>Musiqa topish:</b> Shunchaki nomi yoki ijrochini yozing.\n"
    "2️⃣ <b>Link orqali yuklash:</b> Video havolasini (link) yuboring.\n"
    "3️⃣ <b>Voice (ovoz):</b> Ovozli xabar yuborsangiz, tahlil qilib beraman.\n"
    "4️⃣ <b>Fayllar:</b> .docx yoki PDF fayllarni yuboring.\n\n"
    "💎 <i>Botimiz 24/7 xizmatingizda!</i>" + PROMO_TEXT
)

async def archive_all_results_task(results):
    """Qidiruv natijalarining barchasini orqa fonda kanalga yuklash va keshga qo'shish."""
    for res in results:
        video_id = res['id']
        # Agar bazada allaqachon bo'lsa, o'tkazib yuboramiz
        if archive_service.get_cached_file_id(video_id):
            continue
            
        try:
            logger.info(f"Background archiving: {res['title']}")
            # Audio yuklash
            from services.youtube import download_media
            url = f"https://www.youtube.com/watch?v={video_id}"
            info, file_path = await download_media(url, 0, audio_only=True)
            
            # Kanalga yuborish
            media_file = FSInputFile(file_path)
            duration_str = ""
            if info.get('duration'):
                mins, secs = divmod(int(info['duration']), 60)
                duration_str = f" [{mins}:{secs:02d}]"
                
            archive_msg = await bot.send_audio(
                chat_id=config.ARCHIVE_CHANNEL, 
                audio=media_file, 
                caption=f"🎵 {info.get('title', '')}{duration_str}\n\n#musiqa {BOT_LINK}",
                title=info.get('title', '')
            )
            
            # Bazaga yozish
            archive_service.cache_file_info(video_id, archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0))
            
            # Faylni o'chirish
            if os.path.exists(file_path): os.remove(file_path)
            
            # YouTube bloklamasligi uchun kichik pauza
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Background archiving failed for {video_id}: {e}")
            if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(WELCOME_TEXT, parse_mode="HTML")

@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")

@dp.message(F.text == "📥 Media")
async def media_menu(message: types.Message):
    await message.answer(
        "<b>📥 Media yuklash bo'limi:</b>\n\n"
        "Siz quyidagi tarmoqlardan video yoki audiolarni yuklab olishingiz mumkin:\n"
        "• YouTube (Video & Audio)\n"
        "• Instagram (Reels & Video)\n"
        "• TikTok (Bez vatermark)\n\n"
        "💡 <b>Qanday yuklanadi?</b> Shunchaki media havolasini (link) botga yuboring!" + PROMO_TEXT,
        parse_mode="HTML"
    )

@dp.message(F.text == "📄 Word<->Pdf")
async def docs_menu(message: types.Message):
    await message.answer(
        "<b>📄 Hujjatlarni konvertatsiya qilish:</b>\n\n"
        "Bot yordamida fayllarni tezkor aylantiring:\n"
        "✅ <b>PDF to Word:</b> PDF faylni @toparchik_bot ga yuboring.\n"
        "✅ <b>Word to PDF:</b> .docx faylni botga yuboring.\n\n"
        "⚠️ <i>Eslatma: Fayllar hajmi 20 MB dan oshmasligi tavsiya etiladi.</i>" + PROMO_TEXT,
        parse_mode="HTML"
    )

@dp.message(F.text == "🎙 Ovozli Tahlil")
async def voice_menu(message: types.Message):
    await message.answer(
        "<b>🎙 Ovozli tahlil (AI Transcription):</b>\n\n"
        "Bu bo'lim orqali siz yuborgan ovozli xabarlarni matnga aylantirib, uning mazmunini AI orqali tahlil qilish mumkin.\n\n"
        "🚀 <i>Ushbu funksiya hozirda sinov rejimida va tez orada to'liq ishga tushadi!</i>" + PROMO_TEXT,
        parse_mode="HTML"
    )

# --- Universal Input Handler ---

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    await message.answer(
        "🎙 <b>Ovozli tahlil bo'limi:</b>\n\n"
        "Tez orada ushbu bo'lim ishga tushadi! Kelajakda botimiz orqali qo'shiqni ovoz orqali ham izlashingiz mumkin bo'ladi.\n\n"
        "🚀 <i>Botimiz rivojlanishi uchun yaqinlaringizga ham taklif qiling!</i>" + PROMO_TEXT,
        parse_mode="HTML"
    )

@dp.message(F.document)
async def handle_document(message: types.Message):
    file_name = message.document.file_name.lower() if message.document.file_name else "document"
    
    if file_name.endswith('.pdf'):
        wait_msg = await message.answer("⏳ PDF Word'ga aylantirilmoqda...")
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        input_path = f"downloads/{message.document.file_name}"
        await bot.download_file(file.file_path, input_path)
        
        try:
            from services.docs import convert_pdf_to_docx, run_conversion
            output_path = await run_conversion(convert_pdf_to_docx, input_path)
            doc_file = FSInputFile(output_path)
            await message.answer_document(doc_file, caption=f"✅ Word fayl tayyor! {PROMO_TEXT}", parse_mode="HTML")
        except Exception as exc:
            await message.answer(f"❌ Xatolik yuz berdi: {exc}")
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path): 
                try: os.remove(output_path) 
                except: pass
            await wait_msg.delete()
            
    elif file_name.endswith('.docx') or file_name.endswith('.doc'):
        wait_msg = await message.answer("⏳ Word PDF'ga aylantirilmoqda...")
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        input_path = f"downloads/{message.document.file_name}"
        await bot.download_file(file.file_path, input_path)
        
        try:
            from services.docs import convert_docx_to_pdf, run_conversion
            output_path = await run_conversion(convert_docx_to_pdf, input_path)
            pdf_file = FSInputFile(output_path)
            await message.answer_document(pdf_file, caption=f"✅ PDF fayl tayyor! {PROMO_TEXT}", parse_mode="HTML")
        except Exception as exc:
            await message.answer(f"❌ Xatolik yuz berdi: {exc}")
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path): 
                try: os.remove(output_path) 
                except: pass
            await wait_msg.delete()
            
    else:
        await message.answer("🛑 Faqat PDF yoki Word (.doc, .docx) fayllarni yuboring." + PROMO_TEXT, parse_mode="HTML")

@dp.message()
async def handle_text(message: types.Message, override_text: str = None):
    # Detect if it's a link or a search query
    text = override_text if override_text else message.text
    if "youtube.com" in text or "youtu.be" in text or "tiktok.com" in text or "instagram.com" in text:
        wait_msg = await message.answer("⏳ Media yuklab olinmoqda...")
        try:
            info, file_path = await download_media(text, message.chat.id)
            media_file = FSInputFile(file_path)
            
            duration_str = ""
            if info.get('duration'):
                mins, secs = divmod(int(info['duration']), 60)
                duration_str = f" [{mins}:{secs:02d}]"
                
            await message.answer_audio(
                media_file, 
                title=info.get('title', 'Media'), 
                caption=f"✅ {info.get('title', '')}{duration_str}{PROMO_TEXT}",
                parse_mode="HTML"
            )
            
            # Cache to Archive
            archive_msg = await bot.send_audio(
                chat_id=config.ARCHIVE_CHANNEL, 
                audio=media_file, 
                caption=f"🎵 {info.get('title', '')}{duration_str}\n\n#musiqa {BOT_LINK}",
                title=info.get('title', '')
            )
            archive_service.cache_file_info(info['id'], archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0))
            
        except Exception as exc:
            await message.answer(f"❌ Media yuklashda xato: {exc}", disable_web_page_preview=True)
        finally:
            if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)
            await wait_msg.delete()
    else:
        # Search Archive Cache
        results = archive_service.search_cache(text)
        
        # Search YouTube to fill the rest
        if len(results) < 10:
            try:
                yt_results = await search_youtube(text, max_results=10)
                # Avtomatik ravishda barcha topilgan qo'shiqlarni backgroundda kanalga yuklash
                asyncio.create_task(archive_all_results_task(yt_results))
            except Exception as e:
                logger.error(f"YouTube Search failed: {e}")
                yt_results = []
                
            seen_ids = set([res['id'] for res in results])
            for yt_res in yt_results:
                if yt_res['id'] not in seen_ids:
                    results.append(yt_res)
                    seen_ids.add(yt_res['id'])

        if results:
            def format_duration(seconds):
                if not seconds: return ""
                mins, secs = divmod(int(seconds), 60)
                return f"({mins}:{secs:02d})"
                
            response_text = f"<b>🔍 Qidiruv natijasi:</b> {text}\n\n"
            builder = InlineKeyboardBuilder()
            buttons = []
            
            for i, res in enumerate(results[:10], 1):
                duration = format_duration(res.get('duration', 0))
                response_text += f"<b>{i}.</b> {res['title']} {duration}\n"
                buttons.append(InlineKeyboardButton(text=str(i), callback_data=f"dl_{res['id']}"))

            if buttons:
                builder.add(*buttons)
                builder.adjust(5, 5)

            builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
            response_text += PROMO_TEXT
            await message.answer(response_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            # AI Chat fallback
            response = await ask_gemini(text)
            await message.answer(response + PROMO_TEXT, parse_mode="HTML")

# --- Download Callback ---
@dp.callback_query(F.data.startswith("dl_"))
async def process_download(callback: types.CallbackQuery):
    video_id = callback.data.split("_", 1)[1]
    wait_msg = await callback.message.answer("⏳ Audio yuklab olinmoqda...")
    await callback.answer()

    # Check cache first
    cached_file_id = archive_service.get_cached_file_id(video_id)
    
    caption_text = "❤️ @toparchik_bot orqali istagan musiqangizni tez va oson toping!🚀"
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👉 Guruhga Qo'shish ↗️", url="https://t.me/toparchik_bot?startgroup=true"))
    reply_markup = builder.as_markup()

    if cached_file_id:
        await bot.send_audio(callback.message.chat.id, audio=cached_file_id, caption=caption_text, reply_markup=reply_markup)
        await wait_msg.delete()
        return
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        info, file_path = await download_media(url, callback.message.chat.id, audio_only=True)
        media_file = FSInputFile(file_path)
        
        sent_msg = await bot.send_audio(callback.message.chat.id, media_file, title=info.get('title', 'Audio'), caption=caption_text, reply_markup=reply_markup)
        
        # Cache to Archive
        if config.ARCHIVE_CHANNEL:
            try:
                archive_msg = await bot.send_audio(
                    chat_id=config.ARCHIVE_CHANNEL,
                    audio=sent_msg.audio.file_id,
                    caption=f"#musiqa {info.get('title', '')}",
                    title=info.get('title', '')
                )
                archive_service.cache_file_info(video_id, archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0))
            except Exception as e:
                logger.error(f"Archive error: {e}")
                
    except Exception as exc:
        await callback.message.answer(f"❌ Yuklab olishda xato yuz berdi: {exc}", disable_web_page_preview=True)
    finally:
        if 'file_path' in locals() and os.path.exists(file_path): 
            try:
                os.remove(file_path)
            except:
                pass
        await wait_msg.delete()

@dp.callback_query(F.data == "nav_close")
async def nav_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data.in_({"nav_prev", "nav_next"}))
async def nav_unsupported(callback: types.CallbackQuery):
    await callback.answer("Hozircha faqat dastlabki 10 ta natija ko'rsatilmoqda ❤️", show_alert=True)


# --- Inline Search Handler ---

@dp.inline_query()
async def inline_search(query: types.InlineQuery):
    text = query.query.strip()
    if not text:
        return
    
    # Search in local cache index first
    # This assumes the cache stores title/metadata along with file_id
    # For now, we'll implement a simple keyword search in the cache
    results = []
    for item_id, file_id in archive_service.cache.items():
        # In a real scenario, we'd store the title in the cache too.
        # Let's assume the unique_id is the title for this simple version.
        if text.lower() in item_id.lower():
            results.append(
                types.InlineQueryResultCachedAudio(
                    id=item_id,
                    audio_file_id=file_id,
                    caption=f"✅ @toparchik_bot orqali ulashildi"
                )
            )
    
    await query.answer(results[:50], cache_time=300)

# --- Health check server for Hugging Face ---
async def handle_health(request):
    return web.Response(text="Bot is running!")

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 7860))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server started on port {port}")

async def main():
    logger.info("Bot v2.0 start polling...")
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    # Eski sessiyalarni tozalash (tarmoq tayyor bo'lmasa — davom etamiz)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook o'chirildi.")
    except Exception as e:
        logger.warning(f"Webhook o'chirishda xato (davom etamiz): {e}")

    # Start health check server
    await start_health_server()
    
    # Start polling
    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())
