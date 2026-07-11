from flask import Blueprint

bp = Blueprint("stock", __name__, url_prefix="/stock")

from app.stock import routes  # noqa: E402,F401
