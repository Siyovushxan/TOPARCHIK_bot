import aiohttp
from config import HF_TOKEN

API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3-turbo"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

async def transcribe_audio(file_path: str) -> str:
    if not HF_TOKEN:
        return "HF_TOKEN topilmadi. Iltimos, Hugging Face tokenini qo'shing."

    async with aiohttp.ClientSession() as session:
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            async with session.post(API_URL, headers=headers, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"HF Whisper error: {error_text}")
                    return f"Xatolik (HTTP {response.status}): {error_text}"
                
                result = await response.json()
                return result.get("text", "Ovozli xabardan matn aniqlanmadi.")
        except Exception as exc:
            print(f"Whisper inference error: {exc}")
            return f"Transkripsiya paytida xato yuz berdi: {exc}"
