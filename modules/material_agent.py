# -*- coding: utf-8 -*-
"""
MaterialAgent v3 - LẤY 2-3 TÀI LIỆU THẬT MỖI LẦN CHẠY TỪ CÁC WEB NGUỒN

Luồng: web nguồn -> danh sách bài viết -> mở từng bài -> trích link file (PDF/Drive/...)
       -> kiểm chứng link còn sống -> thu thập đủ KPI 3 tài liệu -> đưa cho AI đóng gói.
"""
import html as html_lib
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlparse
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from google import genai
from google.genai import types
from modules.brand_brain import BrandBrain

# ----------------------------------------------------------------------------
# CẤU HÌNH NGUỒN TÀI LIỆU
# ----------------------------------------------------------------------------
SOURCE_SITES = [
    {"name": "tailieu365", "base": "https://tailieu365.vn", "category_urls": []},
    {"name": "thi365", "base": "https://thi365.vn", "category_urls": []},
    {"name": "thuvienhoclieu", "base": "https://thuvienhoclieu.com", "category_urls": []}
]

ALLOW_POST_PAGE_FALLBACK = True
MAX_POSTS_TO_OPEN = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

SOCIAL_DOMAINS = ("facebook.com", "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "twitter.com", "zalo.me")
FILE_HOSTS = ("mediafire.com", "dropbox.com", "fshare.vn", "1drv.ms", "mega.nz", "onedrive.live.com")
DRIVE_HOSTS = ("drive.google.com", "docs.google.com")
DRIVE_ID_PATTERNS = [
    r"/(?:file|document|spreadsheets|presentation)/d/([\w-]{20,})",
    r"/folders/([\w-]{20,})",
    r"[?&]id=([\w-]{20,})",
]
DRIVE_BAD_MARKERS = [
    "Sorry, the file you have requested does not exist",
    "You need access", "Request access",
    "Bạn cần quyền truy cập", "Yêu cầu quyền truy cập",
]
NOT_POST_PATHS = ("/category/", "/tag/", "/page/", "/author/", "/wp-", "/feed", "/danh-muc", "/tu-khoa", "/lien-he")

SUBJECT_TERMS = {
    "toán": ["toán", "công thức", "hàm số", "phương trình", "tích phân", "đạo hàm", "xác suất", "logic", "định lượng"],
    "tiếng anh": ["tiếng anh", "english", "anh văn", "cấu trúc", "từ vựng", "ngữ pháp", "idiom"],
    "ngữ văn": ["ngữ văn", "văn học", "nghị luận", "đọc hiểu", "tiếng việt"],
    "vật lý": ["vật lý", "vật lí"],
    "hóa": ["hóa học", "môn hóa"],
    "sinh": ["sinh học"],
    "địa lý": ["địa lý", "địa lí"],
}
GRADE_OK = ("lớp 12", "thpt", "tốt nghiệp", "đgnl", "đánh giá năng lực", "vact", "v-act")

DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

# ----------------------------------------------------------------------------
# TIỆN ÍCH CHUNG & KIỂM CHỨNG
# ----------------------------------------------------------------------------
def get_available_models(client):
    try:
        models = []
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            if "gemini" in name.lower() and not any(x in name.lower() for x in ("embed", "image", "tts", "audio")):
                models.append(name)
        if models:
            models.sort(key=lambda n: (n not in DEFAULT_FALLBACK_MODELS, n))
            return models
    except Exception:
        pass
    return DEFAULT_FALLBACK_MODELS

def clean_url(u: str) -> str:
    return html_lib.unescape(u).replace("\\u0026", "&").replace("\\/", "/").strip().rstrip("\\)]},;.\"'")

def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")

def drive_id(url: str):
    if host_of(url) not in DRIVE_HOSTS: return None
    for p in DRIVE_ID_PATTERNS:
        m = re.search(p, url)
        if m: return m.group(1)
    return None

def normalize_drive(url: str) -> str:
    m = re.search(r"drive\.google\.com/file/d/([\w-]{20,})", url)
    return f"https://drive.google.com/file/d/{m.group(1)}/view" if m else url

def is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")

def strip_tags(h: str) -> str:
    h = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", h))).strip()

def meta(html: str, prop: str) -> str:
    for pat in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)["\']',
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']'):
        m = re.search(pat, html, re.I)
        if m: return html_lib.unescape(m.group(1)).strip()
    return ""

def fetch(url: str, timeout: int = 12) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            if (r.encoding or "").lower() in ("", "iso-8859-1"): r.encoding = "utf-8"
            return r.text
    except: pass
    return ""

def fetch_json(url: str, params: dict = None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if r.status_code == 200 and "json" in r.headers.get("Content-Type", "").lower():
            return r.json()
    except: pass
    return None

def web_search(query: str, max_results: int = 5) -> list:
    if not DDGS: return []
    try:
        res = list(DDGS().text(query, region="vn-vi", max_results=max_results))
        return res if res else []
    except: return []

def parse_json_loose(text: str) -> dict:
    text = text.strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}

def check_pdf(url: str, save_path: str, max_mb: int = 40):
    try:
        with requests.get(url, headers=HEADERS, timeout=20, stream=True) as r:
            if r.status_code != 200: return False, False
            chunks, size = [], 0
            for chunk in r.iter_content(65536):
                if not chunk: continue
                if not chunks and b"%PDF" not in chunk[:1024]: return False, False
                chunks.append(chunk)
                size += len(chunk)
                if size > max_mb * 1024 * 1024: return True, False
    except: return False, False
    if size < 10_000: return False, False
    with open(save_path, "wb") as f: f.write(b"".join(chunks))
    return True, True

def verify_drive(url: str) -> bool:
    if not drive_id(url): return False
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code != 200 or "accounts.google.com" in r.url: return False
        return not any(m in r.text[:300_000] for m in DRIVE_BAD_MARKERS)
    except: return False

def verify_host(url: str) -> bool:
    try:
        with requests.get(url, headers=HEADERS, timeout=12, stream=True, allow_redirects=True) as r:
            return r.status_code < 400
    except: return False

def extract_pdf_text(path: str, max_pages: int = 5, max_chars: int = 5000) -> str:
    if not path or not os.path.exists(path) or not PdfReader: return ""
    try:
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:max_pages]).strip()[:max_chars]
    except: return ""

# ----------------------------------------------------------------------------
# PHÂN TÍCH BÀI VIẾT
# ----------------------------------------------------------------------------
def extract_file_links(region_html: str, page_url: str) -> list:
    found, seen, site_host = [], set(), host_of(page_url)
    def classify(u, label=""):
        h = host_of(u)
        if any(s in h for s in SOCIAL_DOMAINS): return None
        if is_pdf_url(u): return "pdf"
        if drive_id(u): return "drive"
        if any(f in h for f in FILE_HOSTS): return "host"
        if h != site_host and re.search(r"tải|download", label, re.I) and h not in ("google.com",): return "host"
        return None

    anchors = re.findall(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', region_html)
    extras = [(u, "") for u in re.findall(r'(?i)(?:src|data-src|data-url)=["\']([^"\']+)["\']', region_html)]
    for href, label in anchors + extras:
        u = clean_url(urljoin(page_url, href))
        if not u.startswith("http"): continue
        kind = classify(u, strip_tags(label))
        if not kind: continue
        if kind == "drive": u = normalize_drive(u)
        if u not in seen:
            seen.add(u)
            found.append({"url": u, "kind": kind})
    return sorted(found, key=lambda x: {"pdf":0, "drive":1, "host":2}[x["kind"]])

def parse_post(html: str, url: str, fallback_title: str = "") -> dict:
    title = meta(html, "og:title") or fallback_title
    if not title:
        m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html) or re.search(r"(?is)<title>(.*?)</title>", html)
        title = strip_tags(m.group(1)) if m else ""
    m = re.search(r"(?is)<article\b.*?</article>", html)
    region = m.group(0) if m else html
    return {
        "title": title.strip(),
        "description": meta(html, "og:description") or meta(html, "description"),
        "thumbnail": meta(html, "og:image"),
        "text": strip_tags(region)[:2500],
        "links": extract_file_links(region, url),
    }

def subject_terms(subject: str) -> list:
    s = (subject or "").lower()
    for key, terms in SUBJECT_TERMS.items():
        if key in s: return terms
    return [w for w in re.findall(r"\w+", s) if w not in {"vact", "đgnl", "thptqg", "thpt", "lớp", "12", "môn", "tài", "liệu"}]

def is_relevant(text: str, terms: list) -> bool:
    t = text.lower()
    if terms and not any(x in t for x in terms): return False
    if re.search(r"lớp\s*(?:[1-9]|10|11)\b", t) and "lớp 12" not in t and not any(g in t for g in GRADE_OK): return False
    return True

def looks_like_post(url: str, base: str) -> bool:
    p = urlparse(url)
    if host_of(url) != host_of(base) or not p.path.strip("/"): return False
    if any(x in p.path.lower() for x in NOT_POST_PATHS): return False
    return not re.search(r"\.(jpg|jpeg|png|gif|webp|svg|css|js|pdf|zip)$", p.path.lower())

# ----------------------------------------------------------------------------
# AGENT VẬN HÀNH CHÍNH
# ----------------------------------------------------------------------------
class MaterialAgent:
    def __init__(self, api_key: str = None):
        self.brain = BrandBrain()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            try:
                import streamlit as st
                if "GEMINI_API_KEY" in st.secrets: self.api_key = st.secrets["GEMINI_API_KEY"]
            except: pass
        if not self.api_key: raise ValueError("❌ Không tìm thấy GEMINI_API_KEY!")

        self.client = genai.Client(api_key=self.api_key)
        self.materials_dir = os.path.join("knowledge_base", "materials")
        self.pdf_dir = os.path.join("knowledge_base", "pdfs")
        self.index_file = os.path.join("knowledge_base", "materials_index.json")
        self.sources_file = os.path.join("knowledge_base", "sources.json")
        os.makedirs(self.materials_dir, exist_ok=True)
        os.makedirs(self.pdf_dir, exist_ok=True)

    def _sources(self) -> list:
        sites = list(SOURCE_SITES)
        if os.path.exists(self.sources_file):
            try:
                with open(self.sources_file, "r", encoding="utf-8") as f: sites += json.load(f)
            except: pass
        return sites

    def _used_urls(self) -> set:
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return {i.get("source_url") for i in json.load(f)} | {i.get("post_url") for i in json.load(f)}
        except: return set()

    def _discover_posts(self, site: dict, terms: list) -> list:
        base = site["base"].rstrip("/")
        queries = terms[:3] or [""]
        posts = {}

        def add(url, title="", html=None):
            url = clean_url(url).split("#")[0]
            if url in posts:
                if title and not posts[url]["title"]: posts[url]["title"] = title
                return
            posts[url] = {"url": url, "title": title, "html": html, "site": site["name"]}

        for q in queries:
            data = fetch_json(f"{base}/wp-json/wp/v2/posts", {"search": q, "per_page": 10, "_fields": "link,title,content"})
            for p in data or []:
                try: add(p["link"], strip_tags(p["title"]["rendered"]), p["content"]["rendered"])
                except: continue

        listing_pages = [f"{base}/?s={quote_plus(q)}" for q in queries if q] + site.get("category_urls", [])
        for pg in listing_pages:
            html = fetch(pg)
            for href, label in re.findall(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html):
                u = clean_url(urljoin(pg, href))
                if looks_like_post(u, base): add(u, strip_tags(label))

        if not posts:
            for q in queries:
                for res in web_search(f"site:{host_of(base)} {q}"):
                    if looks_like_post(res.get("href", ""), base): add(res["href"], res.get("title", ""))

        print(f"📚 {site['name']}: tìm thấy {len(posts)} bài ứng viên")
        return list(posts.values())

    def hunt_real_material_links(self, subject: str = "", target_count: int = 3) -> list:
        """Đào xới và kiểm chứng để lấy đủ KPI 3 tài liệu thật."""
        terms = subject_terms(subject)
        used = self._used_urls()
        
        posts = []
        for site in self._sources():
            posts += self._discover_posts(site, terms)
        posts = [p for p in posts if p["url"] not in used]
        posts.sort(key=lambda p: -sum(t in p["title"].lower() for t in terms))

        results = []
        fallbacks = []

        for idx, post in enumerate(posts[:MAX_POSTS_TO_OPEN]):
            if len(results) >= target_count: break
            
            html = post["html"] or fetch(post["url"])
            info = parse_post(html, post["url"], post["title"])
            if post["html"] and not info["links"]:
                full = fetch(post["url"])
                if full: info = parse_post(full, post["url"], post["title"])
            
            if not info["title"] or not is_relevant(f"{info['title']} {info['text']}", terms): continue

            mat_id = f"mat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(results)}"
            pdf_path = os.path.join(self.pdf_dir, f"{mat_id}.pdf")
            
            base_res = {
                "mat_id": mat_id, "site": post["site"], "post_url": post["url"],
                "post_title": info["title"], "excerpt": f"{info['description']}\n{info['text']}"[:2000],
                "thumbnail": info["thumbnail"]
            }

            has_real_link = False
            for link in info["links"]:
                if link["url"] in used: continue
                local = ""
                if link["kind"] == "pdf":
                    ok, saved = check_pdf(link["url"], pdf_path)
                    local = pdf_path if saved else ""
                elif link["kind"] == "drive": ok = verify_drive(link["url"])
                else: ok = verify_host(link["url"])
                
                if ok:
                    print(f"🎯 [{post['site']}] {info['title']}\n   ↳ Bắt được file: {link['url']}")
                    results.append({**base_res, "source_url": link["url"], "link_type": link["kind"], "pdf_local_path": local})
                    used.add(link["url"])
                    has_real_link = True
                    break
                else:
                    print(f"   ✗ link chết/khóa: {link['url']}")

            if not has_real_link and ALLOW_POST_PAGE_FALLBACK:
                fallbacks.append({**base_res, "source_url": post["url"], "link_type": "post_page", "pdf_local_path": ""})

        # Bổ sung link fallback (link gốc bài viết) nếu chưa đủ target_count
        while len(results) < target_count and fallbacks:
            fb = fallbacks.pop(0)
            if fb["source_url"] not in used:
                print(f"ℹ️ Bổ sung bài viết (fallback): {fb['source_url']}")
                results.append(fb)
                used.add(fb["source_url"])

        return results

    def collect_and_package_materials(self, subject: str = "", target_count: int = 3) -> list:
        """Đóng gói hàng loạt tài liệu thu thập được (Mặc định: 3 bộ/lần)."""
        found_list = self.hunt_real_material_links(subject, target_count)
        if not found_list:
            print("❌ Không tìm được tài liệu hợp lệ từ các web nguồn.")
            return []

        packaged_results = []
        subject_label = subject or "Ôn thi THPT Quốc gia lớp 12"

        for found in found_list:
            pdf_text = extract_pdf_text(found["pdf_local_path"])
            prompt = f"""
Bạn là Chuyên gia Biên soạn Tài liệu Học tập của VACT Giga HCM.
Dưới đây là thông tin THỰC TẾ của một tài liệu ôn thi lớp 12 lấy từ website {found['site']}.

Tiêu đề bài gốc: {found['post_title']}
Link: {found['source_url']}
Mô tả/nội dung trích từ trang:
\"\"\"{found['excerpt']}\"\"\"
Nội dung trích từ file PDF (có thể rỗng):
\"\"\"{pdf_text}\"\"\"

NGUYÊN TẮC BẮT BUỘC:
- Chỉ dựa trên dữ liệu ở trên. Tài liệu thuộc chủ đề nào thì giữ đúng chủ đề đó, tuyệt đối không chuyển sang môn/chủ đề khác.
- Không bịa số lượng, tên tác giả, nội dung không có trong dữ liệu.
- "sample_content" chỉ trích nguyên văn từ dữ liệu thật ở trên; không có thì để chuỗi rỗng.

Hãy đóng gói tài liệu này cho bài đăng Facebook Tặng Tài Liệu (Lead Gen).
Chỉ trả về JSON với các khóa (không dùng markdown):
{{
  "title": "Tên tài liệu hấp dẫn, bám sát tiêu đề gốc",
  "target_audience": "Học sinh 2k9 ôn thi ĐGNL VACT & THPTQG",
  "key_highlights": ["3-4 điểm nổi bật, chỉ dựa trên dữ liệu thật"],
  "sample_content": "Trích 1-2 câu hỏi/kiến thức từ nội dung thật để làm Quiz (hoặc rỗng)",
  "cta_keyword": "Từ khóa comment nhận file (VD: {subject_label})"
}}
"""
            print(f"🤖 Đang dùng AI biên soạn: {found['post_title']}...")
            response, last_error = None, None
            for model_name in get_available_models(self.client):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=self.brain.get_system_context(),
                            temperature=0.3,
                            response_mime_type="application/json",
                        ),
                    )
                    break
                except Exception as e:
                    last_error = e

            if not response:
                print(f"⚠️ Lỗi biên soạn tài liệu này: {last_error}")
                continue

            data = parse_json_loose(response.text)
            data.update({
                "material_id": found["mat_id"],
                "subject": subject_label,
                "source_site": found["site"],
                "original_title": found["post_title"],
                "source_url": found["source_url"],
                "link_type": found["link_type"],
                "post_url": found["post_url"],
                "thumbnail": found["thumbnail"],
                "pdf_local_path": found["pdf_local_path"],
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            })
            if "cta_keyword" not in data or not data["cta_keyword"]:
                data["cta_keyword"] = subject_label

            path = os.path.join(self.materials_dir, f"{data['material_id']}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._update_index(data)
            
            packaged_results.append(data)
            print(f"🎉 Đã biên soạn & lưu: {data.get('title')}")
            print(f"🔗 LINK ({data['link_type']}): {data['source_url']}\n")

        return packaged_results

    def _update_index(self, d: dict):
        index = []
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except: index = []
            
        index = [i for i in index if i.get("material_id") != d["material_id"]]
        index.append({
            "material_id": d["material_id"],
            "title": d.get("title", ""),
            "subject": d["subject"],
            "cta_keyword": d["cta_keyword"],
            "source_site": d["source_site"],
            "source_url": d["source_url"],
            "link_type": d["link_type"],
            "post_url": d["post_url"],
            "pdf_local_path": d.get("pdf_local_path", ""),
            "created_at": d["created_at"],
            "file_path": os.path.join(self.materials_dir, f"{d['material_id']}.json"),
        })
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    agent = MaterialAgent()
    # Chạy vòng lặp lấy 3 tài liệu Toán về hệ thống
    mats = agent.collect_and_package_materials("Toán", target_count=3)
    print("\n--- BÁO CÁO DANH SÁCH TÀI LIỆU ĐÃ ĐÓNG GÓI ---")
    print(json.dumps(mats, ensure_ascii=False, indent=2) if mats else "Không tìm thấy tài liệu hợp lệ.")