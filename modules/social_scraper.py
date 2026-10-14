# -*- coding: utf-8 -*-
import json
import os
import sys
import yt_dlp
from duckduckgo_search import DDGS

# Khai báo đường dẫn gốc dự án
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COMPETITORS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base",
    "competitor_channels.json"
)

def scrape_channel_videos(channel_url: str, max_results: int = 3) -> list:
    """Lấy thông tin tiêu đề, lượt xem, hashtag của các video mới nhất từ kênh TikTok/FB."""
    ydl_opts = {
        'extract_flat': True,
        'playlistend': max_results,
        'quiet': True,
        'no_warnings': True
    }
    
    video_data = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        video_data.append({
                            "title": entry.get("title", "Không có tiêu đề"),
                            "views": entry.get("view_count", 0),
                            "url": entry.get("url", "")
                        })
    except Exception as e:
        print(f"⚠️ Không thể cào dữ liệu từ {channel_url}: {e}")
        
    return video_data

def discover_similar_channels(keyword: str = "luyện thi đánh giá năng lực ĐHQG TPHCM VACT") -> list:
    """Agent tự động tìm các kênh TikTok / Facebook mới thuộc cùng ngách nội dung."""
    discovered = []
    queries = [
        f"site:tiktok.com/@ {keyword}",
        f"site:facebook.com {keyword}"
    ]
    
    try:
        ddgs = DDGS()
        for query in queries:
            results = list(ddgs.text(query, max_results=3))
            for r in results:
                discovered.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "link": r.get("href", "")
                })
    except Exception as e:
        print(f"⚠️ Lỗi khi tìm kênh tương tự: {e}")
        
    return discovered

def fetch_all_competitor_insights(keyword: str = "luyện thi VACT ĐGNL") -> str:
    """Tổng hợp toàn bộ nội dung từ các kênh chỉ định + các kênh Agent tự khám phá."""
    insights = []
    
    # 1. Nạp danh sách kênh hiện có
    if os.path.exists(COMPETITORS_FILE):
        with open(COMPETITORS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            channels = data.get("user_provided_channels", [])
    else:
        channels = []

    # 2. Cào dữ liệu từ từng kênh chỉ định
    for ch in channels:
        url = ch.get("url")
        if url and "tiktok.com" in url:
            print(f"🕷️ Đang cào dữ liệu từ kênh TikTok: {ch.get('name')} ({url})...")
            videos = scrape_channel_videos(url, max_results=3)
            insights.append({
                "channel_name": ch.get("name"),
                "url": url,
                "recent_videos": videos
            })

    # 3. Agent tự động tìm các nguồn nội dung tương tự
    print(f"🔎 Agent đang tự tìm các kênh/bài viết tương tự về từ khóa: '{keyword}'...")
    similar_content = discover_similar_channels(keyword)

    summary_data = {
        "user_channels_insights": insights,
        "auto_discovered_trends": similar_content
    }

    return json.dumps(summary_data, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    print("🧪 Test thử cào nội dung đối thủ...")
    result = fetch_all_competitor_insights()
    print(result[:800] + "\n...[Đã ẩn phần còn lại]")