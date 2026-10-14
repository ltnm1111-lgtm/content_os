# -*- coding: utf-8 -*-
import json
import os


class BrandBrain:
    """Đọc toàn bộ tri thức thương hiệu và đóng gói thành System Instruction cho Agent."""

    def __init__(self, kb_dir: str = None):
        if kb_dir is None:
            # Luôn trỏ đúng thư mục knowledge_base dù chạy script từ đâu
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            kb_dir = os.path.join(base, "knowledge_base")
        self.kb_dir = kb_dir
        self.brand_voice = self._load_json("brand_voice.json", {})
        self.products = self._load_json("products.json", [])
        self.do_and_dont = self._load_json("do_and_dont.json", {})

    def _load_json(self, filename: str, default):
        filepath = os.path.join(self.kb_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"⚠️ Không tìm thấy {filepath}, dùng dữ liệu rỗng.")
        return default

    @staticmethod
    def _bullets(items) -> str:
        return "\n".join(f"  - {i}" for i in items) if items else "  (chưa có)"

    def get_system_context(self) -> str:
        """Tổng hợp toàn bộ tri thức thương hiệu thành ngữ cảnh hệ thống cho LLM."""
        bv = self.brand_voice
        tone = bv.get("tone_of_voice", {})
        pronouns = tone.get("pronouns", {})
        persona = bv.get("persona", {})

        context = f"""
=== BỘ NÃO THƯƠNG HIỆU (BRAND KNOWLEDGE BASE) ===
1. THÔNG TIN THƯƠNG HIỆU & GIỌNG VĂN:
- Tên thương hiệu: {bv.get('brand_name', '')}
- Mô tả: {bv.get('brand_description', '')}
- Khách hàng mục tiêu: {bv.get('target_audience', '')}
- Vai trò nhân vật (persona): {persona.get('role', '')}
- Tính cách:
{self._bullets(persona.get('personality', []))}
- Phong cách viết: {tone.get('style', '')}
- Xưng hô: Tự xưng '{pronouns.get('self', 'Chị')}' và gọi người đọc là '{pronouns.get('reader', 'Em')}'
- Quy tắc trình bày:
{self._bullets(tone.get('formatting_rules', []))}
- Gợi ý từ vựng:
{self._bullets(tone.get('vocabulary_hints', []))}

2. DANH MỤC SẢN PHẨM / DỊCH VỤ:
{json.dumps(self.products, ensure_ascii=False, indent=2)}

3. QUY TẮC NỘI DUNG (DO & DON'T):
- Từ/cụm từ CẤM sử dụng: {", ".join(self.do_and_dont.get('forbidden_words', []))}
- Lỗi CẦN TRÁNH:
{self._bullets(self.do_and_dont.get('common_errors_to_avoid', []))}
- Quy tắc khi nói về giá / cam kết dịch vụ:
{self._bullets(self.do_and_dont.get('claim_rules', []))}
- Quy tắc kiểm chứng thông tin:
{self._bullets(self.do_and_dont.get('fact_check_rules', []))}
=================================================
"""
        return context.strip()

    def check_forbidden(self, text: str) -> list:
        """Trả về danh sách từ cấm xuất hiện trong text (dùng để kiểm duyệt đầu ra của Agent)."""
        lowered = text.lower()
        return [w for w in self.do_and_dont.get("forbidden_words", []) if w.lower() in lowered]


# Kiểm thử module
if __name__ == "__main__":
    brain = BrandBrain()
    print("✅ Đã khởi tạo Bộ não thương hiệu thành công:")
    print(brain.get_system_context()[:600] + "...\n[Đã ẩn phần còn lại]")
    demo = "Học là đậu, cam kết 100% đậu!"
    print("🔎 Test bộ lọc từ cấm:", brain.check_forbidden(demo))
