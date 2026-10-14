# -*- coding: utf-8 -*-
import json
import os
import sys
import glob
import streamlit as st

# Tự động nạp thư mục gốc vào hệ thống
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Nạp API Key từ Streamlit Secrets vào biến môi trường
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

from modules.agent_planner import PlannerAgent

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="VACT Giga - Content OS", page_icon="🚀", layout="wide")

st.title("🤖 VACT Giga HCM - AI Content OS Dashboard")
st.caption("Hệ thống quản trị và vận hành đội ngũ AI Agent tự động")

# --- HÀM HỖ TRỢ LẤY FILE PLAN MỚI NHẤT ---
def get_latest_plan():
    files = glob.glob("data/weekly_plan_*.json")
    if not files:
        return None, None
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f), latest_file

# --- KHU VỰC 1: TRẠNG THÁI CÁC AGENT (AGENTS STATUS BOARD) ---
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

# --- KHU VỰC 2: QUẢN LÝ KÊNH TIKTOK / FB ĐỐI THỦ ---
st.header("🔗 Quản lý Kênh TikTok / FB Đối thủ")

competitor_file = os.path.join("knowledge_base", "competitor_channels.json")

# Hàm đọc dữ liệu từ file JSON
def load_competitor_channels():
    if os.path.exists(competitor_file):
        try:
            with open(competitor_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"user_provided_channels": [], "discovered_channels": []}

# Hàm ghi dữ liệu vĩnh viễn vào file JSON
def save_competitor_channels(data):
    os.makedirs("knowledge_base", exist_ok=True)
    with open(competitor_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Khởi tạo bộ nhớ tạm (Session State) để không bị mất kênh khi reload
if "comp_data" not in st.session_state:
    st.session_state["comp_data"] = load_competitor_channels()

col_c1, col_c2 = st.columns([2, 1])
with col_c1:
    new_channel_url = st.text_input("Thêm link kênh TikTok/FB đối thủ (VD: https://www.tiktok.com/@username):", key="input_url")
with col_c2:
    new_channel_name = st.text_input("Tên gợi nhớ của kênh:", key="input_name")

if st.button("➕ Thêm Kênh vào Hệ thống"):
    if new_channel_url:
        new_item = {
            "platform": "TikTok" if "tiktok" in new_channel_url else "Facebook",
            "name": new_channel_name if new_channel_name else "Kênh đối thủ",
            "url": new_channel_url
        }
        
        # Kiểm tra trùng lặp link
        existing_urls = [c.get("url") for c in st.session_state["comp_data"]["user_provided_channels"]]
        if new_channel_url not in existing_urls:
            # Thêm vào Session State và Lưu ra ổ đĩa
            st.session_state["comp_data"]["user_provided_channels"].append(new_item)
            save_competitor_channels(st.session_state["comp_data"])
            st.success("✅ Đã thêm kênh và tự động lưu vào hệ thống!")
            st.rerun()
        else:
            st.warning("⚠️ Kênh này đã có trong danh sách theo dõi!")

st.caption("📋 Danh sách các kênh Agent đang theo dõi:")
st.json(st.session_state["comp_data"]["user_provided_channels"])

st.divider()

# Thêm import module cào ở đầu file app.py nếu chưa có
from modules.social_scraper import fetch_all_competitor_insights

# --- KHU VỰC 3: CHẶNG 1 - TẠO VÀ DUYỆT PLAN ---
st.header("🎯 Chặng 1: Lên Kế hoạch Content Tuần")

topic_input = st.text_input(
    "Chủ đề chủ đạo tuần này:",
    value="Tập trung kiến thức trọng tâm & tâm lý thi VACT 2k9"
)

if st.button("🚀 Kích hoạt Agent 1 & 2 (Nghiên cứu & Lên Plan)", type="primary"):
    with st.spinner("🤖 Agent 1 đang cào dữ liệu TikTok/FB & tìm kênh mới..."):
        try:
            # 1. Cào dữ liệu từ các kênh đối thủ
            raw_insights = fetch_all_competitor_insights(keyword=topic_input)
            parsed_insights = json.loads(raw_insights)
            
            # Lưu vĩnh viễn dữ liệu cào ra file để không bị mất khi F5
            os.makedirs("data", exist_ok=True)
            with open("data/latest_research.json", "w", encoding="utf-8") as f:
                json.dump(parsed_insights, f, ensure_ascii=False, indent=2)
            
            # 2. Chạy Agent Planner tạo Lịch Content
            planner = PlannerAgent()
            plan = planner.generate_weekly_plan(week_topic=topic_input)
            st.success("✅ Đã cào dữ liệu đối thủ & tạo Plan mới thành công!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi khi chạy Agent: {str(e)}")

# --- HIỂN THỊ DỮ LIỆU NGHIÊN CỨU THỰC TẾ CỦA AGENT 1 ---
research_file = "data/latest_research.json"
if os.path.exists(research_file):
    try:
        with open(research_file, "r", encoding="utf-8") as f:
            latest_research = json.load(f)
            
        st.divider()
        with st.expander("🔍 Xem dữ liệu Agent 1 cào từ các kênh đối thủ & Kênh tự phát hiện", expanded=True):
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.subheader("1. Video mới cào từ các kênh bạn chỉ định:")
                st.json(latest_research.get("user_channels_insights", []))
            with col_r2:
                st.subheader("2. Kênh / bài viết tương tự Agent tự phát hiện:")
                st.json(latest_research.get("auto_discovered_trends", []))
    except Exception as e:
        pass
# --- HIỂN THỊ KẾ HOẠCH BÀI VIẾT VÀ NÚT DUYỆT (HUMAN APPROVAL) ---
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
    
    st.warning("🟧 STEP CỦA BẠN (HUMAN-IN-THE-LOOP): Duyệt Kế hoạch trước khi chuyển sang Chặng 2")
    
    col_approve, col_reject = st.columns([1, 4])
    with col_approve:
        if st.button("✅ DUYỆT PLAN (Chạy tiếp Chặng 2)"):
            st.balloons()
            st.success("🎉 Bạn đã duyệt Plan! Sẵn sàng kích hoạt Agent Viết bài (Chặng 2).")
    with col_reject:
        if st.button("❌ Bỏ qua / Tạo lại Plan khác"):
            st.info("Hãy nhập lại chủ đề trên thanh tìm kiếm và bấm Kích hoạt lại.")
else:
    st.info("Chưa có kế hoạch nào được tạo. Hãy bấm nút phía trên để Agent bắt đầu làm việc.")