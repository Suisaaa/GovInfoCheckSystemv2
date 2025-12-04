from pathlib import Path
from flask import Flask, redirect, url_for, request
from flask_login import current_user
from .extensions import db, migrate, login_manager
from .config import Config
from .main import bp as main_bp
from .auth import bp as auth_bp
from .admin import bp as admin_bp
from .collector import bp as collector_bp
from .models import User

BASE_DIR = Path(__file__).resolve().parent.parent

def create_app():
    app = Flask(__name__, static_folder=str(BASE_DIR / 'static'), template_folder=str(BASE_DIR / 'templates'))
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(collector_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.before_request
    def _force_login():
        if current_user.is_authenticated:
            return None
        if request.endpoint in ('static',) or (request.endpoint and request.endpoint.startswith('auth.')):
            return None
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_settings():
        from .models import Setting
        s = db.session.query(Setting).first()
        return dict(app_setting=s)

    with app.app_context():
        from sqlalchemy import inspect
        from .models import Role, User, Setting
        insp = inspect(db.engine)
        if insp.has_table('role') and not db.session.query(Role).count():
            db.session.add_all([Role(name='admin'), Role(name='user')])
            db.session.commit()
        if insp.has_table('user') and not db.session.query(User).count():
            admin_role = db.session.query(Role).filter_by(name='admin').first()
            if admin_role:
                u = User(username='admin', role=admin_role)
                u.set_password('admin123')
                db.session.add(u)
                db.session.commit()
        if insp.has_table('setting') and not db.session.query(Setting).count():
            db.session.add(Setting(app_name='政企智能舆情分析报告生成'))
            db.session.commit()
    return app
