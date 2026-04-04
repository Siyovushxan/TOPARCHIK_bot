import asyncio
import signal
import time
import logging
import os
import re
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, FSInputFile, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
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
sync_lock = asyncio.Lock()
_user_last_request = {}

# --- Keyboards ---


# Open tugmasi butunlay olib tashlandi


def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🆘 Help"))
    builder.adjust(1)
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
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
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

def parse_artist_from_title(title: str) -> str:
    if not title:
        return ""
    parts = re.split(r'[-–—:]', title, maxsplit=1)
    if len(parts) > 1 and parts[0].strip():
        return parts[0].strip()
    return ""


def detect_platform_from_url(url: str) -> str:
    if not url:
        return ""
    text = url.lower()
    if "youtu.be" in text or "youtube.com" in text:
        return "youtube"
    if "instagram.com" in text:
        return "instagram"
    if "tiktok.com" in text:
        return "tiktok"
    return ""

def is_admin(user_id: int | None) -> bool:
    if not user_id:
        return False
    return user_id in config.ADMIN_IDS if config.ADMIN_IDS else False

def _is_message_missing_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "message to forward not found" in text or "message_id_invalid" in text or "message not found" in text


def _rate_limit_ok(user_id: int | None):
    if not user_id:
        return True, 0
    now = time.monotonic()
    last = _user_last_request.get(user_id, 0.0)
    limit = float(config.USER_RATE_LIMIT_SEC or 0)
    if limit <= 0:
        return True, 0
    if now - last < limit:
        return False, limit - (now - last)
    _user_last_request[user_id] = now
    return True, 0

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
            archive_service.cache_file_info(
                video_id,
                archive_msg.audio.file_id,
                info.get('title', ''),
                info.get('duration', 0),
                artist_name,
                platform="youtube"
            )
            
            # Faylni o'chirish
            if os.path.exists(file_path): os.remove(file_path)
            
            # YouTube bloklamasligi uchun kichik pauza
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Background archiving failed for {video_id}: {e}")
            if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)

async def sync_archive_from_channel(notify_chat_id: int | None):
    archive_chat = config.ARCHIVE_CHANNEL_ID or config.ARCHIVE_CHANNEL
    sync_chat_id = config.SYNC_CHAT_ID or notify_chat_id
    if not sync_chat_id:
        logger.warning("Sync chat ID not configured. Set SYNC_CHAT_ID or trigger from a chat.")
        return

    max_id = max(1, config.ARCHIVE_SYNC_MAX)
    gap_limit = max(1, config.ARCHIVE_SYNC_GAP)
    delay = max(0.05, config.ARCHIVE_SYNC_DELAY)
    found = 0
    misses = 0

    async with sync_lock:
        logger.info(f"Archive sync started up to {max_id} messages...")
        for message_id in range(1, max_id + 1):
            try:
                msg = await bot.forward_message(
                    chat_id=sync_chat_id,
                    from_chat_id=archive_chat,
                    message_id=message_id,
                    disable_notification=True
                )
            except TelegramBadRequest as exc:
                if _is_message_missing_error(exc):
                    misses += 1
                    if misses >= gap_limit:
                        break
                    continue
                logger.warning(f"Forward error at {message_id}: {exc}")
                misses += 1
                if misses >= gap_limit:
                    break
                continue
            except TelegramAPIError as exc:
                logger.warning(f"Telegram API error at {message_id}: {exc}")
                misses += 1
                if misses >= gap_limit:
                    break
                await asyncio.sleep(1.0)
                continue
            except Exception as exc:
                logger.warning(f"Sync error at {message_id}: {exc}")
                misses += 1
                if misses >= gap_limit:
                    break
                continue

            misses = 0
            audio = msg.audio
            if audio:
                title = audio.title or audio.file_name or (msg.caption or "").strip()
                if not title:
                    title = f"Audio {message_id}"
                artist = audio.performer or parse_artist_from_title(title)
                duration = audio.duration or 0
                platform = detect_platform_from_url(msg.caption or "")
                unique_id = audio.file_unique_id or f"tg_{message_id}"
                archive_service.upsert_audio_entry(
                    unique_id=unique_id,
                    file_id=audio.file_id,
                    title=title,
                    duration=duration,
                    artist=artist,
                    platform=platform,
                    message_id=message_id
                )
                found += 1

            try:
                await bot.delete_message(sync_chat_id, msg.message_id)
            except Exception:
                pass

            await asyncio.sleep(delay)

        logger.info(f"Archive sync finished: {found} audio items.")

    if notify_chat_id:
        try:
            await bot.send_message(notify_chat_id, f"Sync tugadi: {found} ta audio topildi.")
        except Exception:
            pass

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")

@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")

@dp.message(Command("sync_archive"))
async def command_sync_archive(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(
            "Sync ishlashi uchun ADMIN_IDS muhit o'zgaruvchisiga o'z ID'ingizni yozing.",
            parse_mode="HTML"
        )
        return

    if sync_lock.locked():
        await message.answer("Sync allaqachon ishlayapti, biroz kuting.")
        return

    await message.answer("Sync boshlandi. Barchasi bo'limi to'ldirilmoqda...")
    asyncio.create_task(sync_archive_from_channel(message.chat.id))

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
    text = "<b>🎤 Artistlar bo‘limi</b>\n\n"
    if not artists:
        text += "<i>Hozircha artistlar mavjud emas.\nKanalga yangi qo'shiq yuklanganda bu bo'limda chiqadi.</i>\n\n"
        text += "<b>Namuna uchun:</b> <a href='https://t.me/toparchik_ai'>@toparchik_ai</a> kanaliga qarang."
        await message.answer(text + PROMO_TEXT, reply_markup=main_menu(), parse_mode="HTML", disable_web_page_preview=False)
        return

    text += "Quyidagi ijrochilardan birini tanlang:\n\n"
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


    # --- WebApp kategoriyalari uchun ---
    # 1. Top yuklanganlar
    if text.strip() == "Top yuklanganlar":
        songs = archive_service.get_top_songs(limit=10)
        if not songs:
            await message.answer("Hozircha top yuklangan qo'shiqlar mavjud emas.")
            return
        response = "<b>🎵 Top yuklanganlar:</b>\n\n"
        for i, song in enumerate(songs, 1):
            response += f"<b>{i}.</b> {song['title']}\n"
        response += "\nIstalgan raqamni yuboring (1-10) yoki qo'shiq nomini yozing, ijro etiladi." + PROMO_TEXT
        # Saqlash uchun kontekst (oddiy variant, global dict)
        message.bot['last_top_songs'] = songs
        await message.answer(response, parse_mode="HTML")
        return

    # 2. YouTube, Instagram, TikTok
    for platform in ["YouTube", "Instagram", "TikTok"]:
        if text.strip() == platform:
            songs = archive_service.get_top_songs_by_platform(platform.lower(), limit=10)
            if not songs:
                await message.answer(f"Hozircha {platform} bo'limida qo'shiqlar mavjud emas.")
                return
            response = f"<b>🎵 {platform} bo'limi:</b>\n\n"
            for i, song in enumerate(songs, 1):
                response += f"<b>{i}.</b> {song['title']}\n"
            response += "\nIstalgan raqamni yuboring (1-10) yoki qo'shiq nomini yozing, ijro etiladi." + PROMO_TEXT
            message.bot['last_top_songs'] = songs
            await message.answer(response, parse_mode="HTML")
            return

    # 3. Raqam yuborilsa, oxirgi ro'yxatdan audio yuborish
    if hasattr(message.bot, 'last_top_songs'):
        songs = message.bot['last_top_songs']
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(songs):
                song = songs[idx]
                file_id = song.get('file_id')
                if file_id:
                    await message.answer_audio(file_id, caption=f"✅ {song['title']}{PROMO_TEXT}", parse_mode="HTML")
                    archive_service.increment_download(song.get("id"))
                    return
        # Qo'shiq nomi bo'yicha ham qidirish
        for song in songs:
            if text.strip().lower() in song.get('title', '').lower():
                file_id = song.get('file_id')
                if file_id:
                    await message.answer_audio(file_id, caption=f"✅ {song['title']}{PROMO_TEXT}", parse_mode="HTML")
                    archive_service.increment_download(song.get("id"))
                    return

    # --- Artistlar bo'limi (avvalgi logika) ---
    if text.strip() == "🎤 Artistlar":
        artists = archive_service.get_all_artists()
        if not artists:
            await message.answer(
                "🎤 Hozircha artistlar mavjud emas. Iltimos, birinchi qo'shiqni yuklab, keyin qayta urinib ko'ring.",
                reply_markup=main_menu()
            )
            return

        response = "<b>🎤 Artistlar bo‘limi</b>\n\nQuyidagi ijrochilardan birini matn sifatida yuboring:\n\n"
        for artist in artists:
            response += f"• {artist}\n"
        response += PROMO_TEXT
        await message.answer(response, parse_mode="HTML")
        return

    artists = archive_service.get_all_artists()
    if text.strip() in artists:
        songs = archive_service.get_songs_by_artist(text.strip())
        if not songs:
            await message.answer("Bu artist uchun qo'shiq topilmadi.")
            return

        def format_duration(seconds):
            if not seconds:
                return ""
            mins, secs = divmod(int(seconds), 60)
            return f" ({mins}:{secs:02d})"

        response = f"<b>🎶 {text.strip()} qo'shiqlari:</b>\n\n"
        for i, song in enumerate(songs[:10], 1):
            response += f"<b>{i}.</b> {song['title']}{format_duration(song.get('duration', 0))}\n"
        response += "\nIstalgan raqamni yuboring (1-10) yoki qo'shiq nomini yozing, ijro etiladi." + PROMO_TEXT
        message.bot['last_top_songs'] = songs[:10]
        await message.answer(response, parse_mode="HTML")
        return

    # 3. Qo'shiq raqami yoki nomi yuborilsa, shu artist kontekstida audio yuborish (oddiy variant, state yo'q)
    # (Agar state kerak bo'lsa, FSM qo'shish mumkin)

    # 4. Standart media va qidiruv logikasi
    if "youtube.com" in text or "youtu.be" in text or "tiktok.com" in text or "instagram.com" in text:
        ok, wait_for = _rate_limit_ok(message.from_user.id if message.from_user else None)
        if not ok:
            await message.answer(f"Juda tez so'rov yuboryapsiz. {wait_for:.1f} soniya kuting.")
            return
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
            archive_service.increment_download(info.get("id"))
            
            # Cache to Archive
            archive_msg = await bot.send_audio(
                chat_id=config.ARCHIVE_CHANNEL, 
                audio=media_file, 
                caption=f"🎵 {info.get('title', '')}{duration_str}\n\n#musiqa {BOT_LINK}",
                title=info.get('title', '')
            )
            artist_name = parse_artist_from_title(info.get('title', ''))
            archive_service.cache_file_info(
                info['id'],
                archive_msg.audio.file_id,
                info.get('title', ''),
                info.get('duration', 0),
                artist_name,
                platform=detect_platform_from_url(text)
            )
            
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
    ok, wait_for = _rate_limit_ok(callback.from_user.id if callback.from_user else None)
    if not ok:
        await callback.answer(f"Juda tez so'rov. {wait_for:.1f}s kuting.", show_alert=True)
        return
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
        archive_service.increment_download(video_id)
        await wait_msg.delete()
        return
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        info, file_path = await download_media(url, callback.message.chat.id, audio_only=True)
        media_file = FSInputFile(file_path)
        
        sent_msg = await bot.send_audio(callback.message.chat.id, media_file, title=info.get('title', 'Audio'), caption=caption_text, reply_markup=reply_markup)
        archive_service.increment_download(video_id)
        
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
                archive_service.cache_file_info(
                    video_id,
                    archive_msg.audio.file_id,
                    info.get('title', ''),
                    info.get('duration', 0),
                    artist_name,
                    platform="youtube"
                )
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
    response_text = f"<b>🎶 {artist} qo'shiqlari:</b>\n\n"
    if not songs:
        response_text += "<i>Bu artist uchun hozircha qo'shiq mavjud emas.</i>\n\n"
        response_text += "<b>Namuna uchun:</b> <a href='https://t.me/toparchik_ai'>@toparchik_ai</a> kanaliga qarang."
        await callback.message.answer(response_text + PROMO_TEXT, reply_markup=main_menu(), parse_mode="HTML", disable_web_page_preview=False)
        await callback.answer()
        return

    def format_duration(seconds):
        if not seconds:
            return ""
        mins, secs = divmod(int(seconds), 60)
        return f" ({mins}:{secs:02d})"

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
    for item_id, data in archive_service.cache.items():
        file_id = data.get("file_id") if isinstance(data, dict) else data
        title = data.get("title") if isinstance(data, dict) else item_id
        if not file_id:
            continue
        # In a real scenario, we'd store the title in the cache too.
        # Let's assume the unique_id is the title for this simple version.
        if text.lower() in (title or "").lower() or text.lower() in item_id.lower():
            results.append(
                types.InlineQueryResultCachedAudio(
                    id=item_id,
                    audio_file_id=file_id,
                    caption=f"✅ @toparchik_bot orqali ulashildi"
                )
            )
    
    await query.answer(results[:50], cache_time=300)

# --- Web App API ---

def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _serialize_song(item: dict) -> dict:
    if not isinstance(item, dict):
        return {}
    return {
        "id": item.get("id") or "",
        "title": item.get("title") or "Unknown",
        "duration": _safe_int(item.get("duration") or 0),
        "file_id": item.get("file_id"),
        "artist": item.get("artist") or "",
        "download_count": _safe_int(item.get("download_count") or 0),
        "play_count": _safe_int(item.get("play_count") or 0),
        "platform": item.get("platform") or "",
        "playable": bool(item.get("file_id")),
    }


def _serialize_song_list(items: list, limit: int = 50) -> list:
    if not items:
        return []
    payload = []
    for item in items[:limit]:
        song = _serialize_song(item)
        if song:
            payload.append(song)
    return payload


async def handle_api_top(request):
    limit = _safe_int(request.query.get("limit"), 200)
    songs = archive_service.get_top_songs(limit=limit)
    return web.json_response({"items": _serialize_song_list(songs, limit)})


async def handle_api_platform(request):
    platform = request.match_info.get("platform", "").lower()
    limit = _safe_int(request.query.get("limit"), 200)
    songs = archive_service.get_top_songs_by_platform(platform, limit=limit)
    return web.json_response({"items": _serialize_song_list(songs, limit)})


async def handle_api_artists(request):
    artists = archive_service.get_artist_stats()
    return web.json_response({"items": artists})


async def handle_api_artist(request):
    artist = unquote_plus(request.match_info.get("artist", ""))
    limit = _safe_int(request.query.get("limit"), 200)
    songs = archive_service.get_songs_by_artist(artist)[:limit]
    return web.json_response({"items": _serialize_song_list(songs, limit)})


async def handle_api_search(request):
    query = request.query.get("q", "").strip()
    if not query:
        return web.json_response({"items": []})
    results = archive_service.search_cache(query)
    return web.json_response({"items": _serialize_song_list(results, 200)})


async def handle_api_all(request):
    limit = _safe_int(request.query.get("limit"), 500)
    songs = archive_service.get_all_songs()
    return web.json_response({"items": _serialize_song_list(songs, limit)})


async def handle_api_play(request):
    song_id = request.match_info.get("song_id")
    if not song_id:
        return web.Response(status=400, text="Missing song_id")
    archive_service.increment_play(song_id)
    return web.json_response({"ok": True})


async def handle_api_audio(request):
    file_id = request.match_info.get("file_id")
    if not file_id:
        return web.Response(status=400, text="Missing file_id")

    try:
        file = await bot.get_file(file_id)
    except Exception as exc:
        logger.error(f"Audio file lookup failed: {exc}")
        return web.Response(status=404, text="File not found")

    file_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
    range_header = request.headers.get("Range")

    try:
        async with aiohttp.ClientSession() as session:
            upstream_headers = {}
            if range_header:
                upstream_headers["Range"] = range_header

            async with session.get(file_url, headers=upstream_headers) as resp:
                if resp.status not in (200, 206):
                    logger.error(f"Telegram file fetch failed: {resp.status}")
                    return web.Response(status=resp.status, text="Upstream error")

                headers = {
                    "Content-Type": resp.headers.get("Content-Type", "audio/mpeg"),
                    "Cache-Control": "public, max-age=3600",
                    "Accept-Ranges": "bytes",
                }
                content_range = resp.headers.get("Content-Range")
                content_length = resp.headers.get("Content-Length")
                if content_range:
                    headers["Content-Range"] = content_range
                if content_length:
                    headers["Content-Length"] = content_length

                stream = web.StreamResponse(status=resp.status, headers=headers)
                await stream.prepare(request)

                async for chunk in resp.content.iter_chunked(65536):
                    await stream.write(chunk)

                await stream.write_eof()
                return stream
    except Exception as exc:
        logger.error(f"Audio proxy error: {exc}")
        return web.Response(status=500, text="Audio stream error")

# --- Health check and Web App server ---
async def handle_health(request):
    return web.Response(text="Bot is running!")

async def handle_webapp(request):
    html_path = os.path.join(os.path.dirname(__file__), "..", "webapp", "index.html")
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

async def build_web_app() -> web.Application:
    """Build and return the aiohttp web application with all routes registered."""
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/webapp", handle_root)
    app.router.add_static(
        "/webapp-static",
        os.path.join(os.path.dirname(__file__), "..", "webapp"),
        show_index=False
    )
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/top", handle_api_top)
    app.router.add_get("/api/all", handle_api_all)
    app.router.add_get("/api/platform/{platform}", handle_api_platform)
    app.router.add_get("/api/artists", handle_api_artists)
    app.router.add_get("/api/artist/{artist}", handle_api_artist)
    app.router.add_get("/api/search", handle_api_search)
    app.router.add_get("/api/audio/{file_id}", handle_api_audio)
    app.router.add_post("/api/play/{song_id}", handle_api_play)
    return app


async def main():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    # Optional: auto-sync archive cache on startup
    if config.ARCHIVE_SYNC_ON_START:
        asyncio.create_task(sync_archive_from_channel(config.SYNC_CHAT_ID))

    # Set bot commands visible in Telegram menu
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam olish")
    ])

    port = int(os.environ.get("PORT", 8080))

    # --- Webhook mode (default for multi-replica deployments) ---
    if config.RAILWAY_PUBLIC_DOMAIN and not config.POLLING_ENABLED:
        webhook_url = f"https://{config.RAILWAY_PUBLIC_DOMAIN}{config.WEBHOOK_PATH}"
        logger.info(f"Bot v2.0 starting in webhook mode: {webhook_url}")

        # Register the webhook with Telegram
        await bot.set_webhook(
            url=webhook_url,
            secret_token=config.WEBHOOK_SECRET or None,
            drop_pending_updates=True,
        )
        logger.info("Telegram webhook registered.")

        app = await build_web_app()

        # Mount the aiogram webhook handler onto the aiohttp app
        webhook_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=config.WEBHOOK_SECRET or None,
        )
        webhook_handler.register(app, path=config.WEBHOOK_PATH)

        # Wire aiogram startup/shutdown lifecycle into aiohttp
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Webhook server listening on port {port}")

        # Keep running until a shutdown signal is received
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        logger.info("Shutdown signal received, stopping webhook server...")
        await runner.cleanup()
        await bot.session.close()
        return

    # --- Polling mode (single-instance / local development) ---
    logger.info("Bot v2.0 starting in polling mode...")

    # Remove any existing webhook before polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Existing webhook removed.")
    except Exception as e:
        logger.warning(f"Could not remove webhook (continuing): {e}")

    # Start the health-check / API server alongside polling
    app = await build_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server started on port {port}")

    if not config.POLLING_ENABLED:
        logger.warning("POLLING_ENABLED=0 — polling disabled (webapp only).")
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        logger.info("Shutdown signal received, stopping webapp server...")
        await runner.cleanup()
        await bot.session.close()
        return

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
