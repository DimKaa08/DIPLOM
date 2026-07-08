# backend/soundcloud_auth.py
import base64
import time
import requests
import urllib3
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("SOUNDCLOUD_CLIENT_ID")
CLIENT_SECRET = os.getenv("SOUNDCLOUD_CLIENT_SECRET")

_cached_token    = None
_token_expires_at = 0


def fetch_soundcloud_access_token() -> str:
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < (_token_expires_at - 30):
        return _cached_token

    print("[SoundCloud OAuth] Запрашиваем новый токен доступа...")

    raw_credentials    = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(raw_credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type":  "application/x-www-form-urlencoded",
        "Accept":        "application/json; charset=utf-8",
    }

    # ИСПРАВЛЕНО: увеличен timeout с 5 до 15 секунд — в Docker сеть медленнее.
    # verify=False отключает проверку SSL-сертификата — решает
    # SSLEOFError внутри контейнера без доступа к системным CA-сертификатам.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    for attempt in range(3):
        try:
            r = requests.post(
                "https://secure.soundcloud.com/oauth/token",
                headers=headers,
                data={"grant_type": "client_credentials"},
                timeout=15,
                verify=False,   # SSL обходим внутри Docker
            )

            if r.status_code != 200:
                print(f"[SoundCloud OAuth] Ошибка токена ({r.status_code}): {r.text}")
                return ""

            res_data         = r.json()
            _cached_token    = res_data.get("access_token", "")
            _token_expires_at = time.time() + res_data.get("expires_in", 3600)

            print("[SoundCloud OAuth] Токен получен и закэширован.")
            return _cached_token

        except requests.exceptions.Timeout:
            print(f"[SoundCloud OAuth] Таймаут (попытка {attempt + 1}/3)...")
        except Exception as e:
            print(f"[SoundCloud OAuth] Ошибка (попытка {attempt + 1}/3): {e}")

    print("[SoundCloud OAuth] Все попытки исчерпаны.")
    return ""