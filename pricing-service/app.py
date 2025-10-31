# pricing-service/app.py
from flask import Flask, request, jsonify
import os, json, re, time, hashlib, threading, concurrent.futures

# ================== Config ==================
PROVIDER      = os.getenv("PROVIDER", "gemini").strip().lower()   # "gemini" | "openai" | "auto"
GEMINI_MODEL  = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SOFT_TIMEOUT  = int(os.getenv("SOFT_TIMEOUT", "8"))                # chờ kết quả "mềm" (giây)
HARD_TIMEOUT  = int(os.getenv("HARD_TIMEOUT", "15"))               # timeout request tới provider (giây)
CACHE_TTL     = int(os.getenv("CACHE_TTL", "600"))                 # 10 phút
STRICT_AI     = os.getenv("STRICT_AI", "0").lower() in ("1","true","yes")  # AI-only, không fallback

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # tiếng Việt không bị escape

SYSTEM_PROMPT = (
    "Bạn là trợ lý định giá chợ đồ xe điện cũ VN. "
    "Hãy ước lượng giá VNĐ hợp lý dựa trên thông tin sản phẩm (xe/pin), "
    "bối cảnh thị trường VN, khấu hao theo năm, số km, dung lượng pin, khu vực. "
    "Chỉ trả về JSON có các field: suggested_price (int), range.low (int), range.high (int), explanation (string). "
    "Không thêm văn bản ngoài JSON."
)

# ================== Chuẩn hoá + Cache ==================
def _num(x):
    if x is None: return None
    m = re.search(r"\d+(?:\.\d+)?", str(x))
    return float(m.group(0)) if m else None

def normalize(payload: dict) -> dict:
    p = {
        "product_type": (payload.get("product_type") or "car").strip().lower(),
        "name": (payload.get("name") or "").strip(),
        "brand": (payload.get("brand") or "").strip(),
        "province": (payload.get("province") or "").strip(),
        "year": int(_num(payload.get("year")) or 0) or None,
        "mileage": int(_num(payload.get("mileage")) or 0) or None,
        "battery_capacity_kwh": float(_num(payload.get("battery_capacity_kwh") or payload.get("battery_capacity")) or 0) or None,
        "description": (payload.get("description") or "").strip(),
    }
    return {k: v for k, v in p.items() if v not in (None, "", [])}

def _key(d: dict) -> str:
    s = json.dumps(d, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

_CACHE = {}  # key -> (expire_ts, result_dict)

def cache_get(d: dict):
    it = _CACHE.get(_key(d))
    return it[1] if it and it[0] > time.time() else None

def cache_set(d: dict, result: dict, ttl=CACHE_TTL):
    _CACHE[_key(d)] = (time.time() + ttl, result)

# ================== Baseline fallback (siêu nhanh, thực tế hơn) ==================
def _base_price_from_name(name_l: str) -> int:
    base_table = {
        "vinfast vf e34": 790_000_000,
        "mg zs ev":       650_000_000,
        "byd atto 3":     820_000_000,
        "nissan leaf":    900_000_000,   # mốc tham chiếu cho Leaf
    }
    for k, v in base_table.items():
        if k in name_l:
            return v
    return 700_000_000  # mốc mặc định

def baseline_price(p: dict) -> dict:
    name_l = (p.get("name") or "").lower()
    base = _base_price_from_name(name_l)

    year = p.get("year") or 2022
    mileage = p.get("mileage") or 0
    province = (p.get("province") or "").lower()
    cap = p.get("battery_capacity_kwh") or 0.0

    # Khấu hao năm: 5–10%/năm, sau 5 năm chậm lại ~5%/năm. Trần 60%.
    age = max(0, 2025 - year)
    year_dep = 0.0
    if age <= 5:
        year_dep = 0.08 * age
    else:
        year_dep = 0.08 * 5 + 0.05 * (age - 5)
    year_dep = min(0.60, max(0.0, year_dep))

    # Khấu hao km: 10–15% mỗi 100k km, trần 45%.
    mileage_dep = min(0.45, 0.12 * (mileage / 100_000.0))

    # Điều chỉnh dung lượng pin rất nhẹ (so với 40 kWh làm mốc).
    battery_adj = 1.0
    if cap:
        battery_adj *= (1.0 + min(0.10, max(-0.10, (cap - 40.0) / 400.0)))  # ±10% max

    # Điều chỉnh vùng miền
    region_adj = 1.0
    if "hà nội" in province or "ha noi" in province or "hồ chí minh" in province or "ho chi minh" in province:
        region_adj *= 1.05  # +5%

    # Gộp khấu hao tổng, có trần 75% để tránh rơi xuống “giá sắt vụn”
    total_dep = min(0.75, max(0.0, year_dep + mileage_dep))

    price = int(base * (1 - total_dep) * battery_adj * region_adj)
    low, high = int(price * 0.92), int(price * 1.08)

    return {
        "suggested_price": price,
        "range": {"low": low, "high": high},
        "explanation": (
            "Ước lượng nhanh theo kinh nghiệm: năm 5–10%/năm, mỗi 100k km ~10–15%, "
            "HN/HCM +~5%, có điều chỉnh nhẹ theo dung lượng pin."
        ),
    }

# ================== Prompt builder ==================
def build_user_prompt(payload: dict) -> str:
    f = {
        "product_type": payload.get("product_type", "car"),
        "name": payload.get("name", ""),
        "brand": payload.get("brand", ""),
        "province": payload.get("province", ""),
        "year": payload.get("year", ""),
        "mileage": payload.get("mileage", ""),
        "battery_capacity": payload.get("battery_capacity") or payload.get("battery_capacity_kwh") or "",
        "description": payload.get("description", ""),
    }
    guide = (
        "Nguyên tắc định giá thực tế tại VN:\n"
        "- Mỗi năm giảm khoảng 5–10% giá trị ban đầu (sau 5 năm mức giảm chậm hơn ~5%/năm).\n"
        "- Mỗi 100k km giảm thêm ~10–15%.\n"
        "- Hãng phổ biến giữ giá tốt; HN/HCM nhỉnh hơn khoảng 3–7%.\n"
        "- Xe 5–7 năm, 200–300k km nhưng pin còn ổn vẫn ~40–60% giá ban đầu.\n"
        "- Đưa ra khoảng giá hợp lý (low–high) và giá gợi ý nằm trong khoảng đó."
    )
    reference = (
        "Nếu không có dữ liệu sẵn, lấy xe cùng phân khúc để suy luận. "
        "Ví dụ: Nissan Leaf 2018 giá mới ~900 triệu tại VN (mốc tham chiếu)."
    )
    return (
        f"{guide}\n{reference}\n\n"
        f"INPUT:\n"
        f"- Loại: {f['product_type']}\n"
        f"- Tên: {f['name']}\n"
        f"- Hãng: {f['brand']}\n"
        f"- Năm SX: {f['year']}\n"
        f"- Số km: {f['mileage']}\n"
        f"- Dung lượng pin: {f['battery_capacity']}\n"
        f"- Khu vực: {f['province']}\n"
        f"- Mô tả: {f['description']}\n\n"
        "OUTPUT JSON schema:\n"
        "{\n"
        '  "suggested_price": 0,\n'
        '  "range": {"low": 0, "high": 0},\n'
        '  "explanation": "lý do ngắn gọn (≤2 câu)"\n'
        "}"
    )

def _clean_json_text(txt: str) -> str:
    if not isinstance(txt, str):
        return json.dumps({"suggested_price": 0, "range": {"low": 0, "high": 0}, "explanation": "empty"})
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, flags=re.S)
    if m:
        txt = m.group(1)
    try:
        json.loads(txt)
        return txt
    except Exception:
        return json.dumps({"suggested_price": 0, "range": {"low": 0, "high": 0}, "explanation": txt[:600]})

# ================== Providers ==================
# OpenAI
try:
    from openai import OpenAI as OpenAIClient
    _openai_client = OpenAIClient()
except Exception:
    _openai_client = None

def call_openai(payload: dict) -> str:
    if not _openai_client:
        raise RuntimeError("OpenAI client not initialized")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY")

    user_prompt = build_user_prompt(payload)
    resp = _openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        timeout=HARD_TIMEOUT,
        max_tokens=220
    )
    return resp.choices[0].message.content  # JSON string

# Gemini
try:
    from google import genai
    _gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception:
    _gemini_client = None

def call_gemini(payload: dict) -> str:
    if not _gemini_client:
        raise RuntimeError("Gemini client not initialized")
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("Missing GOOGLE_API_KEY")

    user_prompt = build_user_prompt(payload)
    try:
        try:
            resp = _gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                system_instruction=SYSTEM_PROMPT,
                generation_config={"response_mime_type": "application/json"},
                safety_settings=None,
                timeout=HARD_TIMEOUT,
            )
        except TypeError:
            resp = _gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                system_instruction=SYSTEM_PROMPT,
                safety_settings=None,
                timeout=HARD_TIMEOUT,
            )
    except TypeError:
        resp = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}]}],
            safety_settings=None,
            timeout=HARD_TIMEOUT,
        )

    txt = getattr(resp, "text", None)
    if not txt:
        try:
            txt = resp.candidates[0].content.parts[0].text
        except Exception:
            raise RuntimeError("Empty response from Gemini")

    return _clean_json_text(txt)

# ================== Warm-up (chạy ẩn, không chặn) ==================
def _warmup_once():
    try:
        dummy = {
            "product_type":"car","name":"warmup",
            "year":2022,"mileage":1000,"battery_capacity_kwh":40
        }
        if PROVIDER == "openai":
            _ = call_openai(dummy)
        elif PROVIDER == "gemini":
            _ = call_gemini(dummy)
        else:  # auto → thử cái có key
            if os.getenv("GOOGLE_API_KEY"):
                try: _ = call_gemini(dummy)
                except: pass
            if os.getenv("OPENAI_API_KEY"):
                try: _ = call_openai(dummy)
                except: pass
    except Exception:
        pass

# Flask 3 bỏ before_first_request → tự khởi động thread warmup khi import
threading.Thread(target=_warmup_once, daemon=True).start()

# ================== Health ==================
@app.get("/")
def health():
    keys = {
        "openai": "present" if os.getenv("OPENAI_API_KEY") else "missing",
        "gemini": "present" if os.getenv("GOOGLE_API_KEY") else "missing",
    }
    return jsonify(service="pricing", status="ok", tip="POST /predict",
                   provider=PROVIDER, strict_ai=STRICT_AI, keys=keys), 200

# ================== Predict (race song song + cache + AI-only) ==================
@app.post("/predict")
def predict():
    # 1) parse
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify(error="bad_request", detail="Invalid JSON body"), 400

    p = normalize(data)

    # 2) cache
    cached = cache_get(p)
    if cached:
        return jsonify(cached), 200

    # 3) chọn provider
    tasks = []
    if PROVIDER == "openai":
        tasks = [("openai", call_openai)]
    elif PROVIDER == "gemini":
        tasks = [("gemini", call_gemini)]
    else:  # auto
        if os.getenv("GOOGLE_API_KEY"): tasks.append(("gemini", call_gemini))
        if os.getenv("OPENAI_API_KEY"): tasks.append(("openai", call_openai))
        if not tasks:
            return jsonify(error="no_provider", detail="Missing both OPENAI_API_KEY and GOOGLE_API_KEY"), 500

    # 4) race song song (lấy kết quả đầu tiên trong SOFT_TIMEOUT)
    result, source = None, None
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futures = {ex.submit(fn, p): name for name, fn in tasks}
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=SOFT_TIMEOUT):
                name = futures[fut]
                try:
                    content = fut.result()  # JSON string
                    result = json.loads(content)
                    source = name
                    break
                except Exception:
                    continue
        except concurrent.futures.TimeoutError:
            result = None

    # 5) AI-only: nếu không có kết quả từ AI
    if not result:
        if STRICT_AI:
            return jsonify({
                "error": "ai_timeout",
                "detail": "Không nhận được phản hồi từ nhà cung cấp AI trong thời gian cho phép.",
                "_meta": {"source": "none"}
            }), 504
        # cho phép fallback nếu STRICT_AI=0
        result = baseline_price(p)
        source = "baseline"

    # 6) gắn nguồn, cache & trả
    result["_meta"] = {"source": source or PROVIDER}
    cache_set(p, result, ttl=CACHE_TTL)
    return jsonify(result), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=True)
