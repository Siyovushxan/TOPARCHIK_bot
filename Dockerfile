FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/bin:${PATH}"

RUN apt-get -o Acquire::Retries=5 update && apt-get install -y --no-install-recommends \
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
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN if [ -f /usr/bin/nodejs ] && [ ! -f /usr/bin/node ]; then ln -s /usr/bin/nodejs /usr/bin/node; fi

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
