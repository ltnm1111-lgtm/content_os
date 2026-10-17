# -*- coding: utf-8 -*-
import json
import os
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
                if "GEMINI_API_KEY" in st.secrets:
                    self.api_key = st.secrets["GEMINI_API_KEY"]
            except Exception:
                pass
        self.client = genai.Client(api_key=self.api_key)

    def generate_weekly_plan(self, week_topic: str) -> dict:
        system_instruction = self.brain.get_system_context()
        
        prompt = f"""
Bạn là Agent Planner (Trưởng phòng Nội dung) của VACT Giga HCM.
Nhiệm vụ: Lên kế hoạch nội dung HOÀN CHỈNH CHO CẢ TUẦN (Từ Thứ 2 đến Chủ Nhật - ĐÚNG 7 BÀI) với chủ đề: "{week_topic}".

BẮT BUỘC RẢI ĐỀU 4 ĐỊNH DẠNG SAU TRONG 7 NGÀY:
1. "FB_LEAD_GEN": Facebook Dạng 1 - Tặng tài liệu PDF/Drive.
2. "FB_QUIZ": Facebook Dạng 2 - Quiz tương tác 4 Icon.
3. "FB_TEXT_OVERLAY": Facebook Dạng 3 - Chữ đè lên video TikTok/Reels.
4. "TIKTOK": Kịch bản quay video TikTok.

Yêu cầu đầu ra BẮT BUỘC là file JSON thuần túy (không bọc markdown ```json):
{{
  "week_topic": "{week_topic}",
  "created_at": "YYYY-MM-DD",
  "posts": [
    {{
      "id": 1,
      "day": "Thứ 2",
      "channel": "Facebook",
      "format_type": "FB_LEAD_GEN",
      "angle": "Tặng tài liệu Tiếng Anh VACT",
      "hook_idea": "Giật tít tặng tài liệu hiếm...",
      "cta": "Comment 'VACT' để nhận link"
    }},
    {{
      "id": 2,
      "day": "Thứ 3",
      "channel": "TikTok",
      "format_type": "TIKTOK",
      "angle": "...",
      "hook_idea": "...",
      "cta": "..."
    }}
    // BẮT BUỘC LIỆT KÊ TIẾP TỪ THỨ 4 ĐẾN CHỦ NHẬT (ID TỪ 3 ĐẾN 7). TỔNG CỘNG 7 BÀI!
  ]
}}
"""
        models_to_try = get_available_models(self.client)
        response = None
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
                )
                break
            except Exception:
                pass

        if not response:
            raise RuntimeError("Lỗi sinh kế hoạch.")
            
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)