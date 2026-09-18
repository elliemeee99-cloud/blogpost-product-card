import streamlit as st

# 设置网页宽屏显示
st.set_page_config(page_title="智能商品卡片生成器", layout="wide")
st.title("🛍️ 博客商品卡片自动生成器")

# 检查 API Key 是否配置成功
st.sidebar.header("系统状态")
if "DEEPSEEK_API_KEY" in st.secrets:
    st.sidebar.success("✅ DeepSeek API Key 已连接")
else:
    st.sidebar.error("❌ 未读取到 API Key，请检查 Secrets 设置")

# 主界面输入区
st.markdown("### 第一步：输入内容与商品源")
col1, col2 = st.columns(2)
with col1:
    blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="例如：https://yourblog.com/post")
with col2:
    shop_url = st.text_input("候选商品列表页链接 (Shop URL)", placeholder="例如：https://yourshop.com/category")

# 操作按钮
if st.button("开始匹配并生成卡片 🚀", type="primary"):
    if not blog_url or not shop_url:
        st.warning("⚠️ 请先填写博客和商品页面的链接！")
    else:
        st.info("界面测试成功！下一步我们将在这里接入爬虫和大模型处理逻辑...")
