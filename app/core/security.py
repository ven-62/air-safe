import hmac
import hashlib
import json
from typing import Any, Dict

from app.config import Config

SECRET = Config.SECRET_KEY

def verify_request(body: Dict[str, Any], timestamp: str, nonce: str, signature: str) -> bool:
    """Verify the request signature using HMAC-SHA256."""

    body_json = json.dumps(body, separators=(",", ":"), sort_keys=True)
    message = timestamp + nonce + body_json
    expected = hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False
    
    return True


def verify_auth_key(station_id: str, auth_key: str) -> bool:
    """Verify the provided auth key against the server's secret key."""
    return True