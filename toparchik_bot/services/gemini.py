import asyncio
import logging
import time
import datetime
from google import genai as google_genai
from toparchik_bot.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Models ordered from highest-quota/cheapest to lowest-quota.
# gemini-2.0-flash — eng tez va arzon yangi model
# gemini-1.5-flash — ishonchli zaxira
# gemini-1.5-flash-8b — oxirgi zaxira (eng arzon)
GEMINI_MODELS = (
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
)

SYSTEM_PROMPT = (
    "Sen TOPARCHIK AI — musiqa va media sohasida ixtisoslashgan yordamchi botsan. "
    "Foydalanuvchilar seni asosan qo'shiq, artist, musiqa janri, YouTube va musiqa tarixi "
    "haqida so'rash uchun ishlatadi. "
    "Javoblaringni qisqa, aniq va do'stona yoz. O'zbek tilida javob ber. "
    "Agar savol musiqaga bog'liq bo'lmasa, muloyimlik bilan foydalanuvchini "
    "@toparchik_bot orqali qo'shiq yoki link yuborishga yo'nalt. "
    "Hech qachon zararli yoki noo'rin kontent yaratma."
)

_GEMINI_DAILY_EXHAUSTED = {}  # model_name -> reset_timestamp
GEMINI_BACKOFF_UNTIL = 0.0
GEMINI_KEY_INVALID = False

client = google_genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(m in text for m in ("quota exceeded", "resource_exhausted", "429", "too many requests"))


def is_daily_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(m in text for m in ("generaterequestsperday", "daily", "per day"))


async def ask_gemini(prompt: str) -> str:
    global GEMINI_BACKOFF_UNTIL, GEMINI_KEY_INVALID

    if not GEMINI_API_KEY:
        return "⚠️ AI xizmati sozlanmagan. Administrator bilan bog'laning."

    if GEMINI_KEY_INVALID:
        return "⚠️ AI kaliti yaroqsiz. Administrator bilan bog'laning."

    now = time.time()
    if now < GEMINI_BACKOFF_UNTIL:
        wait_sec = int(GEMINI_BACKOFF_UNTIL - now)
        return f"⏳ AI bir oz band. {wait_sec} soniyadan keyin qayta urinib ko'ring."

    full_prompt = f"{SYSTEM_PROMPT}\n\nFoydalanuvchi savoli: {prompt}"

    for model_name in GEMINI_MODELS:
        if time.time() < _GEMINI_DAILY_EXHAUSTED.get(model_name, 0):
            continue

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda m=model_name: client.models.generate_content(
                    model=m,
                    contents=full_prompt,
                )
            )
            if response and response.text:
                logger.info(f"Gemini javob berdi ({model_name}): {len(response.text)} belgi")
                return response.text

        except Exception as exc:
            exc_str = str(exc)

            if "404" in exc_str or "not found" in exc_str.lower():
                logger.warning(f"Gemini model mavjud emas: {model_name}")
                continue

            if "api key" in exc_str.lower() or "api_key_invalid" in exc_str.lower():
                GEMINI_KEY_INVALID = True
                logger.error(f"Gemini API key yaroqsiz: {exc}")
                return "⚠️ AI kaliti yaroqsiz. Administrator bilan bog'laning."

            if is_quota_error(exc):
                if is_daily_quota_error(exc):
                    now_dt = datetime.datetime.now()
                    midnight = (now_dt + datetime.timedelta(days=1)).replace(
                        hour=0, minute=5, second=0, microsecond=0
                    )
                    _GEMINI_DAILY_EXHAUSTED[model_name] = midnight.timestamp()
                    logger.warning(f"Gemini {model_name} kunlik limitga yetdi.")
                    continue
                else:
                    GEMINI_BACKOFF_UNTIL = time.time() + 30
                    logger.warning(f"Gemini {model_name} rate limit. 30s kutilmoqda.")
                    continue

            logger.error(f"Gemini xato ({model_name}): {exc}")
            continue

    return "🤖 AI hozirda band yoki barcha modellar limitga yetdi. Iltimos, biroz kutib qayta urinib ko'ring."
