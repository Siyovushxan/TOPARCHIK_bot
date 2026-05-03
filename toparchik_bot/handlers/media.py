import asyncio
import os
import re
import time
import logging
from urllib.parse import quote_plus, unquote_plus
from aiogram import Router, types, F, Bot
from aiogram.types import FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from toparchik_bot import config
from toparchik_bot.services.youtube import search_youtube, download_media
from toparchik_bot.services.archive import archive_service
from toparchik_bot.services.gemini import ask_gemini

logger = logging.getLogger(__name__)
router = Router()

BOT_LINK = "@toparchik_bot"
PROMO_TEXT = f"\n\n🔥 <i>Eng sara musiqalar va aqlli AI xizmatlari faqat bizda: {BOT_LINK}</i>"

_user_last_request = {}

def parse_artist_from_title(title: str) -> str:
    if not title: return ""
    parts = re.split(r'[-–—:]', title, maxsplit=1)
    if len(parts) > 1 and parts[0].strip():
        return parts[0].strip()
    return ""

def detect_platform_from_url(url: str) -> str:
    if not url: return ""
    text = url.lower()
    if "youtu.be" in text or "youtube.com" in text: return "youtube"
    if "instagram.com" in text: return "instagram"
    if "tiktok.com" in text: return "tiktok"
    return ""

def _rate_limit_ok(user_id: int | None):
    if not user_id: return True, 0
    now = time.monotonic()
    last = _user_last_request.get(user_id, 0.0)
    limit = float(config.USER_RATE_LIMIT_SEC or 0)
    if limit <= 0: return True, 0
    if now - last < limit: return False, limit - (now - last)
    _user_last_request[user_id] = now
    return True, 0

async def archive_all_results_task(results, bot: Bot):
    """Qidiruv natijalarining barchasini orqa fonda kanalga yuklash va keshga qo'shish."""
    for res in results:
        video_id = res['id']
        if archive_service.get_cached_file_id(video_id):
            continue
            
        try:
            logger.info(f"Background archiving: {res['title']}")
            url = f"https://www.youtube.com/watch?v={video_id}"
            info, file_path = await download_media(url, 0, audio_only=True)
            
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
            
            artist_name = parse_artist_from_title(info.get('title', ''))
            archive_service.cache_file_info(
                video_id,
                archive_msg.audio.file_id,
                info.get('title', ''),
                info.get('duration', 0),
                artist_name,
                platform="youtube"
            )
            
            if os.path.exists(file_path): os.remove(file_path)
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Background archiving failed for {video_id}: {e}")
            if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)

@router.message(F.text == "📥 Media")
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

@router.message(F.text == "🎤 Artistlar")
async def artist_menu(message: types.Message):
    artists = archive_service.get_all_artists()
    text = "<b>🎤 Artistlar bo‘limi</b>\n\n"
    if not artists:
        text += "<i>Hozircha artistlar mavjud emas.\nKanalga yangi qo'shiq yuklanganda bu bo'limda chiqadi.</i>"
        await message.answer(text + PROMO_TEXT, parse_mode="HTML")
        return

    text += "Quyidagi ijrochilardan birini tanlang:\n\n"
    builder = InlineKeyboardBuilder()
    for artist in artists:
        builder.add(InlineKeyboardButton(text=artist, callback_data=f"artist_sel_{quote_plus(artist)}"))
    builder.adjust(2)
    builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
    await message.answer(text + PROMO_TEXT, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message()
async def handle_media_and_search(message: types.Message):
    text = message.text
    if not text: return

    # 1. URL pattern detection
    if any(p in text for p in ["youtube.com", "youtu.be", "tiktok.com", "instagram.com"]):
        ok, wait_for = _rate_limit_ok(message.from_user.id)
        if not ok:
            await message.answer(f"Juda tez so'rov yuboryapsiz. {wait_for:.1f} soniya kuting.")
            return
        
        await message.bot.send_chat_action(message.chat.id, "record_voice")
        wait_msg = await message.answer("⏳ Media yuklab olinmoqda...")
        try:
            info, file_path = await download_media(text, message.chat.id)
            media_file = FSInputFile(file_path)
            
            duration_str = ""
            if info.get('duration'):
                mins, secs = divmod(int(info['duration']), 60)
                duration_str = f" [{mins}:{secs:02d}]"
                
            sent_msg = await message.answer_audio(
                media_file, 
                title=info.get('title', 'Media'), 
                caption=f"✅ {info.get('title', '')}{duration_str}{PROMO_TEXT}",
                parse_mode="HTML"
            )
            archive_service.increment_download(info.get("id"))
            
            # Cache to Archive Channel
            if config.ARCHIVE_CHANNEL:
                try:
                    archive_msg = await message.bot.send_audio(
                        chat_id=config.ARCHIVE_CHANNEL, 
                        audio=sent_msg.audio.file_id, 
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
                except Exception as e:
                    logger.error(f"Archive error: {e}")
            
        except Exception as exc:
            logger.error(f"Media download error: {exc}")
            await message.answer(
                f"❌ <b>Media yuklashda xato yuz berdi.</b>\n\n"
                f"<i>{exc}</i>\n\n"
                "💡 Boshqa link yuboring yoki qo'shiq nomini yozing.",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        finally:
            if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)
            await wait_msg.delete()
        return

    # 2. Search logic (Archive first, then YouTube)
    results = archive_service.search_cache(text)
    if len(results) < 10:
        await message.bot.send_chat_action(message.chat.id, "typing")
        search_msg = await message.answer("🔍 YouTube dan qidirilmoqda...")
        try:
            yt_results = await search_youtube(text, max_results=10)
            asyncio.create_task(archive_all_results_task(yt_results, message.bot))
            seen_ids = {res['id'] for res in results}
            for yt_res in yt_results:
                if yt_res['id'] not in seen_ids:
                    results.append(yt_res)
                    seen_ids.add(yt_res['id'])
        except Exception as e:
            logger.error(f"YouTube Search failed: {e}")
        finally:
            try:
                await search_msg.delete()
            except: pass

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

# --- Callbacks ---

@router.callback_query(F.data.startswith("dl_"))
async def process_download(callback: types.CallbackQuery):
    video_id = callback.data.split("_", 1)[1]
    ok, wait_for = _rate_limit_ok(callback.from_user.id)
    if not ok:
        await callback.answer(f"Juda tez so'rov. {wait_for:.1f}s kuting.", show_alert=True)
        return
    
    await callback.bot.send_chat_action(callback.message.chat.id, "record_voice")
    wait_msg = await callback.message.answer("⏳ Audio yuklab olinmoqda...")
    await callback.answer()

    cached_file_id = archive_service.get_cached_file_id(video_id)
    caption_text = "❤️ @toparchik_bot orqali istagan musiqangizni tez va oson toping!🚀"
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👉 Guruhga Qo'shish ↗️", url="https://t.me/toparchik_bot?startgroup=true"))
    
    if cached_file_id:
        await callback.message.answer_audio(cached_file_id, caption=caption_text, reply_markup=builder.as_markup())
        archive_service.increment_download(video_id)
        await wait_msg.delete()
        return
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        info, file_path = await download_media(url, callback.message.chat.id, audio_only=True)
        sent_msg = await callback.message.answer_audio(FSInputFile(file_path), title=info.get('title', 'Audio'), caption=caption_text, reply_markup=builder.as_markup())
        archive_service.increment_download(video_id)
        
        if config.ARCHIVE_CHANNEL:
            try:
                archive_msg = await callback.bot.send_audio(
                    chat_id=config.ARCHIVE_CHANNEL,
                    audio=sent_msg.audio.file_id,
                    caption=f"#musiqa {info.get('title', '')}",
                    title=info.get('title', '')
                )
                archive_service.cache_file_info(video_id, archive_msg.audio.file_id, info.get('title', ''), info.get('duration', 0), parse_artist_from_title(info.get('title', '')), platform="youtube")
            except: pass
    except Exception as exc:
        logger.error(f"Download callback error: {exc}")
        await callback.message.answer(
            f"❌ <b>Yuklashda xato:</b>\n<i>{exc}</i>\n\n"
            "💡 Boshqa qo'shiq tanlang yoki nom bilan qidiring.",
            parse_mode="HTML"
        )
    finally:
        if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)
        await wait_msg.delete()

@router.callback_query(F.data == "nav_close")
async def nav_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data.startswith("artist_sel_"))
async def artist_selected(callback: types.CallbackQuery):
    # artist_sel_ prefix ni to'g'ri olib tashlash (split emas, removeprefix)
    raw = callback.data.removeprefix("artist_sel_")
    artist = unquote_plus(raw)
    songs = archive_service.get_songs_by_artist(artist)
    response_text = f"<b>🎶 {artist} qo'shiqlari:</b>\n\n"
    
    if not songs:
        response_text += "<i>Bu artist uchun hozircha qo'shiq mavjud emas.</i>"
        await callback.message.answer(response_text + PROMO_TEXT, parse_mode="HTML")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    buttons = []
    for i, song in enumerate(songs[:10], 1):
        mins, secs = divmod(int(song.get('duration', 0)), 60)
        dur = f" ({mins}:{secs:02d})"
        response_text += f"<b>{i}.</b> {song['title']}{dur}\n"
        buttons.append(InlineKeyboardButton(text=str(i), callback_data=f"dl_{song['id']}"))

    if buttons:
        builder.add(*buttons)
        builder.adjust(5, 5)

    builder.add(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="artist_back"))
    builder.add(InlineKeyboardButton(text="❌ Yopish", callback_data="nav_close"))
    await callback.message.answer(response_text + PROMO_TEXT, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "artist_back")
async def artist_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await artist_menu(callback.message)
    await callback.answer()
