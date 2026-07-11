from datetime import datetime, time, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.history import bp
from app.models import Bill, BillLineItem, Product
from app.services import billing_service
from app.utils import admin_required, local_tz


def _local_date_to_utc(date_str, end_of_day=False):
    """Filter dates are entered in the shop's timezone; bills are stored UTC."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    local = datetime.combine(d, t, tzinfo=local_tz())
    return local.astimezone(timezone.utc).replace(tzinfo=None)


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    bill_number = request.args.get("bill_number", "").strip()
    status = request.args.get("status", "")
    product_id = request.args.get("product", type=int)
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    page = request.args.get("page", 1, type=int)

    query = Bill.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Bill.customer_name.ilike(like), Bill.customer_phone.ilike(like)))
    if bill_number:
        query = query.filter(Bill.bill_number.ilike(f"%{bill_number}%"))
    if status in ("completed", "voided"):
        query = query.filter(Bill.status == status)
    if product_id:
        query = query.join(BillLineItem).filter(BillLineItem.product_id == product_id).distinct()
    try:
        if date_from:
            query = query.filter(Bill.bill_date >= _local_date_to_utc(date_from))
        if date_to:
            query = query.filter(Bill.bill_date <= _local_date_to_utc(date_to, end_of_day=True))
    except ValueError:
        flash("Invalid date filter.", "warning")

    pagination = db.paginate(
        query.order_by(Bill.bill_date.desc()), page=page, per_page=25, error_out=False
    )
    products = Product.query.order_by(Product.name).all()
    return render_template(
        "history/index.html",
        pagination=pagination,
        bills=pagination.items,
        products=products,
        filters={
            "q": q,
            "bill_number": bill_number,
            "status": status,
            "product": product_id,
            "from": date_from,
            "to": date_to,
        },
    )


@bp.route("/<int:bill_id>/void", methods=["POST"])
@admin_required
def void(bill_id):
    bill = db.get_or_404(Bill, bill_id)
    try:
        billing_service.void_bill(bill, current_user.id)
        flash(f"Bill {bill.bill_number} voided — stock restored.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("billing.view", bill_id=bill.id))
