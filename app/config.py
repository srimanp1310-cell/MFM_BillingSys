import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _database_url():
    """Normalize host-provided URLs (Render/Railway give postgres://) to the
    psycopg3 driver SQLAlchemy expects."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url or ("sqlite:///" + str(BASE_DIR / "instance" / "app.db"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    SQLALCHEMY_DATABASE_URI = _database_url()

    # Set SECURE_COOKIES=1 in production (HTTPS hosts).
    SESSION_COOKIE_SECURE = os.environ.get("SECURE_COOKIES") == "1"
    REMEMBER_COOKIE_SECURE = os.environ.get("SECURE_COOKIES") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Display defaults; shop details are editable in Admin > Settings.
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "₹")  # ₹

    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")

    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 30  # 30 days, staff devices


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
