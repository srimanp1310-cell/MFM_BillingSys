"""Low-stock notifications. Web Push delivery is wired in the PWA phase;
until then this records intent via app logging only."""

from flask import current_app


def notify_low_stock(products):
    """Send a push notification for products that just hit their reorder level."""
    if not products:
        return
    names = ", ".join(f"{p.name} ({p.quantity_on_hand} left)" for p in products)
    current_app.logger.info("LOW STOCK: %s", names)
    try:
        from app.services import push_service

        push_service.broadcast(
            title="Low stock alert",
            body=f"Reorder needed: {names}",
            url="/stock/?low=1",
        )
    except ImportError:
        pass  # push_service arrives in the PWA phase
