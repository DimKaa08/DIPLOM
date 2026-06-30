# backend/soundcloud_auth.py
import base64
import time
import requests

# ⚠️ Вставьте сюда ваши данные из панели https://soundcloud.com/you/apps
CLIENT_ID = "fiuzE85k3o4UWMYgDJCeS1RwwsSINyOT"
CLIENT_SECRET = "EbbqTaPWFPkLXts90DPr84EnwewdhZcu"

# Внутреннее кэширование токена в памяти
_cached_token = None
_token_expires_at = 0

def fetch_soundcloud_access_token() -> str:
    """
    Автоматически получает и обновляет официальный OAuth 2.1 токен для SoundCloud.
    Использует Client Credentials Flow через HTTP Basic Authentication.
    """
    global _cached_token, _token_expires_at
    
    # Если токен существует и еще действует (с запасом в 30 секунд), возвращаем его
    if _cached_token and time.time() < (_token_expires_at - 30):
        return _cached_token

    print("[SoundCloud OAuth] Запрашиваем новый токен доступа...")
    url = "https://secure.soundcloud.com/oauth/token"
    
    # Формируем обязательную по стандарту OAuth 2.1 Basic-авторизацию
    raw_credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(raw_credentials.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json; charset=utf-8"
    }
    data = {"grant_type": "client_credentials"}
    
    try:
        r = requests.post(url, headers=headers, data=data, timeout=5)
        if r.status_code != 200:
            print(f"[SoundCloud OAuth] Ошибка генерации токена ({r.status_code}): {r.text}")
            return ""
            
        res_data = r.json()
        _cached_token = res_data.get("access_token")
        # Кэшируем токен на время его жизни (обычно 3600 секунд)
        _token_expires_at = time.time() + res_data.get("expires_in", 3600)
        
        print("[SoundCloud OAuth] Токен успешно получен и сохранен в кэш.")
        return _cached_token
        
    except Exception as e:
        print(f"[SoundCloud OAuth] Ошибка соединения с сервером авторизации: {e}")
        return ""