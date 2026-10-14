# -*- coding: utf-8 -*-
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from modules.brand_brain import BrandBrain

DEFAULT_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

def get_available_models(client):
    try:
        models = []
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            if "gemini" in name.lower() and "embed" not in name.lower():
                models.append(name)
        if models:
            return models
    except Exception as e:
        print(f"⚠️ Không thể lấy danh sách model tự động ({e}). Dùng danh sách mặc định.")
    return DEFAULT_FALLBACK_MODELS


class WriterAgent:
    def __init__(self, api_key: str = None):
        self.brain = BrandBrain()
        
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            try:
                import streamlit as st
                if "GEMINI_API_KEY" in st.secrets:
                    self.api_key = st.secrets["GEMINI_API_KEY"]
            except Exception:
                pass

        if not self.api_key:
            raise ValueError("❌ Không tìm thấy GEMINI_API_KEY cho Writer Agent!")

        self.client = genai.Client(api_key=self.api_key)

    def _get_latest_material(self) -> dict:
        """Đọc bộ tài liệu mới nhất từ kho MaterialAgent."""
        if os.path.exists("knowledge_base/materials_index.json"):
            try:
                with open("knowledge_base/materials_index.json", "r", encoding="utf-8") as f:
                    materials = json.load(f)
                    if materials:
                        return materials[-1]
            except Exception:
                pass
        return {
            "title": "TRỌN BỘ CẤU TRÚC TIẾNG ANH & BÀI TẬP VACT 2K9",
            "cta_keyword": "Cấu trúc tiếng anh",
            "source_url": "https://drive.google.com/file/d/1vActEnglish2026_SampleDoc/view",
            "sample_content": "Tom's work as a college admissions officer, who is part-time, brings him some social skills."
        }

    def write_single_post(self, post_info: dict) -> dict:
        channel = post_info.get("channel", "Facebook")
        format_type = post_info.get("format_type", "FB_LEAD_GEN")
        angle = post_info.get("angle", "")
        hook_idea = post_info.get("hook_idea", "")
        cta = post_info.get("cta", "")

        # Đã sửa thêm self vào đây
        material = self._get_latest_material()
        system_instruction = self.brain.get_system_context()

        if "TikTok" in channel or format_type == "TIKTOK":
            format_req = """
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Kịch bản TikTok):
🎬 [3S HOOK ĐẦU]: Câu nói/cảnh quay cực giật gân, xoáy sâu vào tâm lý 2k9 thi VACT.
🎥 [VISUAL NOTES]: Gợi ý chi tiết góc quay, hình ảnh đính kèm.
🎙️ [AUDIO DIALOGUE]: Lời thoại dồn dập, tự nhiên chuẩn giọng 'Chị đại'.
🎯 [CTA]: Lời kêu gọi ngắn gọn thúc đẩy bình luận/inbox.
"""
        elif format_type == "FB_LEAD_GEN" or "Tặng Tài liệu" in angle or "Dạng 1" in angle:
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 1 - Tặng Tài Liệu Lead Gen):
📌 [TIÊU ĐỀ]: In hoa, giật gân, dùng emoji gây chú ý về bộ tài liệu: '{material.get("title")}'.
💎 [TÓM TẮT GIÁ TRỊ]: 3-4 dòng bullet points nêu rõ tài liệu giúp ích gì cho sĩ tử 2k9.
👇 [CÔNG THỨC 3 BƯỚC NHẬN TÀI LIỆU]:
   - Bước 1: Thả tim bài viết
   - Bước 2: Share bài viết
   - Bước 3: Comment từ khóa '{material.get("cta_keyword")}'
🔗 [NỘI DUNG TÀI LIỆU GỐC]: Đính kèm thông tin tham khảo nguồn {material.get("source_url")}.
"""
        elif format_type == "FB_QUIZ" or "Quiz" in angle or "Dạng 2" in angle:
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 2 - Quiz Tương Tác Thả Icon):
❓ [ĐỀ BÀI/CÂU HỎI]: Trích xuất hoặc biên soạn 1 câu hỏi/lỗi sai ngắn gọn từ tài liệu: '{material.get("sample_content")}'.
🎯 [4 ĐÁP ÁN GẮN ICON REACTION]:
   😆 A. [Đáp án A]
   👍 B. [Đáp án B]
   ❤️ C. [Đáp án C]
   😲 D. [Đáp án D]
💬 [CTA]: Thúc đẩy học sinh thả cảm xúc tương ứng để chọn đáp án đúng.
"""
        else:
            format_req = """
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 3 - Text-Overlay Video):
📝 [VĂN BẢN CHÈN VIDEO DỌC]:
- Viết thành các dòng ngắn gọn dạng đạn (bullet points), thoáng mắt.
- Dùng emoji sinh động (🧠, 💡, ⚡, 🎯) ở đầu mỗi dòng.
- Không viết lời chào hay văn xuôi dài, đảm bảo ngắt dòng chuẩn để chèn vừa màn hình TikTok/Reels.
"""

        prompt = f"""
Bạn là Agent Writer (Chị Đại VACT Giga HCM).
Hãy viết bài dựa trên thông tin sau:
- Nền tảng: {channel}
- Angle: {angle}
- Gợi ý Hook: {hook_idea}
- Target CTA: {cta}

{format_req}
"""

        models_to_try = get_available_models(self.client)
        response = None
        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7
                    ),
                )
                break
            except Exception as e:
                print(f"⚠️ Model {model_name} bận, thử model tiếp theo...")

        if not response:
            raise RuntimeError("❌ Tất cả model đều thất bại khi tạo nội dung bài viết.")

        return {
            "id": post_info.get("id"),
            "day": post_info.get("day", "Thứ 2"),
            "channel": channel,
            "format_type": format_type,
            "angle": angle,
            "content": response.text.strip(),
            "source_url": material.get("source_url") if (format_type == "FB_LEAD_GEN" or "Dạng 1" in angle) else "",
            "status": "Drafted"
        }

    def generate_all_drafts(self, plan_data: dict) -> dict:
        posts = plan_data.get("posts", [])
        drafted_posts = []

        for p in posts:
            draft = self.write_single_post(p)
            drafted_posts.append(draft)

        result_data = {
            "plan_topic": plan_data.get("week_topic", ""),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "drafts": drafted_posts
        }

        os.makedirs("data", exist_ok=True)
        file_path = f"data/weekly_drafts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        return result_data