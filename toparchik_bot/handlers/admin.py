import asyncio
import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from toparchik_bot import config
from toparchik_bot.services.archive import archive_service

logger = logging.getLogger(__name__)
router = Router()

sync_lock = asyncio.Lock()

def is_admin(user_id: int | None) -> bool:
    if not user_id: return False
    return user_id in config.ADMIN_IDS if config.ADMIN_IDS else False

def _is_message_missing_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(m in text for m in ["message to forward not found", "message_id_invalid", "message not found"])

def parse_artist_from_title(title: str) -> str:
    import re
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

async def sync_archive_from_channel(bot: Bot, notify_chat_id: int | None):
    archive_chat = config.ARCHIVE_CHANNEL_ID or config.ARCHIVE_CHANNEL
    sync_chat_id = config.SYNC_CHAT_ID or notify_chat_id
    if not sync_chat_id:
        logger.warning("Sync chat ID not configured.")
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
                    if misses >= gap_limit: break
                    continue
                logger.warning(f"Forward error at {message_id}: {exc}")
                misses += 1
                if misses >= gap_limit: break
                continue
            except Exception as exc:
                logger.warning(f"Sync error at {message_id}: {exc}")
                misses += 1
                if misses >= gap_limit: break
                continue

            misses = 0
            audio = msg.audio
            if audio:
                title = audio.title or audio.file_name or (msg.caption or "").strip()
                if not title: title = f"Audio {message_id}"
                artist = audio.performer or parse_artist_from_title(title)
                duration = audio.duration or 0
                platform = detect_platform_from_url(msg.caption or "")
                unique_id = audio.file_unique_id or f"tg_{message_id}"
                archive_service.upsert_audio_entry(
                    unique_id=unique_id, file_id=audio.file_id, title=title,
                    duration=duration, artist=artist, platform=platform, message_id=message_id
                )
                found += 1

            try: await bot.delete_message(sync_chat_id, msg.message_id)
            except: pass
            await asyncio.sleep(delay)

        logger.info(f"Archive sync finished: {found} audio items.")

    if notify_chat_id:
        try: await bot.send_message(notify_chat_id, f"Sync tugadi: {found} ta audio topildi.")
        except: pass

@router.message(Command("sync_archive"))
async def command_sync_archive(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Sync ishlashi uchun ADMIN_IDS muhit o'zgaruvchisiga o'z ID'ingizni yozing.")
        return

    if sync_lock.locked():
        await message.answer("Sync allaqachon ishlayapti, biroz kuting.")
        return

    await message.answer("Sync boshlandi. Barchasi bo'limi to'ldirilmoqda...")
    asyncio.create_task(sync_archive_from_channel(message.bot, message.chat.id))
