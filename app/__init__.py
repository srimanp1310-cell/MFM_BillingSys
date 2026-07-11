import os

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

    @login_manager.user_loader
    def load_user(user_id):  # replaced by the real loader in the auth phase
        return None

    from app.main import bp as main_bp

    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_globals():
        return {"currency": app.config["CURRENCY_SYMBOL"]}

    return app
