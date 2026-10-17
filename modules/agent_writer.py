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

        # NHẬN DIỆN CHÍNH XÁC BÀI DẠNG 1
        is_fb_lead_gen = (format_type == "FB_LEAD_GEN" or "Dạng 1" in angle)

        material = self._get_latest_material() if is_fb_lead_gen else {}
        system_instruction = self.brain.get_system_context()

        if "TikTok" in channel or format_type == "TIKTOK":
            format_req = """
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Kịch bản TikTok):
🎬 [3S HOOK ĐẦU]: Câu nói/cảnh quay cực giật gân.
🎥 [VISUAL NOTES]: Gợi ý chi tiết góc quay, hình ảnh đính kèm.
🎙️ [AUDIO DIALOGUE]: Lời thoại dồn dập, tự nhiên chuẩn giọng 'Chị đại'.
🎯 [CTA]: Lời kêu gọi ngắn gọn.
"""
        elif is_fb_lead_gen:
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 1 - Tặng Tài Liệu Lead Gen):
📌 [TIÊU ĐỀ]: In hoa, giật gân về tài liệu: '{material.get("title", "TÀI LIỆU VACT")}'.
💎 [TÓM TẮT GIÁ TRỊ]: 3-4 dòng bullet points.
👇 [CÔNG THỨC 3 BƯỚC NHẬN TÀI LIỆU]: Thả tim -> Share -> Comment từ khóa '{material.get("cta_keyword", "VACT")}'
"""
        elif format_type == "FB_QUIZ" or "Dạng 2" in angle:
            format_req = """
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 2 - Quiz Tương Tác Thả Icon):
❓ [ĐỀ BÀI/CÂU HỎI]: Biên soạn 1 câu hỏi trắc nghiệm/lỗi sai.
🎯 [4 ĐÁP ÁN GẮN ICON REACTION]: 😆 A. | 👍 B. | ❤️ C. | 😲 D.
💬 [CTA]: Thúc đẩy học sinh thả icon.
"""
        else:
            format_req = """
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 3 - Text-Overlay Video):
📝 [VĂN BẢN CHÈN VIDEO DỌC]: Viết thành các dòng ngắn gọn (bullet points), ngắt dòng chuẩn, emoji sinh động (không chào hỏi, không viết văn xuôi).
"""

        prompt = f"""Bạn là Agent Writer. Viết bài với thông tin:
- Nền tảng: {channel} | Angle: {angle} | Hook: {hook_idea} | CTA: {cta}
{format_req}"""

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

# ĐẢM BẢO CHỈ TRẢ VỀ URL KHI ĐÚNG DẠNG 1
        return {
            "id": post_info.get("id"),
            "day": post_info.get("day", "Thứ 2"),
            "channel": channel,
            "format_type": format_type,
            "angle": angle,
            "content": response.text.strip(),
            "source_url": material.get("source_url", "") if is_fb_lead_gen else "",
            "status": "Drafted"
        }