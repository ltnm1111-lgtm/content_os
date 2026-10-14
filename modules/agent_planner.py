# -*- coding: utf-8 -*-
import json
import os
import sys
from datetime import datetime

# Tự động thêm thư mục gốc dự án (content_os) vào Python path để tránh lỗi Import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
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

def search_vact_news(query: str) -> str:
    """Tìm kiếm tin tức, lịch thi, thông báo mới nhất về kỳ thi ĐGNL/VACT."""
    try:
        results = list(DDGS().text(query, max_results=3))
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi tìm kiếm: {str(e)}"

def get_available_models(client):
    """Tự động quét danh sách model khả dụng từ API Key của bạn."""
    try:
        models = []
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            if "gemini" in name.lower():
                models.append(name)
        if models:
            return models
    except Exception as e:
        print(f"⚠️ Không thể lấy tự động danh sách model ({e}). Sử dụng danh sách mặc định.")
    
    return DEFAULT_FALLBACK_MODELS

def generate_with_fallback(client, contents: str, system_instruction: str, temperature: float = 0.3):
    """Tự động duyệt qua từng model khả dụng cho đến khi tạo nội dung thành công."""
    models_to_try = get_available_models(client)
    last_exception = None

    for model_name in models_to_try:
        try:
            print(f"🔄 Agent Planner đang thử Model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature
                ),
            )
            print(f"✅ Thành công với Model: {model_name}\n")
            return response
        except Exception as e:
            print(f"⚠️ Model '{model_name}' chưa phản hồi ({e}). Tự chuyển model tiếp theo...")
            last_exception = e

    raise RuntimeError(f"❌ Tất cả model đều thất bại. Lỗi cuối cùng: {last_exception}")


class PlannerAgent:
    def __init__(self):
        self.brain = BrandBrain()
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.client = genai.Client(api_key=self.api_key)

    def generate_weekly_plan(self, week_topic: str = "Tập trung kiến thức trọng tâm & tâm lý thi VACT 2k9") -> dict:
        """Agent phân tích chủ đề tuần và xuất kế hoạch 5-7 bài viết chuẩn định dạng JSON."""
        
        # 1. Thu thập tin tức thời gian thực bằng Tool
        print(f"🔍 Agent 1 (Research) đang tìm tin tức liên quan đến: '{week_topic}'...")
        search_data = search_vact_news("lịch thi đánh giá năng lực ĐHQG TPHCM VACT mới nhất")

        # 2. Xây dựng Prompt cho Agent Planner
        system_instruction = self.brain.get_system_context()
        
        prompt = f"""
Bạn là Agent 2 (Content Planner) của VACT Giga HCM.
Dựa vào dữ liệu nghiên cứu thị trường:
{search_data}

Hãy lập kế hoạch Content 5 bài đăng cho tuần tới với chủ đề chủ đạo: "{week_topic}".

Yêu cầu đầu ra BẮT BUỘC trả về định dạng JSON thuần túy (không chứa markdown ```json):
{{
  "week_topic": "{week_topic}",
  "created_at": "{datetime.now().strftime('%Y-%m-%d')}",
  "posts": [
    {{
      "id": 1,
      "day": "Thứ 2",
      "channel": "Facebook / TikTok",
      "angle": "Góc nhìn/chủ đề bài viết",
      "hook_idea": "Idea câu Hook thu hút học sinh 2k9",
      "cta": "Lời kêu gọi hành động",
      "status": "Pending"
    }}
  ]
}}
"""

        print("🤖 Agent 2 (Planner) đang tính toán và xây dựng kế hoạch tuần...")
        
        # 3. Gọi sinh nội dung bằng cơ chế Fallback tự động
        response = generate_with_fallback(
            client=self.client,
            contents=prompt,
            system_instruction=system_instruction,
            temperature=0.3
        )

        # 4. Xử lý & Làm sạch JSON trả về
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        plan_data = json.loads(clean_text)

        # 5. Lưu kế hoạch ra file JSON local
        os.makedirs("data", exist_ok=True)
        file_path = f"data/weekly_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu Lịch Content Tuần vào file: {file_path}")
        return plan_data


if __name__ == "__main__":
    planner = PlannerAgent()
    plan = planner.generate_weekly_plan()
    print("\n--- BẢNG KẾ HOẠCH CONTENT TUẦN (JSON) ---")
    print(json.dumps(plan, ensure_ascii=False, indent=2))