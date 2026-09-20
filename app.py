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

st.title("🛍️ 博客商品卡片自动生成器 (多模板专业版)")

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

# ================= HTML 模板库 =================
# 修复了破图问题，使用了稳定的外部图片
dummy_image = "https://images.unsplash.com/photo-1605806616949-1e87b487cb2a?auto=format&fit=crop&w=400&q=80"

templates = {
    "模板 1：左右结构 (经典极简)": {
        "type": "single", # 单个商品独立成一段代码
        "height": 220,
        "html": """
<div style="display: flex; flex-direction: row; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; max-width: 100%; min-height: 200px; box-sizing: border-box; margin-bottom: 20px;">
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
        "type": "single",
        "height": 450,
        "html": """
<div style="background-color: #FFF8EC; border-radius: 24px; padding: 18px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 350px; box-sizing: border-box; border: 1px solid #F7E8D5; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto 20px auto;">
    <div style="width: 100%; aspect-ratio: 1/1; border-radius: 16px; overflow: hidden; margin-bottom: 16px; background-color: #fff; display: flex; align-items: center; justify-content: center;">
        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: contain;" alt="{title}">
    </div>
    <h3 style="margin: 0 0 10px 0; color: #3E2723; font-size: 18px; font-weight: 800; line-height: 1.3;">{title}</h3>
    <div style="color: #A1887F; font-size: 12px; margin-bottom: 20px; font-weight: 500;">{specs}</div>
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #F59E0B; font-size: 22px; font-weight: 800;">{price}</span>
        <a href="{buy_link}" target="_blank" style="background-color: #F59E0B; color: #ffffff; text-decoration: none; padding: 10px 24px; border-radius: 24px; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3); transition: opacity 0.3s;" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 3：多商品轮播 (组合模块)": {
        "type": "carousel", # 多个商品打包成一段代码
        "height": 400,
        "html": """
<!-- 轮播图外层容器，支持横向滚动 -->
<div style="display: flex; overflow-x: auto; gap: 16px; padding: 20px 10px; background-color: #FAFAFA; font-family: sans-serif; -webkit-overflow-scrolling: touch; border-radius: 12px;">
    {carousel_items}
</div>
""",
        "item_html": """
    <!-- 单个轮播卡片 -->
    <div style="flex: 0 0 auto; width: 220px; background-color: #FFFFFF; border-radius: 16px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: space-between;">
        <div style="width: 100%; aspect-ratio: 1/1; border-radius: 12px; overflow: hidden; margin-bottom: 12px; background-color: #f9f9f9; display: flex; align-items: center; justify-content: center;">
            <img src="{image_url}" style="width: 100%; height: 100%; object-fit: contain;" alt="{title}">
        </div>
        <h3 style="margin: 0 0 8px 0; color: #333333; font-size: 14px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">{title}</h3>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto;">
            <span style="color: #333333; font-size: 16px; font-weight: 800;">{price}</span>
            <a href="{buy_link}" target="_blank" style="background-color: #E8D3C3; color: #6D4C41; text-decoration: none; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: bold;">{cta_text}</a>
        </div>
    </div>
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

def fetch_direct_urls(url_list_text):
    urls = [u.strip() for u in url_list_text.split('\n') if u.strip().startswith('http')]
    products = []
    for url in urls:
        clean_url = url.split('?')[0]
        soup = get_soup(clean_url)
        if soup:
            title = soup.title.string if soup.title else "未命名商品"
            img_url = "https://dummyimage.com/300x300/f5f5f5/a3a3a3.png&text=No+Image"
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                img_url = urljoin(clean_url, og_img['content']).split('?')[0]
            products.append({"title": title, "url": clean_url, "thumbnail": img_url})
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
    main_image = urljoin(product_url, main_image).split('?')[0] if main_image else "[https://dummyimage.com/400x400/f5f5f5/a3a3a3.png&text=No+Image](https://dummyimage.com/400x400/f5f5f5/a3a3a3.png&text=No+Image)"
    text_content = soup.get_text(separator='\n', strip=True)[:5000]
    
    # 统一提取逻辑：不再强求提取长篇 details，加快速度，只提取核心信息
    prompt = f"""
    Analyze the following product page text. DO NOT TRANSLATE. Extract in the EXACT ORIGINAL LANGUAGE.
    Extract into JSON:
    1. "title": The product name.
    2. "price": The price (e.g., "28,00 €").
    3. "specs": Extract the specifications list. If none, output "Standard".
    4. "cta_text": Generate a "Buy Now" button text in original language.
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

tab1, tab2 = st.tabs(["🤖 AI 智能海选模式", "🔗 手动直达模式 (填链接)"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="用于语义匹配分析", key="ai_blog")
    with col2: shop_url = st.text_input("商品列表页/着陆页链接 (Landing Page)", placeholder="用于抓取候选商品", key="ai_shop")
    
    if st.button("🔍 抓取并智能海选"):
        if not blog_url or not shop_url: st.warning("请填写完整的两个链接！")
        else:
            with st.spinner("1/2 正在抓取博客和着陆页候选商品..."):
                blog_text = fetch_blog_context(blog_url)
                pool = fetch_product_list(shop_url)
            if not pool: st.error("未能抓取到有效图片，请检查链接。")
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
                                if "thumbnail" not in item: item["thumbnail"] = "[https://dummyimage.com/300x300/f5f5f5/a3a3a3.png&text=No+Image](https://dummyimage.com/300x300/f5f5f5/a3a3a3.png&text=No+Image)"
                                valid_top_30.append(item)
                    
                    if valid_top_30:
                        st.session_state.matched_products = valid_top_30
                        st.session_state.step = 2
                        st.rerun()

with tab2:
    st.info("💡 如果不需要 AI 匹配，请直接在下方粘贴商品详情页链接。一行一个。")
    direct_urls = st.text_area("输入商品链接：", placeholder="[https://example.com/product-1](https://example.com/product-1)\n[https://example.com/product-2](https://example.com/product-2)", height=150)
    
    if st.button("🚀 直接获取这些商品信息"):
        if not direct_urls.strip():
            st.warning("请至少输入一个链接！")
        else:
            with st.spinner("正在解析您提供的链接，请稍候..."):
                fetched_products = fetch_direct_urls(direct_urls)
                if fetched_products:
                    st.session_state.matched_products = fetched_products
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("未能成功解析任何链接，请确保链接格式正确并以 http 开头。")

if st.session_state.step >= 2 and st.session_state.matched_products:
    st.markdown("### 步骤 2：人工确认生成名单")
    st.info(f"以下是候选池中的 {len(st.session_state.matched_products)} 个商品。勾选下方图片确认：")
    
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
    
    dummy_data = {
        "image_url": dummy_image,
        "title": "Premium Wireless Headphones",
        "price": "$129.99",
        "specs": "Color: Beige &nbsp;•&nbsp; Active Noise Cancelling",
        "buy_link": "#",
        "cta_text": "Add To Cart"
    }
    
    # 动态渲染三列模板预览（横向平铺，下方带独立生成按钮）
    tmpl_cols = st.columns(len(templates))
    for col, (tmpl_name, tmpl_data) in zip(tmpl_cols, templates.items()):
        with col:
            st.markdown(f"**{tmpl_name}**")
            
            # 如果是轮播图模板，需要渲染假的数据集合
            if tmpl_data["type"] == "carousel":
                dummy_item = tmpl_data["item_html"].format(**dummy_data)
                # 塞三个假商品进去，演示轮播效果
                preview_html = tmpl_data["html"].replace("{carousel_items}", dummy_item * 3)
            else:
                preview_html = tmpl_data["html"].format(**dummy_data)
                
            st.components.v1.html(preview_html, height=tmpl_data["height"] + 20)
            
            if st.button(f"✨ 使用【{tmpl_name.split('：')[0]}】生成", key=f"btn_{tmpl_name}", use_container_width=True):
                st.session_state.selected_template = tmpl_name
                st.session_state.step = 4
                st.rerun()

if st.session_state.step >= 4 and st.session_state.selected_template:
    st.markdown("### 步骤 4：最终生成结果")
    st.info(f"👉 当前使用的排版：**{st.session_state.selected_template}**")
    
    selected_items = [p for p in st.session_state.matched_products if p["url"] in st.session_state.selected_urls]
    tmpl_config = templates[st.session_state.selected_template]
    render_height = tmpl_config["height"] + 40
    
    my_bar = st.progress(0, text="正在逐个深入详情页提取数据...")
    total = len(selected_items)
    
    # 用于收集所有商品的数据（轮播图模式专用）
    all_extracted_data = []
    
    for i, item in enumerate(selected_items):
        prod_url = item["url"]
        prod_title_preview = item["title"]
        details_data = extract_product_details(prod_url)
        
        if details_data:
            raw_specs = details_data.get("specs", "")
            if isinstance(raw_specs, list): specs_str = "&nbsp;•&nbsp;".join([str(x) for x in raw_specs])
            elif isinstance(raw_specs, dict): specs_str = "&nbsp;•&nbsp;".join([f"{k}: {v}" for k, v in raw_specs.items()])
            else: specs_str = str(raw_specs).replace('\n', '&nbsp;•&nbsp;')
            details_data["specs_formatted"] = specs_str
            
            all_extracted_data.append(details_data)
            
            # ========== 独立卡片模式输出 ==========
            if tmpl_config["type"] == "single":
                card_html = tmpl_config["html"].format(
                    image_url=details_data.get("image_url", ""),
                    title=details_data.get("title", ""),
                    price=details_data.get("price", ""),
                    specs=specs_str,
                    buy_link=details_data.get("buy_link", ""),
                    cta_text=details_data.get("cta_text", "Buy Now")
                )
                
                st.markdown(f"**📝 {details_data.get('title', prod_title_preview)}**")
                col_left, col_right = st.columns([1, 1], gap="large")
                with col_left:
                    st.components.v1.html(card_html, height=render_height, scrolling=True)
                with col_right:
                    with st.expander("点击展开 / 复制 HTML 代码"):
                        st.code(card_html, language='html')
                st.write("---") 
        else:
            st.error(f"❌ '{prod_title_preview}' 数据抓取失败。")
        
        my_bar.progress((i + 1) / total, text=f"已处理 {i+1}/{total} 个商品...")
        
    # ========== 组合轮播模式输出 ==========
    if tmpl_config["type"] == "carousel" and all_extracted_data:
        st.markdown("**📝 以下是包含所有勾选商品的轮播图代码组件**")
        
        # 拼接所有的轮播子项
        carousel_items_str = ""
        for data in all_extracted_data:
            carousel_items_str += tmpl_config["item_html"].format(
                image_url=data.get("image_url", ""),
                title=data.get("title", ""),
                price=data.get("price", ""),
                buy_link=data.get("buy_link", ""),
                cta_text=data.get("cta_text", "Buy Now")
            )
            
        # 塞入外层容器
        final_carousel_html = tmpl_config["html"].replace("{carousel_items}", carousel_items_str)
        
        col_left, col_right = st.columns([1, 1], gap="large")
        with col_left:
            st.caption("👁️ 视觉预览 (可左右滑动)")
            st.components.v1.html(final_carousel_html, height=render_height, scrolling=True)
        with col_right:
            st.caption("💻 对应完整 HTML 代码")
            with st.expander("点击展开 / 复制 HTML 代码"):
                st.code(final_carousel_html, language='html')
                
    st.success("✅ 全部处理完毕！")
