from flask import current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.main import bp
from app.models import PushSubscription


@bp.route("/health")
def health():
    return {"status": "ok"}


@bp.route("/")
@login_required
def index():
    return redirect(url_for("billing.index"))


@bp.route("/offline")
def offline():
    return render_template("offline.html")


@bp.route("/service-worker.js")
def service_worker():
    # served from the root so its scope covers the whole app
    resp = current_app.send_static_file("service-worker.js")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    if not endpoint or "p256dh" not in keys or "auth" not in keys:
        return jsonify({"ok": False, "error": "Invalid subscription."}), 400
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = keys["p256dh"]
        existing.auth = keys["auth"]
    else:
        db.session.add(
            PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh=keys["p256dh"],
                auth=keys["auth"],
            )
        )
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if endpoint:
        PushSubscription.query.filter_by(endpoint=endpoint).delete()
        db.session.commit()
    return jsonify({"ok": True})
