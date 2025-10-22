# pricing-service/app.py
from flask import Flask, request, jsonify
import os, json, re

PROVIDER = os.getenv("PROVIDER", "openai").strip().lower()

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # tiếng Việt không bị escape

# ===== OpenAI (fallback) =====
from openai import OpenAI as OpenAIClient
openai_client = OpenAIClient()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ===== Gemini (mặc định) =====
try:
    from google import genai
    gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception:
    gemini_client = None

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = (
    "Bạn là trợ lý định giá chợ đồ xe điện cũ VN. "
    "Hãy ước lượng giá VNĐ hợp lý dựa trên thông tin sản phẩm (xe/pin), "
    "bối cảnh thị trường chung (giả định), khấu hao theo năm, số km, dung lượng pin, khu vực. "
    "Chỉ trả về JSON có các field: suggested_price (int), range.low (int), range.high (int), explanation (string). "
    "Không thêm văn bản ngoài JSON."
)

def build_user_prompt(payload: dict) -> str:
    f = {
        "product_type": payload.get("product_type", "car"),
        "name": payload.get("name", ""),
        "brand": payload.get("brand", ""),
        "province": payload.get("province", ""),
        "year": payload.get("year", ""),
        "mileage": payload.get("mileage", ""),
        "battery_capacity": payload.get("battery_capacity", ""),
        "description": payload.get("description", ""),
    }
    guide = (
        "Dựa trên quy tắc kinh nghiệm:\n"
        "- Xe: mỗi năm ±(1–3)%, số km làm giảm giá dần (vd 100k km giảm ~30–40%).\n"
        "- Hãng phổ biến (VinFast, Tesla, Hyundai, Kia, MG, etc.) có thanh khoản tốt.\n"
        "- Khu vực HN/HCM nhỉnh hơn ~1–5%.\n"
        "- Dung lượng pin lớn hơn, tình trạng tốt thì giá tốt hơn.\n"
        "Hãy cân đối và cho ra giá hợp lý hiện tại."
    )
    return (
        f"{guide}\n\n"
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
        '  "explanation": "lý do ngắn gọn"\n'
        "}"
    )

def _clean_json_text(txt: str) -> str:
    """Bóc JSON nếu bị bọc trong ```json ... ``` hoặc có text thừa."""
    if not isinstance(txt, str):
        return json.dumps({"suggested_price": 0, "range": {"low": 0, "high": 0}, "explanation": "empty"})
    # gỡ code-fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, flags=re.S)
    if m:
        txt = m.group(1)
    # thử parse, nếu fail thì gói vào explanation
    try:
        json.loads(txt)
        return txt
    except Exception:
        return json.dumps({"suggested_price": 0, "range": {"low": 0, "high": 0}, "explanation": txt[:600]})

def call_openai(payload: dict) -> str:
    user_prompt = build_user_prompt(payload)
    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content  # JSON string chuẩn

def call_gemini(payload: dict) -> str:
    if not gemini_client:
        raise RuntimeError("Gemini client not initialized")
    user_prompt = build_user_prompt(payload)

    # 1) Thử API mới có system_instruction + generation_config
    try:
        try:
            resp = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                system_instruction=SYSTEM_PROMPT,
                generation_config={"response_mime_type": "application/json"},
            )
        except TypeError:
            # 2) SDK không nhận generation_config
            resp = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                system_instruction=SYSTEM_PROMPT,
            )
    except TypeError:
        # 3) SDK rất cũ: không có system_instruction → nhét system + prompt vào user
        resp = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}]}],
        )

    # Lấy text
    txt = getattr(resp, "text", None)
    if not txt:
        try:
            txt = resp.candidates[0].content.parts[0].text
        except Exception:
            raise RuntimeError("Empty response from Gemini")

    return _clean_json_text(txt)

@app.get("/")
def health():
    keys = {
        "openai": "present" if os.getenv("OPENAI_API_KEY") else "missing",
        "gemini": "present" if os.getenv("GOOGLE_API_KEY") else "missing",
    }
    return jsonify(service="pricing", status="ok", tip="POST /predict",
                   provider=PROVIDER, keys=keys), 200

@app.post("/predict")
def predict():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify(error="bad_request", detail="Invalid JSON body"), 400
    try:
        if PROVIDER == "gemini":
            content = call_gemini(data)
        else:
            content = call_openai(data)
        return app.response_class(content, status=200, mimetype="application/json")
    except Exception as e:
        return jsonify(error="pricing-ai-failed", detail=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5003)), debug=True)
