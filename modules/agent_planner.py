# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from google import genai
from google.genai import types
from modules.brand_brain import BrandBrain

DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

def get_available_models(client):
    try:
        models = [m.name.replace("models/", "") if hasattr(m, "name") else str(m) for m in client.models.list() if "gemini" in m.name.lower()]
        return models if models else DEFAULT_FALLBACK_MODELS
    except Exception:
        return DEFAULT_FALLBACK_MODELS

class PlannerAgent:
    def __init__(self, api_key: str = None):
        self.brain = BrandBrain()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            try:
                import streamlit as st
                if "GEMINI_API_KEY" in st.secrets: self.api_key = st.secrets["GEMINI_API_KEY"]
            except Exception: pass
        self.client = genai.Client(api_key=self.api_key)

    def generate_weekly_plan(self, week_topic: str) -> dict:
        system_instruction = self.brain.get_system_context()
        
        prompt = f"""
Bạn là Agent Planner (Trưởng phòng Nội dung VACT Giga HCM).
Nhiệm vụ: Lập Kế hoạch Lịch Đăng Bài FULL 7 NGÀY TUẦN (Thứ 2 đến Chủ Nhật - Đúng 7 bài) cho chủ đề: "{week_topic}".

QUY TẮC BẮT BUỘC VỀ NỀN TẢNG & ĐỊNH DẠNG:
1. Phải trải đều đủ cả 4 định dạng trong tuần:
   - "FB_LEAD_GEN" (Facebook Dạng 1: Tặng tài liệu)
   - "FB_QUIZ" (Facebook Dạng 2: Quiz Tương tác)
   - "FB_TEXT_OVERLAY" (Facebook Dạng 3: Video chữ đè màn hình)
   - "TIKTOK" (Video TikTok Script)
2. Đối với bài "FB_LEAD_GEN" và "FB_QUIZ": BẮT BUỘC chỉ định rõ MÔN HỌC ("subject": "Toán Logic", "Tiếng Anh VACT", "Ngữ văn ĐGNL",...).
3. Đối với bài "FB_TEXT_OVERLAY" và "TIKTOK": Chỉ định rõ góc nhìn Trend/Tâm lý sĩ tử.

Trả về JSON thuần (không chứa markdown ```json):
{{
  "week_topic": "{week_topic}",
  "created_at": "{datetime.now().strftime('%Y-%m-%d')}",
  "posts": [
    {{"id": 1, "day": "Thứ 2", "channel": "Facebook", "format_type": "FB_LEAD_GEN", "subject": "Tiếng Anh VACT", "angle": "Tặng bộ cấu trúc ăn điểm", "hook_idea": "...", "cta": "..."}},
    {{"id": 2, "day": "Thứ 3", "channel": "Facebook", "format_type": "FB_QUIZ", "subject": "Toán Logic VACT", "angle": "Bẫy đề thi hay gặp", "hook_idea": "...", "cta": "..."}},
    {{"id": 3, "day": "Thứ 4", "channel": "TikTok", "format_type": "TIKTOK", "subject": "", "angle": "Tâm lý trì hoãn ôn thi", "hook_idea": "...", "cta": "..."}},
    {{"id": 4, "day": "Thứ 5", "channel": "Facebook", "format_type": "FB_TEXT_OVERLAY", "subject": "", "angle": "Chiến thuật làm bài 150 phút", "hook_idea": "...", "cta": "..."}},
    {{"id": 5, "day": "Thứ 6", "channel": "Facebook", "format_type": "FB_LEAD_GEN", "subject": "Toán Logic VACT", "angle": "Công thức giải nhanh", "hook_idea": "...", "cta": "..."}},
    {{"id": 6, "day": "Thứ 7", "channel": "Facebook", "format_type": "FB_QUIZ", "subject": "Tiếng Anh VACT", "angle": "Thử thách câu khó", "hook_idea": "...", "cta": "..."}},
    {{"id": 7, "day": "Chủ Nhật", "channel": "TikTok", "format_type": "TIKTOK", "subject": "", "angle": "Review lịch ôn tuần tới", "hook_idea": "...", "cta": "..."}}
  ]
}}
"""
        models_to_try = get_available_models(self.client)
        response = None
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
                )
                break
            except Exception: pass

        if not response: raise RuntimeError("Lỗi tạo kế hoạch.")
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)