import hashlib
import hmac
from urllib.parse import parse_qsl
import time


class TelegramInitDataError(Exception):
    pass


def _build_data_check_string(init_data: str) -> tuple[str, str, dict[str, str]]:
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", "")
    if not received_hash:
        raise TelegramInitDataError("initData missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    return data_check_string, received_hash, data


def verify_init_data(init_data: str, bot_token: str, *, max_age_seconds: int = 86400) -> bool:
    data_check_string, received_hash, data = _build_data_check_string(init_data)

    # Telegram WebApp validation uses a derived secret key:
    # secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    # https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return False

    auth_date_raw = data.get("auth_date")
    if not auth_date_raw:
        return False
    try:
        auth_date = int(auth_date_raw)
    except ValueError:
        return False

    now = int(time.time())
    if auth_date > now:
        return False
    return (now - auth_date) <= max_age_seconds

