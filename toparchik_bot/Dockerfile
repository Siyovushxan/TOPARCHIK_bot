FROM python:3.11-slim-bookworm

# Add apt-get retry logic and install system dependencies:
# - build-essential, python3-dev: for compiling some pip packages if needed
# - ffmpeg: audio/video processing
# - libreoffice-writer, libreoffice-calc: docx conversion
# - libmagic1: for file type detection (python-magic)
# - libfontconfig1, libxrender1, libgl1: often needed for LibreOffice/PyMuPDF headless
# - nodejs: js engine for yt-dlp/js2py
RUN apt-get -o Acquire::Retries=5 update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    ffmpeg \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-common \
    fonts-liberation \
    libmagic1 \
    libfontconfig1 \
    libxrender1 \
    libgl1 \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Help node detection if needed
RUN if [ -f /usr/bin/nodejs ] && [ ! -f /usr/bin/node ]; then ln -s /usr/bin/nodejs /usr/bin/node; fi

WORKDIR /app

# Ensure we have the latest pip
RUN pip install --no-cache-dir --upgrade pip

# Barcha kerakli kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni nusxalash
COPY . .

# Botni ishga tushirish
CMD ["python", "app.py"]
