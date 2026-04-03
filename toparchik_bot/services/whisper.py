import aiohttp
import asyncio
from config import HF_TOKEN

API_URLS = [
    "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3-turbo",
    "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3",
]
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

async def transcribe_audio(file_path: str) -> str:
    if not HF_TOKEN:
        return "HF_TOKEN topilmadi."

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            last_error = "Noma'lum xato."
            for url in API_URLS:
                try:
                    async with session.post(url, headers=headers, data=data) as response:
                        # Handle 503 (Loading)
                        if response.status == 503:
                            await asyncio.sleep(5)
                            # Retry once for 503
                            async with session.post(url, headers=headers, data=data) as retry_resp:
                                if retry_resp.status == 200:
                                    result = await retry_resp.json()
                                    return result.get("text", "Matn aniqlanmadi.")
                            continue

                        if response.status != 200:
                            try:
                                error_data = await response.json()
                                last_error = error_data.get("error", str(error_data))
                            except:
                                error = await response.text()
                                last_error = f"HTTP {response.status}: {error[:100]}"
                            print(f"HF Whisper error ({url.split('/')[-1]}): {last_error}")
                            continue
                        
                        result = await response.json()
                        return result.get("text", "Matn aniqlanmadi.")
                except Exception as e:
                    last_error = str(e)
                    continue
            
            return f"Xatolik: {last_error[:100]}"
        except Exception as exc:
            print(f"Whisper general error: {exc}")
            return f"Transkripsiya xatosi: {exc}"
