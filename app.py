import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import re
from urllib.parse import urljoin

# ================= 配置与初始化 =================
st.set_page_config(page_title="智能商品卡片生成器", layout="wide", initial_sidebar_state="collapsed")

# 🎨 UI 视觉重构：Google Material Design 规范
st.markdown("""
<style>
.stApp { background-color: #F8F9FA; color: #202124; font-family: 'Google Sans', 'Roboto', -apple-system, sans-serif; }
p, span, label { color: #5F6368 !important; }
h1, h2, h3, h4 { font-family: 'Google Sans', 'Roboto', sans-serif !important; color: #202124 !important; font-weight: 500 !important; }
h1 { font-size: 1.8rem !important; padding-bottom: 0.5rem; }
h3 { font-size: 1.2rem !important; }
[data-testid="block-container"] { padding-top: 2rem !important; padding-bottom: 4rem !important; max-width: 1200px; }

[data-testid="stPageLink-NavLink"] { background-color: #FFFFFF; border-radius: 24px; padding: 8px 20px; border: 1px solid #DADCE0; transition: all 0.2s ease; justify-content: center; font-weight: 500; }
[data-testid="stPageLink-NavLink"]:hover { background-color: #F1F3F4; border-color: #DADCE0; }
[data-testid="stPageLink-NavLink"] p { color: #1A73E8 !important; }

.stButton > button { border-radius: 4px !important; border: none !important; font-weight: 500 !important; padding: 8px 24px !important; transition: all 0.2s ease !important; }
.stButton > button[kind="primary"] { background-color: #1A73E8 !important; box-shadow: none !important; }
.stButton > button[kind="primary"] * { color: #FFFFFF !important; }
.stButton > button[kind="primary"]:hover { background-color: #174EA6 !important; box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15) !important; }
.stButton > button[kind="secondary"] { background: #FFFFFF !important; border: 1px solid #DADCE0 !important; }
.stButton > button[kind="secondary"] * { color: #1A73E8 !important; }
.stButton > button[kind="secondary"]:hover { background: #F1F3F4 !important; }

.stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { border-radius: 4px !important; border: 1px solid #DADCE0 !important; background-color: #FFFFFF !important; padding: 10px 14px !important; }
.stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus, .stSelectbox>div>div>div:focus { border: 2px solid #1A73E8 !important; padding: 9px 13px !important; box-shadow: none !important; }
[data-testid="stForm"], [data-testid="stExpander"] { background-color: #FFFFFF; border-radius: 8px !important; border: 1px solid #DADCE0 !important; box-shadow: none !important; padding: 20px !important; }
[data-testid="stAlert"] { border-radius: 8px !important; border: 1px solid #DADCE0 !important; background-color: #FFFFFF !important; border-left: 4px solid #1A73E8 !important; }

.stTabs [data-baseweb="tab-list"] { gap: 16px; border-bottom: 1px solid #DADCE0; padding-bottom: 0px; }
.stTabs [data-baseweb="tab"] { padding: 12px 16px !important; background-color: transparent; border: none !important; font-weight: 500; }
.stTabs [aria-selected="true"] { border-bottom: 3px solid #1A73E8 !important; }
.stTabs [aria-selected="true"] * { color: #1A73E8 !important; }

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ================= 顶部全局导航栏 =================
nav_col1, nav_col2, _ = st.columns([1.5, 1.5, 7])
with nav_col1:
    st.page_link("app.py", label="📇 核心：商品卡片生成器", use_container_width=True)
with nav_col2:
    st.page_link("pages/banner_test.py", label="🖼️ 测试：Banner与WP发布", use_container_width=True)
st.markdown("<br>", unsafe_allow_html=True)

st.title("🛍️ 博客商品卡片自动生成器 (GEO版)")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

if "matched_products" not in st.session_state: st.session_state.matched_products = []
if "step" not in st.session_state: st.session_state.step = 1
if "selected_urls" not in st.session_state: st.session_state.selected_urls = []
if "output_mode" not in st.session_state: st.session_state.output_mode = "card"
if "selected_template" not in st.session_state: st.session_state.selected_template = ""
if "generated_cards_list" not in st.session_state: st.session_state.generated_cards_list = []

dummy_image = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22400%22%20viewBox%3D%220%200%20400%20400%22%3E%3Crect%20width%3D%22400%22%20height%3D%22400%22%20fill%3D%22%23F3F4F6%22%2F%3E%3Ctext%20x%3D%2250%25%22%20y%3D%2250%25%22%20dominant-baseline%3D%22middle%22%20text-anchor%3D%22middle%22%20font-family%3D%22sans-serif%22%20font-size%3D%2224%22%20fill%3D%22%239CA3AF%22%3E%E5%95%86%E5%93%81%E5%9B%BE%E7%89%87%E9%A2%84%E8%A7%88%3C%2Ftext%3E%3C%2Fsvg%3E"

# ================= HTML 响应式模板库 (防破坏 Inline CSS) =================
templates = {
    "模板 1：左右结构 (经典极简)": {
        "type": "single",
        "html": """
{json_ld}
<div style="display: flex; flex-wrap: wrap; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; width: 100%; box-sizing: border-box; margin-bottom: 20px;">
    <div style="flex: 1 1 200px; min-width: 40%; background-color: #ffffff; padding: 15px; box-sizing: border-box; text-align: center; display: flex; align-items: center; justify-content: center;">
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored">
            <img src="{image_url}" alt="{title}" style="max-width: 100%; max-height: 220px; object-fit: contain; border-radius: 8px; border: none; outline: none;">
        </a>
    </div>
    <div style="flex: 2 1 300px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box;">
        <div>
            <h3 style="margin-top: 0; color: #333333; font-size: 16px; margin-bottom: 12px; line-height: 1.4;">{title}</h3>
            <div style="margin-bottom: 12px;">
                <span style="background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; display: inline-block;">🏷️ {price}</span>
            </div>
            <div style="background-color: #FFF5E4; border-radius: 8px; padding: 12px; margin-bottom: 15px; font-size: 13px; color: #555555; line-height: 1.5;">
                <strong>⚙️ </strong>{specs}
            </div>
        </div>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px; margin-top: 10px;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 4：左右结构 (纯净无规格)": {
        "type": "single",
        "html": """
{json_ld}
<div style="display: flex; flex-wrap: wrap; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; width: 100%; box-sizing: border-box; margin-bottom: 20px; min-height: 200px;">
    <div style="flex: 1 1 200px; min-width: 40%; background-color: #ffffff; padding: 15px; box-sizing: border-box; text-align: center; display: flex; align-items: center; justify-content: center;">
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored">
            <img src="{image_url}" alt="{title}" style="max-width: 100%; max-height: 220px; object-fit: contain; border-radius: 8px; border: none; outline: none;">
        </a>
    </div>
    <div style="flex: 2 1 300px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box;">
        <div>
            <h3 style="margin-top: 0; color: #333333; font-size: 16px; margin-bottom: 12px; line-height: 1.4;">{title}</h3>
            <div style="margin-bottom: 15px;">
                <span style="background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; display: inline-block;">🏷️ {price}</span>
            </div>
        </div>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px; margin-top: auto;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 2：上下结构 (圆润多巴胺)": {
        "type": "single",
        "html": """
{json_ld}
<div style="background-color: #FFF8EC; border-radius: 24px; padding: 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; width: 100%; max-width: 350px; box-sizing: border-box; border: 1px solid #F7E8D5; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto 20px auto;">
    <div style="width: 100%; height: 260px; border-radius: 16px; overflow: hidden; margin-bottom: 16px; background-color: #fff; display: flex; align-items: center; justify-content: center; text-align:center;">
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored">
            <img src="{image_url}" alt="{title}" style="max-width: 100%; max-height: 260px; object-fit: contain; border: none; outline: none;">
        </a>
    </div>
    <h3 style="margin: 0 0 10px 0; color: #3E2723; font-size: 18px; font-weight: 800; line-height: 1.3;">{title}</h3>
    <div style="color: #A1887F; font-size: 12px; margin-bottom: 20px; font-weight: 500; line-height: 1.4; height: 50px; overflow: hidden;">{specs}</div>
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #F59E0B; font-size: 22px; font-weight: 800;">{price}</span>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" style="background-color: #F59E0B; color: #ffffff; text-decoration: none; padding: 10px 24px; border-radius: 24px; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3); display: inline-block;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 3：多商品轮播 (单行极简)": {
        "type": "carousel",
        "html": """
{json_ld}
<div style="background-color: #FDFBF7; padding: 20px 10px; font-family: sans-serif; border-radius: 16px; margin-bottom: 20px; box-sizing: border-box; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch;">
    {carousel_items}
</div>
""",
        "item_html": """
<div style="display: inline-block; vertical-align: top; width: 220px; white-space: normal; background-color: #FFFFFF; border-radius: 16px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-right: 16px; box-sizing: border-box;">
    <div style="width: 100%; height: 180px; border-radius: 12px; overflow: hidden; margin-bottom: 12px; background-color: #f9f9f9; text-align: center;">
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored"><img src="{image_url}" alt="{title}" style="max-width: 100%; max-height: 180px; object-fit: contain;"></a>
    </div>
    <h3 style="margin: 0 0 12px 0; color: #333333; font-size: 14px; line-height: 1.4; white-space: normal;">{title}</h3>
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #111111; font-size: 16px; font-weight: 800;">{price}</span>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" style="background-color: #D4BBAA; color: #ffffff; text-decoration: none; padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: bold; display: inline-block;">{cta_text}</a>
    </div>
</div>
"""
    }
}

# ================= 核心爬虫与 AI 函数 =================

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except: return None

def fetch_blog_context(blog_url):
    soup = get_soup(blog_url)
    if not soup: return ""
    return soup.get_text(separator='\n', strip=True)[:4000]

def fetch_product_list(category_url):
    soup = get_soup(category_url)
    if not soup: return []
    seen_urls = set()
    products = []
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        full_url = urljoin(category_url, href)
        clean_url = full_url.split('?')[0]
        if len(title) > 5 and clean_url not in seen_urls and "javascript" not in clean_url:
            img = a.find('img')
            if not img and a.parent: img = a.parent.find('img')
            if not img and a.parent and a.parent.parent: img = a.parent.parent.find('img')
            if img:
                src = img.get('data-src') or img.get('src')
                if src:
                    img_url = urljoin(category_url, src).split('?')[0]
                    seen_urls.add(clean_url)
                    products.append({"title": title, "url": clean_url, "thumbnail": img_url})
                    if len(products) >= 60: break
    return products

def fetch_direct_urls(url_list_text):
    urls = [u.strip() for u in url_list_text.split('\n') if u.strip().startswith('http')]
    products = []
    for url in urls:
        clean_url = url.split('?')[0]
        soup = get_soup(clean_url)
        if soup:
            title = soup.title.string if soup.title else "未命名商品"
            img_url = dummy_image
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                img_url = urljoin(clean_url, og_img['content']).split('?')[0]
            products.append({"title": title, "url": clean_url, "thumbnail": img_url})
    return products

def clean_json_response(content):
    content = content.strip()
    if content.startswith("```"):
        start_idx = content.find('\n') + 1
        end_idx = content.rfind('```')
        if start_idx > 0 and end_idx > start_idx:
            content = content[start_idx:end_idx].strip()
    return content

def ai_match_top_30(blog_text, product_list):
    prompt = f"""You are an expert e-commerce recommender. Select and return AS MANY relevant products as possible, up to a maximum of 30. Blog Post: {blog_text[:3000]} Product Candidates: {json.dumps(product_list, ensure_ascii=False)} Output ONLY a JSON array of the selected products."""
    try:
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"} if "json" in prompt.lower() else None, max_tokens=4000)
        return json.loads(clean_json_response(response.choices[0].message.content))
    except: return product_list[:30]

def extract_product_details(product_url):
    soup = get_soup(product_url)
    if not soup: return None
    main_image = ""
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'): main_image = og_img['content']
    else:
        img_tag = soup.find('img')
        if img_tag: main_image = img_tag.get('data-src') or img_tag.get('src', '')
    main_image = urljoin(product_url, main_image).split('?')[0] if main_image else dummy_image
    
    og_price = soup.find('meta', property='product:price:amount') or soup.find('meta', property='og:price:amount')
    price_hint = f"\n[SYSTEM HINT]: The true product price is {og_price.get('content')}." if og_price and og_price.get('content') else ""
    text_content = soup.get_text(separator='\n', strip=True)[:5000]
    prompt = f"""Analyze the following product page text. DO NOT TRANSLATE. Extract into JSON: "title", "price", "return_days", "specs" (brief), "cta_text". RULES: NEVER extract shipping fees. {price_hint} Page Text: {text_content}"""
    try:
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, max_tokens=1500)
        result = json.loads(clean_json_response(response.choices[0].message.content))
        result["image_url"] = main_image
        result["buy_link"] = product_url
        return result
    except: return None

# ================= 结构化数据 =================
def format_price_for_schema(price_str):
    if not price_str: return "0.00"
    p = str(price_str).replace(',', '.') 
    p = re.sub(r'[^\d.]', '', p)         
    parts = p.split('.')
    if len(parts) > 2: p = "".join(parts[:-1]) + "." + parts[-1]
    return p if p else "0.00"

def generate_single_json_ld(title, image_url, price, buy_link, return_days):
    price_num = format_price_for_schema(price)
    url_lower = str(buy_link).lower()
    currency = 'EUR' if 'fr.' in url_lower or 'de.' in url_lower or 'es.' in url_lower or 'it.' in url_lower else 'USD'
    ld = {
        "@context": "https://schema.org/", "@type": "Product", "name": title[:140], "image": image_url, "brand": {"@type": "Brand", "name": "Callie"},
        "offers": {"@type": "Offer", "price": price_num, "priceCurrency": currency, "url": buy_link, "availability": "https://schema.org/InStock"}
    }
    return f'\n<div style="display: none; visibility: hidden; height: 0; width: 0; overflow: hidden;">\n<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False)}\n</script>\n</div>\n'

def generate_carousel_json_ld(products_data):
    items = []
    for i, data in enumerate(products_data):
        price_num = format_price_for_schema(data.get("price", ""))
        items.append({
            "@type": "ListItem", "position": i + 1,
            "item": { "@type": "Product", "name": data.get("title", "")[:140], "image": data.get("image_url", ""), "brand": {"@type": "Brand", "name": "Callie"},
            "offers": {"@type": "Offer", "price": price_num, "url": data.get("buy_link", "")} }
        })
    ld = {"@context": "https://schema.org/", "@type": "ItemList", "itemListElement": items}
    return f'\n<div style="display: none; visibility: hidden; height: 0; width: 0; overflow: hidden;">\n<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False)}\n</script>\n</div>\n'

# ================= WordPress 智能无损注入函数 (终极修复版) =================
def push_cards_to_wp_h2(wp_url, username, password, post_id, cards_html_list):
    base_api = wp_url.rstrip('/') + '/wp-json/wp/v2'
    auth = (username, password)
    
    post_endpoint = f"{base_api}/posts/{post_id}"
    try:
        res_get = requests.get(f"{post_endpoint}?context=edit", auth=auth, timeout=15, allow_redirects=True)
        if res_get.status_code == 404:
            post_endpoint = f"{base_api}/pages/{post_id}"
            res_get = requests.get(f"{post_endpoint}?context=edit", auth=auth, timeout=15, allow_redirects=True)
            
        if res_get.status_code != 200: 
            return False, f"无法读取原文，权限不足或查无此文: {res_get.text[:100]}"
            
        real_endpoint = res_get.url.split('?')[0] 
        post_data = res_get.json()
        current_content = post_data.get('content', {}).get('raw', '')
    except Exception as e: 
        return False, f"读取异常: {e}"

    # 包装为标准的 Custom HTML 区块
    formatted_cards = [f'\n<!-- wp:html -->\n{card}\n<!-- /wp:html -->\n' for card in cards_html_list]
    
    # 【核心修复】：使用非贪婪匹配，把古腾堡区块外壳(<!-- wp:heading -->)和内部的<h2>作为一个完整的整体进行切割
    # 这样卡片就会被插入在这个整体的外面，绝对不会污染破坏区块！
    pattern = r'((?:<!--\s*wp:heading[\s\S]*?-->\s*)?<h2[^>]*>)'
    parts = re.split(pattern, current_content, flags=re.IGNORECASE)
    
    new_content = ""
    card_idx = 0
    h2_found_count = 0
    
    if len(parts) == 1:
        new_content = current_content + "".join(formatted_cards)
    else:
        for part in parts:
            part_lower = part.strip().lower()
            if part_lower.startswith('<h2') or part_lower.startswith('<!-- wp:heading'):
                h2_found_count += 1
                if card_idx < len(formatted_cards):
                    new_content += formatted_cards[card_idx]
                    card_idx += 1
            new_content += part
        while card_idx < len(formatted_cards):
            new_content += formatted_cards[card_idx]
            card_idx += 1

    update_data = {'content': new_content}
    try:
        res_update = requests.post(real_endpoint, json=update_data, auth=auth, timeout=30, allow_redirects=False)
        if res_update.status_code in [301, 302, 307, 308]:
            real_endpoint = res_update.headers.get('Location')
            res_update = requests.post(real_endpoint, json=update_data, auth=auth, timeout=30, allow_redirects=False)

        if res_update.status_code in [200, 201]:
            updated_json = res_update.json()
            saved_content = updated_json.get('content', {}).get('raw', '')
            
            if "application/ld+json" not in saved_content and len(cards_html_list) > 0:
                return False, "❌ 致命错误：写入被服务器安全插件拦截。"

            msg = f"已强制写入数据库校验通过！雷达检测到 {h2_found_count} 个 H2 标签，成功插入 {min(card_idx, h2_found_count)} 个模块"
            if card_idx > h2_found_count:
                msg += f" (另有 {card_idx - h2_found_count} 个模块被追加到了文章末尾)。"
            msg += " 👉 请现在去后台按 F5 完全刷新页面。"
            return True, msg
        else: 
            return False, f"更新失败: {res_update.text[:200]}"
    except Exception as e: 
        return False, f"更新异常: {e}"

# ================= 界面工作流 =================

st.markdown("### 步骤 1：输入数据源")
tab1, tab2 = st.tabs(["🤖 AI 智能海选模式", "🔗 手动直达模式"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="用于语义匹配分析")
    with col2: shop_url = st.text_input("商品列表页/着陆页链接 (Landing Page)", placeholder="用于抓取候选商品")
    if st.button("🔍 抓取并智能海选", type="primary"):
        if not blog_url or not shop_url: st.warning("请填写完整的两个链接！")
        else:
            with st.spinner("正在抓取及分析..."):
                blog_text = fetch_blog_context(blog_url)
                pool = fetch_product_list(shop_url)
                if pool:
                    raw_top_30 = ai_match_top_30(blog_text, pool)
                    st.session_state.matched_products = [item for item in (raw_top_30 if isinstance(raw_top_30, list) else []) if isinstance(item, dict) and "url" in item]
                    for p in st.session_state.matched_products: p.setdefault("thumbnail", dummy_image)
                    if st.session_state.matched_products:
                        st.session_state.step = 2
                        st.rerun()

with tab2:
    st.info("💡 如果不需要给 Blog 找对应的商品，请直接在下方粘贴商品详情页链接。一行一个。")
    direct_urls = st.text_area("输入商品链接：", height=150)
    if st.button("🚀 直接获取这些商品信息", type="primary"):
        if direct_urls.strip():
            with st.spinner("正在解析您提供的链接，请稍候..."):
                st.session_state.matched_products = fetch_direct_urls(direct_urls)
                if st.session_state.matched_products:
                    st.session_state.step = 2
                    st.rerun()

if st.session_state.step >= 2 and st.session_state.matched_products:
    st.markdown("### 步骤 2：人工确认生成名单")
    with st.form("selection_form"):
        temp_selected = []
        cols_per_row = 10
        for i in range(0, len(st.session_state.matched_products), cols_per_row):
            row_items = st.session_state.matched_products[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for col, item in zip(cols, row_items):
                with col:
                    st.image(item["thumbnail"], use_container_width=True)
                    if st.checkbox("选择", key=f"chk_{item['url']}"): temp_selected.append(item["url"])
            st.write("") 
        if st.form_submit_button("➡️ 确认选中，进入下一步", type="primary"):
            if temp_selected:
                st.session_state.selected_urls = temp_selected
                st.session_state.step = 3
                st.rerun()

if st.session_state.step >= 3 and st.session_state.selected_urls:
    st.markdown("### 步骤 3：选择数据输出模式")
    mode_choice = st.radio("请选择：", ["🎨 生成高转化商品卡片 (包含完整排版与样式)", "🖼️ 仅生成纯净原图 (纯粹 SEO 优化，抗干扰)"], horizontal=True, label_visibility="collapsed")
    
    if mode_choice.startswith("🎨"):
        st.session_state.output_mode = "card"
        dummy_data = {"image_url": dummy_image, "title": "Custom Halloween Decoration", "price": "28.00 €", "specs": "Material: Resin &nbsp;•&nbsp; Size: 10x15 cm", "buy_link": "https://fr.callie.com", "cta_text": "Add To Cart", "json_ld": ""}
        tmpl_cols = st.columns(len(templates))
        for col, (tmpl_name, tmpl_data) in zip(tmpl_cols, templates.items()):
            with col:
                st.markdown(f"**{tmpl_name}**")
                preview_html = tmpl_data["html"].replace("{carousel_items}", tmpl_data.get("item_html","").format(**dummy_data) * 3).format(**dummy_data) if tmpl_data["type"] == "carousel" else tmpl_data["html"].format(**dummy_data)
                st.html(f'<div style="height: 380px; overflow-y: auto; overflow-x: hidden; border: 1px solid #DADCE0; border-radius: 8px; padding: 10px; background: #fff;"><div style="transform: scale(0.75); transform-origin: top left; width: 133%;">{preview_html}</div></div>')
                if st.button(f"✨ 使用【{tmpl_name.split('：')[0]}】生成", key=f"btn_{tmpl_name}", use_container_width=True):
                    st.session_state.selected_template = tmpl_name
                    st.session_state.step = 4
                    st.rerun()
    else:
        st.session_state.output_mode = "image"
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ 确认使用【纯净原图】模式并提取数据", type="primary"):
            st.session_state.step = 4
            st.rerun()

if st.session_state.step >= 4:
    st.markdown("### 步骤 4：最终生成结果")
    selected_items = [p for p in st.session_state.matched_products if p["url"] in st.session_state.selected_urls]
    my_bar = st.progress(0, text="正在逐个深入详情页提取数据...")
    all_extracted_data = []
    generated_single_cards = [] 
    
    for i, item in enumerate(selected_items):
        details_data = extract_product_details(item["url"])
        if details_data:
            raw_specs = details_data.get("specs", "")
            specs_str = "&nbsp;•&nbsp;".join([str(x) for x in raw_specs]) if isinstance(raw_specs, list) else str(raw_specs).replace('\n', '&nbsp;•&nbsp;')
            details_data["specs_formatted"] = specs_str
            all_extracted_data.append(details_data)
            
            ld_script = generate_single_json_ld(details_data.get("title", ""), details_data.get("image_url", ""), details_data.get("price", ""), details_data.get("buy_link", ""), details_data.get("return_days", 30))
            
            if st.session_state.output_mode == "image":
                raw_img_html = f"""{ld_script}<div style="text-align: center; margin-bottom: 25px;"><a href="{details_data.get("buy_link")}" target="_blank" rel="nofollow sponsored" title="{details_data.get("title", "Callie Product")}"><img src="{details_data.get("image_url")}" alt="{details_data.get("title", "Callie Product")}" style="max-width: 100%; height: auto; border-radius: 8px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05);"></a></div>"""
                generated_single_cards.append(raw_img_html)
                st.markdown(f"**📝 原图预览: {details_data.get('title', item['title'])}**")
                c1, c2 = st.columns([1, 1], gap="large")
                with c1: st.html(raw_img_html)
                with c2: 
                    with st.expander("💻 点击展开 / 复制 HTML 代码"): st.code(raw_img_html, language='html')
                st.write("---") 
            else:
                tmpl_config = templates[st.session_state.selected_template]
                if tmpl_config["type"] == "single":
                    card_html = tmpl_config["html"].format(image_url=details_data.get("image_url", ""), title=details_data.get("title", ""), price=details_data.get("price", ""), specs=specs_str, buy_link=details_data.get("buy_link", ""), cta_text=details_data.get("cta_text", "Buy Now"), json_ld=ld_script)
                    generated_single_cards.append(card_html)
                    st.markdown(f"**📝 卡片预览: {details_data.get('title', item['title'])}**")
                    c1, c2 = st.columns([1, 1], gap="large")
                    with c1: st.html(f'<div style="max-height: 450px; overflow-y: auto;">{card_html}</div>')
                    with c2: 
                        with st.expander("💻 点击展开 / 复制完整 HTML 代码"): st.code(card_html, language='html')
                    st.write("---") 
        my_bar.progress((i + 1) / len(selected_items), text=f"已处理 {i+1}/{len(selected_items)} 个商品...")
        
    if st.session_state.output_mode == "card" and templates[st.session_state.selected_template]["type"] == "carousel" and all_extracted_data:
        st.markdown("**📝 以下是包含所有勾选商品的轮播图代码组件**")
        ld_script = generate_carousel_json_ld(all_extracted_data)
        carousel_items_str = "".join([templates[st.session_state.selected_template]["item_html"].format(image_url=data.get("image_url", ""), title=data.get("title", ""), price=data.get("price", ""), buy_link=data.get("buy_link", ""), cta_text=data.get("cta_text", "Buy Now")) for data in all_extracted_data])
        final_carousel_html = templates[st.session_state.selected_template]["html"].replace("{carousel_items}", carousel_items_str).format(json_ld=ld_script)
        st.session_state.generated_cards_list = [final_carousel_html]
        c1, c2 = st.columns([1, 1], gap="large")
        with c1: st.html(f'<div style="max-height: 450px; overflow-y: auto;">{final_carousel_html}</div>')
        with c2: 
            with st.expander("💻 点击展开 / 复制完整轮播 HTML 代码"): st.code(final_carousel_html, language='html')
    elif generated_single_cards:
        st.session_state.generated_cards_list = generated_single_cards
                
    st.success(f"✅ 全部处理完毕！已生成 {len(st.session_state.generated_cards_list)} 个模块。")

# ================= 步骤 5：自动注入文章 =================
if st.session_state.step >= 4 and getattr(st.session_state, "generated_cards_list", None):
    st.markdown("---")
    st.markdown("### 步骤 5：智能注入 WordPress 文章")
    
    col_w1, col_w2 = st.columns([1, 1], gap="large")
    with col_w1:
        st.info("💡 **H2 对齐无损注入逻辑**\n\n系统使用正则表达式自动读取文章，并将生成的商品卡片按顺序插入到每个 `<h2>` 的上方。保留了原文所有的高级区块排版。")
        st.markdown(f"**待推送的模块总数：** `{len(st.session_state.generated_cards_list)}` 个")
        
    with col_w2:
        my_wp_sites = {"🇩🇪 德语站": "DE", "🇫🇷 法语站": "FR", "🇪🇸 西班牙站": "ES", "🇮🇹 意大利站": "IT", "🇳🇱 荷兰站": "NL", "🇳🇴 挪威站": "NO", "🇸🇪 瑞典站": "SE", "🇫🇮 芬兰站": "FI", "🇵🇱 波兰站": "PL"}
        site_urls = {"DE": "https://www.callie.de/blog", "FR": "https://fr.callie.com/blog", "ES": "https://www.callie.es/blog", "IT": "https://it.callie.com/blog", "NL": "https://nl.callie.com/blog", "NO": "https://no.callie.com/blog", "SE": "https://www.callie.se/blog", "FI": "https://www.callie.fi/blog", "PL": "https://pl.callie.com/blog"}
        
        selected_site_name = st.selectbox("🎯 选择目标网站：", list(my_wp_sites.keys()))
        site_prefix = my_wp_sites[selected_site_name]
        wp_url = site_urls[site_prefix]
        
        user_key = "WP_USER"
        pass_key = f"WP_PASS_{site_prefix}"
        
        if user_key in st.secrets and pass_key in st.secrets:
            st.success(f"🔒 凭证已加载")
            wp_user = st.secrets[user_key]
            wp_pass = st.secrets[pass_key]
        else:
            st.warning(f"⚠️ 缺少 {pass_key}，请前往后台添加。")
            c1, c2 = st.columns(2)
            with c1: wp_user = st.text_input("用户名", value=st.secrets.get("WP_USER", ""))
            with c2: wp_pass = st.text_input(f"应用密码", type="password")
            
        target_post_id = st.text_input("🎯 指定文章 ID (必填)", help="填入你要修改的文章 ID (纯数字，如 1024)。")
        
        if st.button("🚀 开始无损注入并更新", type="primary"):
            if not target_post_id.strip() or not wp_user or not wp_pass: st.warning("请确保 ID 与验证信息完整！")
            else:
                with st.spinner("正在防破坏式注入并更新文章..."):
                    success, msg = push_cards_to_wp_h2(wp_url, wp_user, wp_pass, target_post_id, st.session_state.generated_cards_list)
                    if success: st.success(f"🎉 {msg}")
                    else: st.error(msg)
