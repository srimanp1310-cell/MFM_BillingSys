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


_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
    "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
    "Eighteen", "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digits(n):
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three_digits(n):
    out = ""
    if n >= 100:
        out = _ONES[n // 100] + " Hundred"
        if n % 100:
            out += " and " + _two_digits(n % 100)
    else:
        out = _two_digits(n)
    return out


def amount_in_words(amount):
    """Indian-numbering words for an invoice total, e.g. 3150 ->
    'Three Thousand One Hundred and Fifty Only'."""
    from decimal import Decimal

    amount = Decimal(amount).quantize(Decimal("0.01"))
    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    if rupees == 0:
        words = "Zero"
    else:
        parts = []
        crore, rest = divmod(rupees, 10_000_000)
        lakh, rest = divmod(rest, 100_000)
        thousand, hundreds = divmod(rest, 1000)
        if crore:
            parts.append(_three_digits(crore) + " Crore")
        if lakh:
            parts.append(_two_digits(lakh) + " Lakh")
        if thousand:
            parts.append(_two_digits(thousand) + " Thousand")
        if hundreds:
            parts.append(_three_digits(hundreds))
        words = " ".join(parts)

    if paise:
        words += f" and {_two_digits(paise)} Paise"
    return words + " Only"
