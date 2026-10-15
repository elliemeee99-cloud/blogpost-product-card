import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import re
import base64
from urllib.parse import urljoin
from PIL import Image, ImageOps
from io import BytesIO

# ================= 配置与初始化 =================
st.set_page_config(page_title="Banner与推送测试", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp { background-color: #F8F9FA; color: #202124; font-family: 'Google Sans', 'Roboto', -apple-system, sans-serif; }
p, span, label { color: #5F6368 !important; }
h1, h2, h3, h4 { font-family: 'Google Sans', 'Roboto', sans-serif !important; color: #202124 !important; font-weight: 500 !important; }
h1 { font-size: 1.8rem !important; padding-bottom: 0.5rem; }
h3 { font-size: 1.2rem !important; }
[data-testid="block-container"] { padding-top: 2rem !important; padding-bottom: 4rem !important; max-width: 1280px; }

[data-testid="stPageLink-NavLink"] { background-color: #FFFFFF; border-radius: 8px; padding: 10px 20px; border: 1px solid #E5E7EB; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05); transition: all 0.2s ease; justify-content: center; font-weight: 500; }
[data-testid="stPageLink-NavLink"]:hover { border-color: #1A73E8; color: #1A73E8 !important; }

/* 强制修复主按钮与表单提交按钮的白色字体 */
.stButton > button { border-radius: 8px !important; border: none !important; font-weight: 600 !important; padding: 8px 16px !important; transition: all 0.2s ease !important; }
button[kind="primary"], button[kind="primaryFormSubmit"], div[data-testid="stForm"] button { 
    background-color: #1A73E8 !important; 
    color: #FFFFFF !important; 
    box-shadow: 0 1px 2px rgba(26, 115, 232, 0.2) !important; 
    border: none !important;
}
button[kind="primary"] *, button[kind="primaryFormSubmit"] *, div[data-testid="stForm"] button * { 
    color: #FFFFFF !important; 
    fill: #FFFFFF !important; 
}
button[kind="primary"]:hover, div[data-testid="stForm"] button:hover { 
    background-color: #174EA6 !important; 
    transform: translateY(-1px); 
}

.stButton > button[kind="secondary"] { background: #FFFFFF !important; color: #374151 !important; border: 1px solid #D1D5DB !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
.stButton > button[kind="secondary"] * { color: #374151 !important; }
.stButton > button[kind="secondary"]:hover { background: #F3F4F6 !important; border-color: #9CA3AF !important; }

.stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { border-radius: 8px !important; border: 1px solid #D1D5DB !important; background-color: #FFFFFF !important; padding: 10px 12px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
.stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus, .stSelectbox>div>div>div:focus { border-color: #1A73E8 !important; box-shadow: 0 0 0 1px #1A73E8 !important; }

[data-testid="stForm"], [data-testid="stExpander"] { background-color: #FFFFFF; border-radius: 12px !important; border: 1px solid #E5E7EB !important; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06) !important; padding: 20px !important; }
[data-testid="stAlert"] { border-radius: 8px !important; border: 1px solid #E5E7EB !important; background-color: #FFFFFF !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; border-left: 4px solid #1A73E8 !important; }

.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid #E5E7EB; padding-bottom: 0px; }
.stTabs [data-baseweb="tab"] { padding: 12px 16px !important; background-color: transparent; border: none !important; color: #6B7280; font-weight: 500; }
.stTabs [aria-selected="true"] { color: #1A73E8 !important; border-bottom: 2px solid #1A73E8 !important; font-weight: 600; }

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

nav_col1, nav_col2, _ = st.columns([1.5, 1.5, 7])
with nav_col1: st.page_link("app.py", label="📇 核心：商品卡片生成器", use_container_width=True)
with nav_col2: st.page_link("pages/banner_test.py", label="🖼️ 测试：Banner与WP发布", use_container_width=True)
st.markdown("<br>", unsafe_allow_html=True)

st.title("🖼️ Banner 生成与 WordPress 直推测试区")

if "DEEPSEEK_API_KEY" in st.secrets:
    client_ds = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 DeepSeek API Key")
    st.stop()

if "b_step" not in st.session_state: st.session_state.b_step = 1
if "b_pool" not in st.session_state: st.session_state.b_pool = []
if "b_selected_keys" not in st.session_state: st.session_state.b_selected_keys = []
if "b_banner_bytes" not in st.session_state: st.session_state.b_banner_bytes = None

dummy_image = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22400%22%20fill%3D%22%23F3F4F6%22%2F%3E"

# ================= 数据抓取与过滤函数 =================
def get_soup(url):
    try: return BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15).text, 'lxml')
    except: return None

def fetch_blog_context(blog_url):
    soup = get_soup(blog_url)
    return soup.get_text(separator='\n', strip=True)[:4000] if soup else ""

def fetch_product_list(category_url):
    soup = get_soup(category_url)
    if not soup: return []
    seen, products = set(), []
    for a in soup.find_all('a', href=True):
        title, clean_url = a.get_text(strip=True), urljoin(category_url, a['href']).split('?')[0]
        if len(title) > 5 and clean_url not in seen and "javascript" not in clean_url:
            img = a.find('img') or (a.parent and a.parent.find('img')) or (a.parent and a.parent.parent and a.parent.parent.find('img'))
            if img and (img.get('data-src') or img.get('src')):
                src = img.get('data-src') or img.get('src')
                if not any(x in str(src).lower() for x in ['logo', 'icon', 'svg', 'gif']):
                    seen.add(clean_url)
                    img_url = urljoin(category_url, src).split('?')[0]
                    products.append({"title": title, "url": clean_url, "thumbnail": img_url, "candidate_key": f"{clean_url}###0"})
                    if len(products) >= 60: break
    return products

def ai_match_top_30(blog_text, product_list):
    prompt = f"""Select AS MANY relevant products as possible (up to 30). Blog Post: {blog_text[:3000]} Candidates: {json.dumps(product_list, ensure_ascii=False)} Output JSON array only."""
    try:
        res = client_ds.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"} if "json" in prompt.lower() else None, max_tokens=4000).choices[0].message.content.strip()
        if res.startswith("```"): res = res.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        return json.loads(res)
    except: return product_list[:30]

def fetch_direct_urls(url_list_text):
    urls = [u.strip() for u in url_list_text.split('\n') if u.strip().startswith('http')]
    candidates = []
    bad_keywords = ['logo', 'icon', 'svg', 'gif', 'badge', 'avatar', 'footer', 'header', 'menu', 
                    'video', 'play', 'mp4', 'youtube', 'vimeo', 'trust', 'payment', 
                    'related', 'recommend', 'upsell', 'cross', 'recent', 'history', 
                    'review', 'testimonial', 'popup', 'modal', 'cart', 'bottom', 'sidebar', 'nav']
    for url in urls:
        clean_url = url.split('?')[0]
        soup = get_soup(clean_url)
        if soup:
            title = (soup.title.string if soup.title else "未命名商品").replace('\n', ' ').strip()
            valid_imgs = []
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                valid_imgs.append(urljoin(clean_url, og_img['content']).split('?')[0])
            
            for img in soup.find_all('img'):
                src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                if not src: continue
                parent, is_bad, depth = img.parent, False, 0
                while parent and depth < 5:
                    p_class = " ".join(parent.get('class', [])).lower()
                    p_id = (parent.get('id') or '').lower()
                    if any(x in p_class or x in p_id for x in bad_keywords):
                        is_bad = True
                        break
                    parent = parent.parent
                    depth += 1
                if is_bad: continue
                
                src_lower = str(src).lower()
                img_class = " ".join(img.get('class', [])).lower()
                if any(x in src_lower or x in img_class for x in bad_keywords): continue
                if not any(ext in src_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']): continue
                
                full_url = urljoin(clean_url, src).split('?')[0]
                if ('uploads' in full_url.lower() or 'product' in full_url.lower()) and full_url not in valid_imgs:
                    valid_imgs.append(full_url)
            
            if not valid_imgs: valid_imgs.append(dummy_image)
            for idx, img_url in enumerate(valid_imgs[:4]):
                candidates.append({"title": title, "url": clean_url, "thumbnail": img_url, "candidate_key": f"{clean_url}###{idx}"})
    return candidates

# ================= 图像下载与处理辅助函数 =================
def download_product_images(image_urls):
    """下载选中的商品原图，转为标准 RGB JPEG 字节流与 PIL 对象"""
    pil_imgs, bytes_list = [], []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in image_urls[:4]:
        if url.startswith("data:image"): continue
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                pil_imgs.append(img)
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=90)
                bytes_list.append(buf.getvalue())
        except Exception:
            continue
    return pil_imgs, bytes_list

def format_to_banner_size(img_bytes, force_1200x630=True):
    """将生成的图片统一转换为标准 JPEG，可选智能居中裁剪为 1200x630 横版 Banner"""
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    if force_1200x630:
        img = ImageOps.fit(img, (1200, 630), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()

def create_banner_collage(image_urls):
    pil_imgs, _ = download_product_images(image_urls)
    if not pil_imgs: return None
    banner = Image.new('RGB', (1200, 630), (255, 255, 255))
    w_per_img = 1200 // len(pil_imgs)
    for i, img in enumerate(pil_imgs):
        banner.paste(ImageOps.fit(img, (w_per_img, 630), Image.Resampling.LANCZOS), (i * w_per_img, 0))
    buf = BytesIO()
    banner.save(buf, format="JPEG", quality=88)
    return buf.getvalue()

# ================= 核心：Gemini 与 OpenAI 生图引擎 =================
def generate_banner_gemini(prompt: str, ref_images_bytes: list, api_key: str, model_choice: str) -> bytes:
    api_key = api_key.strip()
    if not api_key:
        raise Exception("未读取到 GEMINI_API_KEY，请检查 Secrets 配置。")

    headers = {"Content-Type": "application/json"}

    # 通道 A：多模态参考图生成 (支持直接传入抓到的商品图片)
    if "flash-image" in model_choice:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_choice}:generateContent?key={api_key}"
        parts = []
        for img_b in ref_images_bytes:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(img_b).decode("utf-8")
                }
            })
        parts.append({
            "text": f"Create a wide horizontal 16:9 e-commerce blog banner image incorporating the exact products shown in the reference images. {prompt}"
        })
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
        }
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        if res.status_code != 200:
            raise Exception(f"Gemini 接口返回错误 ({res.status_code}): {res.text}")
        
        data = res.json()
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        raise Exception(f"Gemini 未返回图片数据，响应内容: {json.dumps(data, ensure_ascii=False)[:300]}")

    # 通道 B：Imagen 3 纯文本生成
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_choice}:predict?key={api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9", "outputOptions": {"mimeType": "image/jpeg"}}
        }
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        if res.status_code != 200:
            raise Exception(f"Imagen 接口返回错误 ({res.status_code}): {res.text}")
        data = res.json()
        preds = data.get("predictions", [])
        if preds and preds[0].get("bytesBase64Encoded"):
            return base64.b64decode(preds[0]["bytesBase64Encoded"])
        raise Exception(f"Imagen 未返回图片数据: {res.text[:300]}")


def generate_banner_openai(prompt: str, ref_images_bytes: list, api_key: str, base_url: str, model_name: str) -> bytes:
    api_key = api_key.strip()
    base_url = (base_url.strip() or "https://api.openai.com/v1").rstrip("/")
    if not api_key:
        raise Exception("未读取到 OPENAI_API_KEY，请检查 Secrets 配置。")

    headers = {"Authorization": f"Bearer {api_key}"}

    # 1. 若选择 gpt-image-1 且有商品原图，优先调用 /images/edits 传入商品原图进行融合生图
    if model_name == "gpt-image-1" and ref_images_bytes:
        edit_url = f"{base_url}/images/edits"
        files = [("image[]", (f"product_{i}.jpg", BytesIO(b), "image/jpeg")) for i, b in enumerate(ref_images_bytes)]
        data_form = {
            "model": "gpt-image-1",
            "prompt": f"Create a wide horizontal e-commerce blog banner featuring the exact products in the reference images. {prompt}",
            "size": "1536x1024",
            "n": "1"
        }
        res = requests.post(edit_url, headers=headers, data=data_form, files=files, timeout=90)
        if res.status_code == 200:
            item = res.json()["data"][0]
            if item.get("b64_json"): return base64.b64decode(item["b64_json"])
            if item.get("url"): return requests.get(item["url"], timeout=30).content

    # 2. 标准生成接口（带自动模型回退）
    gen_url = f"{base_url}/images/generations"
    models_to_try = [model_name] + [m for m in ["gpt-image-1", "dall-e-3", "dall-e-2"] if m != model_name]
    last_error = ""

    for m in models_to_try:
        payload = {"model": m, "prompt": prompt, "n": 1}
        if m == "dall-e-3":
            payload["size"] = "1792x1024"
        elif m == "gpt-image-1":
            payload["size"] = "1536x1024"
        else:
            payload["size"] = "1024x1024"

        res = requests.post(gen_url, headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=90)
        if res.status_code == 200:
            item = res.json()["data"][0]
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"])
            elif item.get("url"):
                return requests.get(item["url"], timeout=30).content
        else:
            last_error = f"[{m}] HTTP {res.status_code}: {res.text}"
            if "does not exist" in res.text or "invalid_value" in res.text or "model_not_found" in res.text:
                continue
            else:
                break

    raise Exception(f"OpenAI 生图请求失败: {last_error}")


# ================= WordPress 推送函数 =================
def push_to_wordpress(wp_url, username, password, title, banner_bytes, post_id=""):
    base_api = wp_url.rstrip('/') + '/wp-json/wp/v2'
    auth, media_id, media_url = (username, password), None, ""
    
    if banner_bytes:
        try:
            res_media = requests.post(f"{base_api}/media", headers={'Content-Type': 'image/jpeg', 'Content-Disposition': 'attachment; filename="callie-banner.jpg"'}, data=banner_bytes, auth=auth, timeout=30)
            if res_media.status_code in [200, 201]: media_id, media_url = res_media.json().get('id'), res_media.json().get('source_url')
            else: return False, f"图片上传失败: {res_media.text}"
        except Exception as e: return False, f"图片上传异常: {e}"

    try:
        if post_id.strip():
            post_endpoint = f"{base_api}/posts/{post_id.strip()}"
            res_get = requests.get(f"{post_endpoint}?context=edit", auth=auth, timeout=15, allow_redirects=True)
            if res_get.status_code == 404:
                post_endpoint = f"{base_api}/pages/{post_id.strip()}"
                res_get = requests.get(f"{post_endpoint}?context=edit", auth=auth, timeout=15, allow_redirects=True)
                
            if res_get.status_code != 200: return False, "无法读取原文章。"
            
            real_endpoint = res_get.url.split('?')[0]
            current_content = res_get.json().get('content', {}).get('raw', '')
            
            if media_url: current_content = f'\n<!-- wp:html -->\n<p style="text-align:center;"><img src="{media_url}" alt="Blog Banner" style="max-width:100%; height:auto; border-radius:12px; margin-bottom:20px;"/></p>\n<!-- /wp:html -->\n' + current_content
            update_data = {'content': current_content}
            if title: update_data['title'] = title
            if media_id: update_data['featured_media'] = media_id
            
            res_post = requests.post(real_endpoint, json=update_data, auth=auth, timeout=30, allow_redirects=False)
            if res_post.status_code in [301, 302, 307, 308]:
                res_post = requests.post(res_post.headers.get('Location'), json=update_data, auth=auth, timeout=30, allow_redirects=False)
            action_text = "更新特定文章"
        else:
            banner_html = f'\n<!-- wp:html -->\n<p style="text-align:center;"><img src="{media_url}" alt="Blog Banner" style="max-width:100%; height:auto; border-radius:12px; margin-bottom:20px;"/></p>\n<!-- /wp:html -->\n' if media_url else ""
            post_data = {'title': title, 'content': banner_html, 'status': 'draft'}
            if media_id: post_data['featured_media'] = media_id 
            res_post = requests.post(f"{base_api}/posts", json=post_data, auth=auth, timeout=30)
            action_text = "新建草稿"
            
        if res_post.status_code in [200, 201]: return True, f"{action_text}成功并写入！"
        else: return False, f"{action_text}失败: {res_post.text}"
    except Exception as e: return False, f"发布异常: {e}"

# ================= UI 布局 =================

st.markdown("### 步骤 1：输入数据源获取商品图片")
tab_b1, tab_b2 = st.tabs(["🤖 AI 智能海选模式", "🔗 手动直达模式"])

with tab_b1:
    col1, col2 = st.columns(2)
    with col1: b_blog_url = st.text_input("博客文章链接", placeholder="用于语义匹配分析", key="b_blog")
    with col2: b_shop_url = st.text_input("商品列表页链接", placeholder="用于抓取候选商品", key="b_shop")
    if st.button("🔍 抓取并智能海选", type="primary", key="b_btn_ai"):
        if not b_blog_url or not b_shop_url: st.warning("请填写完整的两个链接！")
        else:
            with st.spinner("正在抓取博客和候选商品..."):
                blog_text = fetch_blog_context(b_blog_url)
                raw_pool = fetch_product_list(b_shop_url)
            if not raw_pool: st.error("未能抓取到有效图片，请检查链接。")
            else:
                with st.spinner("正在请求 AI 海选..."):
                    matched = ai_match_top_30(blog_text, raw_pool)
                    extracted = matched.values() if isinstance(matched, dict) else [matched]
                    valid_pool = [item for sublist in extracted if isinstance(sublist, list) for item in sublist if isinstance(item, dict) and "url" in item]
                    for idx, p in enumerate(valid_pool):
                        p.setdefault("thumbnail", dummy_image)
                        p.setdefault("candidate_key", f"{p['url']}###{idx}")
                    if valid_pool:
                        st.session_state.b_pool = valid_pool
                        st.session_state.b_step = 2
                        st.session_state.b_banner_bytes = None
                        st.rerun()

with tab_b2:
    st.info("💡 直接填入商品链接提取图片 (一行一个，每个商品自动提取前 4 张纯净商品图)")
    b_direct_urls = st.text_area("输入商品链接：", height=150)
    if st.button("🚀 获取商品图片", type="primary", key="b_btn_direct"):
        if b_direct_urls.strip():
            with st.spinner("正在解析商品相册图片..."):
                st.session_state.b_pool = fetch_direct_urls(b_direct_urls)
                st.session_state.b_step = 2
                st.session_state.b_banner_bytes = None
                st.rerun()

if st.session_state.b_step >= 2 and st.session_state.b_pool:
    st.markdown("---")
    st.markdown("### 步骤 2：选择用于生成 Banner 的商品图 (建议勾选 1-4 张)")
    with st.form("b_selection_form"):
        b_temp_selected = []
        cols_per_row = 8
        for i in range(0, len(st.session_state.b_pool), cols_per_row):
            row_items = st.session_state.b_pool[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for col, item in zip(cols, row_items):
                with col:
                    st.image(item["thumbnail"], use_container_width=True)
                    c_key = item.get("candidate_key", item["url"])
                    if st.checkbox("选中此图", key=f"b_chk_{c_key}"):
                        b_temp_selected.append(c_key)
        if st.form_submit_button("➡️ 确认所选，进入 Banner 生成", type="primary"):
            if not b_temp_selected: st.warning("请至少勾选一张商品图！")
            else:
                st.session_state.b_selected_keys = b_temp_selected
                st.session_state.b_step = 3
                st.rerun()

if st.session_state.b_step >= 3 and st.session_state.b_selected_keys:
    st.markdown("---")
    st.markdown("### 步骤 3：一键生成 Banner 与推送到 WordPress")
    
    selected_items = [p for p in st.session_state.b_pool if p.get("candidate_key", p["url"]) in st.session_state.b_selected_keys]
    selected_img_urls = [item["thumbnail"] for item in selected_items]
    selected_titles = list(dict.fromkeys([item.get("title", "")[:40] for item in selected_items if item.get("title")]))
    
    col_b1, col_b2 = st.columns([1, 1], gap="large")
    with col_b1:
        st.info(f"🖼️ 已选中 **{len(selected_img_urls)}** 张商品原图。AI 模式下会自动将商品原图喂给模型进行场景合成。")
        
        banner_mode = st.radio(
            "选择生成方式：", 
            ["✨ Gemini 多模态生图 (原生参考图融合)", "🤖 ChatGPT / OpenAI 生图", "🧩 原图智能拼接 (快速免费)"], 
            horizontal=True
        )
        
        if banner_mode.startswith("🧩"):
            if st.button("🎨 1. 生成拼接 Banner", type="secondary"):
                with st.spinner("下载原图并拼接中..."):
                    banner_data = create_banner_collage(selected_img_urls)
                    if banner_data:
                        st.session_state.b_banner_bytes = banner_data
                        st.success("✅ 拼接 Banner 生成成功！")
                    else: st.error("拼图失败，请检查原图链接是否可访问。")
        else:
            default_prompt = (
                f"A warm, aesthetic lifestyle blog banner photography featuring these personalized gift products ({'; '.join(selected_titles)}). "
                f"Cozy Nordic home setting, soft natural lighting, high resolution, photorealistic, no text overlay."
            )
            
            if banner_mode.startswith("✨"):
                gem_key = st.secrets.get("GEMINI_API_KEY", "")
                if gem_key:
                    st.caption("🔒 已从 Secrets 自动加载 `GEMINI_API_KEY`")
                else:
                    gem_key = st.text_input("🔑 输入 GEMINI_API_KEY:", type="password")
                
                gem_model = st.selectbox(
                    "🤖 选择 Gemini 生图模型：",
                    ["gemini-2.5-flash-image", "gemini-2.0-flash-exp-image-generation", "imagen-3.0-generate-002"],
                    help="推荐使用 gemini-2.5-flash-image，支持直接读取你勾选的商品原图并融合到新背景中！"
                )
            else:
                oai_key = st.secrets.get("OPENAI_API_KEY", "")
                oai_base = st.secrets.get("OPENAI_PROXY_URL", "https://api.openai.com/v1")
                if oai_key:
                    st.caption("🔒 已从 Secrets 自动加载 `OPENAI_API_KEY`")
                with st.expander("⚙️ OpenAI 接口与模型设置", expanded=not bool(oai_key)):
                    oai_key = st.text_input("🔑 OPENAI_API_KEY:", value=oai_key, type="password")
                    oai_base = st.text_input("🔗 Base URL:", value=oai_base)
                    oai_model = st.selectbox(
                        "🤖 选择 OpenAI 模型：",
                        ["gpt-image-1", "dall-e-3"],
                        help="gpt-image-1 支持传入商品参考图；若账号未开通指定模型，系统会自动尝试回退。"
                    )

            ai_prompt = st.text_area("输入生图提示词 (支持中英文)：", value=default_prompt, height=100)
            force_crop = st.checkbox("📐 自动适配为 1200×630 标准 Blog Banner 比例", value=True)
            
            if st.button("✨ 1. 结合所选商品图生成 AI Banner", type="primary"):
                if not ai_prompt.strip():
                    st.warning("提示词不能为空！")
                else:
                    with st.spinner("正在下载商品参考图并呼叫 AI 绘图 (约需 15-30 秒)..."):
                        try:
                            _, ref_bytes = download_product_images(selected_img_urls)
                            if banner_mode.startswith("✨"):
                                raw_bytes = generate_banner_gemini(ai_prompt, ref_bytes, gem_key, gem_model)
                            else:
                                raw_bytes = generate_banner_openai(ai_prompt, ref_bytes, oai_key, oai_base, oai_model)
                            
                            st.session_state.b_banner_bytes = format_to_banner_size(raw_bytes, force_crop)
                            st.success("✅ AI Banner 生成成功！")
                        except Exception as e:
                            st.error(f"生图失败：{str(e)}")

        if st.session_state.b_banner_bytes:
            st.image(st.session_state.b_banner_bytes, caption="已生成的 Banner 预览图 (1200×630)")

    with col_b2:
        st.info("🚀 选择目标网站，自动更新指定文章或新建博客草稿。")
        my_wp_sites = {"🇩🇪 德语站": "DE", "🇫🇷 法语站": "FR", "🇪🇸 西班牙站": "ES", "🇮🇹 意大利站": "IT", "🇳🇱 荷兰站": "NL", "🇳🇴 挪威站": "NO", "🇸🇪 瑞典站": "SE", "🇫🇮 芬兰站": "FI", "🇵🇱 波兰站": "PL"}
        site_urls = {"DE": "https://www.callie.de/blog", "FR": "https://fr.callie.com/blog", "ES": "https://www.callie.es/blog", "IT": "https://it.callie.com/blog", "NL": "https://nl.callie.com/blog", "NO": "https://no.callie.com/blog", "SE": "https://www.callie.se/blog", "FI": "https://www.callie.fi/blog", "PL": "https://pl.callie.com/blog"}
        
        selected_site_name = st.selectbox("🎯 请选择要发布的网站：", list(my_wp_sites.keys()))
        site_prefix = my_wp_sites[selected_site_name]
        wp_url = site_urls[site_prefix]
        
        # 静默加载默认账号与对应站点密码，不再展示账号输入框
        user_key = "WP_USER"
        pass_key = f"WP_PASS_{site_prefix}"
        
        if user_key in st.secrets and pass_key in st.secrets:
            st.success("🔒 凭证已自动加载")
            wp_user = st.secrets[user_key]
            wp_pass = st.secrets[pass_key]
        else:
            st.warning(f"⚠️ 缺少 {pass_key}，请前往后台 Secrets 添加。")
            c1, c2 = st.columns(2)
            with c1: wp_user = st.text_input("用户名", value=st.secrets.get("WP_USER", ""))
            with c2: wp_pass = st.text_input("应用密码", type="password")
            
        post_title = st.text_input("📝 博客标题 (新建草稿时使用)", value="🔥 自动 Banner 推送测试")
        target_post_id = st.text_input("🎯 指定文章 ID (可选)", help="留空则每次新建草稿。如果想更新已有的文章，请填入该文章的 ID。")
        
        if st.button("🚀 2. 推送并强制校验", type="primary"):
            if not st.session_state.b_banner_bytes: st.warning("请先在左侧点击生成 Banner！")
            elif not wp_user or not wp_pass: st.warning("请配置或填完所有的 WordPress 验证信息！")
            else:
                with st.spinner("正在穿透跳转保护进行推送..."):
                    success, msg = push_to_wordpress(wp_url, wp_user, wp_pass, post_title, st.session_state.b_banner_bytes, target_post_id)
                    if success: st.success(f"🎉 {msg}")
                    else: st.error(msg)
