FROM python:3.11-slim

WORKDIR /app

# Системные зависимости (yt-dlp нужен ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем PyTorch CPU отдельно — он скачивается с другого индекса
# и весит ~200 МБ. Отдельный RUN-слой кэшируется независимо от остального кода.
RUN pip install --no-cache-dir torch==2.4.1 \
    --index-url https://download.pytorch.org/whl/cpu

# Остальные зависимости — с обычного PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код последним — при изменении кода только этот слой пересобирается
COPY . .

EXPOSE 8000