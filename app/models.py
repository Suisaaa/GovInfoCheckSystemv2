from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    role = db.relationship('Role')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    app_name = db.Column(db.String(128), nullable=False, default='政企智能舆情分析报告生成')
    logo_path = db.Column(db.String(256))

class CollectionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(512), nullable=False)
    cover = db.Column(db.String(512))
    url = db.Column(db.String(1024), unique=True, nullable=False)
    source = db.Column(db.String(256))
    keyword = db.Column(db.String(128))
    deep_status = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class CollectionDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('collection_item.id'), nullable=False)
    content_text = db.Column(db.Text)
    content_html = db.Column(db.Text)
    final_url = db.Column(db.String(1024))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    item = db.relationship('CollectionItem')

class CrawlRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    site = db.Column(db.String(256), nullable=False)
    title_xpath = db.Column(db.Text)
    content_xpath = db.Column(db.Text)
    request_headers = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

class AIEngine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(128), nullable=False)
    api_url = db.Column(db.String(512), nullable=False)
    api_key = db.Column(db.String(512))
    model_name = db.Column(db.String(256), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
