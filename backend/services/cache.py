# backend/services/cache.py
"""
Централизованный Redis-клиент для кеширования.
Используется в recommendations.py (хранение) и events.py (инвалидация).
"""
import os
import json
import redis

_client: redis.Redis | None = None

def get_redis() -> redis.Redis:
    """Ленивая инициализация — подключаемся только при первом вызове."""
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _client = redis.from_url(url, decode_responses=True)
    return _client


# ── Рекомендации ──────────────────────────────────────────────────────────
REC_TTL = 300  # секунд — рекомендации хранятся 5 минут


def recs_key(user_id: int) -> str:
    return f"recs:{user_id}"


def get_cached_recs(user_id: int) -> list | None:
    """Возвращает список треков из кеша или None если кеш пуст/просрочен."""
    try:
        raw = get_redis().get(recs_key(user_id))
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[Cache] Ошибка чтения: {e}")
    return None


def set_cached_recs(user_id: int, tracks: list, ttl: int = REC_TTL) -> None:
    """Сохраняет список треков в Redis с TTL."""
    try:
        get_redis().setex(recs_key(user_id), ttl, json.dumps(tracks, ensure_ascii=False))
    except Exception as e:
        print(f"[Cache] Ошибка записи: {e}")


def invalidate_recs(user_id: int) -> None:
    """
    Удаляет кеш рекомендаций для пользователя.
    Вызывается при каждом новом взаимодействии (events.py)
    и после дизлайка (recommendations.py).
    """
    try:
        deleted = get_redis().delete(recs_key(user_id))
        if deleted:
            print(f"[Cache] Инвалидирован кеш рекомендаций для юзера {user_id}")
    except Exception as e:
        print(f"[Cache] Ошибка инвалидации: {e}")