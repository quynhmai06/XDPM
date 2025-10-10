from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

# ====== OpenAI client ======
# Yêu cầu: export OPENAI_API_KEY=...
client = OpenAI(
    # Nếu bạn cần chỉ định org/project, bỏ comment 2 dòng dưới (tuỳ tài khoản bạn có nhiều org/project):
    # organization=os.getenv("OPENAI_ORG"),
    # project=os.getenv("OPENAI_PROJECT"),
)

SYSTEM_PROMPT = (
    "Bạn là trợ lý định giá chợ đồ xe điện cũ VN. "
    "Hãy ước lượng giá VNĐ hợp lý dựa trên thông tin sản phẩm (xe/pin), "
    "bối cảnh thị trường chung (giả định), khấu hao theo năm, số km, dung lượng pin, khu vực. "
    "Chỉ trả về JSON có các field: suggested_price (int), range.low (int), range.high (int), explanation (string). "
    "Không thêm văn bản ngoài JSON."
)

def build_user_prompt(payload: dict) -> str:
    # Gom dữ liệu người bán nhập
    fields = {
        "product_type": payload.get("product_type", "car"),
        "name": payload.get("name", ""),
        "brand": payload.get("brand", ""),
        "province": payload.get("province", ""),
        "year": payload.get("year", ""),
        "mileage": payload.get("mileage", ""),
        "battery_capacity": payload.get("battery_capacity", ""),
        "description": payload.get("description", ""),
    }
    # Prompt gợi ý: có baseline + rule, nhưng để model “lý giải” ra con số và biên độ
    guide = (
        "Dựa trên quy tắc kinh nghiệm:\n"
        "- Xe: mỗi năm ±(1–3)%, số km làm giảm giá dần (vd 100k km giảm ~30–40%).\n"
        "- Hãng phổ biến (VinFast, Tesla, Hyundai, Kia, MG, etc.) có thanh khoản tốt.\n"
        "- Khu vực HN/HCM nhỉnh hơn ~1–5%.\n"
        "- Dung lượng pin lớn hơn, tình trạng tốt thì giá tốt hơn.\n"
        "Hãy cân đối và cho ra giá hợp lý hiện tại."
    )
    # Mô tả input rõ ràng để model trả JSON đúng
    return (
        f"{guide}\n\n"
        f"INPUT:\n"
        f"- Loại: {fields['product_type']}\n"
        f"- Tên: {fields['name']}\n"
        f"- Hãng: {fields['brand']}\n"
        f"- Năm SX: {fields['year']}\n"
        f"- Số km: {fields['mileage']}\n"
        f"- Dung lượng pin: {fields['battery_capacity']}\n"
        f"- Khu vực: {fields['province']}\n"
        f"- Mô tả: {fields['description']}\n\n"
        "OUTPUT JSON schema:\n"
        "{\n"
        '  "suggested_price": 0,\n'
        '  "range": {"low": 0, "high": 0},\n'
        '  "explanation": "lý do ngắn gọn"\n'
        "}"
    )

def call_openai_price(payload: dict) -> dict:
    user_prompt = build_user_prompt(payload)

    # Bạn có thể dùng model mới như "gpt-4o" hoặc model bạn được cấp.
    # Nên set temperature thấp để kết quả ổn định hơn.
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content
    # Trả về JSON string → Flask route sẽ return thẳng
    return content

@app.get("/")
def health():
    return jsonify(service="pricing", status="ok", tip="POST /predict"), 200

@app.post("/predict")
def predict():
    data = request.get_json(force=True)
    try:
        content = call_openai_price(data)
        # content là JSON string từ model, trả nguyên xi:
        return app.response_class(content, status=200, mimetype="application/json")
    except Exception as e:
        # Không log key; chỉ log lỗi chung
        return jsonify(error="pricing-ai-failed", detail=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5003)), debug=True)
