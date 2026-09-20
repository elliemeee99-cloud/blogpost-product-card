import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from urllib.parse import urljoin

# ================= 配置与初始化 =================
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")

st.markdown("""
<style>
[data-testid="stTooltipIcon"] svg { display: none !important; }
[data-testid="stTooltipIcon"]::after { content: "ⓘ"; font-size: 16px; color: #888; margin-left: 2px; }
</style>
""", unsafe_allow_html=True)

st.title("🛍️ 博客商品卡片自动生成器 (多模板版)")

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
if "selected_urls" not in st.session_state:
    st.session_state.selected_urls = []

# ================= HTML 模板库 =================
templates = {
    "模板 1：左右结构 (极简无描述)": {
        "height": 250,
        "html": """
<div style="display: flex; flex-direction: row; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; max-width: 100%; min-height: 200px; box-sizing: border-box;">
    <div style="width: 40%; background-color: #ffffff; display: flex; align-items: center; justify-content: center; padding: 10px; box-sizing: border-box;">
        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: contain; border-radius: 8px;" alt="{title}">
    </div>
    <div style="width: 60%; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box;">
        <div>
            <h3 style="margin-top: 0; color: #333333; font-size: 16px; margin-bottom: 15px; line-height: 1.4;">{title}</h3>
            <div style="margin-bottom: 15px;">
                <span style="background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">🏷️ {price}</span>
            </div>
            <div style="background-color: #FFF5E4; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-size: 13px; color: #555555; line-height: 1.5; max-height: 120px; overflow-y: auto;">
                <strong>⚙️ </strong>{specs}
            </div>
        </div>
        <a href="{buy_link}" target="_blank" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px; transition: background-color 0.3s;" onmouseover="this.style.backgroundColor='#43D8C9'" onmouseout="this.style.backgroundColor='#FF6F59'">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 2：上下结构 (圆润多巴胺)": {
        "height": 550,
        "html": """
<div style="background-color: #FFF8EC; border-radius: 24px; padding: 18px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 350px; box-sizing: border-box; border: 1px solid #F7E8D5; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto;">
    <div style="width: 100%; aspect-ratio: 1/1; border-radius: 16px; overflow: hidden; margin-bottom: 16px; background-color: #fff; display: flex; align-items: center; justify-content: center;">
        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: contain;" alt="{title}">
    </div>
    <h3 style="margin: 0 0 10px 0; color: #3E2723; font-size: 20px; font-weight: 800; line-height: 1.3;">{title}</h3>
    <div style="color: #A1887F; font-size: 12px; margin-bottom: 12px; font-weight: 500;">{specs}</div>
    <div style="color: #5D4037; font-size: 14px; margin-bottom: 24px; line-height: 1.5; font-weight: 500;">{details}</div>
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #F59E0B; font-size: 22px; font-weight: 800;">{price}</span>
        <a href="{buy_link}" target="_blank" style="background-color: #F59E0B; color: #ffffff; text-decoration: none; padding: 10px 24px; border-radius: 24px; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3); transition: opacity 0.3s;" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">{cta_text}</a>
    </div>
</div>
"""
    }
}

# ================= 核心爬虫与 AI 函数 =================

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
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

def ai_match_top_30(blog_text, product_list):
    prompt = f"""
    You are an expert e-commerce recommender.
    I will provide a Blog Post content and a list of product candidates (title + URL + thumbnail).
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
        result_text = response.choices[0].message.content
        if result_text.startswith("```json"): result_text = result_text.replace("```json\n", "").replace("```", "")
        return json.loads(result_text)
    except:
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
        if img_tag: main_image = img_tag.get('data-src') or img_tag.get('src', '')
    main_image = urljoin(product_url, main_image).split('?')[0] if main_image else "[https://via.placeholder.com/400x300](https://via.placeholder.com/400x300)"
    text_content = soup.get_text(separator='\n', strip=True)[:5000]
    
    prompt = f"""
    Analyze the following product page text. DO NOT TRANSLATE. Extract in the EXACT ORIGINAL LANGUAGE. No Chinese.
    Extract into JSON:
    1. "title": The product name.
    2. "price": The price (e.g., "28,00 €").
    3. "specs": Extract the specifications list.
    4. "details": Extract a brief 1-2 sentence description of the product.
    5. "cta_text": Generate a "Buy Now" button text in original language.
    Page Text: {text_content}
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

# ================= 界面工作流 =================

st.markdown("### 步骤 1：输入数据源")
col1, col2 = st.columns(2)
with col1: blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="用于语义匹配分析")
with col2: shop_url = st.text_input("商品列表页/着陆页链接 (Landing Page)", placeholder="用于抓取候选商品")

if st.button("🔍 智能抓取并海选商品"):
    if not blog_url or not shop_url: st.warning("请填写完整的两个链接！")
    else:
        with st.spinner("1/2 正在抓取博客和着陆页候选商品..."):
            blog_text = fetch_blog_context(blog_url)
            pool = fetch_product_list(shop_url)
        if not pool: st.error("未能从商品列表页抓取到有效图片，请检查链接。")
        else:
            with st.spinner(f"2/2 已抓取 {len(pool)} 个含图商品，正在请求 AI 海选..."):
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
                            if "thumbnail" not in item: item["thumbnail"] = "[https://via.placeholder.com/300?text=No+Image](https://via.placeholder.com/300?text=No+Image)"
                            valid_top_30.append(item)
                
                if valid_top_30:
                    st.session_state.matched_products = valid_top_30
                    st.session_state.step = 2
                    st.rerun()

if st.session_state.step >= 2 and st.session_state.matched_products:
    st.markdown("### 步骤 2：人工确认生成名单")
    st.info(f"以下是 AI 海选出的 {len(st.session_state.matched_products)} 个商品。勾选下方图片确认：")
    
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
            st.write("") 
        
        if st.form_submit_button("➡️ 确认选中，进入下一步 (选择模板)", type="primary"):
            if not temp_selected: st.warning("请至少勾选一个商品！")
            else:
                st.session_state.selected_urls = temp_selected
                st.session_state.step = 3
                st.rerun()

if st.session_state.step >= 3 and st.session_state.selected_urls:
    st.markdown("### 步骤 3：选择商品卡片模板")
    
    # 模板选择单选框
    template_choice = st.radio(
        "请选择您想要生成的排版样式：", 
        list(templates.keys()), 
        horizontal=True
    )
    
    st.markdown("#### ✨ 模板效果预览")
    # 用于预览的虚拟数据
    dummy_data = {
        "image_url": "[https://images.unsplash.com/photo-1556228578-0d85b1a4d571?auto=format&fit=crop&w=400&q=80](https://images.unsplash.com/photo-1556228578-0d85b1a4d571?auto=format&fit=crop&w=400&q=80)",
        "title": "Vanilla ice cream",
        "price": "$16.99",
        "specs": "Vegan &nbsp;•&nbsp; Gluten Free &nbsp;•&nbsp; Organic",
        "details": "Blending cream, milk, sugar and natural vanilla. A perfect sweet treat.",
        "buy_link": "#",
        "cta_text": "Add To Cart"
    }
    
    # 获取选中模板的代码和渲染高度
    selected_tmpl_html = templates[template_choice]["html"]
    render_height = templates[template_choice]["height"]
    
    # 在左侧显示预览
    col_prev1, col_prev2 = st.columns([1.5, 2.5])
    with col_prev1:
        st.components.v1.html(selected_tmpl_html.format(**dummy_data), height=render_height)
        
    st.write("---")
    
    # 步骤 4 集成在按钮后
    if st.button("🚀 开始抓取详情并生成最终代码", type="primary"):
        st.markdown("### 步骤 4：最终生成结果")
        
        selected_items = [p for p in st.session_state.matched_products if p["url"] in st.session_state.selected_urls]
        
        my_bar = st.progress(0, text="正在逐个深入详情页提取数据...")
        total = len(selected_items)
        
        for i, item in enumerate(selected_items):
            prod_url = item["url"]
            prod_title_preview = item["title"]
            details_data = extract_product_details(prod_url)
            
            if details_data:
                # 规格清洗
                raw_specs = details_data.get("specs", "")
                if isinstance(raw_specs, list): specs_str = "&nbsp;•&nbsp;".join([str(x) for x in raw_specs])
                elif isinstance(raw_specs, dict): specs_str = "&nbsp;•&nbsp;".join([f"{k}: {v}" for k, v in raw_specs.items()])
                else: specs_str = str(raw_specs).replace('\n', '&nbsp;•&nbsp;')
                
                # 注入数据
                card_html = selected_tmpl_html.format(
                    image_url=details_data.get("image_url", ""),
                    title=details_data.get("title", ""),
                    price=details_data.get("price", ""),
                    specs=specs_str,
                    details=details_data.get("details", ""),
                    buy_link=details_data.get("buy_link", ""),
                    cta_text=details_data.get("cta_text", "Buy Now")
                )
                
                st.markdown(f"**📝 {details_data.get('title', prod_title_preview)}**")
                col_left, col_right = st.columns([1, 1], gap="large")
                
                with col_left:
                    st.caption("👁️ 视觉预览")
                    st.components.v1.html(card_html, height=render_height, scrolling=True)
                with col_right:
                    st.caption("💻 对应 HTML 代码")
                    # 将代码包裹在折叠面板中，保持界面清爽
                    with st.expander("点击展开 / 复制 HTML 代码"):
                        st.code(card_html, language='html')
                    
                st.write("---") 
            else:
                st.error(f"❌ '{prod_title_preview}' 数据抓取失败。")
            
            my_bar.progress((i + 1) / total, text=f"已处理 {i+1}/{total} 个卡片...")
        
        st.success(f"✅ 成功生成 {total} 个商品卡片！")
