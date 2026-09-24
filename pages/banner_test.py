import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from urllib.parse import urljoin
from PIL import Image, ImageOps
from io import BytesIO

# ================= 配置与初始化 =================
st.set_page_config(page_title="Banner与推送测试", layout="wide", initial_sidebar_state="collapsed")

# 彻底隐藏左侧边栏
st.markdown("""
<style>
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
st.markdown("---")

st.title("🖼️ Banner 生成与 WordPress 直推测试区")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

# 独立的状态缓存
if "b_step" not in st.session_state: st.session_state.b_step = 1
if "b_pool" not in st.session_state: st.session_state.b_pool = []
if "b_urls" not in st.session_state: st.session_state.b_urls = []
if "b_banner_bytes" not in st.session_state: st.session_state.b_banner_bytes = None
if "b_final_html" not in st.session_state: st.session_state.b_final_html = ""

dummy_image = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22400%22%20viewBox%3D%220%200%20400%20400%22%3E%3Crect%20width%3D%22400%22%20height%3D%22400%22%20fill%3D%22%23F7E8D5%22%2F%3E%3Ctext%20x%3D%2250%25%22%20y%3D%2250%25%22%20dominant-baseline%3D%22middle%22%20text-anchor%3D%22middle%22%20font-family%3D%22sans-serif%22%20font-size%3D%2224%22%20fill%3D%22%233E2723%22%3E%E5%95%86%E5%93%81%E5%9B%BE%E7%89%87%E9%A2%84%E8%A7%88%3C%2Ftext%3E%3C%2Fsvg%3E"

def get_soup(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except: return None

def fetch_direct_urls(url_list_text):
    urls = [u.strip() for u in url_list_text.split('\n') if u.strip().startswith('http')]
    products = []
    for url in urls:
        soup = get_soup(url.split('?')[0])
        if soup:
            title = soup.title.string if soup.title else "未命名商品"
            img_url = dummy_image
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'): img_url = urljoin(url, og_img['content']).split('?')[0]
            products.append({"title": title, "url": url.split('?')[0], "thumbnail": img_url})
    return products

def extract_basic_details(product_url):
    soup = get_soup(product_url)
    if not soup: return None
    main_image = ""
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'): main_image = og_img['content']
    main_image = urljoin(product_url, main_image).split('?')[0] if main_image else dummy_image
    
    prompt = f"""
    Extract from text in EXACT ORIGINAL LANGUAGE. Do not extract shipping fees as price.
    Extract into JSON: "title", "price", "cta_text" (e.g. "Buy Now").
    Page Text: {soup.get_text(separator=' ', strip=True)[:3000]}
    """
    try:
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, max_tokens=500)
        res_str = response.choices[0].message.content.strip()
        if res_str.startswith("```"): res_str = res_str.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        result = json.loads(res_str)
        result["image_url"] = main_image
        result["buy_link"] = product_url
        return result
    except: return None

def create_banner_collage(image_urls):
    imgs = []
    for url in image_urls:
        if len(imgs) >= 4: break 
        if url.startswith("data:image"): continue
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200: imgs.append(Image.open(BytesIO(res.content)).convert("RGB"))
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
        headers = {'Content-Type': 'image/jpeg', 'Content-Disposition': 'attachment; filename="test-banner.jpg"'}
        try:
            res_media = requests.post(f"{base_api}/media", headers=headers, data=banner_bytes, auth=auth, timeout=30)
            if res_media.status_code in [200, 201]: media_id = res_media.json().get('id')
            else: return False, f"图片上传失败: {res_media.text}"
        except Exception as e: return False, f"图片上传异常: {e}"
            
    post_data = {'title': title, 'content': html_content, 'status': 'draft'}
    if media_id: post_data['featured_media'] = media_id
        
    try:
        res_post = requests.post(f"{base_api}/posts", json=post_data, auth=auth, timeout=30)
        if res_post.status_code in [200, 201]: return True, res_post.json().get('link')
        else: return False, f"草稿创建失败: {res_post.text}"
    except Exception as e: return False, f"发布异常: {e}"

# ================= UI 布局 =================

st.markdown("### 步骤 1：输入商品链接")
b_direct_urls = st.text_area("直接填入商品链接提取图片 (一行一个)：", height=150)
if st.button("🚀 获取商品图片", type="primary"):
    if b_direct_urls.strip():
        with st.spinner("正在解析图片..."):
            st.session_state.b_pool = fetch_direct_urls(b_direct_urls)
            st.session_state.b_step = 2
            st.session_state.b_final_html = ""
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
                    if st.checkbox("选中拼图", key=f"b_chk_{item['url']}"):
                        b_temp_selected.append(item["url"])
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
        st.info("🚀 选择目标网站，自动上传 Banner 并生成博客草稿。")
        
        my_wp_sites = {
            "🇩🇪 德语站 (www.callie.de)": {"url": "https://www.callie.de/blog", "prefix": "DE"},
            "🇫🇷 法语站 (fr.callie.com)": {"url": "https://fr.callie.com/blog", "prefix": "FR"},
            "🇪🇸 西班牙站 (www.callie.es)": {"url": "https://www.callie.es/blog", "prefix": "ES"},
            "🇮🇹 意大利站 (it.callie.com)": {"url": "https://it.callie.com/blog", "prefix": "IT"},
            "🇳🇱 荷兰站 (nl.callie.com)": {"url": "https://nl.callie.com/blog", "prefix": "NL"},
            "🇳🇴 挪威站 (no.callie.com)": {"url": "https://no.callie.com/blog", "prefix": "NO"},
            "🇸🇪 瑞典站 (www.callie.se)": {"url": "https://www.callie.se/blog", "prefix": "SE"},
            "🇫🇮 芬兰站 (www.callie.fi)": {"url": "https://www.callie.fi/blog", "prefix": "FI"},
            "🇵🇱 波兰站 (pl.callie.com)": {"url": "https://pl.callie.com/blog", "prefix": "PL"}
        }
        
        selected_site_name = st.selectbox("🎯 请选择要发布的网站：", list(my_wp_sites.keys()))
        selected_site_data = my_wp_sites[selected_site_name]
        wp_url = selected_site_data["url"]
        site_prefix = selected_site_data["prefix"]
        
        # 核心修改：统一的用户名，独立的站点密码
        user_key = "WP_USER"
        pass_key = f"WP_PASS_{site_prefix}"
        
        # 密码智能加载系统
        if user_key in st.secrets and pass_key in st.secrets:
            st.success(f"🔒 已自动加载全局账号与【{selected_site_name.split(' ')[1]}】的专属密码。")
            wp_user = st.secrets[user_key]
            wp_pass = st.secrets[pass_key]
        else:
            st.warning(f"⚠️ 未在 Secrets 中找到 {pass_key}，请手动输入或前往后台添加。")
            c1, c2 = st.columns(2)
            with c1: wp_user = st.text_input("用户名", value=st.secrets.get("WP_USER", ""))
            with c2: wp_pass = st.text_input(f"应用密码 (缺少 {pass_key})", type="password")
            
        post_title = st.text_input("博客草稿标题", value="🔥 自动 Banner 推送测试")
        
        if st.button("🚀 2. 推送至 WordPress", type="primary"):
            if not st.session_state.b_banner_bytes: 
                st.warning("请先在左侧点击生成 Banner！")
            elif not wp_user or not wp_pass: 
                st.warning("请配置或填完所有的 WordPress 验证信息！")
            else:
                with st.spinner("1/2 正在提取商品简单卡片 (用作草稿正文)..."):
                    if not st.session_state.b_final_html:
                        selected_items = [p for p in st.session_state.b_pool if p["url"] in st.session_state.b_urls]
                        temp_html = []
                        for item in selected_items:
                            d = extract_basic_details(item["url"])
                            if d: temp_html.append(f'<div style="border:1px solid #ddd; padding:10px; margin-bottom:10px; display:flex;"><img src="{d.get("image_url")}" width="100" style="margin-right:15px;"><div><h4>{d.get("title")}</h4><p style="color:red; font-size:18px;"><b>{d.get("price")}</b></p><a href="{d.get("buy_link")}" target="_blank" style="background:#ff6f59; color:#fff; padding:8px 15px; text-decoration:none; border-radius:5px;">Buy Now</a></div></div>')
                        st.session_state.b_final_html = "\n".join(temp_html)
                
                with st.spinner(f"2/2 正在向 {selected_site_name} 推送，这可能需要几十秒..."):
                    content = '<p>这是一篇自动生成的测试草稿。</p>' + st.session_state.b_final_html
                    success, msg = push_to_wordpress(wp_url, wp_user, wp_pass, post_title, content, st.session_state.b_banner_bytes)
                    if success: 
                        st.success(f"🎉 成功发布到【{selected_site_name}】！请登录对应的 WordPress 后台查看最新草稿。")
                    else: 
                        st.error(msg)
