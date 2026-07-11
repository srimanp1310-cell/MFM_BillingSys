from decimal import Decimal

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models import ROLE_ADMIN, ROLE_STAFF, Brand, Category, Product, User


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def users(db):
    admin = User(username="admin", role=ROLE_ADMIN)
    admin.set_password("adminpass")
    staff = User(username="staff", role=ROLE_STAFF)
    staff.set_password("staffpass")
    db.session.add_all([admin, staff])
    db.session.commit()
    return {"admin": admin, "staff": staff}


@pytest.fixture()
def products(db):
    chairs = Category(name="Chairs", track_size=False)
    mattress = Category(name="Mattress", track_size=True)
    db.session.add_all([chairs, mattress])
    db.session.flush()
    nilkamal = Brand(name="Nilkamal", category_id=chairs.id)
    db.session.add(nilkamal)
    db.session.flush()
    chair = Product(
        code="CHA-001", name="Plastic Chair", category_id=chairs.id, brand_id=nilkamal.id,
        unit_price=Decimal("500.00"), quantity_on_hand=0, reorder_level=5,
    )
    bed = Product(
        code="MAT-001", name="Ortho Mattress", category_id=mattress.id, size="72x36",
        unit_price=Decimal("8000.00"), quantity_on_hand=0, reorder_level=2,
    )
    db.session.add_all([chair, bed])
    db.session.commit()
    return {"chair": chair, "bed": bed}


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


@pytest.fixture()
def admin_client(client, users):
    login(client, "admin", "adminpass")
    return client


@pytest.fixture()
def staff_client(client, users):
    login(client, "staff", "staffpass")
    return client
