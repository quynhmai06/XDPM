from config import Config
def vnd(n: int) -> str: return f"{n:,.0f} VND".replace(",", ",")
def bank_info(grand: int, pay_id: int, order_id: int) -> dict:
    memo = f"PAY{pay_id}-ORD{order_id}"
    qr_text = f"{Config.BANK_NAME} | STK:{Config.BANK_ACCOUNT} | CTK:{Config.BANK_OWNER} | ND:{memo} | AMT:{grand}"
    return {"bank_name":Config.BANK_NAME, "bank_account":Config.BANK_ACCOUNT,
            "bank_owner":Config.BANK_OWNER, "memo":memo, "qr_text":qr_text}
