import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from urllib.parse import urljoin

# ================= 配置与初始化 =================
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")

# 注入 CSS 黑魔法：将原生 ? 图标替换为 ⓘ 图标
st.markdown("""
<style>
[data-testid="stTooltipIcon"] svg {
    display: none !important;
}
[data-testid="stTooltipIcon"]::after {
    content: "ⓘ";
    font-size: 16px;
    color: #888;
    margin-left: 2px;
}
</style>
""", unsafe_allow_html=True)

st.title("🛍️ 博客商品卡片自动生成器 (左右分栏版)")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

if "matched_products" not in st.session_state:
    st.session_state.matched_products = []
if "step" not in st.session_state:
    st.session_state.step = 1

# ================= 核心爬虫与 AI 函数 =================

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
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
            if not img and a.parent:
                img = a.parent.find('img')
            if not img and a.parent and a.parent.parent:
                img = a.parent.parent.find('img')
                
            if img:
                src = img.get('data-src') or img.get('src')
                if src:
                    img_url = urljoin(category_url, src).split('?')[0]
                    seen_urls.add(clean_url)
                    products.append({"title": title, "url": clean_url, "thumbnail": img_url})
                    if len(products) >= 60:
                        break
    return products

def ai_match_top_30(blog_text, product_list):
    prompt = f"""
    You are an expert e-commerce recommender.
    I will provide a Blog Post content and a list of product candidates (title + URL + thumbnail).
    Based on the context, theme, and audience of the Blog Post, select exactly the top 30 most relevant products (or all of them if there are fewer than 30).
    
    Blog Post:
    {blog_text[:3000]}
    
    Product Candidates:
    {json.dumps(product_list, ensure_ascii=False)}
    
    Output ONLY a JSON array of the selected products, keeping their original "title", "url", and "thumbnail". No other text.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if "json" in prompt.lower() else None,
            max_tokens=4000
        )
        result_text = response.choices[0].message.content
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json\n", "").replace("```", "")
        return json.loads(result_text)
    except Exception as e:
        st.error(f"匹配出错: {e}")
        return product_list[:30]

def extract_product_details(product_url):
    soup = get_soup(product_url)
    if not soup: return None
    
    main_image = ""
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        main_image = og_img['content']
    else:
        img_tag = soup.find('img')
        if img_tag:
            main_image = img_tag.get('data-src') or img_tag.get('src', '')
    main_image = urljoin(product_url, main_image).split('?')[0] if main_image else "[https://via.placeholder.com/400x300](https://via.placeholder.com/400x300)"

    text_content = soup.get_text(separator='\n', strip=True)[:5000]
    
    prompt = f"""
    Analyze the following product page text. 
    CRITICAL RULE: DO NOT TRANSLATE. You MUST extract content in the EXACT ORIGINAL LANGUAGE of the webpage. No Chinese unless the page is in Chinese.
    
    Extract into JSON:
    1. "title": The product name.
    2. "price": The price (e.g., "28,00 €").
    3. "specs": Extract the specifications list exactly as they appear. If there are none, output a brief default like "Standard".
    4. "cta_text": Generate a "Buy Now" button text in the page's original language (e.g., "Acheter maintenant").

    Page Text:
    {text_content}
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1500
        )
        result = json.loads(response.choices[0].message.content)
        result["image_url"] = main_image
        result["buy_link"] = product_url
        return result
    except:
        return None

# ================= HTML 模板 =================
html_template = """
<div style="display: flex; flex-direction: row; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; max-width: 100%; min-height: 220px;">
    <div style="width: 40%; background-color: #ffffff; display: flex; align-items: center; justify-content: center; padding: 10px;">
        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: contain; border-radius: 8px;" alt="{title}">
    </div>
    <div style="width: 60%; padding: 20px; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
            <h3 style="margin-top: 0; color: #333333; font-size: 16px; margin-bottom: 15px; line-height: 1.4;">{title}</h3>
            <div style="margin-bottom: 15px;">
                <span style="background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">🏷️ {price}</span>
            </div>
            <div style="background-color: #FFF5E4; border-radius: 8px; padding: 12px; margin-bottom: 20px; font-size: 13px; color: #555555; line-height: 1.5; max-height: 150px; overflow-y: auto;">
                <strong>⚙️ </strong>{specs}
            </div>
        </div>
        <a href="{buy_link}" target="_blank" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px; transition: background-color 0.3s;" onmouseover="this.style.backgroundColor='#43D8C9'" onmouseout="this.style.backgroundColor='#FF6F59'">{cta_text}</a>
    </div>
</div>
"""

# ================= 界面工作流 =================

st.markdown("### 步骤 1：输入数据源")
col1, col2 = st.columns(2)
with col1:
    blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="用于语义匹配分析")
with col2:
    shop_url = st.text_input("商品列表页/着陆页链接 (Landing Page)", placeholder="用于抓取候选商品")

if st.button("🔍 智能抓取并海选 30 个商品"):
    if not blog_url or not shop_url:
        st.warning("请填写完整的两个链接！")
    else:
        with st.spinner("1/2 正在抓取博客和着陆页候选商品..."):
            blog_text = fetch_blog_context(blog_url)
            pool = fetch_product_list(shop_url)
            
        if not pool:
            st.error("未能从商品列表页抓取到有效商品图片，请检查链接。")
        else:
            with st.spinner(f"2/2 已抓取 {len(pool)} 个含图商品，正在请求 AI 进行语义海选..."):
                raw_top_30 = ai_match_top_30(blog_text, pool)
                
                if isinstance(raw_top_30, dict):
                    extracted = []
                    for val in raw_top_30.values():
                        if isinstance(val, list):
                            extracted = val
                            break
                    raw_top_30 = extracted if extracted else [raw_top_30]
                
                valid_top_30 = []
                if isinstance(raw_top_30, list):
                    for item in raw_top_30:
                        if isinstance(item, dict) and "url" in item:
                            if "thumbnail" not in item:
                                item["thumbnail"] = "[https://via.placeholder.com/300?text=No+Image](https://via.placeholder.com/300?text=No+Image)"
                            valid_top_30.append(item)
                
                if not valid_top_30:
                    st.error("大模型返回的数据格式异常，请稍后重试。")
                else:
                    st.session_state.matched_products = valid_top_30
                    st.session_state.step = 2

if st.session_state.step >= 2 and st.session_state.matched_products:
    st.markdown("### 步骤 2：人工确认生成名单")
    st.info("以下是 AI 海选出的商品。勾选下方图片确认生成：")
    
    with st.form("selection_form"):
        selected_urls = []
        
        # 10 列网格
        cols_per_row = 10
        for i in range(0, len(st.session_state.matched_products), cols_per_row):
            row_items = st.session_state.matched_products[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            
            for col, item in zip(cols, row_items):
                with col:
                    st.image(item["thumbnail"], use_container_width=True)
                    # 鼠标悬浮在 ⓘ 上会显示商品标题
                    if st.checkbox("选择", key=f"chk_{item['url']}", help=item['title']):
                        selected_urls.append(item["url"])
            
            st.write("") 
            
        submit_btn = st.form_submit_button("✨ 生成选中的商品卡片", type="primary")
    
    if submit_btn:
        if not selected_urls:
            st.warning("请至少勾选一个商品！")
        else:
            st.markdown("### 步骤 3：最终结果")
            
            selected_items = [p for p in st.session_state.matched_products if p["url"] in selected_urls]
            
            progress_text = "正在逐个深入详情页提取数据..."
            my_bar = st.progress(0, text=progress_text)
            
            total = len(selected_items)
            for i, item in enumerate(selected_items):
                prod_url = item["url"]
                prod_title_preview = item["title"]
                
                details_data = extract_product_details(prod_url)
                
                if details_data:
                    card_html = html_template.format(
                        image_url=details_data.get("image_url", ""),
                        title=details_data.get("title", ""),
                        price=details_data.get("price", ""),
                        specs=details_data.get("specs", "").replace('\n', '<br>'),
                        buy_link=details_data.get("buy_link", ""),
                        cta_text=details_data.get("cta_text", "Buy Now")
                    )
                    
                    st.markdown(f"**📝 {details_data.get('title', prod_title_preview)}**")
                    
                    # 核心改动：采用左右 1:1 分栏结构
                    col_left, col_right = st.columns([1, 1], gap="large")
                    
                    with col_left:
                        st.caption("👁️ 视觉预览")
                        st.components.v1.html(card_html, height=280)
                        
                    with col_right:
                        st.caption("💻 对应 HTML 代码")
                        st.code(card_html, language='html')
                        
                    st.write("---") # 底部添加分割线，区分下一个商品
                else:
                    st.error(f"❌ '{prod_title_preview}' 数据抓取失败。")
                
                my_bar.progress((i + 1) / total, text=f"已处理 {i+1}/{total} 个卡片...")
            
            st.success(f"✅ 成功生成 {total} 个商品卡片！")
