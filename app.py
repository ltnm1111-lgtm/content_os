# -*- coding: utf-8 -*-
import json
import os
import sys
import glob
import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

from modules.agent_planner import PlannerAgent
from modules.agent_writer import WriterAgent
from modules.social_scraper import fetch_all_competitor_insights

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="VACT Giga - Content OS", page_icon="🚀", layout="wide")

st.title("🤖 VACT Giga HCM - AI Content OS Dashboard")
st.caption("Hệ thống quản trị và vận hành đội ngũ AI Agent tự động")

def get_latest_plan():
    files = glob.glob("data/weekly_plan_*.json")
    if not files:
        return None, None
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f), latest_file

def get_latest_drafts():
    files = glob.glob("data/weekly_drafts_*.json")
    if not files:
        return None
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f)

# --- KHU VỰC 1: TRẠNG THÁI CÁC AGENT ---
st.subheader("📊 Trạng thái Đội ngũ Agent")
col1, col2, col3, col4 = st.columns(4)

latest_plan, file_path = get_latest_plan()
has_plan = latest_plan is not None

with col1:
    st.metric(label="Agent 1 & 2 (Research & Plan)", value="🟢 Đã sẵn sàng")
with col2:
    st.metric(label="Agent 3 (Writer)", value="🟢 Đã sẵn sàng" if has_plan else "⚪ Chờ Plan")
with col3:
    st.metric(label="Agent 4 (Evaluator)", value="🟢 Đã sẵn sàng" if has_plan else "⚪ Chờ Bài viết")
with col4:
    st.metric(label="Kế hoạch hiện tại", value=os.path.basename(file_path) if file_path else "Chưa có")

st.divider()

# --- KHU VỰC 2: QUẢN LÝ KÊNH ĐỐI THỦ ---
st.header("🔗 Quản lý Kênh TikTok / FB Đối thủ")

competitor_file = os.path.join("knowledge_base", "competitor_channels.json")

def load_competitor_channels():
    if os.path.exists(competitor_file):
        try:
            with open(competitor_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"user_provided_channels": [], "discovered_channels": []}

def save_competitor_channels(data):
    os.makedirs("knowledge_base", exist_ok=True)
    with open(competitor_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "comp_data" not in st.session_state:
    st.session_state["comp_data"] = load_competitor_channels()

col_c1, col_c2 = st.columns([2, 1])
with col_c1:
    new_channel_url = st.text_input("Thêm link kênh TikTok/FB đối thủ:", key="input_url")
with col_c2:
    new_channel_name = st.text_input("Tên gợi nhớ của kênh:", key="input_name")

if st.button("➕ Thêm Kênh vào Hệ thống"):
    if new_channel_url:
        new_item = {
            "platform": "TikTok" if "tiktok" in new_channel_url else "Facebook",
            "name": new_channel_name if new_channel_name else "Kênh đối thủ",
            "url": new_channel_url
        }
        existing_urls = [c.get("url") for c in st.session_state["comp_data"]["user_provided_channels"]]
        if new_channel_url not in existing_urls:
            st.session_state["comp_data"]["user_provided_channels"].append(new_item)
            save_competitor_channels(st.session_state["comp_data"])
            st.success("✅ Đã thêm kênh vào hệ thống!")
            st.rerun()
        else:
            st.warning("⚠️ Kênh này đã có trong danh sách theo dõi!")

st.caption("📋 Danh sách các kênh Agent đang theo dõi:")
st.json(st.session_state["comp_data"]["user_provided_channels"])

st.divider()

# --- KHU VỰC 3: CHẶNG 1 - TẠO VÀ DUYỆT PLAN ---
st.header("🎯 Chặng 1: Lên Kế hoạch Content Tuần")

topic_input = st.text_input(
    "Chủ đề chủ đạo tuần này:",
    value="Tập trung kiến thức trọng tâm & tâm lý thi VACT 2k9"
)

if st.button("🚀 Kích hoạt Agent 1 & 2 (Nghiên cứu & Lên Plan)", type="primary"):
    with st.spinner("🤖 Agent 1 đang cào dữ liệu TikTok/FB & Planner Agent tạo Lịch..."):
        try:
            raw_insights = fetch_all_competitor_insights(keyword=topic_input)
            parsed_insights = json.loads(raw_insights)
            
            os.makedirs("data", exist_ok=True)
            with open("data/latest_research.json", "w", encoding="utf-8") as f:
                json.dump(parsed_insights, f, ensure_ascii=False, indent=2)
            
            planner = PlannerAgent()
            plan = planner.generate_weekly_plan(week_topic=topic_input)
            st.success("✅ Đã cào dữ liệu đối thủ & tạo Plan mới thành công!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi khi chạy Agent: {str(e)}")

# HIỂN THỊ KẾ HOẠCH & DUYỆT TỰ ĐỘNG CHUYỂN CHẶNG 2
if has_plan:
    st.subheader(f"📅 Bảng Kế hoạch Tuần (Tạo ngày: {latest_plan.get('created_at', 'N/A')})")
    posts = latest_plan.get("posts", [])
    
    st.dataframe(
        posts,
        column_config={
            "id": "STT",
            "day": "Thứ",
            "channel": "Kênh",
            "angle": "Góc nhìn (Angle)",
            "hook_idea": "Gợi ý câu Hook",
            "cta": "CTA",
            "status": "Trạng thái"
        },
        use_container_width=True
    )

    st.divider()
    st.warning("🟧 STEP CỦA BẠN (HUMAN-IN-THE-LOOP): Duyệt Kế hoạch để tự động viết bài Chặng 2")
    
    col_approve, col_reject = st.columns([1, 4])
    with col_approve:
        if st.button("✅ DUYỆT PLAN & TỰ ĐỘNG VIẾT BÀI", type="primary", key="btn_approve_plan"):
            with st.spinner("🤖 Bạn đã duyệt Plan! Writer Agent đang tự động viết bài & kịch bản..."):
                try:
                    # Ghi file latest_plan.json
                    os.makedirs("data", exist_ok=True)
                    with open("data/latest_plan.json", "w", encoding="utf-8") as f:
                        json.dump(latest_plan, f, ensure_ascii=False, indent=2)
                    
                    # Tự động gọi Writer Agent sinh bài viết ngay tại đây
                    writer = WriterAgent()
                    drafts = writer.generate_all_drafts(latest_plan)
                    
                    st.balloons()
                    st.success("🎉 Đã duyệt Plan và tạo xong toàn bộ bài viết Chặng 2!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi khi viết bài tự động: {str(e)}")

    with col_reject:
        if st.button("❌ Bỏ qua / Tạo lại Plan khác", key="btn_reject_plan"):
            st.info("Hãy nhập lại chủ đề trên thanh tìm kiếm và bấm Kích hoạt lại.")
else:
    st.info("Chưa có kế hoạch nào được tạo. Hãy bấm nút phía trên để Agent bắt đầu làm việc.")

# --- KHU VỰC CHẶNG 2: BẢN THẢO BÀI VIẾT TỰ ĐỘNG HIỂN THỊ ---
st.divider()
st.header("✍️ Chặng 2: Bản thảo Nội dung Chi tiết (Writer Agent)")

latest_drafts = get_latest_drafts()
if latest_drafts:
    st.subheader(f"📅 Bản thảo Tuần (Chủ đề: {latest_drafts.get('plan_topic')})")
    drafts = latest_drafts.get("drafts", [])
    days_order = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    
    for day in days_order:
        day_posts = [p for p in drafts if p.get("day") == day or p.get("day") == f"Thứ {days_order.index(day)+2}"]
        
        if day_posts or any(p.get("day") == day for p in drafts):
            st.markdown(f"### 🗓️ {day}")
            posts_to_show = [p for p in drafts if p.get("day") == day]
            if not posts_to_show:
                posts_to_show = day_posts

            for post in posts_to_show:
                channel = post.get("channel", "Facebook")
                fmt = post.get("format_type", "")
                
                if "TikTok" in channel:
                    badge = "🎵 TikTok Script"
                elif fmt == "FB_LEAD_GEN" or "Dạng 1" in post.get("angle", ""):
                    badge = "📘 FB Dạng 1: Tặng Tài Liệu (Lead Gen)"
                elif fmt == "FB_QUIZ" or "Dạng 2" in post.get("angle", ""):
                    badge = "📘 FB Dạng 2: Quiz Tương Tác (Reaction)"
                else:
                    badge = "📘 FB Dạng 3: Text-Overlay Video"

                with st.expander(f"{badge} | Angle: {post.get('angle')}", expanded=True):
                    if post.get("source_url"):
                        st.info(f"🔗 **URL Tài liệu học tập gốc:** [{post.get('source_url')}]({post.get('source_url')})")
                    
                    st.markdown("**Nội dung chi tiết:**")
                    st.markdown(post.get("content"))
                    
                    st.text_area(
                        "✏️ Co-pilot (Chỉnh sửa nội dung nếu muốn):",
                        value=post.get("content"),
                        key=f"edit_{post.get('id')}_{day}",
                        height=200
                    )
else:
    st.info("💡 Hãy bấm nút **'✅ DUYỆT PLAN & TỰ ĐỘNG VIẾT BÀI'** ở trên để Writer Agent xuất bản thảo tại đây.")