import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from urllib.parse import urljoin

# 1. 页面与 API 配置
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")
st.title("🛍️ 博客商品卡片自动生成器")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

# 2. 网页抓取通用函数 (强化图片提取与相对路径补全)
def scrape_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 提取正文文本和链接
        text_content = soup.get_text(separator=' ', strip=True)[:4000]
        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if len(text) > 2:
                links.append(f"[{text}]({a['href']})")
                
        # 提取图片 (兼顾懒加载并补全完整域名)
        images = []
        for img in soup.find_all('img'):
            src = img.get('data-src') or img.get('data-original') or img.get('src')
            if src:
                # 自动将 /images/pic.jpg 这样的相对路径补全为带域名的绝对路径
                full_img_url = urljoin(url, src) 
                if full_img_url not in images:
                    images.append(full_img_url)
        
        return f"页面文本：\n{text_content}\n\n页面链接：\n" + "\n".join(links[:100]) + "\n\n页面图片：\n" + "\n".join(images[:80])
    except Exception as e:
        return str(e)

# 3. HTML 卡片模板 (夏日汽水多巴胺配色)
html_template = """
<div style="display: flex; flex-direction: row; align-items: stretch; border-radius: 15px; overflow: hidden; background-color: #FAFAFA; box-shadow: 0 4px 15px rgba(255, 111, 89, 0.1); margin-bottom: 20px; font-family: sans-serif; max-width: 800px;">
    <div style="flex: 1; min-width: 200px;">
        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: cover;" alt="{title}">
    </div>
    <div style="flex: 1.5; padding: 20px; display: flex; flex-direction: column; justify-content: space-between;">
        <h3 style="margin-top: 0; color: #4A403A; font-size: 18px;">{title}</h3>
        <div style="margin-bottom: 15px;">
            <span style="background-color: #FF6F59; color: #FFFFFF; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">🏷️ {price}</span>
        </div>
        <div style="background-color: #FFF5E4; border-radius: 8px; padding: 12px; margin-bottom: 15px; font-size: 13px; color: #4A403A; line-height: 1.5;">
            <strong>💡 详情:</strong> {details}<br><br>
            <strong>⚙️ 规格:</strong> {specs}
        </div>
        <a href="{buy_link}" target="_blank" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; transition: background-color 0.3s;" onmouseover="this.style.backgroundColor='#43D8C9'" onmouseout="this.style.backgroundColor='#FF6F59'">立即获取 🚀</a>
    </div>
</div>
"""

# 4. 主界面交互
st.markdown("### 第一步：输入数据源")
col1, col2 = st.columns(2)
with col1:
    blog_url = st.text_input("博客文章链接", placeholder="输入你的 Blog URL")
with col2:
    shop_url = st.text_input("候选商品列表页链接", placeholder="输入电商页面 URL")

if st.button("开始匹配并生成卡片 🚀", type="primary"):
    if not blog_url or not shop_url:
        st.warning("⚠️ 请填写完整的两个链接！")
    else:
        with st.spinner("正在抓取网页并请求 DeepSeek 进行语义匹配，请稍候..."):
            # 抓取内容
            blog_data = scrape_page(blog_url)
            shop_data = scrape_page(shop_url)
            
            # 构建 Prompt
            prompt = f"""
            你是一个资深的电商导购专家。我将给你一篇博客文章的内容，以及一个商品候选页面的内容（包含文本、链接和图片列表）。
            请根据博客文章的上下文（主题、情感、受众），从商品页面中挑选出最相关的 3 个商品。
            
            博客内容：
            {blog_data[:2000]}
            
            商品候选页内容：
            {shop_data[:5000]}
            
            请严格按照以下 JSON 格式输出，不要包含任何其他说明文字：
            [
              {{
                "title": "精炼后的商品标题",
                "price": "提取到的价格(如果找不到则写 '查看详情')",
                "details": "根据博客内容写一句推荐理由",
                "specs": "提取尺寸/材质/规则等，找不到则写 '通用规则'",
                "buy_link": "商品购买链接",
                "image_url": "从上面提供的'页面图片'列表中，挑选出与该商品最匹配的图片链接。如果绝对找不到，必须固定填入: https://via.placeholder.com/400x300?text=Image+Not+Found"
              }}
            ]
            """
            
            try:
                # 调用 DeepSeek API
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"} if "json" in prompt else None,
                    max_tokens=2000
                )
                
                # 解析返回的 JSON 字符串
                result_text = response.choices[0].message.content
                if result_text.startswith("```json"):
                    result_text = result_text.replace("```json\n", "").replace("```", "")
                elif result_text.startswith("```"):
                    result_text = result_text.replace("```\n", "").replace("```", "")
                
                products = json.loads(result_text)
                
                st.success("✅ 匹配生成成功！")
                
                st.markdown("### 第二步：预览与代码获取")
                tabs = st.tabs(["👁️ 视觉预览", "💻 纯 HTML 代码"])
                
                final_html_codes = ""
                
                with tabs[0]:
                    for p in products:
                        # 渲染变量到模板中，并加入后备默认值以防 LLM 漏填字段
                        card_html = html_template.format(
                            image_url=p.get("image_url", "https://via.placeholder.com/400x300?text=Image+Not+Found"),
                            title=p.get("title", "未命名商品"),
                            price=p.get("price", "查看详情"),
                            details=p.get("details", "无推荐理由"),
                            specs=p.get("specs", "通用规则"),
                            buy_link=p.get("buy_link", "#")
                        )
                        st.components.v1.html(card_html, height=250)
                        final_html_codes += card_html + "\n\n"
                        
                with tabs[1]:
                    st.code(final_html_codes, language='html')
                    st.info("💡 提示：点击代码框右上角的复制按钮，直接粘贴到 WordPress 的【自定义 HTML】区块中即可！")
                    
            except Exception as e:
                st.error(f"❌ 处理过程中出现错误: {e}")
