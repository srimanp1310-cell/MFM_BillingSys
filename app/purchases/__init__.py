from flask import Blueprint

bp = Blueprint("purchases", __name__, url_prefix="/purchases")

from app.purchases import routes  # noqa: E402,F401
