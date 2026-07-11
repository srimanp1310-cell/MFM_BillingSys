from flask import render_template
from flask_login import login_required

from app.stock import bp


@bp.route("/")
@login_required
def index():
    return render_template("placeholder.html", title="Stock Status")
