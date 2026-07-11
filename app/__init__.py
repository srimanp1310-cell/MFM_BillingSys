import os

import click
from flask import Flask

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.billing import bp as billing_bp
    from app.history import bp as history_bp
    from app.main import bp as main_bp
    from app.purchases import bp as purchases_bp
    from app.stock import bp as stock_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(admin_bp)

    from app.utils import amount_in_words, to_local

    app.add_template_filter(amount_in_words, "in_words")

    @app.template_filter("localdt")
    def localdt(dt, fmt="%d-%m-%Y %I:%M %p"):
        local = to_local(dt)
        return local.strftime(fmt) if local else ""

    @app.template_filter("localdate")
    def localdate(dt, fmt="%d-%m-%Y"):
        local = to_local(dt)
        return local.strftime(fmt) if local else ""

    @app.context_processor
    def inject_globals():
        from flask_login import current_user

        from app.models import AppSetting, Product

        try:
            symbol = AppSetting.get("currency_symbol") or app.config["CURRENCY_SYMBOL"]
        except Exception:  # settings table may not exist mid-migration
            symbol = app.config["CURRENCY_SYMBOL"]

        low_stock_count = 0
        if current_user.is_authenticated:
            try:
                low_stock_count = Product.query.filter(
                    Product.is_active.is_(True),
                    Product.reorder_level.isnot(None),
                    Product.quantity_on_hand <= Product.reorder_level,
                ).count()
            except Exception:
                pass

        return {"currency": symbol, "low_stock_count": low_stock_count}

    register_cli(app)
    return app


def register_cli(app):
    @app.cli.command("seed-admin")
    @click.option("--username", default="admin", show_default=True)
    @click.option("--password", default=None, help="If omitted, you will be prompted.")
    def seed_admin(username, password):
        """Create the initial admin user (no-op if username exists)."""
        from app.models import ROLE_ADMIN, User

        username = username.strip().lower()
        if User.query.filter_by(username=username).first():
            click.echo(f"User '{username}' already exists — nothing to do.")
            return
        if not password:
            password = click.prompt("Password for admin", hide_input=True, confirmation_prompt=True)
        user = User(username=username, role=ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{username}' created.")

    @app.cli.command("gen-vapid")
    def gen_vapid():
        """Generate VAPID keys for Web Push; paste the output into .env."""
        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = ec.generate_private_key(ec.SECP256R1())
        private = base64.urlsafe_b64encode(
            key.private_numbers().private_value.to_bytes(32, "big")
        ).rstrip(b"=").decode()
        public = base64.urlsafe_b64encode(
            key.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        ).rstrip(b"=").decode()
        click.echo(f"VAPID_PUBLIC_KEY={public}")
        click.echo(f"VAPID_PRIVATE_KEY={private}")
