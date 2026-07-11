from flask import redirect, url_for
from flask_login import login_required

from app.main import bp


@bp.route("/health")
def health():
    return {"status": "ok"}


@bp.route("/")
@login_required
def index():
    return redirect(url_for("billing.index"))
