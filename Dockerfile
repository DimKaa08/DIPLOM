FROM python:3.11-slim

WORKDIR /app

# Системные зависимости (yt-dlp нужен ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только зависимости — Docker кэширует этот слой
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потом копируем исходный код
COPY . .

EXPOSE 8000