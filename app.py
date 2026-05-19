# NianNian Memorial Studio - MV01+MV02
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st
import pipeline_runner
from llm_client import call_memorial_chat, call_structured, describe_image

st.set_page_config(page_title="NianNian Memorial Studio", layout="wide", initial_sidebar_state="collapsed")

_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,600&family=Noto+Sans+SC:wght@300;400;500;700&family=Noto+Serif+SC:wght@400;500;600&display=swap');
:root{--bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;--border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);--gold:#9C7A45;--gold-l:#B8934F;--gold-dim:rgba(156,122,69,.08);--gold-glow:rgba(156,122,69,.18);--ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;}
html,body,[class*="css"]{font-family:'Noto Sans SC',sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;font-size:16px!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
[data-testid="stSidebarNav"],section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:780px!important;padding:0 20px 100px!important;margin:0 auto!important;}
.nn-topbar{display:flex;align-items:center;justify-content:space-between;padding:24px 0 28px;}
.nn-logo{display:flex;align-items:center;gap:12px;}
.nn-logo-orb{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#B8934F);box-shadow:0 2px 12px rgba(156,122,69,.28);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;font-family:'Cormorant Garamond',serif;}
.nn-logo-name{font-family:'Cormorant Garamond',serif;font-size:1.3rem;font-weight:600;color:var(--ink);}
.nn-logo-sub{font-size:.72rem;color:var(--muted-l);letter-spacing:.05em;}
.nn-badge{font-size:.72rem;font-weight:600;letter-spacing:.05em;color:var(--gold);background:var(--gold-dim);border:1px solid var(--border-h);border-radius:999px;padding:5px 14px;}
.nn-steps-row{display:flex;gap:8px;margin-bottom:36px;align-items:center;}
.nn-step-pill{display:flex;align-items:center;gap:7px;padding:7px 16px;border-radius:999px;font-size:.8rem;font-weight:500;background:var(--surf2);border:1px solid var(--border);color:var(--muted-l);transition:all .2s;}
.nn-step-pill.active{background:var(--surf3);border-color:var(--border-h);color:var(--gold);font-weight:700;}
.nn-step-pill.done{color:var(--muted);}
.nn-step-num{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;background:var(--surf);border:1px solid var(--border);color:var(--muted-l);}
.nn-step-pill.active .nn-step-num{background:var(--gold);border-color:var(--gold);color:#fff;}
.nn-step-divider{flex:1;height:1px;background:var(--border);max-width:40px;}
.nn-card{background:var(--surf);border:1px solid var(--border);border-radius:20px;padding:28px 32px;margin-bottom:16px;box-shadow:0 2px 16px rgba(0,0,0,.04);}
.nn-section-label{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid var(--border);}
label,.stTextInput label,.stTextArea label,.stSelectbox label{font-size:.82rem!important;font-weight:600!important;letter-spacing:.04em!important;text-transform:uppercase!important;color:var(--muted-l)!important;margin-bottom:6px!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{background:var(--surf)!important;border:1px solid var(--border)!important;border-radius:12px!important;color:var(--ink)!important;font-size:1rem!important;padding:13px 16px!important;transition:border-color .2s,box-shadow .2s!important;}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{border-color:var(--border-h)!important;box-shadow:0 0 0 3px var(--gold-dim)!important;outline:none!important;}
.stTextInput>div>div>input::placeholder,.stTextArea>div>div>textarea::placeholder{color:var(--muted)!important;}
.stSelectbox>div>div{background:var(--surf)!important;border:1px solid var(--border)!important;border-radius:12px!important;font-size:1rem!important;}
[data-baseweb="select"]>div{background:var(--surf)!important;border-color:var(--border)!important;}
[data-baseweb="popover"]{background:var(--surf)!important;border:1px solid var(--border)!important;}
[data-baseweb="menu"] li{background:var(--surf)!important;color:var(--ink)!important;}
[data-baseweb="menu"] li:hover{background:var(--surf2)!important;}
.stRadio>div{gap:10px!important;flex-wrap:wrap!important;}
.stRadio>div>label{background:var(--surf2)!important;border:1px solid var(--border)!important;border-radius:999px!important;padding:10px 20px!important;font-size:.95rem!important;font-weight:500!important;text-transform:none!important;letter-spacing:0!important;color:var(--ink-m)!important;cursor:pointer!important;transition:all .2s!important;}
.stRadio>div>label:has(input:checked){background:var(--gold-dim)!important;border-color:var(--border-h)!important;color:var(--gold)!important;font-weight:700!important;}
[data-testid="stFileUploader"]>div{background:var(--surf2)!important;border:1.5px dashed var(--border-h)!important;border-radius:16px!important;}
div.stButton>button{border-radius:999px!important;font-family:'Noto Sans SC',sans-serif!important;font-size:1rem!important;font-weight:600!important;padding:13px 28px!important;transition:all .22s!important;border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;color:var(--ink)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;box-shadow:0 4px 20px var(--gold-glow)!important;font-size:1.05rem!important;padding:15px 36px!important;}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;border-color:var(--gold-l)!important;box-shadow:0 6px 28px rgba(156,122,69,.3)!important;transform:translateY(-1px)!important;}
.nn-chat-wrap{display:flex;flex-direction:column;gap:20px;padding-bottom:8px;}
.nn-chat-ai{display:flex;align-items:flex-start;gap:12px;}
.nn-ai-avatar{width:42px;height:42px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#C4964A 0%,#E8C57A 50%,#9C7A45 100%);background-size:200% 200%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;font-family:'Cormorant Garamond',serif;box-shadow:0 2px 12px rgba(156,122,69,.28);letter-spacing:.02em;animation:avatar-grad 6s ease infinite;}
@keyframes avatar-grad{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.nn-ai-bubble-wrap{display:flex;flex-direction:column;gap:4px;}
.nn-ai-name{font-size:.72rem;font-weight:700;color:var(--gold);letter-spacing:.05em;}
.nn-ai-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 20px 20px 20px;padding:16px 20px;max-width:78%;font-size:1rem;line-height:1.78;color:var(--ink);box-shadow:0 2px 12px rgba(0,0,0,.05);white-space:pre-wrap;}
.nn-chat-user{display:flex;justify-content:flex-end;}
.nn-user-bubble{background:var(--gold);color:#fff;border-radius:20px 4px 20px 20px;padding:14px 20px;max-width:70%;font-size:1rem;line-height:1.7;box-shadow:0 2px 12px rgba(156,122,69,.28);}
@keyframes orb-pulse{0%,100%{transform:scale(1);filter:brightness(1);}50%{transform:scale(1.1);filter:brightness(1.18);}}
@keyframes ring-out{0%{transform:scale(1);opacity:.6;}100%{transform:scale(2.1);opacity:0;}}
@keyframes dot-bounce{0%,80%,100%{transform:translateY(0);opacity:.35;}40%{transform:translateY(-7px);opacity:1;}}
@keyframes grad-shift{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.nn-think-row{display:flex;align-items:flex-start;gap:12px;}
.nn-think-avatar-wrap{position:relative;width:42px;height:42px;flex-shrink:0;}
.nn-think-orb{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#C4964A,#F0D590,#9C7A45,#DCA855);background-size:300% 300%;animation:orb-pulse 2s ease-in-out infinite,grad-shift 4s ease infinite;position:relative;z-index:2;}
.nn-think-ring{position:absolute;inset:0;border-radius:50%;border:1.5px solid rgba(184,147,79,.55);animation:ring-out 2s ease-out infinite;z-index:1;}
.nn-think-ring-2{animation-delay:1s;}
.nn-think-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 20px 20px 20px;padding:16px 22px;display:flex;align-items:center;gap:14px;box-shadow:0 2px 12px rgba(0,0,0,.05);}
.nn-think-dots{display:flex;gap:6px;align-items:center;}
.nn-think-dots span{width:8px;height:8px;border-radius:50%;background:var(--gold);display:block;}
.nn-think-dots span:nth-child(1){animation:dot-bounce 1.4s 0s ease infinite;}
.nn-think-dots span:nth-child(2){animation:dot-bounce 1.4s .22s ease infinite;}
.nn-think-dots span:nth-child(3){animation:dot-bounce 1.4s .44s ease infinite;}
.nn-think-label{font-size:.88rem;color:var(--muted-l);font-style:italic;}
.nn-confirm-strip{background:linear-gradient(135deg,var(--surf2),var(--surf));border:1px solid var(--border-h);border-radius:18px;padding:16px 22px;margin-top:6px;display:flex;align-items:center;gap:10px;box-shadow:0 2px 12px rgba(156,122,69,.08);}
.nn-confirm-dot{width:8px;height:8px;border-radius:50%;background:var(--gold);box-shadow:0 0 0 4px var(--gold-dim);flex-shrink:0;}
.nn-step-header{margin-bottom:28px;}
.nn-step-eyebrow{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:10px;display:flex;align-items:center;gap:8px;}
.nn-step-eyebrow::before{content:'';display:block;width:22px;height:1px;background:var(--gold);opacity:.5;}
.nn-step-title{font-family:'Cormorant Garamond','Noto Serif SC',serif;font-size:clamp(1.6rem,4vw,2.2rem);font-weight:600;line-height:1.15;color:var(--ink);margin-bottom:8px;}
.nn-step-desc{font-size:.95rem;color:var(--muted-l);line-height:1.65;max-width:500px;}
.nn-hint-pill{display:flex;align-items:flex-start;gap:10px;padding:13px 18px;border-radius:12px;border:1px solid var(--border);background:var(--surf2);font-size:.9rem;color:var(--ink-m);line-height:1.5;margin-bottom:12px;}
.nn-hint-dot{width:6px;height:6px;border-radius:50%;background:var(--gold);flex-shrink:0;margin-top:6px;}
.nn-hero{padding:40px 0 36px;text-align:center;}
.nn-hero-title{font-family:'Cormorant Garamond','Noto Serif SC',serif;font-size:clamp(2.4rem,6vw,3.8rem);font-weight:500;line-height:1.12;color:var(--ink);margin-bottom:16px;}
.nn-hero-title em{font-style:italic;color:var(--gold-l);}
.nn-hero-line{width:60px;height:1px;margin:0 auto 20px;background:linear-gradient(90deg,transparent,var(--gold),transparent);}
.nn-hero-sub{font-size:1rem;color:var(--muted-l);line-height:1.7;max-width:440px;margin:0 auto;}
[data-testid="stAlert"]{background:var(--surf2)!important;border-radius:12px!important;border:1px solid var(--border)!important;color:var(--ink-m)!important;}
hr{border-color:var(--border)!important;margin:24px 0!important;}
@keyframes nn-fade-up{from{opacity:0;transform:translateY(16px);}to{opacity:1;transform:translateY(0);}}
.nn-fade-up{animation:nn-fade-up .5s cubic-bezier(.25,.46,.45,.94) both;}
[data-testid="stChatInput"]{max-width:780px!important;margin:0 auto!important;padding:0!important;}
[data-testid="stChatInput"] > div{background:#fff!important;border:1.5px solid var(--border-h)!important;border-radius:999px!important;box-shadow:none!important;padding:4px 6px 4px 20px!important;}
[data-testid="stChatInput"] > div > div{background:#fff!important;border:none!important;box-shadow:none!important;padding:0!important;}
[data-testid="stChatInput"] textarea{background:#fff!important;border:none!important;outline:none!important;box-shadow:none!important;font-size:.95rem!important;color:var(--ink)!important;line-height:1.6!important;padding:10px 0!important;resize:none!important;}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted)!important;font-style:italic!important;}
[data-testid="stChatInput"] button{all:unset!important;cursor:pointer!important;width:32px!important;height:32px!important;border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;flex-shrink:0!important;}
[data-testid="stChatInput"] button:hover{background:var(--gold-dim)!important;}
[data-testid="stChatInput"] button svg{fill:var(--gold)!important;stroke:var(--gold)!important;width:16px!important;height:16px!important;}
</style>"""

st.markdown(_CSS, unsafe_allow_html=True)

# ── Board 导航 ──────────────────────────────────────────────────────────────────
_HOME_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Lato:wght@300;400;700&family=Noto+Sans+SC:wght@300;400;700&family=Noto+Serif+SC:wght@400;600&display=swap" rel="stylesheet">
<style>
/* ── reset streamlit chrome for hero page ── */
.stApp { background: transparent !important; }
.block-container { max-width: 100% !important; padding: 0 !important; position: relative; z-index: 1; }
header[data-testid="stHeader"] { background: transparent !important; }
/* ── full-screen hero shell ── */
.home-hero {
  position: relative; min-height: 100vh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center; padding: 80px 24px 160px;
  overflow: hidden;
}
/* ── brand title ── */
.home-brand {
  font-family: 'Noto Serif SC', 'Playfair Display', serif;
  font-size: clamp(2.4rem, 4vw, 3.6rem);
  font-weight: 600; color: #fff; letter-spacing: .12em;
  margin-bottom: 8px;
  text-shadow: 0 2px 20px rgba(0,0,0,.5);
}
.home-brand em { font-style: italic; color: #FFD54F; letter-spacing: .04em; }
.home-brand-line {
  width: 52px; height: 1px; margin: 0 auto 28px;
  background: linear-gradient(90deg, transparent, rgba(255,213,79,.7), transparent);
}
/* ── badge pill ── */
.home-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 18px; border-radius: 999px;
  background: rgba(255,255,255,0.12);
  backdrop-filter: blur(6px);
  font-size: 12px; letter-spacing: .1em; text-transform: lowercase;
  color: #e8e0d0; margin-bottom: 32px;
}
/* ── heading ── */
.home-h1 {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-size: clamp(2.8rem, 6vw, 5rem);
  font-weight: 700; line-height: 1.15;
  letter-spacing: -.02em; color: #fff;
  max-width: 860px; margin: 0 auto 16px;
  text-shadow: 0 2px 24px rgba(0,0,0,.4);
}
.home-h1 .gold {
  display: block; font-style: italic; color: #FFD54F;
  text-shadow: 0 2px 32px rgba(255,213,79,.3);
}
/* ── sub ── */
.home-sub {
  font-family: 'Lato', 'Noto Sans SC', sans-serif;
  font-size: 1rem; color: rgba(220,210,195,.85);
  max-width: 540px; margin: 0 auto 56px; line-height: 1.7;
}
/* ── buttons row ── */
.home-btn-row {
  display: flex; gap: 20px; justify-content: center;
  flex-wrap: wrap;
}
/* ── streamlit button overrides ── */
div[data-testid="stHorizontalBlock"] { background: transparent !important; }
.hbtn div.stButton > button {
  all: unset !important;
  display: flex !important; flex-direction: column !important;
  align-items: center !important; justify-content: center !important;
  width: 220px !important; min-height: 120px !important;
  background: rgba(255,255,255,0.10) !important;
  backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(255,255,255,0.22) !important;
  border-radius: 20px !important;
  cursor: pointer !important;
  transition: all .3s ease !important;
  padding: 20px 16px !important; gap: 8px !important;
  box-shadow: 0 8px 32px rgba(0,0,0,.18) !important;
}
.hbtn div.stButton > button:hover {
  background: rgba(255,255,255,0.18) !important;
  border-color: rgba(255,213,79,.5) !important;
  transform: translateY(-6px) !important;
  box-shadow: 0 16px 48px rgba(0,0,0,.28) !important;
}
.hbtn div.stButton > button p {
  font-family: 'Lato', 'Noto Sans SC', sans-serif !important;
  font-size: .82rem !important; color: rgba(240,232,218,.85) !important;
  font-style: normal !important; margin: 0 !important; line-height: 1.5 !important;
  text-align: center !important;
}
/* first line of button text = title */
.hbtn div.stButton > button > div:first-child p:first-child,
.hbtn div.stButton > button [data-testid="stMarkdownContainer"] p:first-child {
  font-size: 1rem !important; font-weight: 700 !important;
  color: #fff !important; margin-bottom: 4px !important;
  font-family: 'Playfair Display', serif !important;
}
/* ── divider line ── */
.home-divider {
  width: 48px; height: 1px; margin: 0 auto 20px;
  background: linear-gradient(90deg, transparent, rgba(255,213,79,.6), transparent);
}
</style>
"""

st.session_state.setdefault("main_section", "home")

if st.session_state["main_section"] == "home":
    import base64 as _b64, os as _os
    _img_path = _os.path.join(_os.path.dirname(__file__), "asset", "OurDearFriend.jpg")
    try:
        with open(_img_path, "rb") as _f:
            _img_b64 = _b64.b64encode(_f.read()).decode()
        _img_data = f"data:image/jpeg;base64,{_img_b64}"
    except Exception:
        _img_data = ""

    # 背景：用 <img> 绝对定位 + 遮罩层，避免 CSS url() 被截断
    _bg_html = f"""
    <style>
    .stApp {{ background: #0d0a07 !important; overflow: hidden; }}
    .stApp > div {{ position: relative; z-index: 1; }}
    #nn-bg-img {{
        position: fixed; inset: 0; width: 100%; height: 100%;
        object-fit: cover; object-position: center;
        z-index: -2; display: block;
    }}
    #nn-bg-overlay {{
        position: fixed; inset: 0; z-index: -1;
        background: linear-gradient(160deg,
            rgba(12,8,4,0.50) 0%,
            rgba(18,11,5,0.70) 50%,
            rgba(8,6,3,0.82) 100%);
    }}
    </style>
    <img id="nn-bg-img" src="{_img_data}" alt="">
    <div id="nn-bg-overlay"></div>
    """ if _img_data else "<style>.stApp{{background:#0d0a07!important;}}</style>"
    st.markdown(_bg_html, unsafe_allow_html=True)
    st.markdown(_HOME_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="home-hero">
      <div class="home-brand">念念 <em>AI</em></div>
      <div class="home-brand-line"></div>
      <div class="home-badge">
        <svg width="6" height="6" viewBox="0 0 6 6"><circle cx="3" cy="3" r="3" fill="#FFD54F"/></svg>
        where memory finds a lasting home
        <svg width="6" height="6" viewBox="0 0 6 6"><circle cx="3" cy="3" r="3" fill="#FFD54F"/></svg>
      </div>
      <h1 class="home-h1">
        Keep their story alive.
        <span class="gold">beautifully remembered</span>
      </h1>
      <div class="home-divider"></div>
      <p class="home-sub">
        选择您要使用的功能模块，开始创建追思影像或开启数字人对话体验。
      </p>
    </div>
    """, unsafe_allow_html=True)

    _gap_l, _col1, _col2, _gap_r = st.columns([2.5, 2, 2, 2.5])
    with _col1:
        st.markdown("<div class='hbtn'>", unsafe_allow_html=True)
        if st.button(
            "念念影像制作\n\n采访 · 分析 · 生成追思影像",
            use_container_width=True,
            key="btn_memorial",
        ):
            st.session_state["main_section"] = "memorial"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with _col2:
        st.markdown("<div class='hbtn'>", unsafe_allow_html=True)
        if st.button(
            "数字人对话\n\n微信风格分析 · AI 角色扮演对话",
            use_container_width=True,
            key="btn_digital",
        ):
            st.switch_page("pages/wechat_import.py")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# main_section == "memorial" → 继续执行以下所有逻辑
# ──────────────────────────────────────────────────────────────────────────────

STYLE_OPTIONS = {
    "warm_nostalgia":        "温情追忆（暖色·怀旧）",
    "solemn_formal":         "庄重肃穆（正式·庄严）",
    "uplifting_celebration": "积极颂扬（生命礼赞）",
}
DURATION_OPTIONS = {
    "180": "3 分钟（简约版）",
    "300": "5 分钟（标准版）",
    "480": "8 分钟（完整版）",
}

_NIANNIAN_SYSTEM = (
    "你是「念念 AI」，一位温柔体贴的追思影像制作助手，帮助家属把对亲人的记忆整理成珍贵的追思影像。"
    "说话像温暖的长者朋友，用口语化自然流畅的中文，语气轻柔有耐心。"
    "每次回复 120-200 字，用自然段落，可用换行分段。"
    "第一次回复：先温暖开场感谢家属分享，然后自然总结已了解的信息（约 40 字，不要用字段名称），"
    "温柔指出 1-2 个可以补充的地方，用一句鼓励的话结尾。"
    "后续回复：先肯定补充的信息，信息充分时主动说可以开始制作了。"
    "绝对不要输出 JSON、技术参数、星号格式。"
)

_TEST_DATA = {
    "deceased_name": "陈文斌",
    "deceased_gender": "男",
    "birth_date": "1948年10月15日",
    "death_date": "2025年4月8日",
    "occupation": "退休工程师（原上海机床厂车间主任、某机械制造公司技术部经理）",
    "ceremony_date": "2025年4月15日",
    "ceremony_venue": "上海市黄浦区殡仪馆思源厅",
    "total_duration_sec": 300,
    "speaker_name": "陈明",
    "speaker_relation": "儿子",
    "speaker_style": "深情克制，儒雅温暖，感恩回望，不过度煽情",
    "style_preference": "warm_nostalgia",
    "family_memory_text": (
        "父亲是一个话不多但做什么都认真到底的人。青年时戴黑框眼镜，穿蓝色中山装，眼神里总有一种让人安心的笃定。"
        "退休后每天清晨和母亲去公园打太极拳，风雨无阻，说「动起来才有精气神」。"
        "他爱好书法多年，书法作品多次在社区展览中获奖；还坚持集邮，把每一枚邮票都仔细收进册子，说「小小方寸，装着大世界」。"
        "2020年起成为社区志愿者，帮邻里修电器、疏通水管、调解纠纷，从不推辞，说「退休了更要做点有用的事」。\n\n"
        "事迹一：1968年响应上山下乡号召赴安徽阜阳插队，十年知青岁月中学会种地、木工、电工，1978年高考恢复以优异成绩考上上海工业大学机械工程系，是全公社唯一考上大学的知青。\n"
        "事迹二：1990年担任上海机床厂车间主任，带领团队攻克多项技术难关，1985年起连续多年被评为厂级先进工作者，同事们都叫他「陈工」。\n"
        "事迹三：1975年在安徽阜阳与母亲李秀英举办简朴婚礼，只有几位知青朋友道贺，相伴五十年从未分离，2025年迎来金婚纪念，全家为二老补办了温馨庆典。\n"
        "事迹四：孙女陈雨桐高考前，父亲每天为她备好夜宵放在书桌旁，从不打扰，只在门缝里静静看一眼，说「孩子努力，我们陪着就够了」。"
    ),
    "last_wishes": "希望家人身体健康、和和睦睦，盼孙女陈雨桐学业顺遂。片中多放些他与秀英晨练、写书法的温馨画面，以及全家旅游时的合影。",
}

def _init():
    for k, v in {
        "phase": "form", "form_step": 1, "form_data": {},
        "intake_assets": [], "chat_history": [],
        "ai_thinking": False, "chat_ready": False,
        "cast_roles": [],   # [{id, name, role_label, description, photo_b64, photo_url}]
    }.items():
        st.session_state.setdefault(k, v)

_init()

def save(k, v): st.session_state["form_data"][k] = v
def get(k, d=""): return st.session_state["form_data"].get(k, d)

def render_topbar():
    phase = st.session_state["phase"]
    step = st.session_state["form_step"]
    active = 0 if (phase == "form" and step == 1) else 1 if (phase == "form" and step == 2) else 2
    # 返回主页按钮（右上角）
    _tb_l, _tb_r = st.columns([6, 1])
    with _tb_r:
        if st.button("返回主页", key="topbar_home_btn", help="返回功能选择主页"):
            st.session_state["main_section"] = "home"
            st.rerun()
    st.markdown(
        "<div class='nn-topbar'>"
        "<div class='nn-logo'><div class='nn-logo-orb'>念</div>"
        "<div><div class='nn-logo-name'>念念</div>"
        "<div class='nn-logo-sub'>NianNian Memorial Studio</div></div></div>"
        "<div class='nn-badge'>追思影像制作平台</div>"
        "</div>", unsafe_allow_html=True)
    steps = [("1","基本信息"),("2","回忆 &amp; 风格"),("*","念念 AI 对话")]
    html = "<div class='nn-steps-row'>"
    for i,(num,lbl) in enumerate(steps):
        cls = "active" if i==active else ("done" if i<active else "")
        if i>0: html += "<div class='nn-step-divider'></div>"
        html += f"<div class='nn-step-pill {cls}'><span class='nn-step-num'>{num}</span><span>{lbl}</span></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_step1():
    if not get("deceased_name"):
        st.markdown(
            "<div class='nn-hero nn-fade-up'>"
            "<div class='nn-hero-title'>让记忆<br/><em>永远留存</em></div>"
            "<div class='nn-hero-line'></div>"
            "<div class='nn-hero-sub'>我们会一步一步引导您，把对他/她/它最珍贵的记忆整理成一部专属追思影像。</div>"
            "</div>", unsafe_allow_html=True)
    # ── 测试快捷入口 ──────────────────────────────────────────
    with st.expander(" 测试模式：一键填入陈文斌示例数据", expanded=False):
        st.caption("仅供开发测试用，点击按钮后所有字段将自动填入示例数据。")
        if st.button("填入全部测试数据（陈文斌）", key="fill_test_all"):
            st.session_state["form_data"] = dict(_TEST_DATA)
            st.session_state["form_step"] = 2   # 直接跳到第二步（数据都填好了）
            st.rerun()
    # ─────────────────────────────────────────────────────────
    st.markdown(
        "<div class='nn-step-header'>"
        "<div class='nn-step-eyebrow'>Step 1 · 基本信息</div>"
        "<div class='nn-step-title'>请告诉我们关于他/她/它的基本信息</div>"
        "<div class='nn-step-desc'>请放心，您填写的所有内容都只用于制作这部影像。</div>"
        "</div>", unsafe_allow_html=True)
    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-label'>逝者信息</div>", unsafe_allow_html=True)
    c1,c2 = st.columns([3,2])
    with c1:
        name = st.text_input("逝者姓名 *", value=get("deceased_name"), placeholder="例如：张建国")
        if name: save("deceased_name", name)
    with c2:
        gopts = ["男","女","不便告知"]
        g = st.radio("性别", gopts, index=gopts.index(get("deceased_gender","男")), horizontal=True)
        save("deceased_gender", g)
    c3,c4 = st.columns(2)
    with c3:
        bd = st.text_input("出生日期", value=get("birth_date"), placeholder="例如：1945年3月8日")
        if bd: save("birth_date", bd)
    with c4:
        dd = st.text_input("逝世日期（选填）", value=get("death_date",""), placeholder="例如：2024年11月20日，在世可留空")
        if dd:
            save("death_date", dd)
        else:
            save("death_date", "")
    occ = st.text_input("职业 / 主要身份（可选）", value=get("occupation"), placeholder="例如：木工匠人、退休教师")
    if occ: save("occupation", occ)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-label'>追悼会安排（选填，在世时可暂时留空）</div>", unsafe_allow_html=True)
    c5,c6 = st.columns(2)
    with c5:
        cd = st.text_input("追悼会日期（选填）", value=get("ceremony_date",""), placeholder="例如：2024年11月25日")
        if cd: save("ceremony_date", cd)
        else: save("ceremony_date", "")
    with c6:
        venue = st.text_input("仪式场所（选填）", value=get("ceremony_venue",""), placeholder="例如：XX殡仪馆告别厅")
        if venue: save("ceremony_venue", venue)
        else: save("ceremony_venue", "")
    dur_vals = list(DURATION_OPTIONS.values())
    dur_cur = DURATION_OPTIONS.get(str(get("total_duration_sec","300")), dur_vals[1])
    dur_sel = st.selectbox("影片时长", dur_vals, index=dur_vals.index(dur_cur))
    save("total_duration_sec", int({v:k for k,v in DURATION_OPTIONS.items()}.get(dur_sel,"300")))
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='nn-hint-pill'><span class='nn-hint-dot'></span><span>影片通常在追悼会前 2-3 个工作日完成制作。</span></div>", unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _,col_r = st.columns([1,2])
    with col_r:
        if st.button("下一步", type="primary", use_container_width=True):
            if not get("deceased_name"): st.warning("请填写逝者姓名。")
            elif not get("ceremony_date"): st.warning("请填写追悼会日期。")
            else:
                st.session_state["form_step"] = 2
                st.rerun()

def render_step2():
    st.markdown(
        "<div class='nn-step-header'>"
        "<div class='nn-step-eyebrow'>Step 2 · 回忆 &amp; 风格</div>"
        "<div class='nn-step-title'>用您的文字，描述最难忘的记忆</div>"
        "<div class='nn-step-desc'>请用自己最自然的语言来写，不需要特别整理，AI 会帮您梳理。</div>"
        "</div>", unsafe_allow_html=True)
    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-label'>文字回忆 *</div>", unsafe_allow_html=True)
    mem = st.text_area("回忆叙述", value=get("family_memory_text",""), height=190,
        placeholder="请用自己的语言，描述您对他/她/它最难忘的事...\n\n例如：爷爷退休后每天清晨五点起床为全家煮小米粥，坚持了四十年。",
        label_visibility="collapsed")
    if mem: save("family_memory_text", mem)
    st.markdown("</div>", unsafe_allow_html=True)
    # ──  电影角色管理 ────────────────────────────────────────────────────────
    import uuid as _uuid_app
    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-label'> 电影角色</div>", unsafe_allow_html=True)
    st.caption("主角自动关联逝者，可继续添加出现在影片中的家属/重要人物作为配角")

    # ── 主角卡片（固定）────────────────────────────────────────────────────────
    _app_anc_b64  = st.session_state.get("ancestor_photo_b64")
    _app_dec_name = get("deceased_name") or "逝者"
    _mc1, _mc2, _mc3 = st.columns([1, 5, 2])
    with _mc1:
        if _app_anc_b64:
            st.image("data:image/jpeg;base64," + _app_anc_b64, width=56)
        else:
            st.markdown(
                "<div style='width:56px;height:56px;border-radius:8px;background:#F3F4F6;"
                "display:flex;align-items:center;justify-content:center;font-size:1.4rem;'></div>",
                unsafe_allow_html=True,
            )
    with _mc2:
        st.markdown(
            f"<div style='padding:4px 0;'>"
            f"<span style='font-size:.78rem;font-weight:700;color:#9C7A45;background:#FEF3C7;"
            f"padding:2px 8px;border-radius:999px;margin-right:6px;'>主角</span>"
            f"<span style='font-size:.88rem;font-weight:600;'>{_app_dec_name}</span><br>"
            f"<span style='font-size:.74rem;color:#6B7280;'>"
            + (" 参考照片已上传" if _app_anc_b64 else " 可在下方照片区上传逝者照片")
            + "</span></div>",
            unsafe_allow_html=True,
        )
    with _mc3:
        if _app_anc_b64:
            if st.button("移除照片", key="app_del_anc", use_container_width=True):
                st.session_state.pop("ancestor_photo_b64", None)
                st.session_state.pop("ancestor_photo_filename", None)
                st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── 配角列表 ──────────────────────────────────────────────────────────────
    _app_cast: list = st.session_state["cast_roles"]
    _app_del_id = None
    for _ci, _cr in enumerate(_app_cast):
        _cid = _cr["id"]
        _cc1, _cc2, _cc3 = st.columns([1, 5, 1])
        with _cc1:
            if _cr.get("photo_b64"):
                st.image("data:image/jpeg;base64," + _cr["photo_b64"], width=52)
            else:
                _cup = st.file_uploader("", type=["jpg","jpeg","png","webp"],
                                        key=f"app_cast_photo_{_cid}", label_visibility="collapsed")
                if _cup:
                    import base64 as _b64_app
                    _app_cast[_ci]["photo_b64"] = _b64_app.b64encode(_cup.read()).decode()
                    _app_cast[_ci].pop("photo_url", None)
                    st.session_state["cast_roles"] = _app_cast
                    st.rerun()
        with _cc2:
            _fn1, _fn2 = st.columns(2)
            with _fn1:
                _nn = st.text_input("角色名", value=_cr.get("name",""), key=f"app_cast_name_{_cid}",
                                    label_visibility="collapsed", placeholder="姓名（如：二丫）")
                _app_cast[_ci]["name"] = _nn
            with _fn2:
                _nrl = st.text_input("称谓/关系", value=_cr.get("role_label",""), key=f"app_cast_rl_{_cid}",
                                     label_visibility="collapsed", placeholder="称谓（如：女儿）")
                _app_cast[_ci]["role_label"] = _nrl
            _ndesc = st.text_input("外貌特征（可选）", value=_cr.get("description",""),
                                   key=f"app_cast_desc_{_cid}", label_visibility="collapsed",
                                   placeholder="外貌特征（如：约40岁，短发，温柔）")
            _app_cast[_ci]["description"] = _ndesc
        with _cc3:
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            if st.button("", key=f"app_cast_del_{_cid}", help="删除此角色"):
                _app_del_id = _cid
            if _cr.get("photo_b64"):
                if st.button("移除图", key=f"app_cast_rmphoto_{_cid}", use_container_width=True):
                    _app_cast[_ci]["photo_b64"] = None
                    _app_cast[_ci].pop("photo_url", None)
                    st.session_state["cast_roles"] = _app_cast
                    st.rerun()
        st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    if _app_del_id:
        st.session_state["cast_roles"] = [c for c in _app_cast if c["id"] != _app_del_id]
        st.rerun()

    if st.button("＋ 添加配角", key="app_cast_add"):
        st.session_state["cast_roles"].append({
            "id": str(_uuid_app.uuid4())[:8],
            "name": "", "role_label": "", "description": "", "photo_b64": None,
        })
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-label'>影像风格</div>", unsafe_allow_html=True)
    s_labels = list(STYLE_OPTIONS.values())
    s_cur = STYLE_OPTIONS.get(get("style_preference","warm_nostalgia"), s_labels[0])
    s_sel = st.radio("风格选择", s_labels, index=s_labels.index(s_cur), horizontal=True, label_visibility="collapsed")
    save("style_preference", {v:k for k,v in STYLE_OPTIONS.items()}.get(s_sel,"warm_nostalgia"))
    lw = st.text_area("遗愿 / 其他要补充的话（可选）", value=get("last_wishes",""), height=80, placeholder="例如：希望家人身体健康；片中不要太多哭泣的画面")
    if lw: save("last_wishes", lw)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-label'>照片上传（可选，后续也可以补充）</div>", unsafe_allow_html=True)

    # 参考人像提示
    if st.session_state.get("ancestor_photo_b64"):
        import base64 as _b64
        _thumb = st.session_state["ancestor_photo_b64"][:50]
        st.markdown(
            "<div style='display:flex;align-items:center;gap:10px;padding:10px 14px;"
            "background:#D1FAE5;border:1px solid #6EE7B7;border-radius:10px;margin-bottom:12px;'>"
            "<span style='font-size:1.1rem;'></span>"
            "<span style='font-size:.84rem;color:#065F46;font-weight:600;'>"
            "已识别逝者人像参考照片，分镜生成将锁定此形象</span></div>",
            unsafe_allow_html=True,
        )

    uploaded = st.file_uploader("上传文件", type=["png","jpg","jpeg","webp","mp3","wav","mp4","mov"],
        accept_multiple_files=True, key="step2_files", label_visibility="collapsed")
    if uploaded:
        existing = {a["filename"] for a in st.session_state["intake_assets"]}
        added = 0
        for f in uploaded:
            if f.name in existing: continue
            fb = f.getvalue()
            ext = Path(f.name).suffix.lower().lstrip(".")
            atp = "image" if ext in {"png","jpg","jpeg","webp"} else "audio" if ext in {"mp3","wav","m4a"} else "video"
            desc = ""
            if atp == "image":
                with st.spinner(f"识别 {f.name}..."):
                    try:
                        desc = describe_image(fb, f.name)
                        # 若描述含人像关键词且尚未设置参考照片，则自动设为角色参考图
                        _person_kws = ("人","脸","男","女","老","portrait","person","face","man","woman","elderly","grandfather","grandmother")
                        if not st.session_state.get("ancestor_photo_b64") and any(kw in desc.lower() for kw in _person_kws):
                            import base64 as _b64
                            st.session_state["ancestor_photo_b64"] = _b64.b64encode(fb).decode()
                            st.session_state["ancestor_photo_filename"] = f.name
                    except:
                        desc = f"照片：{f.name}"
            n = len(st.session_state["intake_assets"]) + 1
            st.session_state["intake_assets"].append({"asset_id":f"{atp}_{n:02d}","type":atp,"filename":f.name,"description":desc,"time_period":""})
            added += 1
        if added: st.success(f"已上传 {added} 个文件。")

    # ── 不同时期照片上传（可展开）────────────────────────────────────────────
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    with st.expander(" 上传不同时期的照片（婴儿 / 童年 / 少年 / 青年 / 中年 / 老年）", expanded=False):
        st.caption("为各人生阶段上传代表性照片，AI 将在分镜中更准确地呈现不同时期的样貌。")
        _PERIODS = [
            ("baby",    " 婴儿时期",  "0-3岁"),
            ("child",   " 童年时期",  "4-12岁"),
            ("teen",    " 少年时期",  "13-18岁"),
            ("young",   " 青年时期", "19-35岁"),
            ("middle",  " 中年时期", "36-60岁"),
            ("elder",   " 老年时期",  "60岁以上"),
        ]
        import base64 as _b64_period
        # 初始化时期照片存储
        st.session_state.setdefault("period_photos", {})

        _cols_per_row = 3
        for _row_start in range(0, len(_PERIODS), _cols_per_row):
            _row_items = _PERIODS[_row_start:_row_start + _cols_per_row]
            _pcols = st.columns(_cols_per_row)
            for _pi, (_pid, _plabel, _prange) in enumerate(_row_items):
                with _pcols[_pi]:
                    st.markdown(
                        f"<div style='font-size:.82rem;font-weight:700;color:var(--gold);"
                        f"margin-bottom:4px;'>{_plabel}</div>"
                        f"<div style='font-size:.72rem;color:var(--muted-l);margin-bottom:6px;'>{_prange}</div>",
                        unsafe_allow_html=True,
                    )
                    # 已上传则预览
                    if st.session_state["period_photos"].get(_pid):
                        _pdata = st.session_state["period_photos"][_pid]
                        st.image("data:image/jpeg;base64," + _pdata["b64"], use_container_width=True)
                        st.caption(_pdata.get("filename", ""))
                        if st.button("移除", key=f"rm_period_{_pid}", use_container_width=True):
                            st.session_state["period_photos"].pop(_pid, None)
                            st.rerun()
                    else:
                        _pup = st.file_uploader(
                            f"上传{_plabel}",
                            type=["png","jpg","jpeg","webp"],
                            key=f"period_up_{_pid}",
                            label_visibility="collapsed",
                        )
                        if _pup:
                            _pb = _pup.getvalue()
                            _pb64 = _b64_period.b64encode(_pb).decode()
                            st.session_state["period_photos"][_pid] = {
                                "b64": _pb64,
                                "filename": _pup.name,
                            }
                            # 老年时期照片自动设为主参考图（如果还没有的话）
                            if _pid == "elder" and not st.session_state.get("ancestor_photo_b64"):
                                st.session_state["ancestor_photo_b64"] = _pb64
                                st.session_state["ancestor_photo_filename"] = _pup.name
                            # 将时期照片也加入素材列表
                            _period_label_map = dict((_p, _l) for _p, _l, _ in _PERIODS)
                            _n_asset = len(st.session_state["intake_assets"]) + 1
                            st.session_state["intake_assets"].append({
                                "asset_id": f"image_{_n_asset:02d}",
                                "type": "image",
                                "filename": _pup.name,
                                "description": f"{_period_label_map.get(_pid, _pid)}照片",
                                "time_period": _pid,
                            })
                            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_back,col_next = st.columns(2)
    with col_back:
        if st.button("上一步", use_container_width=True):
            st.session_state["form_step"] = 1
            st.rerun()
    with col_next:
        if st.button("唤起念念 AI", type="primary", use_container_width=True):
            if not get("family_memory_text"): st.warning("请填写一段文字回忆，哪怕一两句也好。")
            else:
                st.session_state["phase"] = "chat"
                st.session_state["ai_thinking"] = True
                st.session_state["chat_ready"] = False
                st.rerun()

def _form_to_text():
    d = st.session_state["form_data"]
    a = st.session_state.get("intake_assets",[])
    lines = [
        "{}：{}，{}，生于 {}，{}职业：{}。".format(
            "在世长辈" if not d.get("death_date") else "逝者",
            d.get("deceased_name","未知"),d.get("deceased_gender",""),
            d.get("birth_date","?"),
            ("逝于 {}，".format(d["death_date"])) if d.get("death_date") else "目前在世，",
            d.get("occupation","未知")),
        "追悼会：{}，地点：{}，影片时长 {} 分钟。".format(
            d.get("ceremony_date","?"),d.get("ceremony_venue","未知"),
            int(d.get("total_duration_sec",300))//60),
        "主要致辞人：{}（{}），致辞风格：{}。".format(
            d.get("speaker_name","未知"),d.get("speaker_relation","?"),d.get("speaker_style","未说明")),
        "影像风格：{}。".format(d.get("style_preference","warm_nostalgia")),
        "家属回忆：{}".format(d.get("family_memory_text","")),
    ]
    if d.get("last_wishes"): lines.append("遗愿：{}".format(d["last_wishes"]))
    if a: lines.append("已上传素材：" + "；".join((x.get("description") or x.get("filename","")) for x in a[:5]))
    return "\n".join(lines)

def _history_to_openai():
    return [{"role":"assistant" if m["role"]=="ai" else "user","content":m["content"]}
            for m in st.session_state["chat_history"]]

_GEN_SYS = (
    "你是追思影像项目信息整理助手。根据表单数据和对话内容，整理出标准 JSON，"
    "包含：deceased_info（name/gender/birth_date/death_date/occupation）、"
    "ceremony_info（date/venue/duration_sec）、relatives（list）、"
    "family_memory_text、style_preference、emotional_intensity、last_wishes、assets（list）。"
    "只输出合法 JSON，不要任何解释。"
)

def _gen_json_silently():
    d = st.session_state["form_data"]
    a = st.session_state.get("intake_assets",[])
    chat = "\n".join("{}：{}".format("念念AI" if m["role"]=="ai" else "家属", m["content"])
                     for m in st.session_state["chat_history"])
    payload = {"form_data":d,"assets":[{"asset_id":x.get("asset_id",""),"type":x.get("type",""),
        "description":x.get("description",""),"time_period":x.get("time_period","")} for x in a],
        "chat_conversation":chat}
    result = call_structured(_GEN_SYS, json.dumps(payload, ensure_ascii=False))
    if not result.get("error"):
        pipeline_runner.save_output("MV01", result)
        jstr = json.dumps(result, ensure_ascii=False, indent=2)
        st.session_state["mv01_intake_json"] = jstr
        st.session_state["mv01_text_input"] = jstr
    return result

_THINK_HTML = (
    "<div class='nn-think-row' style='margin-bottom:20px;'>"
    "<div class='nn-think-avatar-wrap'>"
    "<div class='nn-think-orb'></div>"
    "<div class='nn-think-ring'></div>"
    "<div class='nn-think-ring nn-think-ring-2'></div>"
    "</div>"
    "<div class='nn-think-bubble'>"
    "<div class='nn-think-dots'><span></span><span></span><span></span></div>"
    "<div class='nn-think-label'>念念正在思考...</div>"
    "</div></div>"
)

def _bubble(role, content):
    if role == "ai":
        return ("<div class='nn-chat-ai'><div class='nn-ai-avatar'>念</div>"
                "<div class='nn-ai-bubble-wrap'><div class='nn-ai-name'>念念 AI</div>"
                "<div class='nn-ai-bubble'>{}</div></div></div>").format(content)
    return "<div class='nn-chat-user'><div class='nn-user-bubble'>{}</div></div>".format(content)

def render_chat():
    st.markdown(
        "<div class='nn-step-header nn-fade-up'>"
        "<div class='nn-step-eyebrow'>Step 3 · 念念 AI 对话</div>"
        "<div class='nn-step-title'>我来帮您整理记忆</div>"
        "<div class='nn-step-desc'>您可以在下方补充任何信息，按 Enter 发送。觉得可以了，就点击下方开始制作按钮。</div>"
        "</div>", unsafe_allow_html=True)
    history = st.session_state["chat_history"]
    if history:
        html = "<div class='nn-chat-wrap'>"
        for m in history: html += _bubble(m["role"], m["content"])
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
    think_ph = st.empty()
    if st.session_state["ai_thinking"] and not st.session_state["chat_ready"]:
        think_ph.markdown(_THINK_HTML, unsafe_allow_html=True)
        st.session_state["chat_ready"] = True
        openai_msgs = _history_to_openai()
        if not openai_msgs:
            summary = _form_to_text()
            openai_msgs = [{"role":"user","content":"以下是家属填写的信息，请你温柔自然地和我聊聊：\n\n" + summary}]
        reply = call_memorial_chat(_NIANNIAN_SYSTEM, openai_msgs)
        st.session_state["chat_history"].append({"role":"ai","content":reply})
        st.session_state["ai_thinking"] = False
        st.session_state["chat_ready"] = False
        st.rerun()
        return
    if len(history) >= 1:
        st.markdown(
            "<div class='nn-confirm-strip'><div class='nn-confirm-dot'></div>"
            "<span style='font-size:.9rem;color:var(--ink-m);'>信息确认后，念念 AI 会在后台自动整理并进入影像制作台。</span>"
            "</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        col_go,col_back = st.columns([3,1])
        with col_go:
            if st.button("好了，开始制作", type="primary", use_container_width=True):
                with st.spinner("念念正在整理所有信息，请稍候..."):
                    _gen_json_silently()
                st.session_state["phase"] = "preview"
                st.session_state["preview_ready"] = False
                st.rerun()
        with col_back:
            if st.button("返回修改", use_container_width=True):
                st.session_state["phase"] = "form"
                st.session_state["form_step"] = 2
                st.session_state["ai_thinking"] = False
                st.rerun()
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    user_msg = st.chat_input("您可以继续补充或修改任何信息...按 Enter 发送", key="chat_input_main")
    if user_msg and user_msg.strip():
        st.session_state["chat_history"].append({"role":"user","content":user_msg.strip()})
        st.session_state["ai_thinking"] = True
        st.session_state["chat_ready"] = False
        st.rerun()

# ── 分镜预览阶段：AI 用大白话讲解影片流程 ─────────────────────────────────────
_PREVIEW_SYS = (
    "你是一位亲切的追思影像讲解员，帮助老人家和家属提前了解即将制作的影片内容。"
    "请根据下面提供的逝者信息，用最通俗的大白话（就像面对面和家里老人讲话一样），"
    "把这部追思影像的大致流程讲清楚：先是什么，然后是什么，最后是什么。"
    "语气温柔、耐心，像邻居奶奶聊天一样自然。"
    "格式要求：\n"
    "- 用【先是……】【然后……】【最后……】三段结构，每段2-4句话\n"
    "- 不要用专业词汇，不要说'分镜'、'AI生成'、'模型'这类词\n"
    "- 每段开头加上序号表情：①②③\n"
    "- 总长度控制在150-220字"
)

def render_preview():
    st.markdown(
        "<div class='nn-step-header nn-fade-up'>"
        "<div class='nn-step-eyebrow'>影片预告 · 开始前先听念念说几句</div>"
        "<div class='nn-step-title'>这部影片会是这个样子的……</div>"
        "<div class='nn-step-desc'>念念用大白话帮您讲讲，影片从头到尾大概是怎么走的，您觉得合适，咱们就开始。</div>"
        "</div>", unsafe_allow_html=True)

    # 生成预览文本（只生成一次）
    if not st.session_state.get("preview_text"):
        think_ph = st.empty()
        think_ph.markdown(_THINK_HTML, unsafe_allow_html=True)
        intake_json = st.session_state.get("mv01_intake_json", "")
        if not intake_json:
            intake_json = _form_to_text()
        prompt = f"以下是逝者和家属的信息：\n\n{intake_json}\n\n请用大白话帮家属讲讲这部影片的流程。"
        preview_text = call_memorial_chat(_PREVIEW_SYS, [{"role": "user", "content": prompt}])
        st.session_state["preview_text"] = preview_text
        think_ph.empty()
        st.rerun()

    preview_text = st.session_state.get("preview_text", "")
    if preview_text:
        # 将三段分行显示成卡片
        paragraphs = [p.strip() for p in preview_text.split("\n") if p.strip()]
        cards_html = "<div style='display:flex;flex-direction:column;gap:16px;max-width:720px;margin:0 auto 32px;'>"
        for p in paragraphs:
            cards_html += (
                f"<div style='background:rgba(255,250,240,0.9);border-left:4px solid #C9A96E;"
                f"border-radius:10px;padding:18px 22px;font-size:1.05rem;line-height:1.8;"
                f"color:#3a2e20;box-shadow:0 2px 12px rgba(0,0,0,.06);'>{p}</div>"
            )
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    col_confirm, col_back = st.columns([3, 1])
    with col_confirm:
        if st.button("好的，就按这个来！开始制作 →", type="primary", use_container_width=True):
            st.success("好的！正在进入制作台，请稍候……")
            st.switch_page("pages/pipeline.py")
    with col_back:
        if st.button("返回修改", use_container_width=True):
            st.session_state["phase"] = "chat"
            st.session_state["preview_text"] = ""
            st.rerun()

render_topbar()
_ph = st.session_state["phase"]
_step = st.session_state["form_step"]
if _ph == "form":
    if _step == 1: render_step1()
    else: render_step2()
elif _ph == "preview":
    render_preview()
else:
    render_chat()