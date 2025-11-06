# config.py
import os

class Config:
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///payment.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JSON / i18n
    JSON_AS_ASCII = False  # để hiển thị tiếng Việt đúng

    # Service URLs / constants
    GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
    VAT_RATE = float(os.getenv("VAT_RATE", "0.10"))

    # JWT for contract signing
    JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
    JWT_ALGO = "HS256"

    # Bank info for QR / chuyển khoản
    BANK_NAME = os.getenv("BANK_NAME", "Vietcombank")
    BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "0123456789")
    BANK_OWNER = os.getenv("BANK_OWNER", "EV & Battery Platform")
