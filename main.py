# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from modules.brand_brain import BrandBrain

load_dotenv()

# Danh sách tên model dự phòng mặc định
DEFAULT_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro",
]

def get_available_models(client):
    """Tự động quét và lấy danh sách các model Gemini khả dụng đối với API Key này."""
    try:
        models = []
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            if "gemini" in name.lower():
                models.append(name)
        if models:
            print(f"🔍 Đã tìm thấy {len(models)} model khả dụng cho API Key của bạn: {models[:3]}...")
            return models
    except Exception as e:
        print(f"⚠️ Không thể lấy tự động danh sách model ({e}). Sử dụng danh sách mặc định.")
    
    return DEFAULT_FALLBACK_MODELS

def generate_with_fallback(client, contents: str, system_instruction: str):
    """Tự động duyệt qua danh sách model cho đến khi sinh nội dung thành công."""
    from google.genai import types
    
    models_to_try = get_available_models(client)
    last_exception = None

    for model_name in models_to_try:
        try:
            print(f"🔄 Đang kết nối với Model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction),
            )
            print(f"✅ Thành công với Model: {model_name}\n")
            return response
        except Exception as e:
            print(f"⚠️ Model '{model_name}' chưa phản hồi (Lỗi: {e})")
            print("➡️ Tự động chuyển sang model tiếp theo...\n")
            last_exception = e

    raise RuntimeError(f"❌ Tất cả model đều thất bại. Lỗi cuối cùng: {last_exception}")


def main():
    brain = BrandBrain()
    system_instruction = brain.get_system_context()
    print("✅ Brand Brain đã sẵn sàng. Độ dài System Instruction:", len(system_instruction), "ký tự\n")

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        print("ℹ️ Chưa có GEMINI_API_KEY trong file .env - Vui lòng bổ sung API key.")
        return

    from google import genai
    client = genai.Client(api_key=api_key)

    prompt = "Viết 1 bài Facebook ngắn nhắc học sinh 2k9 chuẩn bị đăng ký thi VACT."
    
    response = generate_with_fallback(client, contents=prompt, system_instruction=system_instruction)

    print("--- BÀI VIẾT TẠO TỪ AGENT ---\n")
    print(response.text)

    violations = brain.check_forbidden(response.text)
    print("\n🔎 Kiểm duyệt từ cấm:", violations if violations else "Không vi phạm (Đạt chuẩn)")


if __name__ == "__main__":
    main()