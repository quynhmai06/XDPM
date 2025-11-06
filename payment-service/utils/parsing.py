from models import Contract

def parse_kv_from_contract(c: Contract):
    kv = {}
    for line in (c.content or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip().lower()] = v.strip()
    def pick(*keys, default=""):
        for k in keys:
            v = kv.get(k.lower())
            if v: return v
        return default
    return {
        "full_name": pick("Họ tên","ho ten", default="(Không rõ)"),
        "phone":     pick("Điện thoại","dien thoai"),
        "email":     pick("Email"),
        "address":   pick("Địa chỉ","dia chi"),
        "tax_code":  pick("Mã số thuế","ma so thue", default="(không)"),
        "note":      pick("Ghi chú","ghi chu"),
    }
