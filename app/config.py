import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(BASE_DIR / "instance" / "app.db")
    )
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
