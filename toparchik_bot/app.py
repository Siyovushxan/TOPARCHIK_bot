import asyncio
import logging
import os
import re
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, FSInputFile, Message
from urllib.parse import quote_plus, unquote_plus
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from toparchik_bot import config
from toparchik_bot.services.gemini import ask_gemini
from toparchik_bot.services.youtube import search_youtube, download_media
from toparchik_bot.services.archive import archive_service
from toparchik_bot.services.docs import convert_pdf_to_docx, run_conversion

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot initialization
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()


# --- Keyboards ---

def categories_inline_markup():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔥 Top yuklanganlar", callback_data="cat_top"))
    builder.add(InlineKeyboardButton(text="📺 YouTube", callback_data="cat_youtube"))
    builder.add(InlineKeyboardButton(text="🎵 TikTok", callback_data="cat_tiktok"))
    builder.add(InlineKeyboardButton(text="📸 Instagram", callback_data="cat_instagram"))
    builder.add(InlineKeyboardButton(text="🎧 Janrlar", callback_data="cat_genre"))
    builder.add(InlineKeyboardButton(text="👨‍🎤 Artistlar", callback_data="cat_artist"))
    builder.adjust(2)
    return builder.as_markup()

def get_web_app_button():
    """Return a valid WebApp button only for HTTPS URLs."""
    url = config.WEB_APP_URL.strip()
    if not url or not url.lower().startswith("https://"):
        if url:
            logger.warning("Invalid WEB_APP_URL for Telegram WebApp button: %s. Skipping web app button.", url)
        return None
    return KeyboardButton(text="🚀 Open", web_app=WebAppInfo(url=url))


def main_menu():
    builder = ReplyKeyboardBuilder()
    web_app_button = get_web_app_button()
    if web_app_button:
        builder.add(web_app_button)
    else:
        builder.add(KeyboardButton(text="🆘 Help"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def ad_inline_markup():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="💎 Hamkorlik", url="https://t.me/erpaiapp"))
    builder.add(InlineKeyboardButton(text="📊 Batafsil", callback_data="ad_more"))
    return builder.as_markup()

# --- Handlers ---


# --- Start command: show categories ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await message.answer("<b>Asosiy bo‘limlar:</b> Kategoriyani tanlang:", reply_markup=categories_inline_markup(), parse_mode="HTML")
# --- Category callbacks ---
def format_song_list(songs, title):
    def format_duration(seconds):
        if not seconds: return ""
        mins, secs = divmod(int(seconds), 60)
        return f"({mins}:{secs:02d})"
    text = f"<b>{title}</b>\n\n"
    builder = InlineKeyboardBuilder()
    for i, song in enumerate(songs, 1):
        text += f"<b>{i}.</b> {song.get('title', '')} {format_duration(song.get('duration', 0))}\n"
        builder.add(InlineKeyboardButton(text=str(i), callback_data=f"dl_{song['id']}"))
    if songs:
        builder.adjust(5, 5)
    builder.add(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="cat_back"))
    builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
    return text + PROMO_TEXT, builder.as_markup()

@dp.callback_query(F.data == "cat_top")
async def cat_top_handler(callback: types.CallbackQuery):
    songs = archive_service.get_top_songs(limit=10)
    text, markup = format_song_list(songs, "🔥 Top yuklanganlar")
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "cat_youtube")
async def cat_youtube_handler(callback: types.CallbackQuery):
    songs = archive_service.get_top_songs_by_platform("youtube", limit=10)
    text, markup = format_song_list(songs, "📺 YouTube'dan eng ko‘p yuklanganlar")
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "cat_tiktok")
async def cat_tiktok_handler(callback: types.CallbackQuery):
    songs = archive_service.get_top_songs_by_platform("tiktok", limit=10)
    text, markup = format_song_list(songs, "🎵 TikTok'dan eng ko‘p yuklanganlar")
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "cat_instagram")
async def cat_instagram_handler(callback: types.CallbackQuery):
    songs = archive_service.get_top_songs_by_platform("instagram", limit=10)
    text, markup = format_song_list(songs, "📸 Instagram'dan eng ko‘p yuklanganlar")
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "cat_back")
async def cat_back_handler(callback: types.CallbackQuery):
    await callback.message.edit_text("<b>Asosiy bo‘limlar:</b> Kategoriyani tanlang:", reply_markup=categories_inline_markup(), parse_mode="HTML")
    await callback.answer()

# Janrlar va Artistlar uchun eski handlerlar ishlatiladi (ular allaqachon bor)

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

def parse_artist_from_title(title: str) -> str:
    if not title:
        return ""
    parts = re.split(r'[-–—:]', title, maxsplit=1)
    if len(parts) > 1 and parts[0].strip():
        return parts[0].strip()
    return ""

WELCOME_TEXT = (
    "<b>✨ TOPARCHIK AI - Universal Media App</b>\n\n"
    "Web App interfeysini ochish uchun pastdagi <b>🚀 Open</b> tugmasini bosing.\n"
    "Bu sizga Telegram ichida alohida sahifada kanalga yuklangan qo‘shiqlarni, janrlarni, top yo‘llanmalarni va platforma bo‘yicha toifalarni ko‘rish imkonini beradi.\n\n"
    "<b>🎯 Nimalar kutishingiz mumkin:</b>\n"
    "• <b>Top yuklanganlar</b> va eng so‘nggi qo‘shiqlar.\n"
    "• <b>YouTube / Instagram / TikTok</b> bo‘limlari.\n"
    "• <b>Janrlar</b> va mashhur artistlar.\n"
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
            from toparchik_bot.services.youtube import download_media
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
            artist_name = parse_artist_from_title(info.get('title', ''))
            archive_service.cache_file_info(video_id, archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0), artist_name)
            
            # Faylni o'chirish
            if os.path.exists(file_path): os.remove(file_path)
            
            # YouTube bloklamasligi uchun kichik pauza
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Background archiving failed for {video_id}: {e}")
            if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")

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

@dp.message(F.text == "🎤 Artistlar")
async def artist_menu(message: types.Message):
    artists = archive_service.get_all_artists()
    if not artists:
        await message.answer(
            "🎤 Hozircha artistlar mavjud emas. Iltimos, birinchi qo'shiqni yuklab, keyin qayta urinib ko'ring.",
            reply_markup=main_menu()
        )
        return

    text = "<b>🎤 Artistlar bo‘limi</b>\n\n" \
           "Quyidagi ijrochilardan birini tanlang:\n\n"
    builder = InlineKeyboardBuilder()
    for artist in artists:
        builder.add(InlineKeyboardButton(text=artist, callback_data=f"artist_sel_{quote_plus(artist)}"))
    builder.adjust(2)
    builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
    await message.answer(text + PROMO_TEXT, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.message(F.text == "🆘 Help")
async def help_button_handler(message: types.Message):
    await command_help_handler(message)

# --- Universal Input Handler ---

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
            from toparchik_bot.services.docs import convert_pdf_to_docx, run_conversion
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
            from toparchik_bot.services.docs import convert_docx_to_pdf, run_conversion
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
            artist_name = parse_artist_from_title(info.get('title', ''))
            archive_service.cache_file_info(info['id'], archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0), artist_name)
            
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
                artist_name = parse_artist_from_title(info.get('title', ''))
                archive_service.cache_file_info(video_id, archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0), artist_name)
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

@dp.callback_query(F.data.startswith("artist_sel_"))
async def artist_selected(callback: types.CallbackQuery):
    artist = unquote_plus(callback.data.split("_", 1)[1])
    songs = archive_service.get_songs_by_artist(artist)
    if not songs:
        await callback.answer("Bu artist uchun qo'shiq topilmadi.", show_alert=True)
        return

    def format_duration(seconds):
        if not seconds:
            return ""
        mins, secs = divmod(int(seconds), 60)
        return f" ({mins}:{secs:02d})"

    response_text = f"<b>🎶 {artist} qo'shiqlari:</b>\n\n"
    builder = InlineKeyboardBuilder()
    buttons = []
    for i, song in enumerate(songs[:10], 1):
        response_text += f"<b>{i}.</b> {song['title']}{format_duration(song.get('duration', 0))}\n"
        buttons.append(InlineKeyboardButton(text=str(i), callback_data=f"dl_{song['id']}"))

    if buttons:
        builder.add(*buttons)
        builder.adjust(5, 5)

    builder.add(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="artist_back"))
    builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
    await callback.message.answer(response_text + PROMO_TEXT, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "artist_back")
async def artist_back(callback: types.CallbackQuery):
    artists = archive_service.get_all_artists()
    if not artists:
        await callback.answer("Hozircha artistlar mavjud emas.", show_alert=True)
        return

    text = "<b>🎤 Artistlar bo‘limi</b>\n\n" \
           "Quyidagi ijrochilardan birini tanlang:\n\n"
    builder = InlineKeyboardBuilder()
    for artist in artists:
        builder.add(InlineKeyboardButton(text=artist, callback_data=f"artist_sel_{quote_plus(artist)}"))
    builder.adjust(2)
    builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
    await callback.message.answer(text + PROMO_TEXT, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


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

# --- Health check and Web App server ---
async def handle_health(request):
    return web.Response(text="Bot is running!")

async def handle_webapp(request):
    html_path = os.path.join(os.path.dirname(__file__), "webapp", "index.html")
    if os.path.exists(html_path):
        return web.FileResponse(html_path)

    # Fallback HTML (agar fayl topilmasa ham 404 bermaymiz)
    html_content = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>TOPARCHIK AI</title>
      <style>body{font-family:Inter,system-ui,sans-serif;background:#070b18;color:#f5f7ff;margin:0;padding:20px;text-align:center;}</style>
    </head>
    <body>
      <h1>TOPARCHIK AI Web App</h1>
      <p>Web App is running!</p>
      <p>Telegram Web App uchun oching.</p>
    </body>
    </html>
    '''
    return web.Response(text=html_content, content_type='text/html')

# Unified route for root + /webapp
async def handle_root(request):
    return await handle_webapp(request)

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/webapp", handle_root)
    app.router.add_get("/health", handle_health)
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

    # Set bot commands visible in Telegram menu
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam olish")
    ])
    
    # Start polling
    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())
