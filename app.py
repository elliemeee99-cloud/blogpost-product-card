import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from urllib.parse import urljoin
import pandas as pd

# ================= 配置与初始化 =================
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")
st.title("🛍️ 博客商品卡片自动生成器 (精细控制版)")

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
    """抓取博客正文用于语义分析"""
    soup = get_soup(blog_url)
    if not soup: return ""
    return soup.get_text(separator='\n', strip=True)[:4000]

def fetch_product_list(category_url):
    """抓取最多 60 个商品候选池供 AI 海选"""
    soup = get_soup(category_url)
    if not soup: return []
    
    seen_urls = set()
    products = []
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        full_url = urljoin(category_url, href)
        if len(title) > 5 and full_url not in seen_urls and "javascript" not in full_url:
            seen_urls.add(full_url)
            products.append({"title": title, "url": full_url})
            if len(products) >= 60:
                break
    return products

def ai_match_top_30(blog_text, product_list):
    """AI 根据博客内容从候选池中选出最匹配的 30 个"""
    prompt = f"""
    You are an expert e-commerce recommender.
    I will provide a Blog Post content and a list of product candidates (title + URL).
    Based on the context, theme, and audience of the Blog Post, select exactly the top 30 most relevant products (or all of them if there are fewer than 30).
    
    Blog Post:
    {blog_text[:3000]}
    
    Product Candidates:
    {json.dumps(product_list, ensure_ascii=False)}
    
    Output ONLY a JSON array of the selected products, keeping their original "title" and "url". No other text.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if "json" in prompt.lower() else None,
            max_tokens=2500
        )
        result_text = response.choices[0].message.content
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json\n", "").replace("```", "")
        return json.loads(result_text)
    except Exception as e:
        st.error(f"匹配出错: {e}")
        return product_list[:30]

def extract_product_details(product_url):
    """深入详情页提取：高清图、无翻译原语言详情、精确规格"""
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
    main_image = urljoin(product_url, main_image) if main_image else "[https://via.placeholder.com/400x300](https://via.placeholder.com/400x300)"

    text_content = soup.get_text(separator='\n', strip=True)[:5000]
    
    prompt = f"""
    Analyze the following product page text. 
    CRITICAL RULE: DO NOT TRANSLATE. You MUST extract content in the EXACT ORIGINAL LANGUAGE of the webpage. No Chinese unless the page is in Chinese.
    
    Extract into JSON:
    1. "title": The product name.
    2. "price": The price (e.g., "28,00 €").
    3. "details": Extract ONLY the EXACT FIRST PARAGRAPH of the product description. Do not summarize or alter the text.
    4. "specs": Extract the specifications list exactly as they appear.
    5. "cta_text": Generate a "Buy Now" button text in the page's original language (e.g., "Acheter maintenant").

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
<div style="display: flex; flex-direction: row; align-items: stretch; border-radius: 15px; overflow: hidden; background-color: #FAFAFA; box-shadow: 0 4px 15px rgba(255, 111, 89, 0.1); margin-bottom: 20px; font-family: sans-serif; max-width: 800px;">
    <div style="flex: 1; min-width: 250px;">
        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: cover;" alt="{title}">
    </div>
    <div style="flex: 1.5; padding: 20px; display: flex; flex-direction: column; justify-content: space-between;">
        <h3 style="margin-top: 0; color: #4A403A; font-size: 18px; margin-bottom: 15px;">{title}</h3>
        <div style="margin-bottom: 15px;">
            <span style="background-color: #FF6F59; color: #FFFFFF; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 15px;">🏷️ {price}</span>
        </div>
        <div style="background-color: #FFF5E4; border-radius: 8px; padding: 15px; margin-bottom: 20px; font-size: 13px; color: #4A403A; line-height: 1.6;">
            <strong>💡 </strong>{details}<br><br>
            <strong>⚙️ </strong>{specs}
        </div>
        <a href="{buy_link}" target="_blank" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; transition: background-color 0.3s;" onmouseover="this.style.backgroundColor='#43D8C9'" onmouseout="this.style.backgroundColor='#FF6F59'">{cta_text}</a>
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
            st.error("未能从商品列表页抓取到商品，请检查链接。")
        else:
            with st.spinner(f"2/2 已抓取 {len(pool)} 个候选链接，正在请求 AI 根据博客内容海选出最匹配的 30 个..."):
                top_30 = ai_match_top_30(blog_text, pool)
                
                # 默认全部不勾选，由人工决定
                for item in top_30:
                    item["Select"] = False 
                
                st.session_state.matched_products = top_30
                st.session_state.step = 2

if st.session_state.step >= 2 and st.session_state.matched_products:
    st.markdown("### 步骤 2：人工确认生成名单")
    st.info("以下是 AI 结合博客内容海选出的 30 个商品。请勾选您需要生成独立卡片的商品：")
    
    df = pd.DataFrame(st.session_state.matched_products)
    if "Select" in df.columns:
        df = df[["Select", "title", "url"]]
        
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn("生成卡片", default=False),
            "title": st.column_config.TextColumn("商品标题", width="medium"),
            "url": st.column_config.LinkColumn("商品链接", width="large")
        },
        disabled=["title", "url"],
        hide_index=True,
        use_container_width=True
    )
    
    if st.button("✨ 生成独立商品卡片", type="primary"):
        selected_rows = edited_df[edited_df["Select"] == True]
        
        if selected_rows.empty:
            st.warning("请至少勾选一个商品！")
        else:
            st.markdown("### 步骤 3：最终结果")
            tabs = st.tabs(["👁️ 视觉预览", "💻 独立 HTML 代码"])
            
            progress_text = "正在逐个深入详情页提取数据..."
            my_bar = st.progress(0, text=progress_text)
            
            total = len(selected_rows)
            for i, (_, row) in enumerate(selected_rows.iterrows()):
                prod_url = row["url"]
                prod_title_preview = row["title"]
                
                details_data = extract_product_details(prod_url)
                
                if details_data:
                    card_html = html_template.format(
                        image_url=details_data.get("image_url", ""),
                        title=details_data.get("title", ""),
                        price=details_data.get("price", ""),
                        details=details_data.get("details", ""),
                        specs=details_data.get("specs", "").replace('\n', '<br>'),
                        buy_link=details_data.get("buy_link", ""),
                        cta_text=details_data.get("cta_text", "Buy Now")
                    )
                    
                    # 视觉预览 Tab
                    with tabs[0]:
                        st.components.v1.html(card_html, height=280)
                    
                    # 代码 Tab：每个商品分离输出独立的带标题的代码块
                    with tabs[1]:
                        st.markdown(f"**📝 {details_data.get('title', prod_title_preview)}**")
                        st.code(card_html, language='html')
                
                my_bar.progress((i + 1) / total, text=f"已处理 {i+1}/{total} 个卡片...")
            
            st.success(f"✅ 成功生成 {total} 个独立商品卡片！请在“独立 HTML 代码”标签页中分别复制使用。")
