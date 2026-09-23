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
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")

st.markdown("""
<style>
[data-testid="stTooltipIcon"] svg { display: none !important; }
[data-testid="stTooltipIcon"]::after { content: "ⓘ"; font-size: 16px; color: #888; margin-left: 2px; }
</style>
""", unsafe_allow_html=True)

st.title("🛍️ 博客商品卡片自动生成器 (全自动发布版)")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

# 状态管理
if "matched_products" not in st.session_state: st.session_state.matched_products = []
if "step" not in st.session_state: st.session_state.step = 1
if "selected_urls" not in st.session_state: st.session_state.selected_urls = []
if "selected_template" not in st.session_state: st.session_state.selected_template = ""
# 新增：用于缓存提取的数据，防止在输入博客密码时刷新页面导致重新扣费抓取
if "extracted_data" not in st.session_state: st.session_state.extracted_data = []
if "final_html_str" not in st.session_state: st.session_state.final_html_str = ""
if "banner_bytes" not in st.session_state: st.session_state.banner_bytes = None

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

# ================= 核心爬虫与 AI 函数 =================

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except:
        return None

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
    prompt = f"""
    You are an expert e-commerce recommender.
    I will provide a Blog Post content and a list of product candidates.
    CRITICAL INSTRUCTION: Select and return AS MANY relevant products as possible, up to a maximum of 30. 
    Blog Post: {blog_text[:3000]}
    Product Candidates: {json.dumps(product_list, ensure_ascii=False)}
    Output ONLY a JSON array of the selected products, keeping their original "title", "url", and "thumbnail".
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if "json" in prompt.lower() else None,
            max_tokens=4000
        )
        return json.loads(clean_json_response(response.choices[0].message.content))
    except:
        return product_list[:30]

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
    Analyze the following product page text. DO NOT TRANSLATE. Extract in the EXACT ORIGINAL LANGUAGE of the webpage.
    CRITICAL RULES FOR PRICE: NEVER extract shipping fees. {price_hint}
    
    Extract into JSON:
    1. "title": The EXACT product name.
    2. "price": The true product price exactly as written.
    3. "return_days": Extract ONLY the numeric days (e.g., 99). Default 30.
    4. "specs": Extract ONLY the top 1-3 physical specifications. Very brief. Default "Standard".
    5. "cta_text": Generate a "Buy Now" button text in the original language.
    Page Text: {text_content}
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1500
        )
        result = json.loads(clean_json_response(response.choices[0].message.content))
        result["image_url"] = main_image
        result["buy_link"] = product_url
        return result
    except Exception as e:
        return None

# ================= 核心清洗、拼接与推送 =================

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

def create_banner_collage(image_urls):
    """提取商品主图，利用 Pillow 拼接成 1200x630 的 Banner"""
    imgs = []
    for url in image_urls:
        if len(imgs) >= 4: break # 最多拼4张图
        if url.startswith("data:image"): continue
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                img = Image.open(BytesIO(res.content)).convert("RGB")
                imgs.append(img)
        except:
            pass
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
    """一键发布到 WordPress"""
    base_api = wp_url.rstrip('/') + '/wp-json/wp/v2'
    auth = (username, password)
    media_id = None
    
    # 1. 上传 Banner 进媒体库
    if banner_bytes:
        headers = {'Content-Type': 'image/jpeg', 'Content-Disposition': 'attachment; filename="product-banner.jpg"'}
        try:
            res_media = requests.post(f"{base_api}/media", headers=headers, data=banner_bytes, auth=auth, timeout=30)
            if res_media.status_code in [200, 201]:
                media_id = res_media.json().get('id')
        except Exception as e:
            return False, f"图片上传失败: {e}"
            
    # 2. 创建文章草稿
    post_data = {'title': title, 'content': html_content, 'status': 'draft'}
    if media_id: post_data['featured_media'] = media_id
        
    try:
        res_post = requests.post(f"{base_api}/posts", json=post_data, auth=auth, timeout=30)
        if res_post.status_code in [200, 201]:
            return True, res_post.json().get('link')
        else:
            return False, f"文章创建失败: {res_post.text}"
    except Exception as e:
        return False, f"网络请求失败: {e}"

# ================= 界面工作流 =================

st.markdown("### 步骤 1：输入数据源")

tab1, tab2 = st.tabs(["🤖 AI 智能海选模式", "🔗 手动直达模式 (直接填链接)"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="用于语义匹配分析")
    with col2: shop_url = st.text_input("商品列表页/着陆页链接 (Landing Page)", placeholder="用于抓取候选商品")
    
    if st.button("🔍 抓取并智能海选"):
        if not blog_url or not shop_url: st.warning("请填写完整的两个链接！")
        else:
            with st.spinner("正在抓取并请求 AI 海选..."):
                blog_text = fetch_blog_context(blog_url)
                pool = fetch_product_list(shop_url)
                if pool:
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
                        st.session_state.matched_products = valid_top_30
                        st.session_state.step = 2
                        st.rerun()

with tab2:
    st.info("💡 如果不需要给 Blog 找对应的商品，请直接在下方粘贴商品详情页链接。一行一个。")
    direct_urls = st.text_area("输入商品链接：", placeholder="https://example.com/product-1\nhttps://example.com/product-2", height=150)
    
    if st.button("🚀 直接获取这些商品信息"):
        if direct_urls.strip():
            with st.spinner("正在解析您提供的链接，请稍候..."):
                fetched_products = fetch_direct_urls(direct_urls)
                if fetched_products:
                    st.session_state.matched_products = fetched_products
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
                    if st.checkbox("选择", key=f"chk_{item['url']}", help=item['title']):
                        temp_selected.append(item["url"])
        if st.form_submit_button("➡️ 确认选中，进入下一步 (选择模板)", type="primary"):
            if temp_selected:
                st.session_state.selected_urls = temp_selected
                st.session_state.step = 3
                st.rerun()

if st.session_state.step >= 3 and st.session_state.selected_urls:
    st.markdown("### 步骤 3：选择商品卡片模板")
    dummy_data = {"image_url": dummy_image, "title": "Custom Halloween Decoration", "price": "28.00 €", "specs": "Material: Resin &nbsp;•&nbsp; Size: 10x15 cm", "buy_link": "https://fr.callie.com", "cta_text": "Add To Cart", "json_ld": ""}
    
    tmpl_cols = st.columns(len(templates))
    for col, (tmpl_name, tmpl_data) in zip(tmpl_cols, templates.items()):
        with col:
            st.markdown(f"**{tmpl_name}**")
            preview_html = tmpl_data["html"].replace("{carousel_items}", tmpl_data.get("item_html", "").format(**dummy_data) * 3).format(**dummy_data) if tmpl_data["type"] == "carousel" else tmpl_data["html"].format(**dummy_data)
            st.html(f'<div style="height: 380px; overflow-y: auto; overflow-x: hidden; border: 1px solid #f0f0f0; border-radius: 8px; padding: 10px;"><div style="transform: scale(0.75); transform-origin: top left; width: 133%;">{preview_html}</div></div>')
            if st.button(f"✨ 使用【{tmpl_name.split('：')[0]}】生成", key=f"btn_{tmpl_name}", use_container_width=True):
                st.session_state.selected_template = tmpl_name
                st.session_state.extracted_data = [] # 切换模板时重置数据
                st.session_state.final_html_str = ""
                st.session_state.banner_bytes = None
                st.session_state.step = 4
                st.rerun()

if st.session_state.step >= 4 and st.session_state.selected_template:
    st.markdown("---")
    st.markdown("### 步骤 4：最终卡片生成结果")
    tmpl_config = templates[st.session_state.selected_template]
    
    # 核心缓存逻辑：如果没提取过数据，则提取；如果已经提取过了，就直接拿缓存（防止底部输入密码时刷新扣费）
    if not st.session_state.extracted_data:
        selected_items = [p for p in st.session_state.matched_products if p["url"] in st.session_state.selected_urls]
        my_bar = st.progress(0, text="正在深入提取数据...")
        temp_extracted = []
        
        for i, item in enumerate(selected_items):
            details_data = extract_product_details(item["url"])
            if details_data:
                raw_specs = details_data.get("specs", "")
                specs_str = "&nbsp;•&nbsp;".join([str(x) for x in raw_specs]) if isinstance(raw_specs, (list, dict)) else str(raw_specs).replace('\n', '&nbsp;•&nbsp;')
                details_data["specs_formatted"] = specs_str
                details_data["specs_plain"] = str(raw_specs).replace('\n', ' ')
                
                if tmpl_config["type"] == "single":
                    ld_script = generate_single_json_ld(details_data.get("title", ""), details_data.get("image_url", ""), details_data.get("price", ""), details_data.get("specs_plain", ""), details_data.get("buy_link", ""), details_data.get("return_days", 30))
                    card_html = tmpl_config["html"].format(image_url=details_data.get("image_url", ""), title=details_data.get("title", ""), price=details_data.get("price", ""), specs=specs_str, buy_link=details_data.get("buy_link", ""), cta_text=details_data.get("cta_text", "Buy Now"), json_ld=ld_script)
                    details_data["card_html"] = card_html
                temp_extracted.append(details_data)
            my_bar.progress((i + 1) / len(selected_items))
            
        st.session_state.extracted_data = temp_extracted
        if tmpl_config["type"] == "carousel" and temp_extracted:
            ld_script = generate_carousel_json_ld(temp_extracted)
            carousel_items_str = "".join([tmpl_config["item_html"].format(image_url=d.get("image_url", ""), title=d.get("title", ""), price=d.get("price", ""), buy_link=d.get("buy_link", ""), cta_text=d.get("cta_text", "Buy Now")) for d in temp_extracted])
            st.session_state.final_html_str = tmpl_config["html"].replace("{carousel_items}", carousel_items_str).format(json_ld=ld_script)
        else:
            st.session_state.final_html_str = "\n<br>\n".join([d["card_html"] for d in temp_extracted])
        st.rerun()

    # 渲染缓存的 HTML
    if tmpl_config["type"] == "single":
        for data in st.session_state.extracted_data:
            st.markdown(f"**📝 {data.get('title', '')}**")
            col_left, col_right = st.columns([1, 1], gap="large")
            with col_left: st.html(f'<div style="max-height: 450px; overflow-y: auto;">{data["card_html"]}</div>')
            with col_right: st.code(data["card_html"], language='html')
            st.write("---")
    else:
        st.markdown("**📝 包含所有勾选商品的轮播图代码组件**")
        col_left, col_right = st.columns([1, 1], gap="large")
        with col_left: st.html(f'<div style="max-height: 450px; overflow-y: auto;">{st.session_state.final_html_str}</div>')
        with col_right: st.code(st.session_state.final_html_str, language='html')

    # ================= 步骤 5：全自动流水线 =================
    st.markdown("### 步骤 5：自动生成 Banner 与推送到博客")
    col_b1, col_b2 = st.columns([1, 1])
    
    with col_b1:
        st.info("🖼️ 自动抽取前 4 张商品主图，生成 1200x630 标准 Banner")
        if st.button("🎨 1. 一键生成拼图 Banner", type="secondary"):
            with st.spinner("正在下载原图并裁切拼接..."):
                img_urls = [d.get("image_url") for d in st.session_state.extracted_data if d.get("image_url")]
                banner_bytes = create_banner_collage(img_urls)
                if banner_bytes:
                    st.session_state.banner_bytes = banner_bytes
                    st.success("✅ Banner 生成成功！")
                else:
                    st.error("拼图失败，未获取到有效图片。")
        
        if st.session_state.banner_bytes:
            st.image(st.session_state.banner_bytes, caption="已生成的 1200x630 博客横幅")

    with col_b2:
        st.info("🚀 填入 WordPress 应用密码，自动创建带 Banner 的草稿文章")
        wp_url = st.text_input("WordPress 网站地址 (如 https://yoursite.com)")
        col_cred1, col_cred2 = st.columns(2)
        with col_cred1: wp_user = st.text_input("用户名")
        with col_cred2: wp_pass = st.text_input("应用密码 (App Password)", type="password")
        post_title = st.text_input("博客草稿标题", value="🔥 推荐好物大盘点")
        
        if st.button("🚀 2. 推送至 WordPress (保存为草稿)", type="primary"):
            if not wp_url or not wp_user or not wp_pass:
                st.warning("请填完所有的 WordPress 配置项！")
            else:
                with st.spinner("正在与 WordPress API 通信... (此过程可能需要几十秒)"):
                    success, msg = push_to_wordpress(
                        wp_url, wp_user, wp_pass, post_title, 
                        st.session_state.final_html_str, 
                        st.session_state.banner_bytes
                    )
                    if success:
                        st.success(f"🎉 发布成功！由于 WordPress API 特性，草稿链接不支持直接访问，请登录您的 WordPress 后台查看。")
                    else:
                        st.error(msg)
