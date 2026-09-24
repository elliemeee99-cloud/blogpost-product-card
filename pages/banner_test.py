import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import re
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

.stButton > button { border-radius: 8px !important; border: none !important; font-weight: 600 !important; padding: 8px 16px !important; transition: all 0.2s ease !important; }
.stButton > button[kind="primary"] { background-color: #1A73E8 !important; color: white !important; box-shadow: 0 1px 2px rgba(26, 115, 232, 0.2) !important; }
.stButton > button[kind="primary"]:hover { background-color: #174EA6 !important; transform: translateY(-1px); }
.stButton > button[kind="secondary"] { background: #FFFFFF !important; color: #374151 !important; border: 1px solid #D1D5DB !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
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
    client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key")
    st.stop()

if "b_step" not in st.session_state: st.session_state.b_step = 1
if "b_pool" not in st.session_state: st.session_state.b_pool = []
if "b_urls" not in st.session_state: st.session_state.b_urls = []
if "b_banner_bytes" not in st.session_state: st.session_state.b_banner_bytes = None

dummy_image = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22400%22%20fill%3D%22%23F3F4F6%22%2F%3E"

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
                seen.add(clean_url)
                products.append({"title": title, "url": clean_url, "thumbnail": urljoin(category_url, img.get('data-src') or img.get('src')).split('?')[0]})
                if len(products) >= 60: break
    return products

def ai_match_top_30(blog_text, product_list):
    prompt = f"""Select AS MANY relevant products as possible (up to 30). Blog Post: {blog_text[:3000]} Candidates: {json.dumps(product_list, ensure_ascii=False)} Output JSON array only."""
    try:
        res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"} if "json" in prompt.lower() else None, max_tokens=4000).choices[0].message.content.strip()
        if res.startswith("```"): res = res.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        return json.loads(res)
    except: return product_list[:30]

def fetch_direct_urls(url_list_text):
    products = []
    for url in [u.strip() for u in url_list_text.split('\n') if u.strip().startswith('http')]:
        clean_url = url.split('?')[0]
        soup = get_soup(clean_url)
        if soup:
            og_img = soup.find('meta', property='og:image')
            products.append({"title": soup.title.string if soup.title else "未命名商品", "url": clean_url, "thumbnail": urljoin(clean_url, og_img['content']).split('?')[0] if og_img and og_img.get('content') else dummy_image})
    return products

def create_banner_collage(image_urls):
    imgs = [Image.open(BytesIO(requests.get(url, timeout=5).content)).convert("RGB") for url in image_urls[:4] if not url.startswith("data:image") and requests.get(url, timeout=5).status_code == 200]
    if not imgs: return None
    banner = Image.new('RGB', (1200, 630), (255, 255, 255))
    w_per_img = 1200 // len(imgs)
    for i, img in enumerate(imgs): banner.paste(ImageOps.fit(img, (w_per_img, 630), Image.Resampling.LANCZOS), (i * w_per_img, 0))
    buf = BytesIO()
    banner.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

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
            res_get = requests.get(f"{base_api}/posts/{post_id.strip()}?context=edit", auth=auth, timeout=15)
            if res_get.status_code != 200: return False, "无法读取原文章。"
            current_content = res_get.json().get('content', {}).get('raw', '')
            if media_url: current_content = f'\n<!-- wp:html -->\n<p style="text-align:center;"><img src="{media_url}" alt="Blog Banner" style="max-width:100%; height:auto; border-radius:12px; margin-bottom:20px;"/></p>\n<!-- /wp:html -->\n' + current_content
            update_data = {'content': current_content}
            if title: update_data['title'] = title
            if media_id: update_data['featured_media'] = media_id
            res_post = requests.post(f"{base_api}/posts/{post_id.strip()}", json=update_data, auth=auth, timeout=30)
            action_text = "更新特定文章"
        else:
            banner_html = f'\n<!-- wp:html -->\n<p style="text-align:center;"><img src="{media_url}" alt="Blog Banner" style="max-width:100%; height:auto; border-radius:12px; margin-bottom:20px;"/></p>\n<!-- /wp:html -->\n' if media_url else ""
            post_data = {'title': title, 'content': banner_html, 'status': 'draft'}
            if media_id: post_data['featured_media'] = media_id 
            res_post = requests.post(f"{base_api}/posts", json=post_data, auth=auth, timeout=30)
            action_text = "新建草稿"
            
        if res_post.status_code in [200, 201]: return True, f"{action_text}成功！"
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
                with st.spinner(f"正在请求 AI 海选..."):
                    matched = ai_match_top_30(blog_text, raw_pool)
                    extracted = matched.values() if isinstance(matched, dict) else [matched]
                    valid_pool = [item for sublist in extracted if isinstance(sublist, list) for item in sublist if isinstance(item, dict) and "url" in item]
                    for p in valid_pool: p.setdefault("thumbnail", dummy_image)
                    if valid_pool:
                        st.session_state.b_pool = valid_pool
                        st.session_state.b_step = 2
                        st.session_state.b_banner_bytes = None
                        st.rerun()

with tab_b2:
    st.info("💡 直接填入商品链接提取图片 (一行一个)")
    b_direct_urls = st.text_area("输入商品链接：", height=150)
    if st.button("🚀 获取商品图片", type="primary", key="b_btn_direct"):
        if b_direct_urls.strip():
            with st.spinner("正在解析图片..."):
                st.session_state.b_pool = fetch_direct_urls(b_direct_urls)
                st.session_state.b_step = 2
                st.session_state.b_banner_bytes = None
                st.rerun()

if st.session_state.b_step >= 2 and st.session_state.b_pool:
    st.markdown("---")
    st.markdown("### 步骤 2：选择用于生成 Banner 的商品 (建议 2-4 个)")
    with st.form("b_selection_form"):
        b_temp_selected = []
        cols_per_row = 8
        for i in range(0, len(st.session_state.b_pool), cols_per_row):
            row_items = st.session_state.b_pool[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for col, item in zip(cols, row_items):
                with col:
                    st.image(item["thumbnail"])
                    if st.checkbox("选中拼图", key=f"b_chk_{item['url']}"): b_temp_selected.append(item["url"])
        if st.form_submit_button("➡️ 确认所选，进入自动化测试", type="primary"):
            if not b_temp_selected: st.warning("请至少勾选一个商品！")
            else:
                st.session_state.b_urls = b_temp_selected
                st.session_state.b_step = 3
                st.rerun()

if st.session_state.b_step >= 3 and st.session_state.b_urls:
    st.markdown("---")
    st.markdown("### 步骤 3：一键生成 Banner 与推送到 WordPress")
    
    col_b1, col_b2 = st.columns([1, 1], gap="large")
    with col_b1:
        st.info("🖼️ 根据选中的商品主图，利用 Python 自动裁切拼接一张 Banner。")
        if st.button("🎨 1. 生成 Banner", type="secondary"):
            with st.spinner("下载原图并拼接中..."):
                selected_items = [p for p in st.session_state.b_pool if p["url"] in st.session_state.b_urls]
                banner_data = create_banner_collage([item["thumbnail"] for item in selected_items])
                if banner_data:
                    st.session_state.b_banner_bytes = banner_data
                    st.success("✅ Banner 生成成功！")
                else: st.error("拼图失败。")
        if st.session_state.b_banner_bytes:
            st.image(st.session_state.b_banner_bytes, caption="已生成的 1200x630 Banner 预览图")

    with col_b2:
        st.info("🚀 选择目标网站，自动更新指定文章或新建博客草稿。")
        my_wp_sites = {"🇩🇪 德语站": "DE", "🇫🇷 法语站": "FR", "🇪🇸 西班牙站": "ES", "🇮🇹 意大利站": "IT", "🇳🇱 荷兰站": "NL", "🇳🇴 挪威站": "NO", "🇸🇪 瑞典站": "SE", "🇫🇮 芬兰站": "FI", "🇵🇱 波兰站": "PL"}
        site_urls = {"DE": "https://www.callie.de/blog", "FR": "https://fr.callie.com/blog", "ES": "https://www.callie.es/blog", "IT": "https://it.callie.com/blog", "NL": "https://nl.callie.com/blog", "NO": "https://no.callie.com/blog", "SE": "https://www.callie.se/blog", "FI": "https://www.callie.fi/blog", "PL": "https://pl.callie.com/blog"}
        
        selected_site_name = st.selectbox("🎯 请选择要发布的网站：", list(my_wp_sites.keys()))
        site_prefix = my_wp_sites[selected_site_name]
        wp_url = site_urls[site_prefix]
        
        # 恢复单账号安全加载逻辑
        user_key = "WP_USER"
        pass_key = f"WP_PASS_{site_prefix}"
        
        if user_key in st.secrets and pass_key in st.secrets:
            st.success(f"🔒 凭证已自动加载")
            wp_user = st.secrets[user_key]
            wp_pass = st.secrets[pass_key]
        else:
            st.warning(f"⚠️ 缺少 {pass_key}，请前往后台添加。")
            c1, c2 = st.columns(2)
            with c1: wp_user = st.text_input("用户名", value=st.secrets.get("WP_USER", ""))
            with c2: wp_pass = st.text_input(f"应用密码", type="password")
            
        post_title = st.text_input("📝 博客标题 (新建草稿时使用)", value="🔥 自动 Banner 推送测试")
        target_post_id = st.text_input("🎯 指定文章 ID (可选)", help="留空则每次新建草稿。如果想更新已有的文章，请填入该文章的 ID。")
        
        if st.button("🚀 2. 推送至 WordPress", type="primary"):
            if not st.session_state.b_banner_bytes: st.warning("请先在左侧点击生成 Banner！")
            elif not wp_user or not wp_pass: st.warning("请配置或填完所有的 WordPress 验证信息！")
            else:
                with st.spinner(f"正在向 {selected_site_name} 推送中..."):
                    success, msg = push_to_wordpress(wp_url, wp_user, wp_pass, post_title, st.session_state.b_banner_bytes, target_post_id)
                    if success: st.success(f"🎉 成功：{msg} 请登录对应的 WordPress 后台查看。")
                    else: st.error(msg)
