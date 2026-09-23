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
st.set_page_config(page_title="博客电商自动化工具箱", layout="wide")

st.markdown("""
<style>
[data-testid="stTooltipIcon"] svg { display: none !important; }
[data-testid="stTooltipIcon"]::after { content: "ⓘ"; font-size: 16px; color: #888; margin-left: 2px; }
/* 优化 Tab 样式 */
div[data-testid="stTabs"] button { font-size: 18px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🛍️ 博客电商自动化工具箱")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

# ================= 底层状态隔离 =================
# 【卡片生成系统】的状态缓存
if "c_matched_products" not in st.session_state: st.session_state.c_matched_products = []
if "c_step" not in st.session_state: st.session_state.c_step = 1
if "c_selected_urls" not in st.session_state: st.session_state.c_selected_urls = []
if "c_selected_template" not in st.session_state: st.session_state.c_selected_template = ""

# 【Banner生成系统】的状态缓存
if "b_step" not in st.session_state: st.session_state.b_step = 1
if "b_pool" not in st.session_state: st.session_state.b_pool = []
if "b_urls" not in st.session_state: st.session_state.b_urls = []
if "b_banner_bytes" not in st.session_state: st.session_state.b_banner_bytes = None
if "b_extracted_data" not in st.session_state: st.session_state.b_extracted_data = []
if "b_final_html_str" not in st.session_state: st.session_state.b_final_html_str = ""

dummy_image = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22400%22%20viewBox%3D%220%200%20400%20400%22%3E%3Crect%20width%3D%22400%22%20height%3D%22400%22%20fill%3D%22%23F7E8D5%22%2F%3E%3Ctext%20x%3D%2250%25%22%20y%3D%2250%25%22%20dominant-baseline%3D%22middle%22%20text-anchor%3D%22middle%22%20font-family%3D%22sans-serif%22%20font-size%3D%2224%22%20fill%3D%22%233E2723%22%3E%E5%95%86%E5%93%81%E5%9B%BE%E7%89%87%E9%A2%84%E8%A7%88%3C%2Ftext%3E%3C%2Fsvg%3E"

# ================= HTML 响应式模板库 =================
templates = {
    "模板 1：左右结构 (经典极简)": {
        "type": "single",
        "html": """
<style>
.g-seo-t1 {{ display: flex; flex-direction: row; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; width: 100%; box-sizing: border-box; margin-bottom: 20px; }}
.g-seo-t1-img {{ width: 40%; background-color: #ffffff; display: flex; align-items: center; justify-content: center; padding: 15px; box-sizing: border-box; }}
.g-seo-t1-img img {{ width: 100%; height: 100%; max-height: 220px; object-fit: contain; border-radius: 8px; }}
.g-seo-t1-content {{ width: 60%; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; }}
.g-seo-t1-title {{ margin-top: 0; color: #333333; font-size: 16px; margin-bottom: 12px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.g-seo-t1-price-wrap {{ margin-bottom: 12px; }}
.g-seo-t1-price {{ background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; }}
.g-seo-t1-specs {{ background-color: #FFF5E4; border-radius: 8px; padding: 12px; margin-bottom: 15px; font-size: 13px; color: #555555; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
.g-seo-t1-btn {{ display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px; transition: background-color 0.3s; }}
.g-seo-t1-btn:hover {{ background-color: #43D8C9; }}
@media (max-width: 640px) {{
    .g-seo-t1 {{ flex-direction: column; }}
    .g-seo-t1-img {{ width: 100%; height: 220px; padding: 20px; border-bottom: 1px solid #eaeaea; }}
    .g-seo-t1-content {{ width: 100%; padding: 15px; }}
}}
</style>
<article class="g-seo-t1">
    <div class="g-seo-t1-img">
        <img src="{image_url}" loading="lazy" alt="{title}">
    </div>
    <div class="g-seo-t1-content">
        <div>
            <h3 class="g-seo-t1-title">{title}</h3>
            <div class="g-seo-t1-price-wrap">
                <span class="g-seo-t1-price">🏷️ {price}</span>
            </div>
            <div class="g-seo-t1-specs">
                <strong>⚙️ </strong>{specs}
            </div>
        </div>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" class="g-seo-t1-btn">{cta_text}</a>
    </div>
</article>
{json_ld}
"""
    },
    "模板 4：左右结构 (纯净无规格)": {
        "type": "single",
        "html": """
<style>
.g-seo-t4 {{ display: flex; flex-direction: row; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; width: 100%; box-sizing: border-box; margin-bottom: 20px; min-height: 200px; }}
.g-seo-t4-img {{ width: 40%; background-color: #ffffff; display: flex; align-items: center; justify-content: center; padding: 15px; box-sizing: border-box; }}
.g-seo-t4-img img {{ width: 100%; height: 100%; max-height: 220px; object-fit: contain; border-radius: 8px; }}
.g-seo-t4-content {{ width: 60%; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; }}
.g-seo-t4-title {{ margin-top: 0; color: #333333; font-size: 16px; margin-bottom: 12px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
.g-seo-t4-price-wrap {{ margin-bottom: 15px; }}
.g-seo-t4-price {{ background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; display: inline-block; }}
.g-seo-t4-btn {{ display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px; transition: background-color 0.3s; margin-top: auto; }}
.g-seo-t4-btn:hover {{ background-color: #43D8C9; }}
@media (max-width: 640px) {{
    .g-seo-t4 {{ flex-direction: column; }}
    .g-seo-t4-img {{ width: 100%; height: 220px; padding: 20px; border-bottom: 1px solid #eaeaea; }}
    .g-seo-t4-content {{ width: 100%; padding: 15px; min-height: 180px; }}
}}
</style>
<article class="g-seo-t4">
    <div class="g-seo-t4-img">
        <img src="{image_url}" loading="lazy" alt="{title}">
    </div>
    <div class="g-seo-t4-content">
        <div>
            <h3 class="g-seo-t4-title">{title}</h3>
            <div class="g-seo-t4-price-wrap">
                <span class="g-seo-t4-price">🏷️ {price}</span>
            </div>
        </div>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" class="g-seo-t4-btn">{cta_text}</a>
    </div>
</article>
{json_ld}
"""
    },
    "模板 2：上下结构 (圆润多巴胺)": {
        "type": "single",
        "html": """
<style>
.g-seo-t2 {{ background-color: #FFF8EC; border-radius: 24px; padding: 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; width: 100%; max-width: 350px; box-sizing: border-box; border: 1px solid #F7E8D5; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto 20px auto; }}
.g-seo-t2-img {{ width: 100%; aspect-ratio: 1/1; border-radius: 16px; overflow: hidden; margin-bottom: 16px; background-color: #fff; display: flex; align-items: center; justify-content: center; }}
.g-seo-t2-title {{ margin: 0 0 10px 0; color: #3E2723; font-size: 18px; font-weight: 800; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.g-seo-t2-specs {{ color: #A1887F; font-size: 12px; margin-bottom: 20px; font-weight: 500; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; height: 50px; }}
.g-seo-t2-bot {{ display: flex; justify-content: space-between; align-items: center; }}
.g-seo-t2-price {{ color: #F59E0B; font-size: 22px; font-weight: 800; }}
.g-seo-t2-btn {{ background-color: #F59E0B; color: #ffffff; text-decoration: none; padding: 10px 24px; border-radius: 24px; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3); transition: opacity 0.3s; }}
.g-seo-t2-btn:hover {{ opacity: 0.8; }}
@media (max-width: 380px) {{
    .g-seo-t2 {{ padding: 15px; }}
    .g-seo-t2-price {{ font-size: 18px; }}
    .g-seo-t2-btn {{ padding: 10px 16px; font-size: 14px; }}
}}
</style>
<article class="g-seo-t2">
    <div class="g-seo-t2-img">
        <img src="{image_url}" loading="lazy" style="width: 100%; height: 100%; object-fit: contain;" alt="{title}">
    </div>
    <h3 class="g-seo-t2-title">{title}</h3>
    <div class="g-seo-t2-specs">{specs}</div>
    <div class="g-seo-t2-bot">
        <span class="g-seo-t2-price">{price}</span>
        <a href="{buy_link}" target="_blank" rel="nofollow sponsored" class="g-seo-t2-btn">{cta_text}</a>
    </div>
</article>
{json_ld}
"""
    },
    "模板 3：多商品轮播 (单行极简)": {
        "type": "carousel",
        "html": """
<style>
.g-seo-t3-sec {{ background-color: #FDFBF7; padding: 30px 10px; font-family: sans-serif; border-radius: 16px; margin-bottom: 20px; box-sizing: border-box; }}
.g-seo-t3-track {{ display: flex; overflow-x: auto; gap: 16px; padding: 10px; -webkit-overflow-scrolling: touch; scrollbar-width: none; }}
.g-seo-t3-track::-webkit-scrollbar {{ display: none; }}
.g-seo-t3-item {{ flex: 0 0 220px; background-color: #FFFFFF; border-radius: 16px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; transition: transform 0.3s ease; }}
.g-seo-t3-item:hover {{ transform: translateY(-5px); }}
.g-seo-t3-img {{ width: 100%; height: 180px; border-radius: 12px; overflow: hidden; margin-bottom: 12px; background-color: #f9f9f9; display: flex; align-items: center; justify-content: center; }}
.g-seo-t3-img img {{ width: 100%; height: 100%; max-height: 180px; object-fit: contain; }}
.g-seo-t3-title {{ margin: 0 0 12px 0; color: #333333; font-size: 14px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.g-seo-t3-bot {{ display: flex; justify-content: space-between; align-items: center; margin-top: auto; }}
.g-seo-t3-price {{ color: #111111; font-size: 16px; font-weight: 800; }}
.g-seo-t3-btn {{ background-color: #D4BBAA; color: #ffffff; text-decoration: none; padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: bold; transition: background-color 0.3s; }}
.g-seo-t3-btn:hover {{ background-color: #C2A594; }}
@media (max-width: 640px) {{
    .g-seo-t3-sec {{ padding: 20px 5px; }}
    .g-seo-t3-item {{ flex: 0 0 170px; padding: 12px; }}
    .g-seo-t3-img {{ height: 140px; }}
    .g-seo-t3-img img {{ max-height: 140px; }}
    .g-seo-t3-title {{ font-size: 13px; margin-bottom: 8px; }}
    .g-seo-t3-price {{ font-size: 14px; }}
    .g-seo-t3-btn {{ padding: 6px 10px; font-size: 11px; }}
}}
</style>
<section aria-label="Product Carousel" class="g-seo-t3-sec">
    <div class="g-seo-t3-track">
        {carousel_items}
    </div>
</section>
{json_ld}
""",
        "item_html": """
        <article class="g-seo-t3-item">
            <div class="g-seo-t3-img">
                <img src="{image_url}" loading="lazy" alt="{title}">
            </div>
            <h3 class="g-seo-t3-title">{title}</h3>
            <div class="g-seo-t3-bot">
                <span class="g-seo-t3-price">{price}</span>
                <a href="{buy_link}" target="_blank" rel="nofollow sponsored" class="g-seo-t3-btn">{cta_text}</a>
            </div>
        </article>
"""
    }
}

# ================= 公共爬虫与处理函数 =================
def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
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
            if og_img and og_img.get('content'): img_url = urljoin(clean_url, og_img['content']).split('?')[0]
            products.append({"title": title, "url": clean_url, "thumbnail": img_url})
    return products

def clean_json_response(content):
    content = content.strip()
    if content.startswith("```"):
        start_idx = content.find('\n') + 1
        end_idx = content.rfind('```')
        if start_idx > 0 and end_idx > start_idx: content = content[start_idx:end_idx].strip()
    return content

def ai_match_top_30(blog_text, product_list):
    prompt = f"""
    You are an expert e-commerce recommender.
    I will provide a Blog Post content and a list of product candidates.
    CRITICAL INSTRUCTION: Select and return AS MANY relevant products as possible, up to a maximum of 30. 
    Blog Post: {blog_text[:3000]}
    Product Candidates: {json.dumps(product_list, ensure_ascii=False)}
    Output ONLY a JSON array of the selected products.
    """
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
    prompt = f"""
    Analyze the following product page text. DO NOT TRANSLATE. Extract in EXACT ORIGINAL LANGUAGE.
    CRITICAL RULES FOR PRICE: NEVER extract shipping fees. {price_hint}
    Extract into JSON:
    1. "title": EXACT product name.
    2. "price": The true product price exactly as written.
    3. "return_days": Extract ONLY numeric days (e.g., 99). Default 30.
    4. "specs": Extract ONLY top 1-3 physical specifications. Very brief. Default "Standard".
    5. "cta_text": Generate "Buy Now" in original language.
    Page Text: {text_content}
    """
    try:
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, max_tokens=1500)
        result = json.loads(clean_json_response(response.choices[0].message.content))
        result["image_url"] = main_image
        result["buy_link"] = product_url
        return result
    except: return None

# ================= 结构化数据 (JSON-LD) 函数 =================
def detect_currency_and_country(url, price_str=""):
    url_lower = str(url).lower()
    if 'fr.' in url_lower: return 'EUR', 'FR'
    if 'de.' in url_lower: return 'EUR', 'DE'
    if 'uk.' in url_lower or '.co.uk/' in url_lower: return 'GBP', 'GB'
    if 'ca.' in url_lower: return 'CAD', 'CA'
    if 'au.' in url_lower or '.com.au/' in url_lower: return 'AUD', 'AU'
    p = str(price_str).upper()
    if '€' in p or 'EUR' in p: return 'EUR', 'FR' 
    if '£' in p or 'GBP' in p: return 'GBP', 'GB'
    return 'USD', 'US' 

def format_price_for_schema(price_str):
    if not price_str: return "0.00"
    p = str(price_str).replace(',', '.') 
    p = re.sub(r'[^\d.]', '', p)         
    parts = p.split('.')
    if len(parts) > 2: p = "".join(parts[:-1]) + "." + parts[-1]
    return p if p else "0.00"

def get_return_days(val):
    try:
        nums = re.findall(r'\d+', str(val))
        return int(nums[0]) if nums else 30
    except: return 30

def generate_single_json_ld(title, image_url, price, specs, buy_link, return_days):
    price_num = format_price_for_schema(price)
    currency, country_code = detect_currency_and_country(buy_link, price)
    days = get_return_days(return_days)
    ld = {
        "@context": "https://schema.org/", "@type": "Product",
        "name": title[:140] + "..." if len(title) > 140 else title, "image": image_url,
        "description": specs[:150] if specs else "Standard",
        "brand": {"@type": "Brand", "name": "Callie"},
        "offers": {
            "@type": "Offer", "price": price_num, "priceCurrency": currency, "url": buy_link, "availability": "https://schema.org/InStock",
            "hasMerchantReturnPolicy": {"@type": "MerchantReturnPolicy", "applicableCountry": country_code, "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow", "merchantReturnDays": days, "returnMethod": "https://schema.org/ReturnByMail", "returnFees": "https://schema.org/FreeReturn"},
            "shippingDetails": {"@type": "OfferShippingDetails", "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": currency}, "deliveryTime": {"@type": "ShippingDeliveryTime", "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 3, "unitCode": "d"}, "transitTime": {"@type": "QuantitativeValue", "minValue": 3, "maxValue": 7, "unitCode": "d"}}}
        }
    }
    return f'\n<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False, indent=2)}\n</script>'

def generate_carousel_json_ld(products_data):
    items = []
    for i, data in enumerate(products_data):
        buy_link = data.get("buy_link", "")
        price_str = data.get("price", "")
        currency, country_code = detect_currency_and_country(buy_link, price_str)
        title = data.get("title", "")
        items.append({
            "@type": "ListItem", "position": i + 1,
            "item": {
                "@type": "Product", "name": title[:140] + "..." if len(title) > 140 else title, "image": data.get("image_url", ""),
                "brand": {"@type": "Brand", "name": "Callie"},
                "offers": {
                    "@type": "Offer", "price": format_price_for_schema(price_str), "priceCurrency": currency, "url": buy_link, "availability": "https://schema.org/InStock",
                    "hasMerchantReturnPolicy": {"@type": "MerchantReturnPolicy", "applicableCountry": country_code, "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow", "merchantReturnDays": get_return_days(data.get("return_days", 30)), "returnMethod": "https://schema.org/ReturnByMail", "returnFees": "https://schema.org/FreeReturn"},
                    "shippingDetails": {"@type": "OfferShippingDetails", "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": currency}, "deliveryTime": {"@type": "ShippingDeliveryTime", "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 3, "unitCode": "d"}, "transitTime": {"@type": "QuantitativeValue", "minValue": 3, "maxValue": 7, "unitCode": "d"}}}
                }
            }
        })
    ld = {"@context": "https://schema.org/", "@type": "ItemList", "itemListElement": items}
    return f'\n<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False, indent=2)}\n</script>'

# ================= Banner 生成与 WP 发布核心功能 =================
def create_banner_collage(image_urls):
    imgs = []
    for url in image_urls:
        if len(imgs) >= 4: break 
        if url.startswith("data:image"): continue
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                img = Image.open(BytesIO(res.content)).convert("RGB")
                imgs.append(img)
        except: pass
    if not imgs: return None
    
    banner_w, banner_h = 1200, 630
    banner = Image.new('RGB', (banner_w, banner_h), (255, 255, 255))
    w_per_img = banner_w // len(imgs)
    
    for i, img in enumerate(imgs):
        img_cropped = ImageOps.fit(img, (w_per_img, banner_h), Image.Resampling.LANCZOS)
        banner.paste(img_cropped, (i * w_per_img, 0))
        
    buf = BytesIO()
    banner.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def push_to_wordpress(wp_url, username, password, title, html_content, banner_bytes):
    base_api = wp_url.rstrip('/') + '/wp-json/wp/v2'
    auth = (username, password)
    media_id = None
    
    if banner_bytes:
        headers = {'Content-Type': 'image/jpeg', 'Content-Disposition': 'attachment; filename="product-banner.jpg"'}
        try:
            res_media = requests.post(f"{base_api}/media", headers=headers, data=banner_bytes, auth=auth, timeout=30)
            if res_media.status_code in [200, 201]: media_id = res_media.json().get('id')
        except Exception as e: return False, f"图片上传异常: {e}"
            
    post_data = {'title': title, 'content': html_content, 'status': 'draft'}
    if media_id: post_data['featured_media'] = media_id
        
    try:
        res_post = requests.post(f"{base_api}/posts", json=post_data, auth=auth, timeout=30)
        if res_post.status_code in [200, 201]: return True, res_post.json().get('link')
        else: return False, f"草稿创建失败: {res_post.text}"
    except Exception as e: return False, f"发布异常: {e}"

# ================= UI 布局：顶部两个核心 Tab =================
tab_card, tab_banner = st.tabs(["📇 核心：商品卡片生成器", "🖼️ 测试：Banner生成与WP发布"])

# ==========================================================
#                      TAB 1: 卡片生成器
# ==========================================================
with tab_card:
    st.info("💡 当前为完整卡片生成工具 (附带 GEO/SEO 响应式支持)。")
    
    st.markdown("### 步骤 1：输入数据源")
    c_tab1, c_tab2 = st.tabs(["🤖 AI 智能海选模式", "🔗 手动直达模式 (直接填链接)"])

    with c_tab1:
        col1, col2 = st.columns(2)
        with col1: c_blog_url = st.text_input("博客文章链接", placeholder="用于语义匹配分析", key="c_blog")
        with col2: c_shop_url = st.text_input("商品列表页链接", placeholder="用于抓取候选商品", key="c_shop")
        
        if st.button("🔍 抓取并智能海选", key="c_btn_fetch_ai"):
            if not c_blog_url or not c_shop_url: st.warning("请填写完整的两个链接！")
            else:
                with st.spinner("1/2 正在抓取博客和着陆页候选商品..."):
                    blog_text = fetch_blog_context(c_blog_url)
                    pool = fetch_product_list(c_shop_url)
                if not pool: st.error("未能抓取到有效图片，请检查链接。")
                else:
                    with st.spinner(f"2/2 已抓取 {len(pool)} 个含图商品，正在请求 AI 海选..."):
                        raw_top_30 = ai_match_top_30(blog_text, pool)
                        extracted = []
                        if isinstance(raw_top_30, dict):
                            for val in raw_top_30.values():
                                if isinstance(val, list): extracted = val; break
                            raw_top_30 = extracted if extracted else [raw_top_30]
                        valid_top_30 = [item for item in raw_top_30 if isinstance(item, dict) and "url" in item]
                        for i in valid_top_30:
                            if "thumbnail" not in i: i["thumbnail"] = dummy_image
                        if valid_top_30:
                            st.session_state.c_matched_products = valid_top_30
                            st.session_state.c_step = 2
                            st.rerun()

    with c_tab2:
        st.info("💡 直接在下方粘贴商品详情页链接。一行一个。")
        c_direct_urls = st.text_area("输入商品链接：", placeholder="https://example.com/product-1\nhttps://example.com/product-2", height=150, key="c_direct")
        
        if st.button("🚀 直接获取这些商品信息", key="c_btn_fetch_direct"):
            if c_direct_urls.strip():
                with st.spinner("正在解析您提供的链接，请稍候..."):
                    fetched_products = fetch_direct_urls(c_direct_urls)
                    if fetched_products:
                        st.session_state.c_matched_products = fetched_products
                        st.session_state.c_step = 2
                        st.rerun()

    if st.session_state.c_step >= 2 and st.session_state.c_matched_products:
        st.markdown("### 步骤 2：人工确认生成名单")
        with st.form("c_selection_form"):
            temp_selected = []
            cols_per_row = 10
            for i in range(0, len(st.session_state.c_matched_products), cols_per_row):
                row_items = st.session_state.c_matched_products[i:i+cols_per_row]
                cols = st.columns(cols_per_row)
                for col, item in zip(cols, row_items):
                    with col:
                        st.image(item["thumbnail"], use_container_width=True)
                        if st.checkbox("选择", key=f"c_chk_{item['url']}", help=item['title']):
                            temp_selected.append(item["url"])
                st.write("") 
            
            if st.form_submit_button("➡️ 确认选中，进入下一步 (选择模板)", type="primary"):
                if not temp_selected: st.warning("请至少勾选一个商品！")
                else:
                    st.session_state.c_selected_urls = temp_selected
                    st.session_state.c_step = 3
                    st.rerun()

    if st.session_state.c_step >= 3 and st.session_state.c_selected_urls:
        st.markdown("### 步骤 3：选择商品卡片模板")
        dummy_data = {"image_url": dummy_image, "title": "Custom Halloween Decoration", "price": "28.00 €", "specs": "Material: Resin &nbsp;•&nbsp; Size: 10x15 cm", "buy_link": "https://fr.callie.com", "cta_text": "Add To Cart", "json_ld": ""}
        
        tmpl_cols = st.columns(len(templates))
        for col, (tmpl_name, tmpl_data) in zip(tmpl_cols, templates.items()):
            with col:
                st.markdown(f"**{tmpl_name}**")
                preview_html = tmpl_data["html"].replace("{carousel_items}", tmpl_data.get("item_html", "").format(**dummy_data) * 3).format(**dummy_data) if tmpl_data["type"] == "carousel" else tmpl_data["html"].format(**dummy_data)
                st.html(f'<div style="height: 380px; overflow-y: auto; overflow-x: hidden; border: 1px solid #f0f0f0; border-radius: 8px; padding: 10px;"><div style="transform: scale(0.75); transform-origin: top left; width: 133%;">{preview_html}</div></div>')
                
                if st.button(f"✨ 使用【{tmpl_name.split('：')[0]}】生成", key=f"c_btn_{tmpl_name}", use_container_width=True):
                    st.session_state.c_selected_template = tmpl_name
                    st.session_state.c_step = 4
                    st.rerun()

    if st.session_state.c_step >= 4 and st.session_state.c_selected_template:
        st.markdown("### 步骤 4：最终生成结果")
        st.info(f"👉 当前使用的排版：**{st.session_state.c_selected_template}**")
        
        selected_items = [p for p in st.session_state.c_matched_products if p["url"] in st.session_state.c_selected_urls]
        tmpl_config = templates[st.session_state.c_selected_template]
        my_bar = st.progress(0, text="正在逐个深入详情页提取数据...")
        all_extracted_data = []
        
        for i, item in enumerate(selected_items):
            details_data = extract_product_details(item["url"])
            if details_data:
                raw_specs = details_data.get("specs", "")
                specs_str = "&nbsp;•&nbsp;".join([str(x) for x in raw_specs]) if isinstance(raw_specs, (list, dict)) else str(raw_specs).replace('\n', '&nbsp;•&nbsp;')
                details_data["specs_formatted"] = specs_str
                details_data["specs_plain"] = str(raw_specs).replace('\n', ' ')
                all_extracted_data.append(details_data)
                
                if tmpl_config["type"] == "single":
                    ld_script = generate_single_json_ld(details_data.get("title", ""), details_data.get("image_url", ""), details_data.get("price", ""), details_data.get("specs_plain", ""), details_data.get("buy_link", ""), details_data.get("return_days", 30))
                    card_html = tmpl_config["html"].format(image_url=details_data.get("image_url", ""), title=details_data.get("title", ""), price=details_data.get("price", ""), specs=specs_str, buy_link=details_data.get("buy_link", ""), cta_text=details_data.get("cta_text", "Buy Now"), json_ld=ld_script)
                    st.markdown(f"**📝 {details_data.get('title', item['title'])}**")
                    col_left, col_right = st.columns([1, 1], gap="large")
                    with col_left: st.html(f'<div style="max-height: 450px; overflow-y: auto;">{card_html}</div>')
                    with col_right: st.code(card_html, language='html')
                    st.write("---") 
            my_bar.progress((i + 1) / len(selected_items))
            
        if tmpl_config["type"] == "carousel" and all_extracted_data:
            st.markdown("**📝 以下是包含所有勾选商品的轮播图代码组件**")
            ld_script = generate_carousel_json_ld(all_extracted_data)
            carousel_items_str = "".join([tmpl_config["item_html"].format(image_url=d.get("image_url", ""), title=d.get("title", ""), price=d.get("price", ""), buy_link=d.get("buy_link", ""), cta_text=d.get("cta_text", "Buy Now")) for d in all_extracted_data])
            final_carousel_html = tmpl_config["html"].replace("{carousel_items}", carousel_items_str).format(json_ld=ld_script)
            col_left, col_right = st.columns([1, 1], gap="large")
            with col_left: st.html(f'<div style="max-height: 450px; overflow-y: auto;">{final_carousel_html}</div>')
            with col_right: st.code(final_carousel_html, language='html')

# ==========================================================
#                      TAB 2: Banner 生成器与推送测试
# ==========================================================
with tab_banner:
    st.markdown("### 步骤 1：输入数据源获取商品图片")
    
    col1, col2 = st.columns(2)
    with col1: b_blog_url = st.text_input("博客文章链接", key="b_blog")
    with col2: b_shop_url = st.text_input("商品列表页链接", key="b_shop")
    b_direct_urls = st.text_area("或者直接填商品链接 (一行一个)：", height=100, key="b_direct")
    
    if st.button("🚀 获取商品图片池", type="primary", key="b_btn_fetch"):
        with st.spinner("正在获取..."):
            if b_direct_urls.strip(): st.session_state.b_pool = fetch_direct_urls(b_direct_urls)
            else:
                blog_text = fetch_blog_context(b_blog_url)
                raw_pool = fetch_product_list(b_shop_url)
                if raw_pool:
                    matched = ai_match_top_30(blog_text, raw_pool)
                    extracted = []
                    if isinstance(matched, dict):
                        for val in matched.values():
                            if isinstance(val, list): extracted = val; break
                        matched = extracted if extracted else [matched]
                    st.session_state.b_pool = [i for i in matched if isinstance(i, dict) and "url" in i]
            
            if st.session_state.b_pool:
                for item in st.session_state.b_pool:
                    if "thumbnail" not in item: item["thumbnail"] = dummy_image
                st.session_state.b_step = 2
                st.rerun()

    if st.session_state.b_step >= 2 and st.session_state.b_pool:
        st.markdown("---")
        st.markdown("### 步骤 2：选择用于拼图的商品 (建议选择 2-4 个)")
        
        with st.form("b_selection_form"):
            b_temp_selected = []
            cols_per_row = 8
            for i in range(0, len(st.session_state.b_pool), cols_per_row):
                row_items = st.session_state.b_pool[i:i+cols_per_row]
                cols = st.columns(cols_per_row)
                for col, item in zip(cols, row_items):
                    with col:
                        st.image(item["thumbnail"])
                        if st.checkbox("选中拼图", key=f"b_chk_{item['url']}"):
                            b_temp_selected.append(item["url"])
            
            if st.form_submit_button("➡️ 确认所选商品，去生成 Banner", type="primary"):
                if not b_temp_selected: st.warning("请至少勾选一个商品！")
                else:
                    st.session_state.b_urls = b_temp_selected
                    st.session_state.b_step = 3
                    st.rerun()

    if st.session_state.b_step >= 3 and st.session_state.b_urls:
        st.markdown("---")
        st.markdown("### 步骤 3：生成与发布流程测试")
        
        col_b1, col_b2 = st.columns([1, 1], gap="large")
        with col_b1:
            st.info("🖼️ 根据选中的商品，自动裁切拼接出一张 1200x630 的标准横幅图。")
            if st.button("🎨 1. 一键生成 Banner", key="b_btn_gen"):
                with st.spinner("下载原图并拼接中..."):
                    selected_items = [p for p in st.session_state.b_pool if p["url"] in st.session_state.b_urls]
                    img_urls = [item["thumbnail"] for item in selected_items]
                    banner_data = create_banner_collage(img_urls)
                    if banner_data:
                        st.session_state.b_banner_bytes = banner_data
                        st.success("✅ Banner 生成成功！")
                    else: st.error("拼图失败，未获取到有效图片。")
            
            if st.session_state.b_banner_bytes:
                st.image(st.session_state.b_banner_bytes, caption="已生成的 1200x630 Banner 预览图")

        with col_b2:
            st.info("🚀 填入信息，将刚才生成的 Banner 上传至媒体库，并创建一篇草稿。")
            
            # 核心缓存逻辑：如果没提取过数据，则提取；如果提取过，直接拿缓存。
            if not st.session_state.b_extracted_data:
                selected_items = [p for p in st.session_state.b_pool if p["url"] in st.session_state.b_urls]
                with st.spinner("正在提取选中商品的详情用于发布测试..."):
                    temp_extracted = []
                    for item in selected_items:
                        d = extract_product_details(item["url"])
                        if d:
                            # 为测试发布生成一个极简卡片
                            card_html = f'<div style="border:1px solid #eee; padding:15px; margin-bottom:15px; display:flex;"><img src="{d.get("image_url")}" width="150" style="margin-right:20px;"><div><h3>{d.get("title")}</h3><p style="color:red; font-size:20px;"><b>{d.get("price")}</b></p><a href="{d.get("buy_link")}" target="_blank" style="background:#ff6f59; color:#fff; padding:10px 20px; text-decoration:none; border-radius:5px;">Buy Now</a></div></div>'
                            temp_extracted.append(card_html)
                    st.session_state.b_extracted_data = temp_extracted
                    st.session_state.b_final_html_str = "\n".join(temp_extracted)
            
            wp_url = st.text_input("WordPress 网站地址 (如 https://yoursite.com)", key="b_wp_url")
            c1, c2 = st.columns(2)
            with c1: wp_user = st.text_input("用户名", key="b_wp_user")
            with c2: wp_pass = st.text_input("应用密码 (App Password)", type="password", key="b_wp_pass")
            post_title = st.text_input("博客草稿标题", value="🔥 自动 Banner 推送测试", key="b_wp_title")
            
            if st.button("🚀 2. 推送至 WordPress (保存为草稿)", type="primary", key="b_btn_push"):
                if not st.session_state.b_banner_bytes:
                    st.warning("请先在左侧点击生成 Banner！")
                elif not wp_url or not wp_user or not wp_pass:
                    st.warning("请填完所有的 WordPress 验证信息！")
                else:
                    with st.spinner("正在通过 REST API 与 WordPress 通信，这可能需要几十秒..."):
                        # 测试发布时，连同生成的极简卡片 HTML 一起发布
                        html_content = '<p>这是一篇通过 API 自动生成的测试草稿，包含了自动拼接的 Banner 和提取的商品卡片。</p><hr>' + st.session_state.b_final_html_str
                        success, msg = push_to_wordpress(wp_url, wp_user, wp_pass, post_title, html_content, st.session_state.b_banner_bytes)
                        if success: st.success("🎉 发布成功！由于接口特性，请登录 WordPress 后台查看最新草稿。")
                        else: st.error(msg)
