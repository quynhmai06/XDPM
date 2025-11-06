import jwt
from config import Config
def sign_contract(payload: dict) -> str:
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGO)
    