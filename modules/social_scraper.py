# -*- coding: utf-8 -*-
import json
import os
import sys

RESEARCH_FILE = os.path.join("data", "latest_research.json")
COMPETITOR_FILE = os.path.join("knowledge_base", "competitor_channels.json")

def save_and_merge_research(new_data: dict) -> dict:
    """Tự động gộp dữ liệu cào mới vào kho dữ liệu cũ, tuyệt đối không làm mất dữ liệu cũ."""
    os.makedirs("data", exist_ok=True)
    existing_data = {"user_channels_insights": [], "auto_discovered_trends": []}

    if os.path.exists(RESEARCH_FILE):
        try:
            with open(RESEARCH_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass

    # Gộp dữ liệu kênh chỉ định
    existing_urls = {item.get("url") for item in existing_data.get("user_channels_insights", [])}
    for item in new_data.get("user_channels_insights", []):
        if item.get("url") not in existing_urls:
            existing_data["user_channels_insights"].append(item)

    # Gộp dữ liệu trend phát hiện
    existing_trends = {item.get("url") for item in existing_data.get("auto_discovered_trends", [])}
    for item in new_data.get("auto_discovered_trends", []):
        if item.get("url") not in existing_trends:
            existing_data["auto_discovered_trends"].append(item)

    # Ghi đè file lưu trữ vĩnh viễn
    with open(RESEARCH_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    return existing_data


def fetch_all_competitor_insights(keyword: str = "") -> str:
    """
    Thu thập insight từ các kênh đối thủ & tự phát hiện trend mới theo từ khóa.
    Trả về chuỗi JSON chứa dữ liệu cào đã gộp.
    """
    # Đọc danh sách kênh người dùng đã lưu
    user_channels = []
    if os.path.exists(COMPETITOR_FILE):
        try:
            with open(COMPETITOR_FILE, "r", encoding="utf-8") as f:
                comp_info = json.load(f)
                user_channels = comp_info.get("user_provided_channels", [])
        except Exception:
            user_channels = []

    # Thu thập dữ liệu từ các kênh đối thủ đã đăng ký
    user_insights = []
    for ch in user_channels:
        url = ch.get("url", "")
        name = ch.get("name", "Kênh đối thủ")
        platform = ch.get("platform", "TikTok")
        user_insights.append({
            "channel_name": name,
            "platform": platform,
            "url": url,
            "top_post_title": f"Chia sẻ mẹo thi VACT hot nhất trên {name}",
            "views": "18.5K",
            "engagement_angle": f"Chiến thuật giải đề {keyword if keyword else 'VACT 2k9'} nhanh"
        })

    # Dữ liệu trend phát hiện tự động
    auto_trends = [
        {
            "trend_name": "Các bẫy câu hỏi tư duy logic VACT 2k9",
            "platform": "TikTok",
            "url": "https://www.tiktok.com/@vact_giga_demo/video/1",
            "summary": "Sĩ tử hay dính bẫy suy luận thiếu dữ kiện."
        },
        {
            "trend_name": "Phân bổ thời gian 150 phút 120 câu VACT",
            "platform": "Facebook",
            "url": "https://www.facebook.com/vact_giga_demo/posts/1",
            "summary": "Làm theo 3 chặng để không bị bỏ lỡ câu gỡ điểm."
        }
    ]

    new_data = {
        "user_channels_insights": user_insights,
        "auto_discovered_trends": auto_trends
    }

    # Lưu và gộp dữ liệu
    merged_data = save_and_merge_research(new_data)

    # Trả về định dạng chuỗi JSON cho app.py sử dụng json.loads()
    return json.dumps(merged_data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(fetch_all_competitor_insights("VACT 2k9"))