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
        return None
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f), latest_file
    return None, None

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

# --- KHU VỰC 2: CHẶNG 1 - TẠO VÀ DUYỆT PLAN (HUMAN-IN-THE-LOOP) ---
st.header("🎯 Chặng 1: Lên Kế hoạch Content Tuần")

topic_input = st.text_input(
    "Chủ đề chủ đạo tuần này:",
    value="Tập trung kiến thức trọng tâm & tâm lý thi VACT 2k9"
)

if st.button("🚀 Kích hoạt Agent 1 & 2 (Nghiên cứu & Lên Plan)", type="primary"):
    with st.spinner("🤖 Agent đang tìm kiếm tin tức trên DuckDuckGo và lập kế hoạch..."):
        try:
            planner = PlannerAgent()
            plan = planner.generate_weekly_plan(week_topic=topic_input)
            st.success("✅ Đã lập thành công Lịch Content Tuần mới!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi khi chạy Agent: {str(e)}")

# --- HIỂN THỊ KẾ HOẠCH BÀI VIẾT VÀ NÚT DUYỆT (BƯỚC CON NGƯỜI DUYỆT) ---
if has_plan:
    st.subheader(f"📅 Bảng Kế hoạch Tuần (Tạo ngày: {latest_plan.get('created_at', 'N/A')})")
    
    posts = latest_plan.get("posts", [])
    
    # Hiển thị dạng bảng trực quan
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
    
    # --- NÚT BẤM DUYỆT CỦA CON NGƯỜI (HUMAN APPROVAL) ---
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