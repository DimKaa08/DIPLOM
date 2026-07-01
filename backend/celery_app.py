# backend/celery_app.py
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "music_app",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.ml.tasks"],  # где искать задачи
)

celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Хранить результаты 24 часа
    result_expires=86400,

    # Временная зона
    timezone="UTC",
    enable_utc=True,

    # Не запускать больше одного обучения одновременно:
    # новая задача встаёт в очередь и ждёт, пока предыдущая не завершится
    task_acks_late=True,
    worker_concurrency=1,

    # Повтор при сбое соединения с Redis (не при ошибке в коде)
    broker_connection_retry_on_startup=True,
)