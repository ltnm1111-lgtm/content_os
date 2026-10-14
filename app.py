# -*- coding: utf-8 -*-
import json
import os
import sys
import glob
import streamlit as st

# Tự động nạp thư mục gốc vào hệ thống
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

competitor_file = "knowledge_base/competitor_channels.json"
if os.path.exists(competitor_file):
    with open(competitor_file, "r", encoding="utf-8") as f:
        comp_data = json.load(f)
else:
    comp_data = {"user_provided_channels": [], "discovered_channels": []}

col_c1, col_c2 = st.columns([2, 1])
with col_c1:
    new_channel_url = st.text_input("Thêm link kênh TikTok/FB đối thủ (VD: https://www.tiktok.com/@username):")
with col_c2:
    new_channel_name = st.text_input("Tên gợi nhớ của kênh:")

if st.button("➕ Thêm Kênh vào Hệ thống"):
    if new_channel_url:
        comp_data["user_provided_channels"].append({
            "platform": "TikTok" if "tiktok" in new_channel_url else "Facebook",
            "name": new_channel_name if new_channel_name else "Kênh đối thủ",
            "url": new_channel_url
        })
        os.makedirs("knowledge_base", exist_ok=True)
        with open(competitor_file, "w", encoding="utf-8") as f:
            json.dump(comp_data, f, ensure_ascii=False, indent=2)
        st.success("✅ Đã thêm kênh thành công!")
        st.rerun()

st.caption("📋 Danh sách các kênh Agent đang theo dõi:")
st.json(comp_data["user_provided_channels"])

st.divider()

# --- KHU VỰC 3: CHẶNG 1 - TẠO VÀ DUYỆT PLAN (HUMAN-IN-THE-LOOP) ---
st.header("🎯 Chặng 1: Lên Kế hoạch Content Tuần")

topic_input = st.text_input(
    "Chủ đề chủ đạo tuần này:",
    value="Tập trung kiến thức trọng tâm & tâm lý thi VACT 2k9"
)

if st.button("🚀 Kích hoạt Agent 1 & 2 (Nghiên cứu & Lên Plan)", type="primary"):
    with st.spinner("🤖 Agent đang cào dữ liệu TikTok/FB & DuckDuckGo để lập kế hoạch..."):
        try:
            planner = PlannerAgent()
            plan = planner.generate_weekly_plan(week_topic=topic_input)
            st.success("✅ Đã lập thành công Lịch Content Tuần mới dựa trên tin tức & kênh đối thủ!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi khi chạy Agent: {str(e)}")

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