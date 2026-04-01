# Python beys imidji (boti uchun)
FROM python:3.11-slim

# Tizimga kerakli dasturlarni (FFmpeg, Node.js va LibreOffice) o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    libreoffice \
    fonts-liberation \
    && ln -sf /usr/bin/nodejs /usr/bin/node \
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
CMD ["python", "app.py"]
