from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="member") 
    approved = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    phone = db.Column(db.String(20), unique=True)

class OAuthAccount(db.Model):
    __tablename__ = "oauth_accounts"
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False)   # 'google' | 'facebook'
    sub = db.Column(db.String(191), nullable=False)       # subject/ID từ provider
    email = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("provider","sub", name="uq_provider_sub"),)
