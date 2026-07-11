from datetime import timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import abort, current_app
from flask_login import current_user, login_required


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def local_tz():
    return ZoneInfo(current_app.config.get("TIMEZONE", "Asia/Kolkata"))


def to_local(dt):
    """Convert a naive-UTC datetime from the DB to the shop's timezone."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(local_tz())


def local_now():
    from datetime import datetime

    return datetime.now(local_tz())
