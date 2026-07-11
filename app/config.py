import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

_DEV_SECRET = "dev-only-insecure-key"


def _database_url():
    """Normalize host-provided URLs (Render/Railway give postgres://) to the
    psycopg3 driver SQLAlchemy expects."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url or ("sqlite:///" + str(BASE_DIR / "instance" / "app.db"))


def _is_production():
    # SECURE_COOKIES=1 marks a production (HTTPS) deployment.
    return os.environ.get("SECURE_COOKIES") == "1"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or _DEV_SECRET
    if _is_production() and SECRET_KEY == _DEV_SECRET:
        raise RuntimeError(
            "SECRET_KEY is not set. Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"` "
            "and set it in the host's environment variables."
        )

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session/cookie security. SECURE flags require HTTPS, so they are driven
    # by SECURE_COOKIES=1 (set in production; leave unset for http://localhost).
    SESSION_COOKIE_SECURE = _is_production()
    REMEMBER_COOKIE_SECURE = _is_production()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 30  # 30 days, staff devices

    # Display defaults; shop details are editable in Admin > Settings.
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "₹")  # ₹
    TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")  # bill dates / numbering year

    # Web Push (low-stock notifications); generate with `flask gen-vapid`.
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
