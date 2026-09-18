import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from urllib.parse import urljoin
import pandas as pd

# ================= 配置与初始化 =================
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")
st.title("🛍️ 博客商品卡片自动生成器 (精细化定制版)")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

# 初始化 Session State
if "product_list" not in st.session_state:
    st.session_state.product_list = []
if "step" not in st.session_state:
    st.session_state.step = 1

# ================= 核心功能函数 =================

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
        st.error(f"网页请求失败: {e}")
        return None

def fetch_product_list(category_url):
    """从列表页抓取最多50个商品链接"""
    soup = get_soup(category_url)
    if not soup: return []
    
    # 提取所有包含文本的有效链接，去除重复，限制50个
    seen_urls = set()
    products = []
    
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        full_url = urljoin(category_url, href)
        
        # 简单过滤：标题长度适中，且不是常见的非商品链接
        if len(title) > 5 and full_url not in seen_urls and "javascript" not in full_url:
            seen_urls.add(full_url)
            products.append({"Select": False, "Title": title, "URL": full_url})
            if len(products) >= 50:
                break
    return products

def extract_product_details(product_url):
    """深入商品详情页，抓取高质量图片和精确文本"""
    soup = get_soup(product_url)
    if not soup: return None
    
    # 1. 强制获取最高质量的主图 (修复图裂问题的终极方案)
    main_image = ""
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        main_image = og_img['content']
    else:
        # 备用方案：找最大的 img 标签
        img_tag = soup.find('img')
        if img_tag:
            main_image = img_tag.get('data-src') or img_tag.get('src', '')
    
    main_image = urljoin(product_url, main_image) if main_image else "https://via.placeholder.com/400x300?text=Image+Not+Found"

    # 2. 提取页面纯文本供 LLM 分析
    text_content = soup.get_text(separator='\n', strip=True)[:6000]
    
    # 3. 严格的提示词 (禁止中文，指定第一段和规格)
    prompt = f"""
    Analyze the following product page text. 
    CRITICAL RULE: DO NOT translate. You MUST keep the EXACT original language of the webpage (e.g., French, English). No Chinese.
    
    Extract the following fields into JSON:
    1. "title": The precise name of the product.
    2. "price": The exact price (e.g., "28,00 €").
    3. "details": Extract ONLY the EXACT FIRST PARAGRAPH of the product description (Description du produit). Do not summarize.
    4. "specs": Extract the specifications (Spécifications, Matière, Mesure, etc.) EXACTLY as they appear. If it's a list, format it clearly.
    5. "cta_text": Generate a short Call to Action button text in the original language of the page (e.g., "Acheter maintenant" for French, "Buy Now" for English).

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
        result["image_url"] = main_image # 覆盖为我们抓取到的高清图
        result["buy_link"] = product_url
        return result
    except Exception as e:
        return None

# ================= 动态去除硬编码的 HTML 模板 =================
# 移除了所有中文标签，纯靠 Icon 和 LLM 提取的内容
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

# ================= 界面交互工作流 =================

# --- 步骤 1：输入链接并获取列表 ---
st.markdown("### 步骤 1：抓取商品候选池")
target_url = st.text_input("输入商品列表页/分类页链接", placeholder="例如：https://yourshop.com/category/halloween")

if st.button("🔍 抓取此页面的商品 (最多50个)"):
    if not target_url:
        st.warning("请填写链接")
    else:
        with st.spinner("正在解析网页链接..."):
            st.session_state.product_list = fetch_product_list(target_url)
            st.session_state.step = 2

# --- 步骤 2：显示列表并勾选 ---
if st.session_state.step >= 2 and st.session_state.product_list:
    st.markdown("### 步骤 2：勾选需要生成卡片的商品")
    st.info("我们在页面上找到了以下链接（已自动过滤无关链接）。请勾选您确认是商品的条目：")
    
    # 使用 st.data_editor 提供批量勾选表格
    df = pd.DataFrame(st.session_state.product_list)
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn("选择", help="勾选以生成卡片", default=False),
            "Title": st.column_config.TextColumn("抓取到的标题/文本", width="medium"),
            "URL": st.column_config.LinkColumn("商品链接", width="large")
        },
        disabled=["Title", "URL"],
        hide_index=True,
        use_container_width=True
    )
    
    # --- 步骤 3：一键生成选中卡片 ---
    if st.button("✨ 为选中的商品生成卡片", type="primary"):
        selected_rows = edited_df[edited_df["Select"] == True]
        
        if selected_rows.empty:
            st.warning("请至少勾选一个商品！")
        else:
            final_html_codes = ""
            st.markdown("### 步骤 3：生成结果")
            tabs = st.tabs(["👁️ 视觉预览", "💻 纯 HTML 代码"])
            
            # 使用进度条
            progress_text = "正在深入每个商品页面提取描述和规格..."
            my_bar = st.progress(0, text=progress_text)
            
            total = len(selected_rows)
            for i, (_, row) in enumerate(selected_rows.iterrows()):
                prod_url = row["URL"]
                
                # 请求 LLM 提取详细信息
                details_data = extract_product_details(prod_url)
                
                if details_data:
                    card_html = html_template.format(
                        image_url=details_data.get("image_url", ""),
                        title=details_data.get("title", ""),
                        price=details_data.get("price", ""),
                        details=details_data.get("details", ""),
                        specs=details_data.get("specs", "").replace('\n', '<br>'), # 处理规格换行
                        buy_link=details_data.get("buy_link", ""),
                        cta_text=details_data.get("cta_text", "Buy Now")
                    )
                    final_html_codes += card_html + "\n\n"
                    
                    with tabs[0]:
                        st.components.v1.html(card_html, height=280)
                
                my_bar.progress((i + 1) / total, text=f"已处理 {i+1}/{total} 个商品...")
            
            with tabs[1]:
                st.code(final_html_codes, language='html')
            
            st.success("✅ 所有选中商品处理完毕！")
