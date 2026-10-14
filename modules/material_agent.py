# -*- coding: utf-8 -*-
"""
MaterialAgent v3 - LẤY TÀI LIỆU THẬT TỪ CÁC WEB NGUỒN (vd tailieu365.vn)

Luồng: web nguồn -> danh sách bài viết -> mở từng bài -> trích link file (PDF/Drive/...)
       -> kiểm chứng link còn sống -> mới đưa cho AI đóng gói.
AI chỉ viết lại nội dung dựa trên dữ liệu thật của bài, không được tự tạo link.

Cài thêm:  pip install ddgs pypdf requests
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
# CẤU HÌNH
# ----------------------------------------------------------------------------
# Các web nguồn. Muốn thêm web/chuyên mục: sửa ở đây hoặc tạo knowledge_base/sources.json
# dạng [{"name": "...", "base": "https://...", "category_urls": ["https://.../chuyen-muc-x/"]}]
# (category_urls: copy URL chuyên mục từ trình duyệt, vd trang "Đánh giá năng lực VACT")
SOURCE_SITES = [
    {"name": "tailieu365", "base": "https://tailieu365.vn", "category_urls": []},
]

# Nếu bài viết không có link file tải được thì có dùng chính link bài viết (link thật) không
ALLOW_POST_PAGE_FALLBACK = True

MAX_POSTS_TO_OPEN = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

SOCIAL_DOMAINS = ("facebook.com", "youtube.com", "youtu.be", "tiktok.com",
                  "instagram.com", "twitter.com", "zalo.me", "t.me", "m.me")
FILE_HOSTS = ("mediafire.com", "dropbox.com", "fshare.vn", "1drv.ms", "mega.nz",
              "onedrive.live.com", "4shared.com")
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
NOT_POST_PATHS = ("/category/", "/tag/", "/page/", "/author/", "/wp-", "/feed",
                  "/danh-muc", "/tu-khoa", "/lien-he", "/gioi-thieu")

# Từ khóa nhận diện môn học. Tên bài thường không ghi "Toán" mà ghi "công thức tính diện tích...",
# nên mỗi môn có thêm từ khóa chủ đề. Để subject="" nếu muốn lấy tài liệu bất kỳ môn nào.
SUBJECT_TERMS = {
    "toán": ["toán", "công thức", "hàm số", "phương trình", "tích phân", "đạo hàm",
             "xác suất", "logarit", "lượng giác", "diện tích", "thể tích", "hình học", "số phức"],
    "tiếng anh": ["tiếng anh", "english", "anh văn", "cấu trúc", "từ vựng", "ngữ pháp",
                  "idiom", "phrasal", "mệnh đề"],
    "ngữ văn": ["ngữ văn", "văn học", "nghị luận", "đọc hiểu", "tác phẩm"],
    "vật lý": ["vật lý", "vật lí", "dao động cơ", "điện xoay chiều"],
    "hóa": ["hóa học", "môn hóa", "este", "peptit"],
    "sinh": ["sinh học", "di truyền"],
    "lịch sử": ["lịch sử"],
    "địa lý": ["địa lý", "địa lí", "atlat"],
}
# Dấu hiệu tài liệu cấp 12 / thi THPTQG / ĐGNL
GRADE_OK = ("lớp 12", "thpt", "tốt nghiệp", "đgnl", "đánh giá năng lực",
            "vact", "v-act", "hsa", "2026", "2027")

DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]


# ----------------------------------------------------------------------------
# TIỆN ÍCH CHUNG
# ----------------------------------------------------------------------------
def get_available_models(client):
    try:
        models = []
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            low = name.lower()
            if "gemini" in low and not any(x in low for x in ("embed", "image", "tts", "live", "audio")):
                models.append(name)
        if models:
            models.sort(key=lambda n: (n not in DEFAULT_FALLBACK_MODELS, n))
            return models
    except Exception as e:
        print(f"⚠️ Không lấy được danh sách model ({e}). Dùng danh sách mặc định.")
    return DEFAULT_FALLBACK_MODELS


def clean_url(u: str) -> str:
    u = html_lib.unescape(u).replace("\\u0026", "&").replace("\\/", "/")
    return u.strip().rstrip("\\)]},;.\"'")


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def drive_id(url: str):
    if urlparse(url).netloc.lower() not in DRIVE_HOSTS:
        return None
    for p in DRIVE_ID_PATTERNS:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def normalize_drive(url: str) -> str:
    """Link nhúng /preview -> link xem /view cho học sinh bấm được."""
    m = re.search(r"drive\.google\.com/file/d/([\w-]{20,})", url)
    return f"https://drive.google.com/file/d/{m.group(1)}/view" if m else url


def is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def strip_tags(h: str) -> str:
    h = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html_lib.unescape(h)).strip()


def meta(html: str, prop: str) -> str:
    for pat in (
        rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']',
    ):
        m = re.search(pat, html, re.I)
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return ""


def fetch(url: str, timeout: int = 12) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return ""
        if (r.encoding or "").lower() in ("", "iso-8859-1"):
            r.encoding = "utf-8"
        return r.text
    except requests.RequestException:
        return ""


def fetch_json(url: str, params: dict = None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if r.status_code == 200 and "json" in r.headers.get("Content-Type", "").lower():
            return r.json()
    except (requests.RequestException, ValueError):
        pass
    return None


def web_search(query: str, max_results: int = 10, retries: int = 2) -> list:
    if DDGS is None:
        return []
    for i in range(retries + 1):
        try:
            res = list(DDGS().text(query, region="vn-vi", max_results=max_results))
            if res:
                return res
        except Exception as e:
            print(f"⚠️ Lỗi tìm kiếm (lần {i + 1}): {e}")
        time.sleep(2 * (i + 1))
    return []


def parse_json_loose(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


# ----------------------------------------------------------------------------
# KIỂM CHỨNG LINK
# ----------------------------------------------------------------------------
def check_pdf(url: str, save_path: str, max_mb: int = 40):
    """(link_ok, saved_locally). Kiểm tra magic bytes %PDF, tránh trang HTML lỗi giả dạng .pdf."""
    try:
        with requests.get(url, headers=HEADERS, timeout=20, stream=True) as r:
            if r.status_code != 200:
                return False, False
            chunks, size = [], 0
            for chunk in r.iter_content(65536):
                if not chunk:
                    continue
                if not chunks and b"%PDF" not in chunk[:1024]:
                    return False, False
                chunks.append(chunk)
                size += len(chunk)
                if size > max_mb * 1024 * 1024:
                    return True, False  # PDF thật nhưng nặng, chỉ giữ link
    except requests.RequestException:
        return False, False
    if size < 10_000:
        return False, False
    with open(save_path, "wb") as f:
        f.write(b"".join(chunks))
    return True, True


def verify_drive(url: str) -> bool:
    if not drive_id(url):
        return False
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
    except requests.RequestException:
        return False
    if r.status_code != 200 or "accounts.google.com" in r.url:
        return False
    return not any(m in r.text[:300_000] for m in DRIVE_BAD_MARKERS)


def verify_host(url: str) -> bool:
    """Kiểm tra mức cơ bản (link còn phản hồi) cho Mediafire/Dropbox/Fshare..."""
    try:
        with requests.get(url, headers=HEADERS, timeout=12, stream=True, allow_redirects=True) as r:
            return r.status_code < 400
    except requests.RequestException:
        return False


def extract_pdf_text(path: str, max_pages: int = 6, max_chars: int = 6000) -> str:
    if not path or not os.path.exists(path) or PdfReader is None:
        return ""
    try:
        reader = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages]).strip()[:max_chars]
    except Exception:
        return ""


# ----------------------------------------------------------------------------
# PHÂN TÍCH BÀI VIẾT
# ----------------------------------------------------------------------------
def extract_file_links(region_html: str, page_url: str) -> list:
    """Trả về [{'url','kind'}] với kind: pdf | drive | host, ưu tiên pdf > drive > host."""
    found, seen = [], set()
    site_host = host_of(page_url)

    def classify(u, label=""):
        h = host_of(u)
        if any(s in h for s in SOCIAL_DOMAINS):
            return None
        if is_pdf_url(u):
            return "pdf"
        if drive_id(u):
            return "drive"
        if any(f in h for f in FILE_HOSTS):
            return "host"
        if h != site_host and re.search(r"tải|download", label, re.I) and h not in ("google.com",):
            return "host"
        return None

    anchors = re.findall(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', region_html)
    extras = [(u, "") for u in re.findall(r'(?i)(?:src|data-src|data-url)=["\']([^"\']+)["\']', region_html)]
    extras += [(u, "") for u in re.findall(r'https?://[^\s\'"<>]+', region_html)]

    for href, label in anchors + extras:
        u = clean_url(urljoin(page_url, href))
        if not u.startswith("http"):
            continue
        kind = classify(u, strip_tags(label))
        if not kind:
            continue
        if kind == "drive":
            u = normalize_drive(u)
        if u not in seen:
            seen.add(u)
            found.append({"url": u, "kind": kind})

    order = {"pdf": 0, "drive": 1, "host": 2}
    return sorted(found, key=lambda x: order[x["kind"]])


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
        if key in s:
            return terms
    skip = {"vact", "đgnl", "thptqg", "thpt", "lớp", "12", "môn", "tài", "liệu"}
    return [w for w in re.findall(r"\w+", s) if w not in skip]


def is_relevant(text: str, terms: list) -> bool:
    """Đúng môn (nếu có chọn môn) và KHÔNG phải tài liệu lớp khác."""
    t = text.lower()
    if terms and not any(x in t for x in terms):
        return False
    if re.search(r"lớp\s*(?:[1-9]|10|11)\b", t) and "lớp 12" not in t and not any(g in t for g in GRADE_OK):
        return False
    return True


def looks_like_post(url: str, base: str) -> bool:
    p = urlparse(url)
    if host_of(url) != host_of(base) or not p.path.strip("/"):
        return False
    if any(x in p.path.lower() for x in NOT_POST_PATHS):
        return False
    return not re.search(r"\.(jpg|jpeg|png|gif|webp|svg|css|js|pdf|zip)$", p.path.lower())


# ----------------------------------------------------------------------------
# AGENT
# ----------------------------------------------------------------------------
class MaterialAgent:
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
        if not self.api_key:
            raise ValueError("❌ Không tìm thấy GEMINI_API_KEY! Hãy kiểm tra file .env hoặc Secrets.")

        self.client = genai.Client(api_key=self.api_key)
        self.materials_dir = os.path.join("knowledge_base", "materials")
        self.pdf_dir = os.path.join("knowledge_base", "pdfs")
        self.index_file = os.path.join("knowledge_base", "materials_index.json")
        self.sources_file = os.path.join("knowledge_base", "sources.json")
        os.makedirs(self.materials_dir, exist_ok=True)
        os.makedirs(self.pdf_dir, exist_ok=True)

    def _sources(self) -> list:
        sites = list(SOURCE_SITES)
        try:
            with open(self.sources_file, "r", encoding="utf-8") as f:
                sites += json.load(f)
        except Exception:
            pass
        return sites

    def _used_urls(self) -> set:
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {i.get("source_url") for i in data} | {i.get("post_url") for i in data}
        except Exception:
            return set()

    # ---------- 1. Lấy danh sách bài viết từ web nguồn ----------
    def _discover_posts(self, site: dict, terms: list) -> list:
        base = site["base"].rstrip("/")
        queries = terms[:3] or [""]
        posts = {}

        def add(url, title="", html=None):
            url = clean_url(url).split("#")[0]
            if url in posts:
                if title and not posts[url]["title"]:
                    posts[url]["title"] = title
                return
            posts[url] = {"url": url, "title": title, "html": html, "site": site["name"]}

        # (a) WordPress REST API: sạch và ổn định nhất nếu web bật
        for q in queries:
            data = fetch_json(f"{base}/wp-json/wp/v2/posts",
                              {"search": q, "per_page": 20, "_fields": "link,title,content"})
            for p in data or []:
                try:
                    add(p["link"], strip_tags(p["title"]["rendered"]), p["content"]["rendered"])
                except (KeyError, TypeError):
                    continue

        # (b) Trang tìm kiếm của web + các chuyên mục bạn khai báo
        listing_pages = [f"{base}/?s={quote_plus(q)}" for q in queries if q]
        listing_pages += site.get("category_urls", [])
        for pg in listing_pages:
            html = fetch(pg)
            for href, label in re.findall(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html):
                u = clean_url(urljoin(pg, href))
                if looks_like_post(u, base):
                    add(u, strip_tags(label))

        # (c) Không ra gì thì thử DuckDuckGo giới hạn trong chính web đó
        if not posts:
            for q in queries:
                for res in web_search(f"site:{host_of(base)} {q}"):
                    if looks_like_post(res.get("href", ""), base):
                        add(res["href"], res.get("title", ""))

        print(f"📚 {site['name']}: tìm thấy {len(posts)} bài ứng viên")
        return list(posts.values())

    # ---------- 2. Mở từng bài, trích + kiểm chứng link ----------
    def hunt_real_material_link(self, subject: str = ""):
        terms = subject_terms(subject)
        used = self._used_urls()
        mat_id = f"mat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pdf_path = os.path.join(self.pdf_dir, f"{mat_id}.pdf")

        posts = []
        for site in self._sources():
            posts += self._discover_posts(site, terms)
        posts = [p for p in posts if p["url"] not in used]
        posts.sort(key=lambda p: -sum(t in p["title"].lower() for t in terms))

        fallback = None
        for post in posts[:MAX_POSTS_TO_OPEN]:
            html = post["html"] or fetch(post["url"])
            info = parse_post(html, post["url"], post["title"])
            if post["html"] and not info["links"]:  # nội dung REST thiếu nút tải -> mở trang đầy đủ
                full = fetch(post["url"])
                if full:
                    info = parse_post(full, post["url"], post["title"])
            if not info["title"] or not is_relevant(f"{info['title']} {info['text']}", terms):
                continue

            result = {
                "mat_id": mat_id, "site": post["site"], "post_url": post["url"],
                "post_title": info["title"], "excerpt": f"{info['description']}\n{info['text']}"[:2000],
                "thumbnail": info["thumbnail"],
            }
            if fallback is None:
                fallback = {**result, "source_url": post["url"], "link_type": "post_page", "pdf_local_path": ""}

            for link in info["links"]:
                if link["url"] in used:
                    continue
                local = ""
                if link["kind"] == "pdf":
                    ok, saved = check_pdf(link["url"], pdf_path)
                    local = pdf_path if saved else ""
                elif link["kind"] == "drive":
                    ok = verify_drive(link["url"])
                else:
                    ok = verify_host(link["url"])
                if ok:
                    print(f"🎯 [{post['site']}] {info['title']}\n   ↳ file {link['kind']}: {link['url']}")
                    return {**result, "source_url": link["url"], "link_type": link["kind"],
                            "pdf_local_path": local}
                print(f"   ✗ link chết/riêng tư: {link['url']}")

        if fallback and ALLOW_POST_PAGE_FALLBACK:
            print(f"ℹ️ Không có link file kiểm chứng được, dùng link bài viết thật: {fallback['source_url']}")
            return fallback
        return None

    # ---------- 3. Đóng gói bằng AI ----------
    def collect_and_package_material(self, subject: str = ""):
        found = self.hunt_real_material_link(subject)
        if not found:
            print("❌ Không tìm được tài liệu phù hợp từ các web nguồn. "
                  "Hãy thêm URL chuyên mục vào category_urls hoặc thử môn khác.")
            return None

        pdf_text = extract_pdf_text(found["pdf_local_path"])
        subject_label = subject or "Ôn thi THPT Quốc gia lớp 12"

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
- Chỉ dựa trên dữ liệu ở trên. Tài liệu thuộc chủ đề nào thì giữ đúng chủ đề đó, tuyệt đối không
  chuyển sang môn/chủ đề khác. Không bịa số lượng, tên tác giả, nội dung không có trong dữ liệu.
- "sample_content" chỉ trích nguyên văn từ dữ liệu thật ở trên; không có thì để chuỗi rỗng.

Hãy đóng gói tài liệu này cho bài đăng Facebook Tặng Tài Liệu (Lead Gen).
Chỉ trả về JSON với các khóa:
{{
  "title": "Tên tài liệu hấp dẫn, bám sát tiêu đề gốc",
  "target_audience": "Học sinh lớp 12 (2k9) ôn thi THPT Quốc gia",
  "key_highlights": ["3-4 điểm nổi bật, chỉ dựa trên dữ liệu thật"],
  "sample_content": "2-3 ý/câu trích từ nội dung thật để làm Quiz, hoặc rỗng",
  "cta_keyword": "Từ khóa comment ngắn, liên quan tài liệu"
}}
"""
        print("🤖 Material Agent đang dùng AI biên soạn thông tin...")
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
                print(f"✅ Biên soạn thành công với Model: {model_name}")
                break
            except Exception as e:
                print(f"⚠️ Thử Model {model_name} thất bại ({e})...")
                last_error = e
        if not response:
            raise RuntimeError(f"Không thể đóng gói thông tin tài liệu. Lỗi: {last_error}")

        data = parse_json_loose(response.text)
        # Các trường "sự thật" do code ghi đè, AI không được đụng vào
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
        data.setdefault("cta_keyword", subject_label)

        path = os.path.join(self.materials_dir, f"{data['material_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._update_index(data)

        print(f"\n🎉 Đã lưu: {data.get('title')}")
        print(f"🔗 LINK ({data['link_type']}): {data['source_url']}")
        return data

    def _update_index(self, d: dict):
        index = []
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                index = []
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
    # subject="" = lấy bất kỳ môn nào; hoặc "Toán", "Tiếng Anh", "Vật lý"...
    mat = agent.collect_and_package_material("Toán")
    print("\n--- BÁO CÁO TÀI LIỆU ĐÃ TÌM THẤY ---")
    print(json.dumps(mat, ensure_ascii=False, indent=2) if mat else "Không tìm thấy tài liệu hợp lệ.")