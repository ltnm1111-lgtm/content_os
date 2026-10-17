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

DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

def get_available_models(client):
    try:
        models = [m.name.replace("models/", "") if hasattr(m, "name") else str(m) for m in client.models.list() if "gemini" in m.name.lower()]
        return models if models else DEFAULT_FALLBACK_MODELS
    except Exception: return DEFAULT_FALLBACK_MODELS

class WriterAgent:
    def __init__(self, api_key: str = None):
        self.brain = BrandBrain()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            try:
                import streamlit as st
                if "GEMINI_API_KEY" in st.secrets: self.api_key = st.secrets["GEMINI_API_KEY"]
            except Exception: pass
        self.client = genai.Client(api_key=self.api_key)

    def _get_matching_material(self, subject: str = "") -> dict:
        """Đọc kho tài liệu để lấy bộ tài liệu khớp với môn học được giao."""
        if os.path.exists("knowledge_base/materials_index.json"):
            try:
                with open("knowledge_base/materials_index.json", "r", encoding="utf-8") as f:
                    materials = json.load(f)
                    if materials:
                        if subject:
                            for mat in reversed(materials):
                                if subject.lower() in mat.get("subject", "").lower() or subject.lower() in mat.get("title", "").lower():
                                    return mat
                        return materials[-1]
            except Exception: pass
        return {
            "title": "TRỌN BỘ CẤU TRÚC TIẾNG ANH & BÀI TẬP VACT 2K9",
            "cta_keyword": "Cấu trúc tiếng anh",
            "source_url": "[https://drive.google.com/file/d/1vActEnglish2026_SampleDoc/view](https://drive.google.com/file/d/1vActEnglish2026_SampleDoc/view)",
            "sample_content": "Cấu trúc 1: S + would rather + V-bare... Ví dụ: She would rather study VACT."
        }

    def write_single_post(self, post_info: dict) -> dict:
        channel = post_info.get("channel", "Facebook")
        format_type = post_info.get("format_type", "FB_LEAD_GEN")
        angle = post_info.get("angle", "")
        subject = post_info.get("subject", "")
        hook_idea = post_info.get("hook_idea", "")
        cta = post_info.get("cta", "")

        material = self._get_matching_material(subject)
        system_instruction = self.brain.get_system_context()

        # DẠNG 1: FB LEAD GEN (GẮN LINK URL & VIẾT CAPTION TỪ TÊN TÀI LIỆU THẬT)
        if format_type == "FB_LEAD_GEN":
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 1 - Tặng Tài Liệu Lead Gen):
📌 [TIÊU ĐỀ]: In hoa, dựa trên ĐÚNG tên tài liệu thật: '{material.get("title")}'.
💎 [TÓM TẮT GIÁ TRỊ]: 3-4 dòng bullet points tóm tắt giá trị bộ tài liệu.
👇 [CÔNG THỨC 3 BƯỚC NHẬN TÀI LIỆU]:
   - Bước 1: Thả tim bài viết
   - Bước 2: Share bài viết
   - Bước 3: Comment từ khóa '{material.get("cta_keyword")}'
"""
        # DẠNG 2: FB QUIZ (TRÍCH 1 CÂU TỪ TÀI LIỆU LÀM ĐỀ - TUYỆT ĐỐI KHÔNG GẮN URL)
        elif format_type == "FB_QUIZ":
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 2 - Quiz Tương Tác Thả Icon):
❓ [ĐỀ BÀI/CÂU HỎI]: Trích xuất hoặc dựa vào nội dung mẫu từ tài liệu thật sau: '{material.get("sample_content")}' để tạo 1 câu hỏi/lỗi sai thực chiến.
🎯 [4 ĐÁP ÁN GẮN ICON REACTION]:
   😆 A. [Đáp án A]
   👍 B. [Đáp án B]
   ❤️ C. [Đáp án C]
   😲 D. [Đáp án D]
💬 [CTA]: Thúc đẩy học sinh thả cảm xúc tương ứng để chọn đáp án.
(LƯU Ý: KHÔNG đính kèm bất kỳ link URL nào vào bài này).
"""
        # DẠNG 3: FB TEXT OVERLAY (DỰA TRÊN TREND ĐỐI THỦ)
        elif format_type == "FB_TEXT_OVERLAY":
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Facebook Dạng 3 - Text-Overlay Video Dọc):
📝 [VĂN BẢN CHÈN VIDEO DỌC]:
- Viết ngắn gọn dạng bullet points, ngắt dòng thoáng mắt, emoji sinh động.
- Tập trung vào Angle tâm lý/chiến thuật: '{angle}'.
"""
        # DẠNG 4: TIKTOK SCRIPT (DỰA TRÊN TREND ĐỐI THỦ)
        else:
            format_req = f"""
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (Kịch bản TikTok Video):
🎬 [3S HOOK ĐẦU]: Câu nói/cảnh quay giật gân xoáy vào góc nhìn: '{angle}'.
🎥 [VISUAL NOTES]: Gợi ý chi tiết góc quay/hình ảnh.
🎙️ [AUDIO DIALOGUE]: Lời thoại dồn dập, tự nhiên chuẩn giọng 'Chị đại'.
🎯 [CTA]: Lời kêu gọi ngắn gọn.
"""

        prompt = f"""Bạn là Agent Writer (Chị Đại VACT). Hãy viết bài với thông tin:
- Nền tảng: {channel} | Môn: {subject} | Angle: {angle} | Hook: {hook_idea} | CTA: {cta}
{format_req}"""

        models_to_try = get_available_models(self.client)
        response = None
        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7)
                )
                break
            except Exception: pass

        if not response: raise RuntimeError("Lỗi khi tạo bài viết.")

        # CHỈ TRẢ VỀ URL KHI ĐÚNG DẠNG 1 (FB_LEAD_GEN)
        return {
            "id": post_info.get("id"),
            "day": post_info.get("day", "Thứ 2"),
            "channel": channel,
            "format_type": format_type,
            "subject": subject,
            "angle": angle,
            "content": response.text.strip(),
            "source_url": material.get("source_url", "") if format_type == "FB_LEAD_GEN" else "",
            "status": "Drafted"
        }

    def generate_all_drafts(self, plan_data: dict) -> dict:
        posts = plan_data.get("posts", [])
        drafted_posts = [self.write_single_post(p) for p in posts]

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