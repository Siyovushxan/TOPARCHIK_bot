import asyncio
import time
import datetime
from google import genai as google_genai
from toparchik_bot.config import GEMINI_API_KEY

# Models ordered from highest-quota/cheapest to lowest-quota.
GEMINI_MODELS = (
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-pro",
)

_GEMINI_DAILY_EXHAUSTED = {}  # model_name -> reset_timestamp
GEMINI_BACKOFF_UNTIL = 0
GEMINI_KEY_INVALID = False

client = google_genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def is_quota_error(exc):
    text = str(exc).lower()
    return any(m in text for m in ("quota exceeded", "resource_exhausted", "429", "too many requests"))

def is_daily_quota_error(exc):
    text = str(exc).lower()
    return any(m in text for m in ("generaterequestsperday", "daily", "per day"))

async def ask_gemini(prompt: str) -> str:
    global GEMINI_BACKOFF_UNTIL, GEMINI_KEY_INVALID

    if not GEMINI_API_KEY:
        return "AI kalit topilmadi."

    if GEMINI_KEY_INVALID:
        return "Gemini API key yaroqsiz."

    now = time.time()
    if now < GEMINI_BACKOFF_UNTIL:
        return f"AI limitga yetdi. {int(GEMINI_BACKOFF_UNTIL - now)} soniyadan keyin qayta urinib ko'ring."

    for model_name in GEMINI_MODELS:
        if time.time() < _GEMINI_DAILY_EXHAUSTED.get(model_name, 0):
            continue

        try:
            # Using synchronous client in loop.run_in_executor to ensure compatibility and stability 
            # if AsyncClient has installation/environment specific issues, 
            # but wrapping it correctly as requested.
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda m=model_name: client.models.generate_content(
                    model=m,
                    contents=prompt,
                )
            )
            if response and response.text:
                return response.text
        except Exception as exc:
            # Filter specifically for 404 NOT_FOUND to log it clearly
            if "404" in str(exc) or "not found" in str(exc).lower():
                print(f"Gemini model {model_name} not available: {exc}")
                continue
            if "api key" in str(exc).lower():
                GEMINI_KEY_INVALID = True
                return "Gemini API key yaroqsiz."
            
            if is_quota_error(exc):
                if is_daily_quota_error(exc):
                    now_dt = datetime.datetime.now()
                    midnight = (now_dt + datetime.timedelta(days=1)).replace(
                        hour=0, minute=5, second=0, microsecond=0
                    )
                    _GEMINI_DAILY_EXHAUSTED[model_name] = midnight.timestamp()
                    continue
                else:
                    GEMINI_BACKOFF_UNTIL = time.time() + 30
                    continue # Try next model if 429
            
            print(f"Gemini error ({model_name}): {exc}")
            continue

    return "AI hozirda band. Iltimos, bir ozdan keyin urinib ko'ring."
