import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

# ================= 配置与初始化 =================
st.set_page_config(page_title="智能商品卡片生成器", layout="wide", initial_sidebar_state="collapsed")

# 🎨 UI 视觉重构：Google Material Design 规范 & 按钮强效变白
st.markdown("""
<style>
.stApp { background-color: #F8F9FA; color: #202124; font-family: 'Google Sans', 'Roboto', -apple-system, sans-serif; }
p, span, label { color: #5F6368 !important; }
h1, h2, h3, h4 { font-family: 'Google Sans', 'Roboto', sans-serif !important; color: #202124 !important; font-weight: 500 !important; }
h1 { font-size: 1.8rem !important; padding-bottom: 0.5rem; }
h3 { font-size: 1.2rem !important; }
[data-testid="block-container"] { padding-top: 2rem !important; padding-bottom: 4rem !important; max-width: 1200px; }

[data-testid="stPageLink-NavLink"] { background-color: #FFFFFF; border-radius: 24px; padding: 8px 20px; border: 1px solid #DADCE0; transition: all 0.2s ease; justify-content: center; font-weight: 500; }
[data-testid="stPageLink-NavLink"]:hover { background-color: #F1F3F4; border-color: #DADCE0; }
[data-testid="stPageLink-NavLink"] p { color: #1A73E8 !important; }

/* 强力修复所有按钮的字体颜色问题，包括表单提交按钮 */
button[kind="primary"], button[kind="primaryFormSubmit"], div[data-testid="stForm"] button { 
    background-color: #1A73E8 !important; 
    color: #FFFFFF !important; 
    box-shadow: none !important; 
    border: none !important; 
}
button[kind="primary"] *, button[kind="primaryFormSubmit"] *, div[data-testid="stForm"] button * { 
    color: #FFFFFF !important; 
    fill: #FFFFFF !important; 
}
button[kind="primary"]:hover, div[data-testid="stForm"] button:hover { 
    background-color: #174EA6 !important; 
    box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15) !important;
}

.stButton > button[kind="secondary"] { background: #FFFFFF !important; border: 1px solid #DADCE0 !important; color: #1A73E8 !important; }
.stButton > button[kind="secondary"] * { color: #1A73E8 !important; }
.stButton > button[kind="secondary"]:hover { background: #F1F3F4 !important; }

.stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { border-radius: 4px !important; border: 1px solid #DADCE0 !important; background-color: #FFFFFF !important; padding: 10px 14px !important; }
.stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus, .stSelectbox>div>div>div:focus { border: 2px solid #1A73E8 !important; padding: 9px 13px !important; box-shadow: none !important; }
[data-testid="stForm"], [data-testid="stExpander"] { background-color: #FFFFFF; border-radius: 8px !important; border: 1px solid #DADCE0 !important; box-shadow: none !important; padding: 20px !important; }
[data-testid="stAlert"] { border-radius: 8px !important; border: 1px solid #DADCE0 !important; background-color: #FFFFFF !important; border-left: 4px solid #1A73E8 !important; }

.stTabs [data-baseweb="tab-list"] { gap: 16px; border-bottom: 1px solid #DADCE0; padding-bottom: 0px; }
.stTabs [data-baseweb="tab"] { padding: 12px 16px !important; background-color: transparent; border: none !important; font-weight: 500; }
.stTabs [aria-selected="true"] { border-bottom: 3px solid #1A73E8 !important; }
.stTabs [aria-selected="true"] * { color: #1A73E8 !important; }

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
st.markdown("<br>", unsafe_allow_html=True)

st.title("🛍️ 博客商品卡片自动生成器 (GEO版)")

if "DEEPSEEK_API_KEY" in st.secrets:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    st.error("❌ 未读取到 API Key，请检查 Settings -> Secrets")
    st.stop()

if "matched_products" not in st.session_state: st.session_state.matched_products = []
if "step" not in st.session_state: st.session_state.step = 1
if "selected_keys" not in st.session_state: st.session_state.selected_keys = [] 
if "output_mode" not in st.session_state: st.session_state.output_mode = "card"
if "selected_template" not in st.session_state: st.session_state.selected_template = ""
if "selected_badge_id" not in st.session_state: st.session_state.selected_badge_id = None
if "generated_cards_list" not in st.session_state: st.session_state.generated_cards_list = []

dummy_image = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22400%22%20viewBox%3D%220%200%20400%20400%22%3E%3Crect%20width%3D%22400%22%20height%3D%22400%22%20fill%3D%22%23F3F4F6%22%2F%3E%3Ctext%20x%3D%2250%25%22%20y%3D%2250%25%22%20dominant-baseline%3D%22middle%22%20text-anchor%3D%22middle%22%20font-family%3D%22sans-serif%22%20font-size%3D%2224%22%20fill%3D%22%239CA3AF%22%3E%E5%95%86%E5%93%81%E5%9B%BE%E7%89%87%E9%A2%84%E8%A7%88%3C%2Ftext%3E%3C%2Fsvg%3E"

# ================= 多语言大促/节日标签库 (3大主题 × 5款素材 × 10国语言) =================

def detect_lang_from_url(url_str):
    """根据商品链接自动识别目标站点语言代码"""
    u = str(url_str).lower()
    lang_map = [
        (['callie.de', 'de.callie'], 'DE'),
        (['fr.callie', 'callie.fr'], 'FR'),
        (['callie.es', 'es.callie'], 'ES'),
        (['it.callie', 'callie.it'], 'IT'),
        (['nl.callie', 'callie.nl'], 'NL'),
        (['callie.se', 'se.callie'], 'SE'),
        (['no.callie', 'callie.no'], 'NO'),
        (['callie.fi', 'fi.callie'], 'FI'),
        (['pl.callie', 'callie.pl'], 'PL'),
    ]
    for patterns, lang in lang_map:
        if any(p in u for p in patterns):
            return lang
    return 'EN'

BADGE_TRANSLATIONS = {
    # --- Black Friday (5 款文案) ---
    "bf_1": {
        "DE": "BLACK FRIDAY", "FR": "BLACK FRIDAY", "ES": "BLACK FRIDAY", "IT": "BLACK FRIDAY",
        "NL": "BLACK FRIDAY", "SE": "BLACK FRIDAY", "NO": "BLACK FRIDAY", "FI": "BLACK FRIDAY",
        "PL": "BLACK FRIDAY", "EN": "BLACK FRIDAY"
    },
    "bf_2": {
        "DE": "BLACK FRIDAY DEAL", "FR": "OFFRE BLACK FRIDAY", "ES": "OFERTA BLACK FRIDAY", "IT": "OFFERTA BLACK FRIDAY",
        "NL": "BLACK FRIDAY DEAL", "SE": "BLACK FRIDAY-KLIPP", "NO": "BLACK FRIDAY-KUPP", "FI": "BLACK FRIDAY -ETU",
        "PL": "OKAZJA BLACK FRIDAY", "EN": "BLACK FRIDAY DEAL"
    },
    "bf_3": {
        "DE": "⚡ BLACK FRIDAY ANGEBOT ⚡", "FR": "⚡ SPÉCIAL BLACK FRIDAY ⚡", "ES": "⚡ ESPECIAL BLACK FRIDAY ⚡", "IT": "⚡ SPECIALE BLACK FRIDAY ⚡",
        "NL": "⚡ BLACK FRIDAY ACTIE ⚡", "SE": "⚡ BLACK FRIDAY-ERBJUDANDE ⚡", "NO": "⚡ BLACK FRIDAY-TILBUD ⚡", "FI": "⚡ BLACK FRIDAY -TARJOUS ⚡",
        "PL": "⚡ OFERTA BLACK FRIDAY ⚡", "EN": "⚡ BLACK FRIDAY SPECIAL ⚡"
    },
    "bf_4": {
        "DE": "BLACK FRIDAY SALE", "FR": "PROMO BLACK FRIDAY", "ES": "REBAJAS BLACK FRIDAY", "IT": "SALDI BLACK FRIDAY",
        "NL": "BLACK FRIDAY SALE", "SE": "BLACK FRIDAY REA", "NO": "BLACK FRIDAY SALG", "FI": "BLACK FRIDAY ALE",
        "PL": "WYPRZEDAŻ BLACK FRIDAY", "EN": "BLACK FRIDAY SALE"
    },
    "bf_5": {
        "DE": "BLACK FRIDAY TIPP", "FR": "SÉLECTION BLACK FRIDAY", "ES": "TOP BLACK FRIDAY", "IT": "SCELTA BLACK FRIDAY",
        "NL": "BLACK FRIDAY TIP", "SE": "BLACK FRIDAY-VAL", "NO": "BLACK FRIDAY-VALG", "FI": "BLACK FRIDAY -VALINTA",
        "PL": "HIT BLACK FRIDAY", "EN": "BLACK FRIDAY PICK"
    },
    # --- Cyber Monday (5 款文案) ---
    "cm_1": {
        "DE": "CYBER MONDAY", "FR": "CYBER MONDAY", "ES": "CYBER MONDAY", "IT": "CYBER MONDAY",
        "NL": "CYBER MONDAY", "SE": "CYBER MONDAY", "NO": "CYBER MONDAY", "FI": "CYBER MONDAY",
        "PL": "CYBER MONDAY", "EN": "CYBER MONDAY"
    },
    "cm_2": {
        "DE": "CYBER MONDAY DEAL", "FR": "OFFRE CYBER MONDAY", "ES": "OFERTA CYBER MONDAY", "IT": "OFFERTA CYBER MONDAY",
        "NL": "CYBER MONDAY DEAL", "SE": "CYBER MONDAY-KLIPP", "NO": "CYBER MONDAY-KUPP", "FI": "CYBER MONDAY -ETU",
        "PL": "OKAZJA CYBER MONDAY", "EN": "CYBER MONDAY DEAL"
    },
    "cm_3": {
        "DE": "⚡ CYBER MONDAY ANGEBOT ⚡", "FR": "⚡ EXCLUSIVITÉ CYBER MONDAY ⚡", "ES": "⚡ ESPECIAL CYBER MONDAY ⚡", "IT": "⚡ SPECIALE CYBER MONDAY ⚡",
        "NL": "⚡ CYBER MONDAY ACTIE ⚡", "SE": "⚡ CYBER MONDAY-ERBJUDANDE ⚡", "NO": "⚡ CYBER MONDAY-TILBUD ⚡", "FI": "⚡ CYBER MONDAY -TARJOUS ⚡",
        "PL": "⚡ OFERTA CYBER MONDAY ⚡", "EN": "⚡ CYBER MONDAY EXCLUSIVE ⚡"
    },
    "cm_4": {
        "DE": "CYBER SALE", "FR": "PROMO CYBER", "ES": "CYBER OFERTA", "IT": "SALDI CYBER",
        "NL": "CYBER SALE", "SE": "CYBER REA", "NO": "CYBER SALG", "FI": "CYBER ALE",
        "PL": "CYBER WYPRZEDAŻ", "EN": "CYBER SALE"
    },
    "cm_5": {
        "DE": "CYBER MONDAY TIPP", "FR": "SÉLECTION CYBER", "ES": "TOP CYBER MONDAY", "IT": "SCELTA CYBER",
        "NL": "CYBER MONDAY TIP", "SE": "CYBER MONDAY-VAL", "NO": "CYBER MONDAY-VALG", "FI": "CYBER MONDAY -VALINTA",
        "PL": "HIT CYBER MONDAY", "EN": "CYBER MONDAY PICK"
    },
    # --- Christmas (5 款文案) ---
    "xm_1": {
        "DE": "WEIHNACHTSGESCHENK", "FR": "CADEAU DE NOËL", "ES": "REGALO DE NAVIDAD", "IT": "REGALO DI NATALE",
        "NL": "KERSTCADEAU", "SE": "JULKLAPPSTIPS", "NO": "JULEGAVETIPS", "FI": "JOULULAHJAIDEA",
        "PL": "PREZENT ŚWIĄTECZNY", "EN": "CHRISTMAS GIFT"
    },
    "xm_2": {
        "DE": "WEIHNACHTS-SPECIAL", "FR": "SPÉCIAL NOËL", "ES": "ESPECIAL NAVIDAD", "IT": "SPECIALE NATALE",
        "NL": "KERST SPECIAL", "SE": "JULSPECIAL", "NO": "JULESPESIAL", "FI": "JOULUN ERIKOISETU",
        "PL": "OFERTA ŚWIĄTECZNA", "EN": "XMAS SPECIAL"
    },
    "xm_3": {
        "DE": "❄️ TOP WEIHNACHTSGESCHENK ❄️", "FR": "❄️ IDÉE CADEAU DE NOËL ❄️", "ES": "❄️ IDEA DE REGALO NAVIDEÑO ❄️", "IT": "❄️ IDEA REGALO DI NATALE ❄️",
        "NL": "❄️ PERFECT KERSTCADEAU ❄️", "SE": "❄️ PERFEKT JULKLAPP ❄️", "NO": "❄️ PERFEKT JULEGAVE ❄️", "FI": "❄️ TÄYDELLINEN JOULULAHJA ❄️",
        "PL": "❄️ IDEALNY PREZENT NA ŚWIĘTA ❄️", "EN": "❄️ CHRISTMAS GIFT IDEA ❄️"
    },
    "xm_4": {
        "DE": "WEIHNACHTS-SALE", "FR": "PROMO DE NOËL", "ES": "OFERTA NAVIDEÑA", "IT": "OFFERTA DI NATALE",
        "NL": "KERSTUITVERKOOP", "SE": "JULREA", "NO": "JULESALG", "FI": "JOULUALE",
        "PL": "ŚWIĄTECZNA OKAZJA", "EN": "HOLIDAY SALE"
    },
    "xm_5": {
        "DE": "FESTTAGS-FAVORIT", "FR": "COUP DE CŒUR NOËL", "ES": "FAVORITO DE NAVIDAD", "IT": "PREFERITO DI NATALE",
        "NL": "KERST FAVORIET", "SE": "JULFAVORIT", "NO": "JULEFAVORITT", "FI": "JOULUN SUOSIKKI",
        "PL": "ŚWIĄTECZNY HIT", "EN": "TOP XMAS PICK"
    }
}

BADGE_CATALOG = {
    "🖤 Black Friday (黑五狂欢)": {
        "bf_1": {
            "name": "素材 1：黑金经典胶囊标 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; background:linear-gradient(135deg,#111111,#2B2B2B); color:#F5D061; padding:4px 10px; border-radius:999px; font-size:10px; font-weight:800; letter-spacing:0.5px; box-shadow:0 2px 6px rgba(0,0,0,0.3); border:1px solid #F5D061; line-height:1.2; white-space:nowrap;">🖤 {text}</div>'
        },
        "bf_2": {
            "name": "素材 2：红黑热销爆款标 (右上)",
            "tpl": '<div style="position:absolute; top:8px; right:8px; z-index:5; pointer-events:none; background:linear-gradient(135deg,#FF2A2A,#B80000); color:#FFFFFF; padding:4px 9px; border-radius:8px 2px 8px 8px; font-size:10px; font-weight:800; letter-spacing:0.4px; box-shadow:0 2px 8px rgba(255,42,42,0.4); line-height:1.2; white-space:nowrap;">🔥 {text}</div>'
        },
        "bf_3": {
            "name": "素材 3：黑金限时特惠底栏 (底部)",
            "tpl": '<div style="position:absolute; bottom:0; left:0; right:0; z-index:5; pointer-events:none; background:linear-gradient(90deg,rgba(15,15,15,0.92),rgba(40,40,40,0.92)); color:#FFD700; padding:5px 6px; text-align:center; font-size:10px; font-weight:800; letter-spacing:0.6px; border-top:1px solid rgba(255,215,0,0.5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{text}</div>'
        },
        "bf_4": {
            "name": "素材 4：黑五双色拼接贴纸 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; display:inline-flex; align-items:center; border-radius:6px; overflow:hidden; box-shadow:0 2px 6px rgba(0,0,0,0.28); line-height:1.1;"><span style="background:#FF3B30; color:#FFFFFF; padding:4px 6px; font-size:10px; font-weight:900;">BF</span><span style="background:#111111; color:#FFFFFF; padding:4px 8px; font-size:10px; font-weight:700; white-space:nowrap;">{text}</span></div>'
        },
        "bf_5": {
            "name": "素材 5：黑曜石鎏金框徽章 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; background:rgba(17,17,17,0.88); color:#FFE082; padding:4px 9px; border-radius:4px; font-size:10px; font-weight:800; border:1.5px solid #D4AF37; box-shadow:0 2px 8px rgba(0,0,0,0.35); letter-spacing:0.5px; line-height:1.2; white-space:nowrap;">✨ {text}</div>'
        }
    },
    "💻 Cyber Monday (网购星期一)": {
        "cm_1": {
            "name": "素材 1：赛博霓虹紫蓝胶囊 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; background:linear-gradient(135deg,#6366F1,#A855F7); color:#FFFFFF; padding:4px 10px; border-radius:999px; font-size:10px; font-weight:800; letter-spacing:0.5px; box-shadow:0 2px 8px rgba(99,102,241,0.45); border:1px solid rgba(255,255,255,0.4); line-height:1.2; white-space:nowrap;">💻 {text}</div>'
        },
        "cm_2": {
            "name": "素材 2：极光青蓝闪购角标 (右上)",
            "tpl": '<div style="position:absolute; top:8px; right:8px; z-index:5; pointer-events:none; background:linear-gradient(135deg,#00F2FE,#4FACFE); color:#0B132B; padding:4px 9px; border-radius:8px 2px 8px 8px; font-size:10px; font-weight:900; letter-spacing:0.4px; box-shadow:0 2px 8px rgba(0,242,254,0.45); line-height:1.2; white-space:nowrap;">🚀 {text}</div>'
        },
        "cm_3": {
            "name": "素材 3：网一数字狂欢底栏 (底部)",
            "tpl": '<div style="position:absolute; bottom:0; left:0; right:0; z-index:5; pointer-events:none; background:linear-gradient(90deg,rgba(15,23,42,0.92),rgba(59,7,100,0.92)); color:#38BDF8; padding:5px 6px; text-align:center; font-size:10px; font-weight:800; letter-spacing:0.6px; border-top:1px solid rgba(56,189,248,0.5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{text}</div>'
        },
        "cm_4": {
            "name": "素材 4：赛博双拼科技贴纸 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; display:inline-flex; align-items:center; border-radius:6px; overflow:hidden; box-shadow:0 2px 6px rgba(0,0,0,0.3); line-height:1.1;"><span style="background:#00F5D4; color:#0F172A; padding:4px 6px; font-size:10px; font-weight:900;">CM</span><span style="background:#1E1B4B; color:#FFFFFF; padding:4px 8px; font-size:10px; font-weight:700; white-space:nowrap;">{text}</span></div>'
        },
        "cm_5": {
            "name": "素材 5：未来感流光框徽章 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; background:rgba(15,23,42,0.9); color:#22D3EE; padding:4px 9px; border-radius:4px; font-size:10px; font-weight:800; border:1.5px solid #22D3EE; box-shadow:0 0 8px rgba(34,211,238,0.4); letter-spacing:0.5px; line-height:1.2; white-space:nowrap;">🌐 {text}</div>'
        }
    },
    "🎄 Christmas (圣诞礼遇季)": {
        "xm_1": {
            "name": "素材 1：圣诞红金经典胶囊 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; background:linear-gradient(135deg,#C1121F,#800016); color:#FFF8D6; padding:4px 10px; border-radius:999px; font-size:10px; font-weight:800; letter-spacing:0.4px; box-shadow:0 2px 6px rgba(193,18,31,0.35); border:1px solid #F4D35E; line-height:1.2; white-space:nowrap;">🎄 {text}</div>'
        },
        "xm_2": {
            "name": "素材 2：松石绿节日礼盒标 (右上)",
            "tpl": '<div style="position:absolute; top:8px; right:8px; z-index:5; pointer-events:none; background:linear-gradient(135deg,#1B4332,#2D6A4F); color:#FFE5EC; padding:4px 9px; border-radius:8px 2px 8px 8px; font-size:10px; font-weight:800; letter-spacing:0.4px; box-shadow:0 2px 6px rgba(27,67,50,0.35); border:1px solid #D8F3DC; line-height:1.2; white-space:nowrap;">🎅 {text}</div>'
        },
        "xm_3": {
            "name": "素材 3：冬日雪花温馨底栏 (底部)",
            "tpl": '<div style="position:absolute; bottom:0; left:0; right:0; z-index:5; pointer-events:none; background:linear-gradient(90deg,rgba(164,22,26,0.92),rgba(27,67,50,0.92)); color:#FFF3B0; padding:5px 6px; text-align:center; font-size:10px; font-weight:800; letter-spacing:0.5px; border-top:1px solid rgba(255,243,176,0.5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{text}</div>'
        },
        "xm_4": {
            "name": "素材 4：圣诞双色丝带贴纸 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; display:inline-flex; align-items:center; border-radius:6px; overflow:hidden; box-shadow:0 2px 6px rgba(0,0,0,0.25); line-height:1.1;"><span style="background:#2D6A4F; color:#FFD166; padding:4px 6px; font-size:10px; font-weight:900;">🎁</span><span style="background:#C1121F; color:#FFFFFF; padding:4px 8px; font-size:10px; font-weight:700; white-space:nowrap;">{text}</span></div>'
        },
        "xm_5": {
            "name": "素材 5：璀璨暖金节日徽章 (左上)",
            "tpl": '<div style="position:absolute; top:8px; left:8px; z-index:5; pointer-events:none; background:rgba(128,0,22,0.9); color:#FFE6A7; padding:4px 9px; border-radius:4px; font-size:10px; font-weight:800; border:1.5px solid #FFD166; box-shadow:0 2px 8px rgba(128,0,22,0.35); letter-spacing:0.4px; line-height:1.2; white-space:nowrap;">🔔 {text}</div>'
        }
    }
}

def get_badge_html(badge_id, product_url=""):
    """根据所选标签 ID 与商品链接自动生成对应国家语言的 HTML 标签代码"""
    if not badge_id:
        return ""
    lang = detect_lang_from_url(product_url)
    localized_text = BADGE_TRANSLATIONS.get(badge_id, {}).get(lang) or BADGE_TRANSLATIONS.get(badge_id, {}).get("EN", "SPECIAL OFFER")
    for theme_dict in BADGE_CATALOG.values():
        if badge_id in theme_dict:
            return theme_dict[badge_id]["tpl"].format(text=localized_text)
    return ""

# ================= 价格数值解析与促销 HTML 组装函数 =================
def parse_price_to_float(price_str):
    if not price_str:
        return 0.0
    s = str(price_str).strip()
    s = re.sub(r'[^\d.,]', '', s)
    if not s:
        return 0.0
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

def format_price_like(ref_price_str, target_val):
    ref = str(ref_price_str or "").strip()
    use_comma = ',' in ref or '€' in ref
    formatted_num = f"{target_val:.2f}".replace('.', ',') if use_comma else f"{target_val:.2f}"
    if re.search(r'\d', ref):
        res = re.sub(r'\d+(?:[.,]\d+)?', formatted_num, ref, count=1)
        if res.startswith('€') and not res.startswith('€ '):
            res = '€ ' + res[1:]
        return res
    return f"€ {formatted_num}"

def build_price_display_html(price, original_price="", discount_text="", style_type="left_right"):
    price = str(price or "").strip()
    orig = str(original_price or "").strip()
    disc = str(discount_text or "").strip()

    has_valid_orig = False
    if orig and orig != price:
        p_val = parse_price_to_float(price)
        o_val = parse_price_to_float(orig)
        if o_val > p_val > 0:
            has_valid_orig = True

    if style_type == "left_right":
        html = f'<span style="background-color: #FF6F59; color: #FFFFFF; padding: 3px 8px; border-radius: 20px; font-weight: bold; font-size: 12px; display: inline-block; vertical-align: middle;">🏷️ {price}</span>'
        if has_valid_orig:
            html += f'<del style="color: #9CA3AF; font-size: 12px; margin-left: 6px; font-weight: 500; vertical-align: middle;">{orig}</del>'
        if disc:
            html += f'<span style="background-color: #FF8A3D; color: #FFFFFF; padding: 2px 7px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-left: 6px; display: inline-block; vertical-align: middle;">{disc}</span>'
        return html

    elif style_type == "top_bottom":
        orig_html = f'<del style="color: #9CA3AF; font-size: 12px; font-weight: 500; margin-left: 5px;">{orig}</del>' if has_valid_orig else ""
        disc_html = f'<div style="margin-top: 3px;"><span style="background-color: #FF8A3D; color: #FFFFFF; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; display: inline-block;">{disc}</span></div>' if disc else ""
        return f'<div style="display: flex; flex-direction: column; align-items: flex-start; line-height: 1.2;"><div><span style="color: #F59E0B; font-size: 18px; font-weight: 800;">{price}</span>{orig_html}</div>{disc_html}</div>'

    elif style_type == "carousel":
        orig_html = f'<del style="color: #9CA3AF; font-size: 11px; font-weight: normal; margin-left: 3px;">{orig}</del>' if has_valid_orig else ""
        disc_html = f'<div style="margin-top: 2px;"><span style="background-color: #FF8A3D; color: #FFFFFF; padding: 1px 5px; border-radius: 3px; font-size: 9.5px; font-weight: bold; display: inline-block;">{disc}</span></div>' if disc else ""
        return f'<div style="display: flex; flex-direction: column; align-items: flex-start; line-height: 1.15;"><div><span style="color: #111111; font-size: 14px; font-weight: 800;">{price}</span>{orig_html}</div>{disc_html}</div>'

    return price

# ================= HTML 响应式模板库 =================
templates = {
    "模板 1：左右结构 (规格列表版)": {
        "type": "single",
        "price_style": "left_right",
        "html": """
{json_ld}
<div style="display: flex; flex-wrap: nowrap; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; width: 100%; box-sizing: border-box; margin-bottom: 20px; min-height: 180px;">
    <div style="flex: 0 0 45%; max-width: 45%; padding: 0; background-color: #ffffff; position: relative; overflow: hidden; border-radius: 12px 0 0 12px;">
        {badge_html}
        <a href="{buy_link}" target="_blank" style="display: block; width: 100%; height: 100%;">
            <img src="{image_url}" alt="{title}" style="width: 100%; height: 100%; object-fit: cover; border: none; margin: 0; display: block; border-radius: 12px 0 0 12px;">
        </a>
    </div>
    <div style="flex: 1 1 55%; padding: 12px 14px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; overflow: hidden;">
        <div style="overflow: hidden;">
            <h3 style="margin-top: 0; color: #333333; font-size: 13px; margin-bottom: 8px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{title}">{title}</h3>
            <div style="margin-bottom: 8px; line-height: 1.4;">
                {price_html}
            </div>
            <div style="background-color: #FFF5E4; border-radius: 8px; padding: 8px 10px; margin-bottom: 10px; font-size: 11px; color: #555555; line-height: 1.4;">
                {specs}
            </div>
        </div>
        <a href="{buy_link}" target="_blank" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 8px; border-radius: 8px; font-weight: bold; font-size: 12px; margin-top: auto; white-space: nowrap;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 4：左右结构 (纯净无规格)": {
        "type": "single",
        "price_style": "left_right",
        "html": """
{json_ld}
<div style="display: flex; flex-wrap: nowrap; align-items: stretch; border-radius: 12px; overflow: hidden; background-color: #FAFAFA; border: 1px solid #eaeaea; font-family: sans-serif; width: 100%; box-sizing: border-box; margin-bottom: 20px; min-height: 160px;">
    <div style="flex: 0 0 45%; max-width: 45%; padding: 0; background-color: #ffffff; position: relative; overflow: hidden; border-radius: 12px 0 0 12px;">
        {badge_html}
        <a href="{buy_link}" target="_blank" style="display: block; width: 100%; height: 100%;">
            <img src="{image_url}" alt="{title}" style="width: 100%; height: 100%; object-fit: cover; border: none; margin: 0; display: block; border-radius: 12px 0 0 12px;">
        </a>
    </div>
    <div style="flex: 1 1 55%; padding: 12px 14px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; overflow: hidden;">
        <div style="overflow: hidden;">
            <h3 style="margin-top: 0; color: #333333; font-size: 13px; margin-bottom: 8px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{title}">{title}</h3>
            <div style="margin-bottom: 12px; line-height: 1.4;">
                {price_html}
            </div>
        </div>
        <a href="{buy_link}" target="_blank" style="display: block; text-align: center; background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 8px; border-radius: 8px; font-weight: bold; font-size: 12px; margin-top: auto; white-space: nowrap;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 2：上下结构 (圆润多巴胺)": {
        "type": "single",
        "price_style": "top_bottom",
        "html": """
{json_ld}
<div style="background-color: #FFF8EC; border-radius: 24px; padding: 16px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; width: 100%; max-width: 350px; box-sizing: border-box; border: 1px solid #F7E8D5; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto 20px auto;">
    <div style="width: 100%; height: 280px; border-radius: 16px; overflow: hidden; margin-bottom: 16px; background-color: #fff; display: flex; align-items: center; justify-content: center; text-align:center; position: relative;">
        {badge_html}
        <a href="{buy_link}" target="_blank" style="display: block; width: 100%; height: 100%;">
            <img src="{image_url}" alt="{title}" style="width: 100%; height: 100%; object-fit: cover; border: none; outline: none;">
        </a>
    </div>
    <h3 style="margin: 0 0 10px 0; color: #3E2723; font-size: 14px; font-weight: 800; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{title}">{title}</h3>
    <div style="color: #A1887F; font-size: 11px; margin-bottom: 16px; font-weight: 500; line-height: 1.4; height: 46px; overflow: hidden;">{specs}</div>
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
        {price_html}
        <a href="{buy_link}" target="_blank" style="background-color: #F59E0B; color: #ffffff; text-decoration: none; padding: 8px 18px; border-radius: 24px; font-weight: bold; font-size: 13px; box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3); display: inline-block; white-space: nowrap;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 6：上下结构 (纯净无规格)": {
        "type": "single",
        "price_style": "top_bottom",
        "html": """
{json_ld}
<div style="background-color: #FFF8EC; border-radius: 24px; padding: 16px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; width: 100%; max-width: 350px; box-sizing: border-box; border: 1px solid #F7E8D5; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto 20px auto;">
    <div style="width: 100%; height: 280px; border-radius: 16px; overflow: hidden; margin-bottom: 14px; background-color: #fff; display: flex; align-items: center; justify-content: center; text-align:center; position: relative;">
        {badge_html}
        <a href="{buy_link}" target="_blank" style="display: block; width: 100%; height: 100%;">
            <img src="{image_url}" alt="{title}" style="width: 100%; height: 100%; object-fit: cover; border: none; outline: none;">
        </a>
    </div>
    <h3 style="margin: 0 0 14px 0; color: #3E2723; font-size: 14px; font-weight: 800; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{title}">{title}</h3>
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
        {price_html}
        <a href="{buy_link}" target="_blank" style="background-color: #F59E0B; color: #ffffff; text-decoration: none; padding: 8px 18px; border-radius: 24px; font-weight: bold; font-size: 13px; box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3); display: inline-block; white-space: nowrap;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 3：多商品轮播 (标准)": {
        "type": "carousel",
        "price_style": "carousel",
        "html": """
{json_ld}
<div style="background-color: #FDFBF7; padding: 20px 10px; font-family: sans-serif; border-radius: 16px; margin-bottom: 20px; box-sizing: border-box; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch;">
    {carousel_items}
</div>
""",
        "item_html": """
<div style="display: inline-block; vertical-align: top; width: 220px; white-space: normal; background-color: #FFFFFF; border-radius: 16px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-right: 16px; box-sizing: border-box;">
    <div style="width: 100%; height: 180px; border-radius: 12px; overflow: hidden; margin-bottom: 12px; background-color: #f9f9f9; text-align: center; position: relative;">
        {badge_html}
        <a href="{buy_link}" target="_blank"><img src="{image_url}" alt="{title}" style="max-width: 100%; max-height: 180px; object-fit: contain;"></a>
    </div>
    <h3 style="margin: 0 0 10px 0; color: #333333; font-size: 13px; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{title}">{title}</h3>
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px;">
        {price_html}
        <a href="{buy_link}" target="_blank" style="background-color: #D4BBAA; color: #ffffff; text-decoration: none; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: bold; display: inline-block; white-space: nowrap;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 5：可滑动轮播 (带交互指示器)": {
        "type": "carousel",
        "price_style": "carousel",
        "html": """
{json_ld}
<div class="callie-carousel-wrapper" style="position: relative; border-radius: 16px; margin-bottom: 20px; background-color: #FDFBF7; font-family: sans-serif; overflow: hidden;">
    <div class="scroll-left" onclick="var b=this.parentElement.querySelector('.scroll-box'); if(b) b.scrollBy({{left: -240, behavior: 'smooth'}});" style="position: absolute; left: 0; top: 0; bottom: 0; width: 40px; background: linear-gradient(to right, rgba(253,251,247,1) 40%, rgba(253,251,247,0)); z-index: 20; display: flex; align-items: center; justify-content: flex-start; padding-left: 6px; cursor: pointer;">
        <span style="color: #D4BBAA; font-size: 32px; font-weight: bold; pointer-events: none; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);">&#10094;</span>
    </div>
    
    <div class="scroll-right" onclick="var b=this.parentElement.querySelector('.scroll-box'); if(b) b.scrollBy({{left: 240, behavior: 'smooth'}});" style="position: absolute; right: 0; top: 0; bottom: 0; width: 40px; background: linear-gradient(to left, rgba(253,251,247,1) 40%, rgba(253,251,247,0)); z-index: 20; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; cursor: pointer;">
        <span style="color: #D4BBAA; font-size: 32px; font-weight: bold; pointer-events: none; text-shadow: -1px 1px 2px rgba(0,0,0,0.1);">&#10095;</span>
    </div>

    <div class="scroll-box" style="padding: 20px 10px; box-sizing: border-box; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch; scroll-snap-type: x mandatory; scrollbar-width: none;">
        <style>.scroll-box::-webkit-scrollbar {{ display: none; }}</style>
        {carousel_items}
        <div style="display: inline-block; width: 20px;"></div>
    </div>
    
    <script>
        document.querySelectorAll('.callie-carousel-wrapper').forEach(function(wrapper) {{
            if(wrapper.dataset.initialized) return;
            wrapper.dataset.initialized = 'true';
            var leftBtn = wrapper.querySelector('.scroll-left');
            var rightBtn = wrapper.querySelector('.scroll-right');
            var box = wrapper.querySelector('.scroll-box');
            if(leftBtn && box) leftBtn.addEventListener('click', function() {{ box.scrollBy({{left: -240, behavior: 'smooth'}}); }});
            if(rightBtn && box) rightBtn.addEventListener('click', function() {{ box.scrollBy({{left: 240, behavior: 'smooth'}}); }});
        }});
    </script>
</div>
""",
        "item_html": """
<div style="display: inline-block; vertical-align: top; width: 220px; white-space: normal; background-color: #FFFFFF; border-radius: 16px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-left: 10px; margin-right: 6px; box-sizing: border-box; scroll-snap-align: start;">
    <div style="width: 100%; height: 180px; border-radius: 12px; overflow: hidden; margin-bottom: 12px; background-color: #f9f9f9; text-align: center; position: relative;">
        {badge_html}
        <a href="{buy_link}" target="_blank"><img src="{image_url}" alt="{title}" style="max-width: 100%; max-height: 180px; object-fit: contain;"></a>
    </div>
    <h3 style="margin: 0 0 10px 0; color: #333333; font-size: 13px; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{title}">{title}</h3>
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px;">
        {price_html}
        <a href="{buy_link}" target="_blank" style="background-color: #D4BBAA; color: #ffffff; text-decoration: none; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: bold; display: inline-block; white-space: nowrap;">{cta_text}</a>
    </div>
</div>
"""
    },
    "模板 7：双图/多图拼图 (居中按钮)": {
        "type": "collage",
        "price_style": "left_right",
        "html": """
{json_ld}
<div style="background-color: #FDFBF7; border-radius: 20px; padding: 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; width: 100%; max-width: 680px; box-sizing: border-box; border: 1px solid #F3ECE3; box-shadow: 0 8px 24px rgba(0,0,0,0.04); margin: 0 auto 24px auto;">
    <div style="display: flex; flex-wrap: nowrap; gap: 14px; justify-content: center; align-items: stretch; margin-bottom: 18px;">
        {collage_items}
    </div>
    <div style="text-align: center;">
        <a href="{buy_link}" target="_blank" style="background-color: #FF6F59; color: #FFFFFF; text-decoration: none; padding: 11px 36px; border-radius: 999px; font-weight: bold; font-size: 14px; display: inline-block; box-shadow: 0 4px 12px rgba(255, 111, 89, 0.28); transition: opacity 0.2s ease;">{cta_text}</a>
    </div>
</div>
""",
        "item_html": """
<div style="flex: 1 1 0; min-width: 0; border-radius: 14px; overflow: hidden; background-color: #FFFFFF; box-shadow: 0 4px 12px rgba(0,0,0,0.05); aspect-ratio: 1 / 1; position: relative;">
    {badge_html}
    <a href="{buy_link}" target="_blank" style="display: block; width: 100%; height: 100%;">
        <img src="{image_url}" alt="{title}" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;">
    </a>
</div>
"""
    }
}

# ================= 过滤尺寸 (Size) 辅助函数 =================
SIZE_KEYWORDS = [
    'size', 'größe', 'groesse', 'grösse', 'maße', 'masse', 'abmessung', 
    'taille', 'dimension', 'tamaño', 'tamano', 'medida', 'taglia', 'misura', 'dimensioni',
    'maat', 'afmeting', 'storlek', 'mått', 'størrelse', 'mål', 'koko', 'mitat', 
    'rozmiar', 'wymiar', 'length', 'width', 'height', 'diameter', 'panjang', 'gewicht', 'weight',
    'länge', 'laenge', 'breite', 'höhe', 'hoehe', 'kettenlänge', 'longueur', 'largeur', 'hauteur',
    'afmetingen', 'measurements'
]

def is_size_spec_key(key_str):
    k_lower = str(key_str).lower().strip()
    return any(kw in k_lower for kw in SIZE_KEYWORDS)

def is_size_spec_line(line_str):
    l_lower = str(line_str).lower().strip()
    if any(kw in l_lower for kw in SIZE_KEYWORDS):
        return True
    if re.search(r'\b\d+(?:[.,]\d+)?\s*(?:cm|mm|inch|in|zoll)\b', l_lower):
        return True
    return False

# ================= 核心爬虫与 AI 海选函数 (修复版) =================

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except: return None

def fetch_blog_context(blog_url):
    soup = get_soup(blog_url)
    if not soup: return ""
    return soup.get_text(separator='\n', strip=True)[:4000]

def extract_img_url_from_tag(img_tag, base_url):
    """
    智能解析 <img> 标签：
    1. 优先扫描所有属性中真实的高清图片地址（cloudfront / uploads / .jpg / .png / .webp）
    2. 若着陆页使用了纯 svg 懒加载占位图，先返回 dummy_image 而不丢弃该商品，后续并发补全真图
    """
    if not img_tag:
        return None
    # 检查是否是明显的网站 Logo 或小图标
    img_cls = " ".join(img_tag.get('class', [])).lower()
    if 'logo' in img_cls:
        return None

    # 优先检查常见懒加载属性与 src
    priority_attrs = ['data-src', 'data-original', 'data-lazy-src', 'data-lazy', 'data-echo', 'srcset', 'src']
    candidates = []
    for attr in priority_attrs:
        val = img_tag.get(attr)
        if val and isinstance(val, str):
            candidates.append(val.strip().split(' ')[0])

    # 再遍历所有其他自定义属性（如 v-lazy 等）
    for attr, val in img_tag.attrs.items():
        if attr not in priority_attrs and isinstance(val, str) and ('http' in val or '/uploads/' in val):
            candidates.append(val.strip().split(' ')[0])

    for c in candidates:
        c_lower = c.lower()
        if any(bad in c_lower for bad in ['logo', 'icon', 'favicon', 'flag', 'payment']):
            continue
        if not c_lower.startswith('data:image') and any(ext in c_lower for ext in ['.jpg', '.jpeg', '.png', '.webp', '/uploads/']):
            return urljoin(base_url, c).split('?')[0]

    # 如果是懒加载的 data:image/svg+xml 占位符，返回 dummy_image 保留该商品资格
    for c in candidates:
        if c.lower().startswith('data:image'):
            return dummy_image

    return None

def fetch_product_list(category_url):
    """
    修复版海选商品列表抓取：
    1. 移除顶部 header/nav 与底部 footer 导航干扰
    2. 兼容懒加载 svg 占位符，绝不误杀第 2 个及之后的商品
    3. 支持向上查找商品卡片容器内的图片与标题
    """
    soup = get_soup(category_url)
    if not soup: return []

    # 移除页头导航和页脚链接，防止把顶部菜单分类抓进商品池
    for nav_tag in soup.find_all(['header', 'nav', 'footer']):
        nav_tag.decompose()

    seen_urls = set()
    products = []
    non_product_paths = [
        '/blog', '/login', '/register', '/cart', '/checkout', '/about', '/contact',
        '/privacy', '/terms', '/shipping', '/return', '/faq', '/track', '/account',
        '/wishlist', '/search', '/pages/', '/policy', '/help'
    ]

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#') or 'javascript' in href.lower() or href.startswith('mailto:'):
            continue

        full_url = urljoin(category_url, href)
        clean_url = full_url.split('?')[0].rstrip('/')

        # 排除当前分类页自身及非商品功能页
        if clean_url == category_url.split('?')[0].rstrip('/'):
            continue
        if any(np in clean_url.lower() for np in non_product_paths):
            continue

        # 查找关联的 <img>（向上最多查找 3 层单商品卡片容器）
        img = a.find('img')
        curr_p = a.parent
        depth = 0
        while not img and curr_p and depth < 3:
            # 仅在当前父容器包含不超过 4 张图时才视为单商品卡片，防止爬到整个商品网格
            imgs_in_p = curr_p.find_all('img')
            if 1 <= len(imgs_in_p) <= 4:
                img = imgs_in_p[0]
                break
            curr_p = curr_p.parent
            depth += 1

        if not img:
            continue

        img_url = extract_img_url_from_tag(img, category_url)
        if not img_url:
            continue

        # 提取商品标题：优先 a 标签文本 -> a 的 title 属性 -> img 的 alt 属性 -> 同卡片内标题文本
        title = a.get_text(" ", strip=True)
        if len(title) <= 5:
            title = (a.get('title') or img.get('alt') or '').strip()
        if len(title) <= 5 and a.parent:
            card_box = a.parent.parent if a.parent.parent else a.parent
            if len(card_box.find_all('a')) <= 4:
                t_cand = card_box.get_text(" ", strip=True)
                if 5 < len(t_cand) <= 180:
                    title = t_cand

        if len(title) > 5:
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                products.append({
                    "title": title[:120],
                    "url": clean_url,
                    "thumbnail": img_url,
                    "candidate_key": f"{clean_url}###0"
                })
            elif img_url != dummy_image:
                # 若同一商品第 1 个 <a> 只有占位图，第 2 个 <a> 拿到了真图，则更新真图
                for existing_p in products:
                    if existing_p["url"] == clean_url and existing_p["thumbnail"] == dummy_image:
                        existing_p["thumbnail"] = img_url
                        break

        if len(products) >= 60:
            break

    return products

def resolve_missing_thumbnails(product_list):
    """
    针对着陆页使用纯 JS 懒加载（静态 HTML 中只有 svg 占位图）的商品，
    并发请求详情页提取 og:image，确保步骤 2 所有海选商品都显示真实高清缩略图
    """
    def _fetch_og(item):
        if item.get("thumbnail") and item["thumbnail"] != dummy_image and not str(item["thumbnail"]).startswith("data:image"):
            return item
        s = get_soup(item["url"])
        if s:
            og = s.find('meta', property='og:image')
            if og and og.get('content'):
                item["thumbnail"] = urljoin(item["url"], og['content']).split('?')[0]
            if not item.get("title") or len(item["title"]) < 6:
                if s.title and s.title.string:
                    item["title"] = s.title.string.strip()
        return item

    needs_resolve = [p for p in product_list if not p.get("thumbnail") or p["thumbnail"] == dummy_image or str(p["thumbnail"]).startswith("data:image")]
    if not needs_resolve:
        return product_list

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(_fetch_og, needs_resolve))
    return product_list

def fetch_direct_urls(url_list_text):
    urls = [u.strip() for u in url_list_text.split('\n') if u.strip().startswith('http')]
    candidates = []
    
    for url in urls:
        clean_url = url.split('?')[0]
        soup = get_soup(clean_url)
        if soup:
            title = soup.title.string if soup.title else ""
            title = title.replace('\n', ' ').strip()
            
            valid_imgs = []
            
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                valid_imgs.append(urljoin(clean_url, og_img['content']).split('?')[0])
            
            bad_keywords = ['logo', 'icon', 'svg', 'gif', 'badge', 'avatar', 'footer', 'header', 'menu', 
                            'video', 'play', 'mp4', 'youtube', 'vimeo', 'trust', 'payment', 
                            'related', 'recommend', 'upsell', 'cross', 'recent', 'history', 
                            'review', 'testimonial', 'popup', 'modal', 'cart', 'bottom', 'sidebar', 'nav']
                            
            for img in soup.find_all('img'):
                src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                if not src: continue
                
                parent = img.parent
                is_bad = False
                depth = 0
                while parent and depth < 5:
                    p_class = " ".join(parent.get('class', [])).lower()
                    p_id = (parent.get('id') or '').lower()
                    if any(x in p_class or x in p_id for x in bad_keywords):
                        is_bad = True
                        break
                    parent = parent.parent
                    depth += 1
                    
                if is_bad: continue
                
                src_lower = str(src).lower()
                img_class = " ".join(img.get('class', [])).lower()
                img_alt = (img.get('alt') or '').lower()
                
                if any(x in src_lower or x in img_class or x in img_alt for x in bad_keywords):
                    continue
                    
                if not any(ext in src_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    continue
                    
                full_url = urljoin(clean_url, src).split('?')[0]
                
                if 'uploads' in full_url.lower() or 'product' in full_url.lower():
                    if full_url not in valid_imgs:
                        valid_imgs.append(full_url)
            
            if not valid_imgs:
                valid_imgs.append(dummy_image)
                
            for idx, img_url in enumerate(valid_imgs[:4]):
                candidates.append({
                    "title": title,
                    "url": clean_url,
                    "thumbnail": img_url,
                    "candidate_key": f"{clean_url}###{idx}" 
                })
    return candidates

def clean_json_response(content):
    content = content.strip()
    if content.startswith("```"):
        start_idx = content.find('\n') + 1
        end_idx = content.rfind('```')
        if start_idx > 0 and end_idx > start_idx:
            content = content[start_idx:end_idx].strip()
    return content

def ai_match_top_30(blog_text, product_list):
    """
    修复版 AI 智能海选：
    明确要求返回 {"products": [...]} JSON 对象，完美匹配 response_format={"type": "json_object"}，
    并兼容字典与列表解包；若 AI 返回数量不足，自动从候选池补齐。
    """
    if len(product_list) <= 15:
        return product_list

    # 仅向 AI 传递精简字段，加快响应并避免 Token 超限
    slim_candidates = [{"title": p.get("title", ""), "url": p.get("url", ""), "thumbnail": p.get("thumbnail", "")} for p in product_list]
    prompt = f"""You are an expert e-commerce recommender. Select AS MANY relevant products as possible from the candidates (aim for 20 to 30 products) that fit the blog post topic.
Blog Post: {blog_text[:2500]}
Product Candidates: {json.dumps(slim_candidates, ensure_ascii=False)}
Output ONLY a valid JSON object with the key "products" containing the array of selected product objects:
{{"products": [{{"title": "...", "url": "...", "thumbnail": "..."}}]}}"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        parsed = json.loads(clean_json_response(response.choices[0].message.content))
        selected = []
        if isinstance(parsed, list):
            selected = [x for x in parsed if isinstance(x, dict) and "url" in x]
        elif isinstance(parsed, dict):
            if "products" in parsed and isinstance(parsed["products"], list):
                selected = [x for x in parsed["products"] if isinstance(x, dict) and "url" in x]
            else:
                for v in parsed.values():
                    if isinstance(v, list):
                        selected = [x for x in v if isinstance(x, dict) and "url" in x]
                        if selected:
                            break
                if not selected and "url" in parsed:
                    selected = [parsed]

        # 如果 AI 过于严苛只选了不到 6 个商品，自动从原候选池按顺序补齐至最多 30 个
        if len(selected) < min(6, len(product_list)):
            seen_u = {x["url"] for x in selected}
            for item in product_list:
                if item["url"] not in seen_u:
                    selected.append(item)
                    seen_u.add(item["url"])
                if len(selected) >= 30:
                    break
        return selected[:30]
    except:
        return product_list[:30]

# ================= 精准 DOM 节点价格提取函数 (零推测保底版) =================
def join_value_and_symbol(price_div):
    if not price_div:
        return ""
    spans = price_div.find_all('span', recursive=False)
    if not spans:
        spans = price_div.find_all('span')
    if spans:
        text = "".join(sp.get_text() for sp in spans)
    else:
        text = price_div.get_text(separator=" ", strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    if text.startswith('€') and not text.startswith('€ '):
        text = '€ ' + text[1:]
    return text

def extract_exact_dom_pricing(soup):
    """直接提取页面第 1 组主商品的 div.now-price, div.old, span.discount-text"""
    dom_sale_price = ""
    dom_old_price = ""
    dom_discount_text = ""

    now_node = soup.select_one('div.now.now-price, div.now-price')
    if now_node:
        candidate_sale = join_value_and_symbol(now_node)
        if parse_price_to_float(candidate_sale) > 0:
            dom_sale_price = candidate_sale
            if now_node.parent:
                sibling_old = now_node.parent.select_one('div.old')
                if sibling_old:
                    dom_old_price = join_value_and_symbol(sibling_old)

    if not dom_old_price:
        old_node = soup.select_one('div.old')
        if old_node:
            dom_old_price = join_value_and_symbol(old_node)

    disc_node = soup.select_one('span.discount-text, .product-detail-trace-15, div.sale-item__price span')
    if disc_node:
        d_txt = re.sub(r'\s+', ' ', disc_node.get_text(strip=True)).strip()
        if d_txt and '%' in d_txt and len(d_txt) <= 35:
            dom_discount_text = d_txt

    return {
        "dom_sale_price": dom_sale_price,
        "dom_old_price": dom_old_price,
        "dom_discount_text": dom_discount_text
    }

def extract_authoritative_anchor_price(soup):
    og_price = soup.find('meta', property='product:price:amount') or soup.find('meta', property='og:price:amount')
    if og_price and og_price.get('content'):
        v = parse_price_to_float(og_price.get('content'))
        if v > 0:
            return v
    return 0.0

def extract_product_details(product_url, preselected_image=None):
    soup = get_soup(product_url)
    if not soup: return None
    
    main_image = preselected_image if preselected_image and preselected_image != dummy_image else ""
    
    if not main_image:
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'): main_image = og_img['content']
        else:
            img_tag = soup.find('img')
            if img_tag: main_image = img_tag.get('data-src') or img_tag.get('src', '')
        main_image = urljoin(product_url, main_image).split('?')[0] if main_image else dummy_image
    
    og_currency_tag = soup.find('meta', property='product:price:currency') or soup.find('meta', property='og:price:currency')
    page_currency = og_currency_tag.get('content', '').strip().upper() if og_currency_tag and og_currency_tag.get('content') else ""
    
    og_desc_tag = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
    page_desc = og_desc_tag.get('content', '').strip() if og_desc_tag and og_desc_tag.get('content') else ""

    dom_pricing = extract_exact_dom_pricing(soup)
    anchor_val = extract_authoritative_anchor_price(soup)

    for tag in soup.find_all(['script', 'style', 'svg', 'noscript', 'head', 'header', 'nav', 'footer']):
        tag.decompose()
    h1_tag = soup.find('h1')
    if h1_tag:
        after_h1_nodes = [h1_tag.get_text(" ", strip=True)]
        for s in h1_tag.find_all_next(string=True):
            t = s.strip()
            if t: after_h1_nodes.append(t)
            if sum(len(x) for x in after_h1_nodes) > 5000: break
        focused_text = "\n".join(after_h1_nodes)
    else:
        focused_text = soup.get_text(separator='\n', strip=True)[:5000]

    hints = []
    if dom_pricing["dom_sale_price"]:
        hints.append(f"[DOM EXACT CURRENT PRICE]: {dom_pricing['dom_sale_price']}")
    elif anchor_val > 0:
        hints.append(f"[META SELLING PRICE]: {anchor_val:.2f}")
    if dom_pricing["dom_old_price"]:
        hints.append(f"[DOM EXACT ORIGINAL PRICE (div.old)]: {dom_pricing['dom_old_price']}")
    if dom_pricing["dom_discount_text"]:
        hints.append(f"[DOM EXACT DISCOUNT TEXT (span.discount-text)]: {dom_pricing['dom_discount_text']}")
    hint_block = "\n".join(hints)
    
    prompt = f"""Analyze the following product page text. DO NOT TRANSLATE. Extract into JSON: 
    1. "title": Summarize the product name into a concise title. Keep it VERY SHORT (Max 35-40 chars). CRITICAL RULE: MUST be in the EXACT SAME LANGUAGE as the source text. DO NOT translate to English.
    2. "price": The current selling product price with currency symbol.
    3. "original_price": The crossed-out original price if present, otherwise "".
    4. "discount_text": The discount badge text if present, otherwise "".
    5. "return_days"
    6. "specs": Extract 2-3 key specifications (e.g., Material, Craftsmanship, Customization) as a JSON Key-Value object. CRITICAL RULE: DO NOT include any size, dimensions, length, width, height, or weight information! Keep keys and values in the ORIGINAL LANGUAGE.
    7. "cta_text": Short action-oriented CTA button text in the ORIGINAL LANGUAGE.
    RULES: NEVER extract shipping fees or option add-on prices.
    {hint_block}
    Page Text:
    {focused_text}"""
    
    try:
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, max_tokens=1500)
        result = json.loads(clean_json_response(response.choices[0].message.content))

        # 零推测原则：优先采用 DOM 真实提取值，绝不通过算术反推编造价格
        final_price = dom_pricing["dom_sale_price"] or str(result.get("price") or "").strip()
        final_orig = dom_pricing["dom_old_price"]
        final_disc = dom_pricing["dom_discount_text"]

        p_float = parse_price_to_float(final_price)
        if not dom_pricing["dom_sale_price"] and anchor_val > 0 and abs(p_float - anchor_val) > 0.1:
            final_price = format_price_like(final_price or "€ 0,00", anchor_val)
            p_float = anchor_val

        o_float = parse_price_to_float(final_orig)
        if o_float <= p_float:
            final_orig = ""

        result["price"] = final_price
        result["original_price"] = final_orig
        result["discount_text"] = final_disc
        result["image_url"] = main_image
        result["buy_link"] = product_url
        result["page_currency"] = page_currency
        result["page_description"] = page_desc
        return result
    except: return None

# ================= 结构化数据 (全字段合规升级版) =================
def format_price_for_schema(price_str):
    val = parse_price_to_float(price_str)
    return f"{val:.2f}" if val > 0 else "0.00"

def detect_currency_and_country(buy_link, price_str="", page_currency=""):
    url_lower = str(buy_link).lower()
    p_str = str(price_str).lower()
    
    domain_map = [
        (['callie.de', 'de.callie'], 'EUR', 'DE'),
        (['fr.callie', 'callie.fr'], 'EUR', 'FR'),
        (['callie.es', 'es.callie'], 'EUR', 'ES'),
        (['it.callie', 'callie.it'], 'EUR', 'IT'),
        (['nl.callie', 'callie.nl'], 'EUR', 'NL'),
        (['callie.fi', 'fi.callie'], 'EUR', 'FI'),
        (['callie.se', 'se.callie'], 'SEK', 'SE'),
        (['no.callie', 'callie.no'], 'NOK', 'NO'),
        (['pl.callie', 'callie.pl'], 'PLN', 'PL'),
        (['uk.callie', 'callie.co.uk'], 'GBP', 'GB'),
    ]
    
    detected_curr, detected_country = 'USD', 'US'
    for patterns, curr, country in domain_map:
        if any(pat in url_lower for pat in patterns):
            detected_curr, detected_country = curr, country
            break
    else:
        if '€' in p_str or 'eur' in p_str:
            detected_curr, detected_country = 'EUR', 'FR'
        elif 'zł' in p_str or 'pln' in p_str:
            detected_curr, detected_country = 'PLN', 'PL'
        elif '£' in p_str or 'gbp' in p_str:
            detected_curr, detected_country = 'GBP', 'GB'
        elif 'kr' in p_str:
            detected_curr, detected_country = 'SEK', 'SE'

    if page_currency and len(page_currency) == 3:
        detected_curr = page_currency

    return detected_curr, detected_country

def build_product_schema_dict(title, image_url, price, buy_link, return_days=30, description="", page_currency="", include_context=True):
    price_num = format_price_for_schema(price)
    currency, country_code = detect_currency_and_country(buy_link, price, page_currency)
    
    try:
        ret_days = int(re.sub(r'[^\d]', '', str(return_days))) if return_days else 30
        if ret_days <= 0 or ret_days > 365: ret_days = 30
    except:
        ret_days = 30

    clean_desc = re.sub(r'<[^>]+>', ' ', str(description or '')).strip()
    if not clean_desc:
        clean_desc = str(title)[:140]

    schema = {}
    if include_context:
        schema["@context"] = "https://schema.org/"
        
    schema.update({
        "@type": "Product",
        "name": str(title)[:140],
        "image": image_url,
        "description": clean_desc[:300],
        "brand": {
            "@type": "Brand",
            "name": "Callie"
        },
        "offers": {
            "@type": "Offer",
            "price": price_num,
            "priceCurrency": currency,
            "url": buy_link,
            "availability": "https://schema.org/InStock",
            "hasMerchantReturnPolicy": {
                "@type": "MerchantReturnPolicy",
                "applicableCountry": country_code,
                "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                "merchantReturnDays": ret_days,
                "returnMethod": "https://schema.org/ReturnByMail",
                "returnFees": "https://schema.org/FreeReturn"
            },
            "shippingDetails": {
                "@type": "OfferShippingDetails",
                "shippingRate": {
                    "@type": "MonetaryAmount",
                    "value": "0.00",
                    "currency": currency
                },
                "shippingDestination": {
                    "@type": "DefinedRegion",
                    "addressCountry": country_code
                },
                "deliveryTime": {
                    "@type": "ShippingDeliveryTime",
                    "handlingTime": {
                        "@type": "QuantitativeValue",
                        "minValue": 1,
                        "maxValue": 3,
                        "unitCode": "DAY"
                    },
                    "transitTime": {
                        "@type": "QuantitativeValue",
                        "minValue": 3,
                        "maxValue": 7,
                        "unitCode": "DAY"
                    }
                }
            }
        }
    })
    return schema

def generate_single_json_ld(title, image_url, price, buy_link, return_days=30, description="", page_currency=""):
    ld = build_product_schema_dict(
        title=title,
        image_url=image_url,
        price=price,
        buy_link=buy_link,
        return_days=return_days,
        description=description,
        page_currency=page_currency,
        include_context=True
    )
    return f'\n<div style="display: none; visibility: hidden; height: 0; width: 0; overflow: hidden;">\n<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False)}\n</script>\n</div>\n'

def generate_carousel_json_ld(products_data):
    unique_by_url = {}
    for data in products_data:
        u = data.get("buy_link", "")
        if u not in unique_by_url:
            unique_by_url[u] = {**data, "all_images": [data.get("image_url", "")]}
        else:
            img_u = data.get("image_url", "")
            if img_u and img_u not in unique_by_url[u]["all_images"]:
                unique_by_url[u]["all_images"].append(img_u)

    unique_list = list(unique_by_url.values())
    if len(unique_list) == 1:
        d = unique_list[0]
        img_field = d["all_images"] if len(d["all_images"]) > 1 else d.get("image_url", "")
        ld = build_product_schema_dict(
            title=d.get("title", ""),
            image_url=img_field,
            price=d.get("price", ""),
            buy_link=d.get("buy_link", ""),
            return_days=d.get("return_days", 30),
            description=d.get("schema_description", ""),
            page_currency=d.get("page_currency", ""),
            include_context=True
        )
    else:
        items = []
        for i, data in enumerate(unique_list):
            img_field = data["all_images"] if len(data["all_images"]) > 1 else data.get("image_url", "")
            product_item = build_product_schema_dict(
                title=data.get("title", ""),
                image_url=img_field,
                price=data.get("price", ""),
                buy_link=data.get("buy_link", ""),
                return_days=data.get("return_days", 30),
                description=data.get("schema_description", ""),
                page_currency=data.get("page_currency", ""),
                include_context=False
            )
            items.append({
                "@type": "ListItem",
                "position": i + 1,
                "item": product_item
            })
        ld = {
            "@context": "https://schema.org/",
            "@type": "ItemList",
            "itemListElement": items
        }
    return f'\n<div style="display: none; visibility: hidden; height: 0; width: 0; overflow: hidden;">\n<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False)}\n</script>\n</div>\n'

# ================= WordPress 智能无损注入函数 =================
def push_cards_to_wp_h2(wp_url, username, password, post_id, cards_html_list):
    base_api = wp_url.rstrip('/') + '/wp-json/wp/v2'
    auth = (username, password)
    
    post_endpoint = f"{base_api}/posts/{post_id}"
    try:
        res_get = requests.get(f"{post_endpoint}?context=edit", auth=auth, timeout=15, allow_redirects=True)
        if res_get.status_code == 404:
            post_endpoint = f"{base_api}/pages/{post_id}"
            res_get = requests.get(f"{post_endpoint}?context=edit", auth=auth, timeout=15, allow_redirects=True)
            
        if res_get.status_code != 200: 
            return False, f"无法读取原文，权限不足或查无此文: {res_get.text[:100]}"
            
        real_endpoint = res_get.url.split('?')[0] 
        post_data = res_get.json()
        current_content = post_data.get('content', {}).get('raw', '')
    except Exception as e: 
        return False, f"读取异常: {e}"

    formatted_cards = [f'\n<!-- wp:html -->\n{card}\n<!-- /wp:html -->\n' for card in cards_html_list]
    
    pattern = r'((?:<!--\s*wp:heading[\s\S]*?-->\s*)?<h2[^>]*>)'
    parts = re.split(pattern, current_content, flags=re.IGNORECASE)
    
    new_content = ""
    card_idx = 0
    h2_found_count = 0
    
    if len(parts) == 1:
        new_content = current_content + "".join(formatted_cards)
    else:
        for part in parts:
            part_lower = part.strip().lower()
            if part_lower.startswith('<h2') or part_lower.startswith('<!-- wp:heading'):
                h2_found_count += 1
                if card_idx < len(formatted_cards):
                    new_content += formatted_cards[card_idx]
                    card_idx += 1
            new_content += part
        while card_idx < len(formatted_cards):
            new_content += formatted_cards[card_idx]
            card_idx += 1

    update_data = {'content': new_content}
    try:
        res_update = requests.post(real_endpoint, json=update_data, auth=auth, timeout=30, allow_redirects=False)
        if res_update.status_code in [301, 302, 307, 308]:
            real_endpoint = res_update.headers.get('Location')
            res_update = requests.post(real_endpoint, json=update_data, auth=auth, timeout=30, allow_redirects=False)

        if res_update.status_code in [200, 201]:
            updated_json = res_update.json()
            saved_content = updated_json.get('content', {}).get('raw', '')
            
            if "application/ld+json" not in saved_content and len(cards_html_list) > 0:
                return False, "❌ 致命错误：写入被服务器安全插件拦截。"

            msg = f"已强制写入数据库校验通过！雷达检测到 {h2_found_count} 个 H2 标签，成功插入 {min(card_idx, h2_found_count)} 个模块"
            if card_idx > h2_found_count:
                msg += f" (另有 {card_idx - h2_found_count} 个模块被追加到了文章末尾)。"
            msg += " 👉 请现在去后台按 F5 完全刷新页面。"
            return True, msg
        else: 
            return False, f"更新失败: {res_update.text[:200]}"
    except Exception as e: 
        return False, f"更新异常: {e}"

# ================= 界面工作流 =================

st.markdown("### 步骤 1：输入数据源")
tab1, tab2 = st.tabs(["🤖 AI 智能海选模式", "🔗 手动直达模式"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: blog_url = st.text_input("博客文章链接 (Blog Post URL)", placeholder="用于语义匹配分析")
    with col2: shop_url = st.text_input("商品列表页/着陆页链接 (Landing Page)", placeholder="用于抓取候选商品")
    if st.button("🔍 抓取并智能海选", type="primary"):
        if not blog_url or not shop_url: st.warning("请填写完整的两个链接！")
        else:
            with st.spinner("正在抓取候选商品池与分析博客语义..."):
                blog_text = fetch_blog_context(blog_url)
                pool = fetch_product_list(shop_url)
                if not pool:
                    st.error("❌ 未能从该着陆页抓取到有效商品链接，请检查链接是否可访问。")
                else:
                    raw_top_30 = ai_match_top_30(blog_text, pool)
                    matched_list = [item for item in (raw_top_30 if isinstance(raw_top_30, list) else []) if isinstance(item, dict) and "url" in item]
                    # 并发补全可能因懒加载缺失的高清缩略图
                    matched_list = resolve_missing_thumbnails(matched_list)
                    for idx, p in enumerate(matched_list):
                        p.setdefault("thumbnail", dummy_image)
                        p["candidate_key"] = f"{p['url']}###{idx}"
                    st.session_state.matched_products = matched_list
                    if st.session_state.matched_products:
                        st.session_state.step = 2
                        st.rerun()

with tab2:
    st.info("💡 直接粘贴商品详情页链接（一行一个），系统将自动过滤无关元素，并为每个商品精准抓取最多 4 张高品质图片供你挑选。")
    direct_urls = st.text_area("输入商品链接：", height=150)
    if st.button("🚀 直接获取商品候选图", type="primary"):
        if direct_urls.strip():
            with st.spinner("正在深入页面智能排雷并解析相册，请稍候..."):
                st.session_state.matched_products = fetch_direct_urls(direct_urls)
                if st.session_state.matched_products:
                    st.session_state.step = 2
                    st.rerun()

if st.session_state.step >= 2 and st.session_state.matched_products:
    st.markdown(f"### 步骤 2：人工确认生成名单 (共筛选出 {len(st.session_state.matched_products)} 个候选)")
    with st.form("selection_form"):
        temp_selected_keys = []
        cols_per_row = 8
        for i in range(0, len(st.session_state.matched_products), cols_per_row):
            row_items = st.session_state.matched_products[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for col, item in zip(cols, row_items):
                with col:
                    st.image(item["thumbnail"], use_container_width=True)
                    display_title = item['title'][:15] + "..." if len(item['title']) > 15 else item['title']
                    st.caption(f"{display_title}")
                    
                    if st.checkbox("选择此图", key=f"chk_{item['candidate_key']}"): 
                        temp_selected_keys.append(item["candidate_key"])
            st.write("") 
        if st.form_submit_button("➡️ 确认选中，进入下一步", type="primary"):
            if temp_selected_keys:
                st.session_state.selected_keys = temp_selected_keys
                st.session_state.step = 3
                st.rerun()

if st.session_state.step >= 3 and st.session_state.selected_keys:
    st.markdown("### 步骤 3：配置促销标签与选择模板")

    key_to_item_preview = {p.get("candidate_key"): p for p in st.session_state.matched_products}
    first_selected_item = next((key_to_item_preview[k] for k in st.session_state.selected_keys if k in key_to_item_preview), None)
    sample_url_for_lang = first_selected_item["url"] if first_selected_item else "https://fr.callie.com"
    sample_thumb_for_preview = first_selected_item["thumbnail"] if first_selected_item and first_selected_item.get("thumbnail") else dummy_image
    detected_preview_lang = detect_lang_from_url(sample_url_for_lang)

    # ---- 步骤 3.1：可选促销标签设置 ----
    st.markdown("#### 🏷️ 3.1 是否在商品图上叠加节日/大促角标？")
    st.caption("💡 注：无论是否开启图片节日角标，只要商品着陆页本身存在 `div.old`（划线原价）与 `span.discount-text`（折扣文案），系统都会自动提取并在卡片价格区域展示出来。")
    enable_badge_choice = st.radio(
        "是否启用图片促销角标：",
        ["❌ 否，不叠加图片节日角标 (仅展示页面自带真实价格与折扣)", "✅ 是，在商品图上添加节日大促角标 (Black Friday / Cyber Monday / Christmas)"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if enable_badge_choice.startswith("❌"):
        st.session_state.selected_badge_id = None
    else:
        with st.container():
            st.info(f"🌍 已根据您勾选的商品自动识别目标站点语言：**`{detected_preview_lang}`**（下方素材与最终生成卡片将自动按各商品对应语言渲染文案）。")
            theme_choice = st.radio(
                "🎉 请选择促销活动主题：",
                list(BADGE_CATALOG.keys()),
                horizontal=True
            )
            theme_materials = BADGE_CATALOG[theme_choice]
            mat_keys = list(theme_materials.keys())

            if st.session_state.selected_badge_id not in mat_keys:
                st.session_state.selected_badge_id = mat_keys[0]

            st.markdown("**🎨 请点击选择以下 5 款标签素材之一（选中后下方模板示例图将实时同步更新）：**")
            mat_cols = st.columns(5)
            for m_col, (m_id, m_info) in zip(mat_cols, theme_materials.items()):
                with m_col:
                    is_active = (st.session_state.selected_badge_id == m_id)
                    border_style = "2px solid #1A73E8" if is_active else "1px solid #DADCE0"
                    badge_preview_snippet = get_badge_html(m_id, sample_url_for_lang)
                    mat_card_html = f"""
                    <html><body style="margin:0; padding:4px; font-family:sans-serif; background:transparent;">
                        <div style="border:{border_style}; border-radius:12px; padding:8px; background:#FFFFFF; text-align:center;">
                            <div style="font-size:11px; font-weight:bold; color:#202124; margin-bottom:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{m_info['name']}</div>
                            <div style="width:100%; height:120px; border-radius:8px; overflow:hidden; position:relative; background:#F3F4F6;">
                                {badge_preview_snippet}
                                <img src="{sample_thumb_for_preview}" style="width:100%; height:100%; object-fit:cover; display:block;">
                            </div>
                        </div>
                    </body></html>
                    """
                    st.components.v1.html(mat_card_html, height=165, scrolling=False)
                    btn_label = "✅ 当前已选" if is_active else f"选用【{m_info['name'].split('：')[0]}】"
                    if st.button(btn_label, key=f"select_mat_{m_id}", type="primary" if is_active else "secondary", use_container_width=True):
                        st.session_state.selected_badge_id = m_id
                        st.rerun()

    st.markdown("---")
    st.markdown("#### 🎨 3.2 选择数据输出模式与卡片模板")
    mode_choice = st.radio("请选择：", ["🎨 生成高转化商品卡片 (包含完整排版与样式)", "🖼️ 仅生成纯净原图 (纯粹 SEO 优化，抗干扰)"], horizontal=True, label_visibility="collapsed")
    
    preview_badge_html = get_badge_html(st.session_state.selected_badge_id, sample_url_for_lang)

    if mode_choice.startswith("🎨"):
        st.session_state.output_mode = "card"
        
        tmpl_items = list(templates.items())
        cols_per_tmpl_row = 4
        for r_idx in range(0, len(tmpl_items), cols_per_tmpl_row):
            row_tmpls = tmpl_items[r_idx:r_idx + cols_per_tmpl_row]
            tmpl_cols = st.columns(cols_per_tmpl_row)
            for col, (tmpl_name, tmpl_data) in zip(tmpl_cols, row_tmpls):
                with col:
                    st.markdown(f"**{tmpl_name}**")
                    p_style = tmpl_data.get("price_style", "left_right")
                    dummy_price_html = build_price_display_html("€ 30,60", "€ 34,00", "10% Korting", style_type=p_style)
                    dummy_data = {
                        "image_url": dummy_image, 
                        "title": "Gepersonaliseerde Gitaar Plectrum Opbergkoffer", 
                        "price": "€ 30,60",
                        "price_html": dummy_price_html,
                        "specs": "<ul style='margin:0; padding-left:16px; color:#555;'><li style='margin-bottom:3px;'><strong>Materiaal:</strong> Kersenhout</li><li><strong>Personalisatie:</strong> Gratis gravure</li></ul>", 
                        "buy_link": sample_url_for_lang, 
                        "cta_text": "In winkelwagen", 
                        "json_ld": "",
                        "badge_html": preview_badge_html
                    }
                    if tmpl_data["type"] == "carousel":
                        preview_html = tmpl_data["html"].replace("{carousel_items}", tmpl_data.get("item_html", "").format(**dummy_data) * 3).format(**dummy_data)
                    elif tmpl_data["type"] == "collage":
                        preview_html = tmpl_data["html"].replace("{collage_items}", tmpl_data.get("item_html", "").format(**dummy_data) * 2).format(**dummy_data)
                    else:
                        preview_html = tmpl_data["html"].format(**dummy_data)
                    
                    wrapped_html = f"<html><body style='margin:0; padding:10px; background:#fff; font-family:sans-serif;'>{preview_html}</body></html>"
                    st.components.v1.html(wrapped_html, height=380, scrolling=True)
                    
                    if st.button(f"✨ 使用【{tmpl_name.split('：')[0]}】生成", key=f"btn_{tmpl_name}", use_container_width=True):
                        st.session_state.selected_template = tmpl_name
                        st.session_state.step = 4
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.session_state.output_mode = "image"
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ 确认使用【纯净原图】模式并提取数据", type="primary"):
            st.session_state.step = 4
            st.rerun()

if st.session_state.step >= 4:
    st.markdown("### 步骤 4：最终生成结果")
    
    key_to_item = {p.get("candidate_key"): p for p in st.session_state.matched_products}
    selected_items = [key_to_item[k] for k in st.session_state.selected_keys if k in key_to_item]
    
    my_bar = st.progress(0, text="正在逐个深入详情页提取数据...")
    all_extracted_data = []
    generated_single_cards = [] 
    url_details_cache = {}
    
    for i, item in enumerate(selected_items):
        prod_url = item["url"]
        if prod_url in url_details_cache:
            details_data = dict(url_details_cache[prod_url])
            details_data["image_url"] = item["thumbnail"]
        else:
            details_data = extract_product_details(prod_url, preselected_image=item["thumbnail"])
            if details_data:
                url_details_cache[prod_url] = dict(details_data)

        if details_data:
            raw_specs = details_data.get("specs", "")
            
            # 强制过滤掉所有包含 Size / 尺寸 的字段
            if isinstance(raw_specs, dict):
                filtered_specs = {k: v for k, v in raw_specs.items() if not is_size_spec_key(k) and not is_size_spec_line(f"{k}: {v}")}
                specs_str = "<ul style='margin:0; padding-left:16px;'>" + "".join([f"<li style='margin-bottom:3px;'><strong>{k}:</strong> {v}</li>" for k, v in filtered_specs.items()]) + "</ul>"
                specs_plain = "; ".join([f"{k}: {v}" for k, v in filtered_specs.items()])
            elif isinstance(raw_specs, list):
                filtered_list = [str(x) for x in raw_specs if not is_size_spec_line(str(x))]
                specs_str = "<ul style='margin:0; padding-left:16px;'>" + "".join([f"<li style='margin-bottom:3px;'>{x}</li>" for x in filtered_list]) + "</ul>"
                specs_plain = "; ".join(filtered_list)
            else:
                lines = [x.strip() for x in str(raw_specs).replace('•', '\n').split('\n') if x.strip() and not is_size_spec_line(x)]
                specs_str = "<ul style='margin:0; padding-left:16px;'>" + "".join([f"<li style='margin-bottom:3px;'>{x}</li>" for x in lines]) + "</ul>"
                specs_plain = "; ".join(lines)
                
            details_data["specs_formatted"] = specs_str
            schema_desc = details_data.get("page_description") or specs_plain or details_data.get("title", "")
            details_data["schema_description"] = schema_desc
            
            item_badge_html = get_badge_html(st.session_state.selected_badge_id, details_data.get("buy_link", ""))
            details_data["badge_html"] = item_badge_html
            all_extracted_data.append(details_data)
            
            ld_script = generate_single_json_ld(
                title=details_data.get("title", ""),
                image_url=details_data.get("image_url", ""),
                price=details_data.get("price", ""),
                buy_link=details_data.get("buy_link", ""),
                return_days=details_data.get("return_days", 30),
                description=schema_desc,
                page_currency=details_data.get("page_currency", "")
            )
            
            if st.session_state.output_mode == "image":
                raw_img_html = f"""{ld_script}<div style="text-align: center; margin-bottom: 25px;"><div style="display: inline-block; position: relative; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">{item_badge_html}<a href="{details_data.get("buy_link")}" target="_blank" title="{details_data.get("title", "Callie Product")}"><img src="{details_data.get("image_url")}" alt="{details_data.get("title", "Callie Product")}" style="max-width: 100%; height: auto; border-radius: 8px; border: none; display: block;"></a></div></div>"""
                generated_single_cards.append(raw_img_html)
                st.markdown(f"**📝 原图预览: {details_data.get('title', item['title'])}**")
                c1, c2 = st.columns([1, 1], gap="large")
                with c1: st.components.v1.html(f"<html><body style='margin:0; padding:10px; background:#fff;'>{raw_img_html}</body></html>", height=450, scrolling=True)
                with c2: 
                    with st.expander("💻 点击展开 / 复制 HTML 代码"): st.code(raw_img_html, language='html')
                st.write("---") 
            else:
                tmpl_config = templates[st.session_state.selected_template]
                if tmpl_config["type"] == "single":
                    p_style = tmpl_config.get("price_style", "left_right")
                    price_display_html = build_price_display_html(
                        price=details_data.get("price", ""),
                        original_price=details_data.get("original_price", ""),
                        discount_text=details_data.get("discount_text", ""),
                        style_type=p_style
                    )
                    card_html = tmpl_config["html"].format(
                        image_url=details_data.get("image_url", ""),
                        title=details_data.get("title", ""),
                        price=details_data.get("price", ""),
                        price_html=price_display_html,
                        specs=specs_str,
                        buy_link=details_data.get("buy_link", ""),
                        cta_text=details_data.get("cta_text", "Buy Now"),
                        json_ld=ld_script,
                        badge_html=item_badge_html
                    )
                    generated_single_cards.append(card_html)
                    st.markdown(f"**📝 卡片预览: {details_data.get('title', item['title'])}**")
                    c1, c2 = st.columns([1, 1], gap="large")
                    with c1: st.components.v1.html(f"<html><body style='margin:0; padding:10px; background:#fff;'>{card_html}</body></html>", height=400, scrolling=True)
                    with c2: 
                        with st.expander("💻 点击展开 / 复制完整 HTML 代码"): st.code(card_html, language='html')
                    st.write("---") 
        my_bar.progress((i + 1) / len(selected_items), text=f"已处理 {i+1}/{len(selected_items)} 个商品...")
        
    if st.session_state.output_mode == "card" and templates[st.session_state.selected_template]["type"] == "carousel" and all_extracted_data:
        st.markdown("**📝 以下是包含所有勾选商品的轮播图代码组件**")
        ld_script = generate_carousel_json_ld(all_extracted_data)
        
        unified_cta_text = all_extracted_data[0].get("cta_text", "Buy Now") if len(all_extracted_data) > 0 else "Buy Now"
        
        carousel_items_str = "".join([templates[st.session_state.selected_template]["item_html"].format(
            image_url=data.get("image_url", ""), 
            title=data.get("title", ""), 
            price=data.get("price", ""),
            price_html=build_price_display_html(
                price=data.get("price", ""),
                original_price=data.get("original_price", ""),
                discount_text=data.get("discount_text", ""),
                style_type="carousel"
            ),
            buy_link=data.get("buy_link", ""), 
            cta_text=unified_cta_text,
            badge_html=data.get("badge_html", "")
        ) for data in all_extracted_data])
        
        final_carousel_html = templates[st.session_state.selected_template]["html"].replace("{carousel_items}", carousel_items_str).format(json_ld=ld_script)
        st.session_state.generated_cards_list = [final_carousel_html]
        c1, c2 = st.columns([1, 1], gap="large")
        with c1: st.components.v1.html(f"<html><body style='margin:0; padding:10px; background:#fff;'>{final_carousel_html}</body></html>", height=360, scrolling=True)
        with c2: 
            with st.expander("💻 点击展开 / 复制完整轮播 HTML 代码"): st.code(final_carousel_html, language='html')

    elif st.session_state.output_mode == "card" and templates[st.session_state.selected_template]["type"] == "collage" and all_extracted_data:
        st.markdown("**📝 以下是包含所选商品图片的拼图模式代码组件**")
        ld_script = generate_carousel_json_ld(all_extracted_data)
        
        primary_buy_link = all_extracted_data[0].get("buy_link", "")
        primary_cta_text = all_extracted_data[0].get("cta_text", "Buy Now")
        
        unique_urls = set(d.get("buy_link", "") for d in all_extracted_data)
        is_same_product = (len(unique_urls) == 1)
        
        collage_items_str = "".join([templates[st.session_state.selected_template]["item_html"].format(
            image_url=data.get("image_url", ""),
            title=data.get("title", ""),
            buy_link=primary_buy_link if is_same_product else data.get("buy_link", primary_buy_link),
            badge_html=data.get("badge_html", "")
        ) for data in all_extracted_data])
        
        final_collage_html = templates[st.session_state.selected_template]["html"].replace("{collage_items}", collage_items_str).format(
            json_ld=ld_script,
            buy_link=primary_buy_link,
            cta_text=primary_cta_text
        )
        st.session_state.generated_cards_list = [final_collage_html]
        c1, c2 = st.columns([1, 1], gap="large")
        with c1: st.components.v1.html(f"<html><body style='margin:0; padding:10px; background:#fff;'>{final_collage_html}</body></html>", height=420, scrolling=True)
        with c2:
            with st.expander("💻 点击展开 / 复制完整拼图 HTML 代码"): st.code(final_collage_html, language='html')

    elif generated_single_cards:
        st.session_state.generated_cards_list = generated_single_cards
                
    st.success(f"✅ 全部处理完毕！已生成 {len(st.session_state.generated_cards_list)} 个模块。")

# ================= 步骤 5：自动注入文章 =================
if st.session_state.step >= 4 and getattr(st.session_state, "generated_cards_list", None):
    st.markdown("---")
    st.markdown("### 步骤 5：智能注入 WordPress 文章")
    
    col_w1, col_w2 = st.columns([1, 1], gap="large")
    with col_w1:
        st.info("💡 **H2 对齐无损注入逻辑**\n\n系统使用正则表达式自动读取文章，并将生成的商品卡片按顺序插入到每个 `<h2>` 的上方。保留了原文所有的高级区块排版。")
        st.markdown(f"**待推送的模块总数：** `{len(st.session_state.generated_cards_list)}` 个")
        
    with col_w2:
        my_wp_sites = {"🇩🇪 德语站": "DE", "🇫🇷 法语站": "FR", "🇪🇸 西班牙站": "ES", "🇮🇹 意大利站": "IT", "🇳🇱 荷兰站": "NL", "🇳🇴 挪威站": "NO", "🇸🇪 瑞典站": "SE", "🇫🇮 芬兰站": "FI", "🇵🇱 波兰站": "PL"}
        site_urls = {"DE": "https://www.callie.de/blog", "FR": "https://fr.callie.com/blog", "ES": "https://www.callie.es/blog", "IT": "https://it.callie.com/blog", "NL": "https://nl.callie.com/blog", "NO": "https://no.callie.com/blog", "SE": "https://www.callie.se/blog", "FI": "https://www.callie.fi/blog", "PL": "https://pl.callie.com/blog"}
        
        selected_site_name = st.selectbox("🎯 选择目标网站：", list(my_wp_sites.keys()))
        site_prefix = my_wp_sites[selected_site_name]
        wp_url = site_urls[site_prefix]
        
        user_key = "WP_USER"
        pass_key = f"WP_PASS_{site_prefix}"
        
        if user_key in st.secrets and pass_key in st.secrets:
            st.success(f"🔒 凭证已加载")
            wp_user = st.secrets[user_key]
            wp_pass = st.secrets[pass_key]
        else:
            st.warning(f"⚠️ 缺少 {pass_key}，请前往后台添加。")
            c1, c2 = st.columns(2)
            with c1: wp_user = st.text_input("用户名", value=st.secrets.get("WP_USER", ""))
            with c2: wp_pass = st.text_input(f"应用密码", type="password")
            
        target_post_id = st.text_input("🎯 指定文章 ID (必填)", help="填入你要修改的文章 ID (纯数字，如 1024)。")
        
        if st.button("🚀 开始无损注入并更新", type="primary"):
            if not target_post_id.strip() or not wp_user or not wp_pass: st.warning("请确保 ID 与验证信息完整！")
            else:
                with st.spinner("正在防破坏式注入并更新文章..."):
                    success, msg = push_cards_to_wp_h2(wp_url, wp_user, wp_pass, target_post_id, st.session_state.generated_cards_list)
                    if success: st.success(f"🎉 {msg}")
                    else: st.error(msg)
