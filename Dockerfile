# Python beys imidji (boti uchun)
FROM python:3.11-slim

# Tizimga kerakli dasturlarni (FFmpeg va Node.js) o'rnatish
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogni belgilash
WORKDIR /app

# Barcha kerakli kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni nusxalash
COPY . .

# .env fayli yo'qligini tekshirish uchun (Koyeb'da muhit o'zgaruvchilari orqali beriladi)
# Botni ishga tushirish
CMD ["python", "bot.py"]
