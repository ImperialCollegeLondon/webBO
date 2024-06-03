from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path, getenv
from flask_login import LoginManager


db = SQLAlchemy()
DB_NAME = "database.db"
URL_PREFIX = getenv("URL_PREFIX", "")


def create_app():
    app = Flask(__name__, static_url_path=f"{URL_PREFIX}/static")
    app.config['SECRET_KEY'] = 'woof!'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_NAME}"
    db.init_app(app)

    from .dataset_forms import data_views
    from .experiment_forms import expt_views
    from .home_dash import home_dash
    from .auth import auth

    app.register_blueprint(home_dash, url_prefix=URL_PREFIX)
    app.register_blueprint(data_views, url_prefix=URL_PREFIX)
    app.register_blueprint(expt_views, url_prefix=URL_PREFIX)
    app.register_blueprint(auth, url_prefix=URL_PREFIX)

    from .models import User

    create_database(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app


def create_database(app):
    if not path.exists('website/' + DB_NAME):
        with app.app_context():
            db.create_all()
