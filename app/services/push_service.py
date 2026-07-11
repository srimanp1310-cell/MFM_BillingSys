"""Web Push delivery via pywebpush. Failures never break the calling flow."""

import json

from flask import current_app
from pywebpush import WebPushException, webpush

from app.extensions import db
from app.models import PushSubscription


def broadcast(title, body, url="/"):
    private_key = current_app.config.get("VAPID_PRIVATE_KEY")
    if not private_key:
        current_app.logger.info("Push skipped: VAPID keys not configured.")
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url})
    claims_email = current_app.config.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")
    sent = 0
    for sub in PushSubscription.query.all():
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": claims_email},
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):  # subscription expired/uninstalled
                db.session.delete(sub)
                db.session.commit()
            else:
                current_app.logger.warning("Push failed for sub %s: %s", sub.id, e)
        except Exception as e:  # never let notifications break billing
            current_app.logger.warning("Push error: %s", e)
    return sent
