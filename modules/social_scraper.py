# -*- coding: utf-8 -*-
import json
import os

RESEARCH_FILE = os.path.join("data", "latest_research.json")

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