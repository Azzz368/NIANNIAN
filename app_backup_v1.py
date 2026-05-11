"""
念念追思影像 · 信息采集主页 (Page 1)
面向 30-60 岁家属用户，采用 LegacyRemembered 暖色象牙风格
完成采集后跳转制作流水线 pages/pipeline.py (Page 2)
"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st

import pipeline_runner
from llm_client import call_structured, describe_image, transcribe_audio

# ── 页面配置 ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="念念 · 追思影像",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 全局 CSS & JS（暖色象牙风格产品站）────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,600&family=Inter:wght@300;400;500;600;700&family=Noto+Serif+SC:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

/* ───────── Design Tokens ───────── */
:root {
  --bg:         #F8F5F0;
  --bg2:        #F2EDE5;
  --surf:       #FFFFFF;
  --surf2:      #FAF7F2;
  --surf3:      #F0EBE2;
  --border:     rgba(180,155,115,.18);
  --border-h:   rgba(160,120,70,.35);
  --gold:       #9C7A45;
  --gold-l:     #B8934F;
  --gold-dim:   rgba(156,122,69,.08);
  --gold-glow:  rgba(156,122,69,.14);
  --ink:        #1E1A14;
  --ink-m:      #4A4035;
  --muted:      #B0A494;
  --muted-l:    #8A7B6A;
  --green:      #5A9A72;
  --red:        #C0604A;
  --blue:       #5A7EA8;
}

/* ───────── Reset & Base ───────── */
html, body, [class*="css"] {
  font-family: 'Inter', 'Noto Sans SC', sans-serif !important;
  color: var(--ink) !important;
  background: var(--bg) !important;
}
.stApp { background: var(--bg) !important; }
#MainMenu, footer, header { display: none !important; }
[data-testid="stSidebarNav"], section[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.block-container {
  max-width: 860px !important;
  padding: 0 24px 80px !important;
  margin: 0 auto !important;
}

/* ───────── Scrollbar ───────── */
::-webkit-scrollbar { width: 5px; background: var(--bg2); }
::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 99px; }

/* ───────── Typography Scale ───────── */
.t-display {
  font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
  font-size: clamp(2.6rem, 6vw, 4.2rem);
  font-weight: 600; line-height: 1.12; letter-spacing: -.02em;
  color: var(--ink) !important;
}
.t-display em { font-style: italic; color: var(--gold-l) !important; }
.t-headline {
  font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
  font-size: clamp(1.5rem, 3.5vw, 2rem);
  font-weight: 600; line-height: 1.2; letter-spacing: -.01em;
  color: var(--ink) !important;
}
.t-title {
  font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
  font-size: 1.25rem; font-weight: 600; letter-spacing: -.005em;
  color: var(--ink) !important;
}
.t-body    { font-size: .9375rem; font-weight: 400; line-height: 1.65; color: var(--ink-m) !important; }
.t-caption { font-size: .8125rem; font-weight: 400; color: var(--muted-l) !important; line-height: 1.5; }
.t-label   { font-size: .75rem;   font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--gold) !important; }

/* ───────── Step Transition Animations ───────── */
@keyframes nn-enter-right {
  from { opacity: 0; transform: translateX(36px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes nn-enter-left {
  from { opacity: 0; transform: translateX(-36px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes nn-enter-up {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes nn-fade-in {
  from { opacity: 0; } to { opacity: 1; }
}
@keyframes nn-pulse-dot {
  0%, 100% { box-shadow: 0 0 0 0 var(--gold-glow); }
  50%       { box-shadow: 0 0 0 6px transparent; }
}

.nn-step-content {
  animation: nn-enter-right .5s cubic-bezier(.25,.46,.45,.94) both;
}
.nn-step-content.dir-back {
  animation: nn-enter-left .5s cubic-bezier(.25,.46,.45,.94) both;
}

/* ───────── Top Bar ───────── */
.nn-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 28px 0 32px;
  animation: nn-fade-in .6s ease both;
}
.nn-logo {
  display: flex; align-items: center; gap: 12px;
}
.nn-logo-mark {
  width: 40px; height: 40px; border-radius: 14px;
  background: linear-gradient(135deg, var(--surf3), var(--surf2));
  border: 1px solid var(--border-h);
  display: flex; align-items: center; justify-content: center;
}
.nn-logo-mark-inner {
  width: 18px; height: 18px; border-radius: 50%;
  background: linear-gradient(135deg, var(--gold), var(--gold-l));
  opacity: .85;
}
.nn-logo-text-main {
  font-family: 'Cormorant Garamond', serif;
  font-size: 1.25rem; font-weight: 600; color: var(--ink);
  letter-spacing: .02em;
}
.nn-logo-text-sub {
  font-size: .7rem; color: var(--muted-l); letter-spacing: .06em;
  text-transform: uppercase; margin-top: 1px;
}
.nn-topbar-badge {
  font-size: .72rem; font-weight: 600; letter-spacing: .06em;
  color: var(--gold); background: var(--gold-dim);
  border: 1px solid var(--border-h); border-radius: 999px;
  padding: 5px 14px;
}

/* ───────── Step Indicator (Horizontal) ───────── */
.nn-stepper {
  display: flex; align-items: center; gap: 0;
  margin-bottom: 44px;
  background: var(--surf); border: 1px solid var(--border);
  border-radius: 999px; padding: 6px;
  box-shadow: 0 1px 6px rgba(0,0,0,.04);
  animation: nn-fade-in .5s .1s ease both;
}
.nn-stepper-item {
  flex: 1; display: flex; align-items: center; justify-content: center;
  gap: 8px; padding: 9px 16px; border-radius: 999px;
  cursor: default; transition: background .25s ease;
}
.nn-stepper-item.active {
  background: var(--surf3);
  box-shadow: 0 2px 10px rgba(0,0,0,.06);
}
.nn-stepper-dot {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700;
  background: var(--surf2); border: 1px solid var(--border);
  color: var(--muted-l);
  transition: all .25s ease;
}
.nn-stepper-item.active .nn-stepper-dot {
  background: var(--gold); border-color: var(--gold);
  color: #fff; animation: nn-pulse-dot 2s ease infinite;
}
.nn-stepper-item.done .nn-stepper-dot {
  background: transparent; border-color: var(--gold);
  color: var(--gold);
}
.nn-stepper-label {
  font-size: .75rem; font-weight: 500; color: var(--muted-l);
  white-space: nowrap;
  display: none;
}
.nn-stepper-item.active .nn-stepper-label { color: var(--ink); display: block; }
.nn-stepper-item.done .nn-stepper-label   { display: none; }
.nn-stepper-divider {
  width: 20px; height: 1px; background: var(--border); flex-shrink: 0;
}

/* ───────── Progress Bar ───────── */
.nn-progress-track {
  height: 2px; background: var(--surf3); border-radius: 2px;
  margin-bottom: 10px; overflow: hidden;
}
.nn-progress-fill {
  height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, var(--gold), var(--gold-l));
  transition: width .6s cubic-bezier(.4,0,.2,1);
}
.nn-progress-label {
  font-size: .72rem; color: var(--muted-l); margin-bottom: 40px;
  display: flex; justify-content: space-between; align-items: center;
}

/* ───────── Step Header ───────── */
.nn-step-header {
  margin-bottom: 36px;
}
.nn-step-eyebrow {
  font-size: .72rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--gold);
  margin-bottom: 14px; display: flex; align-items: center; gap: 8px;
}
.nn-step-eyebrow::before {
  content: ''; display: block; width: 24px; height: 1px;
  background: var(--gold); opacity: .5;
}
.nn-step-desc {
  font-size: .9375rem; color: var(--muted-l); line-height: 1.65;
  margin-top: 10px; max-width: 520px;
}

/* ───────── Cards ───────── */
.nn-card {
  background: var(--surf); border: 1px solid var(--border);
  border-radius: 20px; padding: 32px 36px; margin-bottom: 20px;
  box-shadow: 0 2px 16px rgba(0,0,0,.04);
  transition: border-color .2s ease, box-shadow .2s ease;
}
.nn-card:hover { border-color: var(--border-h); box-shadow: 0 4px 24px rgba(0,0,0,.07); }
.nn-card-sm {
  background: var(--surf2); border: 1px solid var(--border);
  border-radius: 14px; padding: 16px 20px; margin-bottom: 10px;
}
.nn-card-highlight {
  background: linear-gradient(135deg, var(--surf2), var(--surf));
  border: 1px solid var(--border-h); border-radius: 20px;
  padding: 32px 36px; margin-bottom: 20px;
  position: relative; overflow: hidden;
  box-shadow: 0 2px 16px rgba(0,0,0,.04);
}
.nn-card-highlight::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}

/* ───────── Form Fields (override Streamlit) ───────── */
label, .stTextInput label, .stTextArea label, .stSelectbox label,
.stNumberInput label, .stRadio label, .stCheckbox label {
  font-size: .78rem !important; font-weight: 600 !important;
  letter-spacing: .05em !important; text-transform: uppercase !important;
  color: var(--muted-l) !important; margin-bottom: 6px !important;
}
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea,
.stNumberInput > div > div > input {
  background: var(--surf) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  color: var(--ink) !important;
  font-size: .9375rem !important;
  padding: 12px 16px !important;
  transition: border-color .2s ease, box-shadow .2s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-color: var(--border-h) !important;
  box-shadow: 0 0 0 3px var(--gold-dim) !important;
  outline: none !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea  > div > div > textarea::placeholder {
  color: var(--muted) !important;
}
.stSelectbox > div > div {
  background: var(--surf) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  color: var(--ink) !important;
}
.stSelectbox > div > div > div { color: var(--ink) !important; }
[data-baseweb="select"] > div { background: var(--surf) !important; border-color: var(--border) !important; }
[data-baseweb="popover"] { background: var(--surf) !important; border: 1px solid var(--border) !important; }
[data-baseweb="menu"] li { background: var(--surf) !important; color: var(--ink) !important; }
[data-baseweb="menu"] li:hover { background: var(--surf2) !important; }

/* Radio & Checkbox */
.stRadio > div { gap: 10px !important; flex-wrap: wrap !important; }
.stRadio > div > label {
  background: var(--surf2) !important; border: 1px solid var(--border) !important;
  border-radius: 999px !important; padding: 8px 18px !important;
  font-size: .875rem !important; font-weight: 500 !important;
  text-transform: none !important; letter-spacing: 0 !important;
  color: var(--ink-m) !important; cursor: pointer !important;
  transition: all .2s ease !important;
}
.stRadio > div > label:has(input:checked) {
  background: var(--gold-dim) !important; border-color: var(--border-h) !important;
  color: var(--gold) !important;
}
.stCheckbox > label {
  font-size: .875rem !important; font-weight: 400 !important;
  text-transform: none !important; letter-spacing: 0 !important;
  color: var(--ink-m) !important;
}
[data-testid="stCheckbox"] input { accent-color: var(--gold) !important; }

/* File Uploader */
[data-testid="stFileUploader"] > div {
  background: var(--surf2) !important;
  border: 1.5px dashed var(--border-h) !important;
  border-radius: 16px !important;
}
[data-testid="stFileUploader"] span { color: var(--ink-m) !important; }

/* Expander */
div[data-testid="stExpander"] {
  background: var(--surf) !important; border: 1px solid var(--border) !important;
  border-radius: 14px !important;
}
div[data-testid="stExpander"] summary { color: var(--ink-m) !important; }
div[data-testid="stExpander"] summary svg { fill: var(--muted-l) !important; }

/* Divider */
hr { border-color: var(--border) !important; margin: 28px 0 !important; }

/* ───────── Buttons ───────── */
div.stButton > button {
  border-radius: 999px !important;
  font-family: 'Inter', 'Noto Sans SC', sans-serif !important;
  font-size: .875rem !important; font-weight: 600 !important;
  padding: 12px 28px !important; letter-spacing: .02em !important;
  transition: all .22s cubic-bezier(.4,0,.2,1) !important;
  border: 1px solid var(--border) !important;
  background: var(--surf2) !important; color: var(--ink-m) !important;
}
div.stButton > button:hover {
  border-color: var(--border-h) !important; color: var(--ink) !important;
  background: var(--surf3) !important;
}
div.stButton > button[kind="primary"] {
  background: var(--gold) !important;
  border-color: var(--gold) !important; color: #fff !important;
  box-shadow: 0 4px 20px var(--gold-glow) !important;
}
div.stButton > button[kind="primary"]:hover {
  background: var(--gold-l) !important; border-color: var(--gold-l) !important;
  box-shadow: 0 6px 28px rgba(156,122,69,.28) !important;
  transform: translateY(-1px) !important;
}

/* ───────── Pill / Info Blocks ───────── */
.nn-pill {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 14px 18px; border-radius: 14px;
  border: 1px solid var(--border); background: var(--surf2);
  margin-bottom: 12px; font-size: .875rem; color: var(--ink-m); line-height: 1.55;
}
.nn-pill-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 7px;
  background: var(--gold); box-shadow: 0 0 0 3px var(--gold-dim);
}
.nn-section-title {
  font-size: .72rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--gold);
  margin: 28px 0 14px; padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.nn-hint {
  color: var(--muted-l); font-size: .8125rem; line-height: 1.5; margin-top: 6px;
}

/* ───────── Hero Block ───────── */
.nn-hero {
  padding: 60px 0 52px; text-align: center;
  animation: nn-enter-up .7s cubic-bezier(.25,.46,.45,.94) both;
}
.nn-hero-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 18px; border-radius: 999px;
  background: var(--gold-dim); border: 1px solid var(--border-h);
  font-size: .75rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--gold);
  margin-bottom: 28px;
}
.nn-hero-title {
  font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
  font-size: clamp(2.8rem, 7vw, 4.5rem); font-weight: 500;
  line-height: 1.1; letter-spacing: -.025em;
  color: var(--ink) !important; margin-bottom: 22px;
}
.nn-hero-title em { font-style: italic; color: var(--gold-l) !important; }
.nn-hero-sub {
  font-size: 1.0625rem; color: var(--muted-l); line-height: 1.7;
  max-width: 480px; margin: 0 auto 40px;
}
.nn-hero-divider {
  width: 64px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
  margin: 0 auto 40px;
}

/* ───────── Summary Cards ───────── */
.nn-summary-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
  margin-bottom: 24px;
}
.nn-summary-card {
  background: var(--surf2); border: 1px solid var(--border);
  border-radius: 16px; padding: 20px 22px;
  transition: border-color .2s ease;
}
.nn-summary-card:hover { border-color: var(--border-h); }
.nn-summary-kv { font-size: .72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--gold); margin-bottom: 8px; }
.nn-summary-val { font-family: 'Cormorant Garamond', serif; font-size: 1.4rem; font-weight: 500; color: var(--ink); }
.nn-summary-sub { font-size: .8125rem; color: var(--muted-l); margin-top: 4px; }

/* ───────── Nav Buttons Row ───────── */
.nn-nav-row { display: flex; gap: 12px; margin-top: 36px; }
.nn-nav-row .stButton { flex: 1; }

/* ───────── JSON Preview ───────── */
.nn-json-preview {
  background: var(--surf2); border: 1px solid var(--border);
  border-radius: 14px; padding: 20px;
  font-family: 'Courier New', monospace; font-size: .78rem;
  white-space: pre-wrap; max-height: 340px; overflow-y: auto;
  color: var(--ink-m); line-height: 1.55;
}

/* ───────── Alert Overrides ───────── */
[data-testid="stAlert"] {
  background: var(--surf2) !important; border-radius: 12px !important;
  border: 1px solid var(--border) !important; color: var(--ink-m) !important;
}

/* ───────── Step Transition (JS-triggered) ───────── */
.nn-fade-out { animation: nn-fade-out .25s ease forwards !important; }
@keyframes nn-fade-out {
  to { opacity: 0; transform: translateX(-24px); }
}
</style>
"""

_JS = """
<script>
(function(){
  function attachTransitionHandlers() {
    const btns = document.querySelectorAll('div.stButton > button');
    btns.forEach(btn => {
      if (btn.dataset.nnHooked) return;
      btn.dataset.nnHooked = '1';
      btn.addEventListener('click', function(e) {
        const label = btn.innerText || '';
        if (label.includes('下一步') || label.includes('上一步') ||
            label.includes('完成采集') || label.includes('进入制作台') ||
            label.includes('确认添加')) {
          const content = document.querySelector('.nn-step-content');
          if (content) {
            content.style.transition = 'opacity .22s ease, transform .22s ease';
            content.style.opacity = '0';
            content.style.transform = label.includes('上一步') ? 'translateX(24px)' : 'translateX(-24px)';
          }
        }
      });
    });
  }
  const mo = new MutationObserver(attachTransitionHandlers);
  mo.observe(document.body, { childList: true, subtree: true });
  attachTransitionHandlers();
})();
</script>
"""

st.markdown(_CSS, unsafe_allow_html=True)
st.markdown(_JS, unsafe_allow_html=True)

# ── 常量 ─────────────────────────────────────────────────────────────────────
INTAKE_STEPS = [
    {"id": 1, "title": "逝者信息",  "desc": "姓名、生卒日期与生平摘要"},
    {"id": 2, "title": "仪式安排",  "desc": "追悼会时间、地点与影片时长"},
    {"id": 3, "title": "家属信息",  "desc": "亲属关系与主要致辞人"},
    {"id": 4, "title": "素材上传",  "desc": "照片、录音、视频素材"},
    {"id": 5, "title": "风格偏好",  "desc": "文字回忆与影片风格"},
]

STYLE_OPTIONS: Dict[str, str] = {
    "warm_nostalgia":        "温情追忆（暖色、怀旧）",
    "solemn_formal":         "庄重肃穆（正式、庄严）",
    "uplifting_celebration": "积极颂扬（生命礼赞）",
    "gentle_melancholic":    "温柔哀思（静谧、深情）",
}
INTENSITY_OPTIONS: Dict[str, str] = {
    "gentle":   "轻柔舒缓",
    "moderate": "适中平和",
    "intense":  "深情浓烈",
}
CEREMONY_OPTIONS: Dict[str, str] = {
    "family_memorial":  "家庭追悼会",
    "unit_memorial":    "单位公祭",
    "church_funeral":   "教堂葬礼",
    "outdoor_ceremony": "户外告别仪式",
    "simple_farewell":  "简单告别",
}
DURATION_OPTIONS: Dict[str, str] = {
    "180": "3 分钟（简约版）",
    "300": "5 分钟（标准版）",
    "480": "8 分钟（完整版）",
    "600": "10 分钟（豪华版）",
}

# ── Session State 初始化 ──────────────────────────────────────────────────────
st.session_state.setdefault("intake_step",      1)
st.session_state.setdefault("intake_prev_step", 1)
st.session_state.setdefault("intake_data",      {})
st.session_state.setdefault("intake_assets",    [])


# ── 辅助函数 ──────────────────────────────────────────────────────────────────
def go_to(step: int) -> None:
    st.session_state["intake_prev_step"] = st.session_state["intake_step"]
    st.session_state["intake_step"] = step
    st.rerun()


def save_field(key: str, value: Any) -> None:
    st.session_state["intake_data"][key] = value


def get_field(key: str, default: Any = "") -> Any:
    return st.session_state["intake_data"].get(key, default)


def step_done(step_id: int) -> bool:
    d = st.session_state["intake_data"]
    checks: Dict[int, bool] = {
        1: bool(d.get("deceased_name")),
        2: bool(d.get("ceremony_date")),
        3: bool(d.get("relatives")),
        4: True,
        5: bool(d.get("family_memory_text") or d.get("style_preference")),
    }
    return checks.get(step_id, False)


def extract_audio_from_video(video_bytes: bytes, suffix: str) -> Tuple[bytes, str]:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            vp = Path(tmp) / f"input{suffix}"
            ap = Path(tmp) / "audio.wav"
            vp.write_bytes(video_bytes)
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", str(vp), "-vn", "-ac", "1", "-ar", "16000", str(ap)],
                capture_output=True, text=True, check=False,
            )
            if r.returncode != 0 or not ap.exists():
                return b"", r.stderr.strip() or "ffmpeg 解析失败"
            return ap.read_bytes(), ""
    except FileNotFoundError:
        return b"", "未检测到 ffmpeg"
    except Exception as exc:
        return b"", str(exc)


def build_intake_prompt() -> str:
    return (
        "你是追悼会/生命回顾视频项目的信息整理助手。"
        "请根据用户输入的结构化表单数据和素材清单，整理出 MV01 所需的标准 JSON。"
        "必须输出完整 JSON，字段包含："
        "family_memory_text, uploaded_assets（含 asset_id/type/description/time_period）, "
        "style_preference, emotional_intensity, ceremony_type, "
        "ceremony_date（YYYY-MM-DD）, total_duration_sec（数字）, "
        "relatives（含 relation/name/is_main_speaker/speech_preference）, last_wishes。"
        "不要编造不存在的信息。"
    )


# ── 顶栏 & 步骤指示器 ─────────────────────────────────────────────────────────
def render_topbar() -> None:
    done_count = sum(1 for s in INTAKE_STEPS if step_done(s["id"]))
    pct = int(done_count / len(INTAKE_STEPS) * 100)
    current = st.session_state["intake_step"]

    # Logo bar
    st.markdown(
        "<div class='nn-topbar'>"
        "<div class='nn-logo'>"
        "<div class='nn-logo-mark'><div class='nn-logo-mark-inner'></div></div>"
        "<div>"
        "<div class='nn-logo-text-main'>念念</div>"
        "<div class='nn-logo-text-sub'>NianNian Memorial Studio</div>"
        "</div></div>"
        "<div class='nn-topbar-badge'>追思影像制作平台</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Step indicator
    items_html = ""
    for i, s in enumerate(INTAKE_STEPS):
        cls       = "active" if s["id"] == current else ("done" if step_done(s["id"]) else "")
        num_label = "·" if (step_done(s["id"]) and s["id"] != current) else str(s["id"])
        if i > 0:
            items_html += "<div class='nn-stepper-divider'></div>"
        items_html += (
            f"<div class='nn-stepper-item {cls}'>"
            f"<span class='nn-stepper-dot'>{num_label}</span>"
            f"<span class='nn-stepper-label'>{s['title']}</span>"
            "</div>"
        )
    st.markdown(f"<div class='nn-stepper'>{items_html}</div>", unsafe_allow_html=True)

    # Progress
    st.markdown(
        f"<div class='nn-progress-track'>"
        f"<div class='nn-progress-fill' style='width:{pct}%'></div></div>"
        f"<div class='nn-progress-label'>"
        f"<span>已完成 {done_count} / {len(INTAKE_STEPS)} 步</span>"
        f"<span style='color:var(--gold)'>{pct}%</span></div>",
        unsafe_allow_html=True,
    )


# ── 通用组件 ──────────────────────────────────────────────────────────────────
def render_step_header(step_id: int, title: str, subtitle: str) -> None:
    direction_cls = "dir-back" if st.session_state.get("intake_prev_step", 1) > step_id else ""
    st.markdown(
        f"<div class='nn-step-content {direction_cls}'>"
        f"<div class='nn-step-header'>"
        f"<div class='nn-step-eyebrow'>Step {step_id} · {INTAKE_STEPS[step_id-1]['title']}</div>"
        f"<div class='t-headline'>{title}</div>"
        f"<div class='nn-step-desc'>{subtitle}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def close_step_content() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_nav_buttons(step_id: int) -> None:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    cols = st.columns([1, 3, 1])
    with cols[0]:
        if step_id > 1:
            if st.button("上一步", use_container_width=True):
                go_to(step_id - 1)
    with cols[2]:
        label = "下一步" if step_id < len(INTAKE_STEPS) else "完成采集"
        if st.button(label, type="primary", use_container_width=True):
            go_to(step_id + 1 if step_id < len(INTAKE_STEPS) else 6)


# ════════════════════════════════════════════════════════════════════════
# Step 1 · 逝者基本信息
# ════════════════════════════════════════════════════════════════════════
def render_step1() -> None:
    render_step_header(1, "逝者基本信息",
        "请填写逝者的姓名、生卒年月和简要生平——您的每一段记忆都将成为这部影像的灵魂。")

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("逝者姓名 *", value=get_field("deceased_name"), placeholder="例如：张建国")
        if name: save_field("deceased_name", name)
    with c2:
        g_opts = ["男", "女", "不便告知"]
        gender = st.radio("性别", g_opts,
            index=g_opts.index(get_field("deceased_gender", "男")), horizontal=True)
        save_field("deceased_gender", gender)

    c3, c4 = st.columns(2)
    with c3:
        birth = st.text_input("出生日期", value=get_field("birth_date"), placeholder="例如：1948年5月12日")
        if birth: save_field("birth_date", birth)
    with c4:
        death = st.text_input("逝世日期", value=get_field("death_date"), placeholder="例如：2023年10月25日")
        if death: save_field("death_date", death)

    c5, c6 = st.columns(2)
    with c5:
        bp = st.text_input("出生地 / 籍贯", value=get_field("birthplace"), placeholder="例如：山东省济南市")
        if bp: save_field("birthplace", bp)
    with c6:
        occ = st.text_input("职业 / 主要身份", value=get_field("occupation"), placeholder="例如：退休教师")
        if occ: save_field("occupation", occ)

    bio = st.text_area("生平简述（可选）", value=get_field("bio_summary"), height=120,
        placeholder="请简单描述逝者的人生经历、重要时刻，让您最记挂的事情……")
    if bio: save_field("bio_summary", bio)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-title'>荣誉与遗愿</div>", unsafe_allow_html=True)
    military = st.checkbox("曾服兵役 / 有军旅经历", value=get_field("has_military_service", False))
    save_field("has_military_service", military)
    if military:
        md = st.text_input("军旅详情（可选）", value=get_field("military_detail", ""),
            placeholder="例如：1970年入伍，服役10年")
        if md: save_field("military_detail", md)

    awards = st.text_input("荣誉奖励（可选）", value=get_field("awards", ""),
        placeholder="例如：1985年被评为单位先进工作者")
    if awards: save_field("awards", awards)

    lw = st.text_area("遗愿（可选）", value=get_field("last_wishes", ""), height=80,
        placeholder="例如：希望家人身体健康，孙女能考上好大学…")
    if lw: save_field("last_wishes", lw)
    st.markdown("</div>", unsafe_allow_html=True)

    close_step_content()
    render_nav_buttons(1)


# ════════════════════════════════════════════════════════════════════════
# Step 2 · 仪式安排
# ════════════════════════════════════════════════════════════════════════
def render_step2() -> None:
    render_step_header(2, "仪式安排",
        "请告诉我们追悼会的时间与地点，以便我们为影像制定合适的节奏与篇幅。")

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        cd = st.text_input("追悼会日期 *", value=get_field("ceremony_date", ""),
            placeholder="例如：2023年10月29日 或 2023-10-29")
        if cd: save_field("ceremony_date", cd)
    with c2:
        ct = st.text_input("追悼会时间", value=get_field("ceremony_time", ""),
            placeholder="例如：上午 10:00")
        if ct: save_field("ceremony_time", ct)

    c3, c4 = st.columns(2)
    with c3:
        venue = st.text_input("仪式场所", value=get_field("ceremony_venue", ""),
            placeholder="例如：XX 殡仪馆 告别厅")
        if venue: save_field("ceremony_venue", venue)
    with c4:
        ct_vals = list(CEREMONY_OPTIONS.values())
        ct_cur  = CEREMONY_OPTIONS.get(get_field("ceremony_type", "family_memorial"), ct_vals[0])
        ct_sel  = st.selectbox("仪式类型", ct_vals, index=ct_vals.index(ct_cur))
        save_field("ceremony_type",
            {v: k for k, v in CEREMONY_OPTIONS.items()}.get(ct_sel, "family_memorial"))

    dur_vals = list(DURATION_OPTIONS.values())
    dur_cur  = DURATION_OPTIONS.get(str(get_field("total_duration_sec", "300")), dur_vals[1])
    dur_sel  = st.selectbox("影片总时长", dur_vals, index=dur_vals.index(dur_cur))
    save_field("total_duration_sec",
        int({v: k for k, v in DURATION_OPTIONS.items()}.get(dur_sel, "300")))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='nn-pill'><span class='nn-pill-dot'></span>"
        "<span>影片将在追悼会前完成制作，通常需要 2–3 个工作日。</span></div>",
        unsafe_allow_html=True,
    )

    close_step_content()
    render_nav_buttons(2)


# ════════════════════════════════════════════════════════════════════════
# Step 3 · 家属信息
# ════════════════════════════════════════════════════════════════════════
def render_step3() -> None:
    render_step_header(3, "家属信息",
        "添加主要家属成员，以便我们在影像中正确表达亲情关系，并确认主要致辞人。")

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    relatives: List[Dict[str, Any]] = list(get_field("relatives", []))

    with st.expander("添加家属成员", expanded=not bool(relatives)):
        r1, r2 = st.columns(2)
        with r1:
            new_name = st.text_input("姓名", key="new_rel_name", placeholder="例如：张敏")
        with r2:
            new_rel = st.text_input("与逝者关系", key="new_rel_rel",
                placeholder="例如：女儿 / 儿子 / 配偶 / 孙女")
        r3, r4 = st.columns(2)
        with r3:
            new_spk = st.checkbox("是主要致辞人", key="new_rel_spk")
        with r4:
            new_pref = st.text_input("致辞风格偏好（可选）", key="new_rel_pref",
                placeholder="例如：温和真诚")
        if st.button("确认添加", key="add_rel", type="primary"):
            if new_name and new_rel:
                relatives.append({
                    "name": new_name, "relation": new_rel,
                    "is_main_speaker": new_spk,
                    "speech_preference": new_pref or "gentle_and_sincere",
                })
                save_field("relatives", relatives)
                st.success(f"已添加：{new_rel} · {new_name}")
                st.rerun()
            else:
                st.warning("请至少填写姓名和关系。")

    if relatives:
        st.markdown("<div class='nn-section-title'>已添加家属</div>", unsafe_allow_html=True)
        for i, rel in enumerate(relatives):
            col_info, col_del = st.columns([5, 1])
            with col_info:
                spk_tag = "  主要致辞人" if rel.get("is_main_speaker") else ""
                st.markdown(
                    f"<div class='nn-card-sm'>"
                    f"<div style='font-weight:600;color:var(--cream);'>"
                    f"{rel.get('relation','')} · {rel.get('name','')}"
                    f"<span style='color:var(--gold);font-size:.78rem;margin-left:10px;'>{spk_tag}</span></div>"
                    f"<div class='t-caption' style='margin-top:4px;'>致辞风格：{rel.get('speech_preference','')}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("删除", key=f"del_rel_{i}"):
                    relatives.pop(i)
                    save_field("relatives", relatives)
                    st.rerun()
    else:
        st.markdown(
            "<div class='nn-pill'><span class='nn-pill-dot'></span>"
            "<span>尚未添加家属成员，请点击上方表单添加至少一位。</span></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    close_step_content()
    render_nav_buttons(3)


# ════════════════════════════════════════════════════════════════════════
# Step 4 · 素材上传
# ════════════════════════════════════════════════════════════════════════
def render_step4() -> None:
    render_step_header(4, "素材上传",
        "上传逝者的照片、录音或视频——系统会自动识别内容，帮助生成更生动的影像描述。")

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "选择文件（支持 JPG / PNG / MP3 / WAV / MP4，可多选）",
        type=["png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "mp4", "mov", "mkv"],
        accept_multiple_files=True,
        key="intake_files",
    )
    st.markdown("<div class='nn-hint'>上传的素材仅用于本次影像制作，不对外分享。</div>", unsafe_allow_html=True)

    if uploaded_files:
        if st.button("自动识别素材内容", type="primary"):
            assets: List[Dict[str, Any]] = []
            for idx, file in enumerate(uploaded_files, 1):
                fb    = file.getvalue()
                ext   = Path(file.name).suffix.lower().lstrip(".")
                atype = (
                    "image" if ext in {"png", "jpg", "jpeg", "webp"}
                    else "audio" if ext in {"mp3", "wav", "m4a"}
                    else "video"
                )
                info: Dict[str, Any] = {
                    "asset_id": f"{atype}_{idx:02d}",
                    "type": atype, "filename": file.name, "description": "",
                }
                if atype == "image":
                    with st.spinner(f"识别图片 {file.name}…"):
                        try:
                            info["description"] = describe_image(fb, file.name)
                        except Exception:
                            info["description"] = f"照片：{file.name}"
                elif atype == "audio":
                    with st.spinner(f"转写音频 {file.name}…"):
                        try:
                            info["transcript"]  = transcribe_audio(fb, file.name)
                            info["description"] = f"音频：{file.name}"
                        except Exception:
                            info["description"] = f"音频：{file.name}"
                else:
                    ab, err = extract_audio_from_video(fb, f".{ext}")
                    if ab:
                        with st.spinner(f"转写视频音轨 {file.name}…"):
                            try:
                                info["transcript"] = transcribe_audio(ab, f"{file.name}.wav")
                            except Exception:
                                pass
                    info["description"] = f"视频：{file.name}"
                    if err:
                        info["warning"] = err
                assets.append(info)
            st.session_state["intake_assets"] = assets
            save_field("uploaded_assets_raw", assets)
            st.success(f"已识别 {len(assets)} 个素材！请检查和补充下方描述。")

    assets_state: List[Dict[str, Any]] = st.session_state.get("intake_assets", [])
    if assets_state:
        st.markdown("<div class='nn-section-title'>已上传素材</div>", unsafe_allow_html=True)
        for i, asset in enumerate(assets_state):
            with st.expander(f"{asset['asset_id']} · {asset['filename']}", expanded=False):
                c_l, c_r = st.columns([2, 3])
                with c_l:
                    icons = {"image": "图片", "audio": "音频", "video": "视频"}
                    st.markdown(f"<span class='t-caption'>类型：{icons.get(asset['type'],'')} {asset['type']}</span>",
                        unsafe_allow_html=True)
                with c_r:
                    desc   = st.text_input("内容描述（可修改）", value=asset.get("description",""), key=f"ad_{i}")
                    period = st.text_input("时间段（可选）", value=asset.get("time_period",""), key=f"ap_{i}",
                        placeholder="例如：2015 或 1980年代")
                    assets_state[i]["description"] = desc
                    assets_state[i]["time_period"] = period
                if asset.get("transcript"):
                    st.caption(f"转写：{asset['transcript'][:200]}…")
                if asset.get("warning"):
                    st.warning(asset["warning"])
        st.session_state["intake_assets"] = assets_state
        save_field("uploaded_assets_raw", assets_state)

    notes = st.text_area("素材补充说明（可选）", value=get_field("asset_notes", ""), height=100,
        placeholder="例如：photo_01 是全家福，audio_01 是生日讲话录音…")
    if notes: save_field("asset_notes", notes)
    st.markdown("</div>", unsafe_allow_html=True)

    close_step_content()
    render_nav_buttons(4)


# ════════════════════════════════════════════════════════════════════════
# Step 5 · 回忆与风格
# ════════════════════════════════════════════════════════════════════════
def render_step5() -> None:
    render_step_header(5, "回忆与风格偏好",
        "用自己的文字描述对逝者最深的记忆，并告诉我们您希望影像呈现的情感氛围。")

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    mem = st.text_area(
        "文字回忆叙述 *",
        value=get_field("family_memory_text", ""),
        height=200,
        placeholder=(
            "请用自己的语言，描述您对亲人最难忘的记忆……\n\n"
            "例如：爷爷退休后每天清晨五点起床为全家煮小米粥，坚持了四十年……"
        ),
    )
    if mem: save_field("family_memory_text", mem)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='nn-card'>", unsafe_allow_html=True)
    st.markdown("<div class='nn-section-title'>影像风格</div>", unsafe_allow_html=True)
    s_labels = list(STYLE_OPTIONS.values())
    s_cur    = STYLE_OPTIONS.get(get_field("style_preference", "warm_nostalgia"), s_labels[0])
    s_sel    = st.radio("请选择最符合心意的风格", s_labels, index=s_labels.index(s_cur), horizontal=True)
    save_field("style_preference",
        {v: k for k, v in STYLE_OPTIONS.items()}.get(s_sel, "warm_nostalgia"))

    st.markdown("<div class='nn-section-title'>情感强度</div>", unsafe_allow_html=True)
    i_labels = list(INTENSITY_OPTIONS.values())
    i_cur    = INTENSITY_OPTIONS.get(get_field("emotional_intensity", "moderate"), i_labels[1])
    i_sel    = st.radio("影像的情感浓度", i_labels, index=i_labels.index(i_cur), horizontal=True)
    save_field("emotional_intensity",
        {v: k for k, v in INTENSITY_OPTIONS.items()}.get(i_sel, "moderate"))

    st.markdown("<div class='nn-section-title'>其他需求（可选）</div>", unsafe_allow_html=True)
    sp = st.text_area("特殊要求或注意事项", value=get_field("special_requirements", ""), height=80,
        placeholder="例如：希望片头有一段沉默、不要使用过于悲伤的背景音乐…")
    if sp: save_field("special_requirements", sp)
    st.markdown("</div>", unsafe_allow_html=True)

    close_step_content()
    render_nav_buttons(5)


# ════════════════════════════════════════════════════════════════════════
# Step 6 · 预览 & 生成 MV01 JSON
# ════════════════════════════════════════════════════════════════════════
def _generate_mv01_json() -> None:
    d   = st.session_state["intake_data"]
    raw = st.session_state.get("intake_assets", [])
    cleaned: List[Dict[str, Any]] = []
    for a in raw:
        ca: Dict[str, Any] = {
            "asset_id":    a.get("asset_id", ""),
            "type":        a.get("type", ""),
            "description": a.get("description", ""),
            "time_period": a.get("time_period", "unknown"),
        }
        if a.get("transcript"):
            ca["transcript"] = a["transcript"][:500]
        cleaned.append(ca)

    payload: Dict[str, Any] = {
        "deceased_info": {
            "name":            d.get("deceased_name", ""),
            "gender":          d.get("deceased_gender", ""),
            "birth_date":      d.get("birth_date", ""),
            "death_date":      d.get("death_date", ""),
            "birthplace":      d.get("birthplace", ""),
            "occupation":      d.get("occupation", ""),
            "bio_summary":     d.get("bio_summary", ""),
            "military":        d.get("has_military_service", False),
            "military_detail": d.get("military_detail", ""),
            "awards":          d.get("awards", ""),
        },
        "ceremony_info": {
            "date":         d.get("ceremony_date", ""),
            "time":         d.get("ceremony_time", ""),
            "venue":        d.get("ceremony_venue", ""),
            "type":         d.get("ceremony_type", "family_memorial"),
            "duration_sec": d.get("total_duration_sec", 300),
        },
        "relatives":            d.get("relatives", []),
        "family_memory_text":   d.get("family_memory_text", ""),
        "style_preference":     d.get("style_preference", "warm_nostalgia"),
        "emotional_intensity":  d.get("emotional_intensity", "moderate"),
        "last_wishes":          d.get("last_wishes", ""),
        "special_requirements": d.get("special_requirements", ""),
        "assets":               cleaned,
        "asset_notes":          d.get("asset_notes", ""),
    }

    with st.spinner("AI 正在整理信息，请稍候…"):
        result = call_structured(
            build_intake_prompt(),
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    if result.get("error"):
        st.error(f"整理失败：{result.get('message', '未知错误')}")
        return

    jstr = json.dumps(result, ensure_ascii=False, indent=2)
    st.session_state["mv01_intake_json"] = jstr
    st.session_state["mv01_text_input"]  = jstr
    pipeline_runner.save_output("MV01_intake", result)
    st.success("MV01 JSON 已生成！请预览确认，然后进入制作台。")
    st.rerun()


def render_preview() -> None:
    d   = st.session_state["intake_data"]
    raw = st.session_state.get("intake_assets", [])

    direction_cls = "dir-back" if st.session_state.get("intake_prev_step", 5) > 6 else ""
    st.markdown(
        f"<div class='nn-step-content {direction_cls}'>"
        "<div class='nn-hero'>"
        "<div class='nn-hero-eyebrow'>· 信息采集完成 ·</div>"
        "<div class='nn-hero-title'>准备好了吗？<br/><em>让我们开始制作</em></div>"
        "<div class='nn-hero-divider'></div>"
        "<div class='nn-hero-sub'>所有信息已收集完毕。点击下方按钮，AI 将把您的记忆整理成标准化数据，"
        "然后进入追思影像制作台。</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Summary cards
    dur = d.get("total_duration_sec", 300)
    st.markdown(
        f"<div class='nn-summary-grid'>"
        f"<div class='nn-summary-card'>"
        f"<div class='nn-summary-kv'>逝者</div>"
        f"<div class='nn-summary-val'>{d.get('deceased_name', '—')}</div>"
        f"<div class='nn-summary-sub'>{d.get('birth_date','...')} — {d.get('death_date','...')}</div>"
        f"</div>"
        f"<div class='nn-summary-card'>"
        f"<div class='nn-summary-kv'>仪式日期</div>"
        f"<div class='nn-summary-val' style='font-size:1.1rem'>{d.get('ceremony_date','—')}</div>"
        f"<div class='nn-summary-sub'>{d.get('ceremony_venue','')}</div>"
        f"</div>"
        f"<div class='nn-summary-card'>"
        f"<div class='nn-summary-kv'>影片时长</div>"
        f"<div class='nn-summary-val'>{dur // 60} 分钟</div>"
        f"<div class='nn-summary-sub'>{STYLE_OPTIONS.get(d.get('style_preference',''),'')}</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    relatives = d.get("relatives", [])
    if relatives:
        rel_text = "　".join([f"{r.get('relation','')} {r.get('name','')}" for r in relatives])
        spk      = next((r["name"] for r in relatives if r.get("is_main_speaker")), "")
        st.markdown(
            f"<div class='nn-pill'><span class='nn-pill-dot'></span>"
            f"<span><b>家属：</b>{rel_text}"
            + (f"　主要致辞人：{spk}" if spk else "")
            + "</span></div>",
            unsafe_allow_html=True,
        )
    if raw:
        imgs = sum(1 for a in raw if a["type"] == "image")
        auds = sum(1 for a in raw if a["type"] == "audio")
        vids = sum(1 for a in raw if a["type"] == "video")
        st.markdown(
            f"<div class='nn-pill'><span class='nn-pill-dot'></span>"
            f"<span><b>素材：</b>已上传 {len(raw)} 个"
            f"（图片 {imgs}　音频 {auds}　视频 {vids}）</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_gen, col_back = st.columns(2)
    with col_gen:
        if st.button("AI 整理成 MV01 JSON", type="primary", use_container_width=True):
            _generate_mv01_json()
    with col_back:
        if st.button("返回修改", use_container_width=True):
            go_to(5)

    if "mv01_intake_json" in st.session_state:
        st.markdown("<div class='nn-section-title'>MV01 输入 JSON（预览）</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='nn-json-preview'>{st.session_state['mv01_intake_json']}</div>",
            unsafe_allow_html=True,
        )

    # ── 进入制作台 ── 可随时跳转，无需等待 AI 整理完成
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='border-top:1px solid var(--border);padding-top:28px;text-align:center;'>"
        "<div class='t-caption' style='color:var(--muted);margin-bottom:12px;letter-spacing:.06em;'>"
        "准备好了吗？可以随时进入制作台预览流程，不必等待 AI 整理完成</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "准备好了，让我们开始制作",
        type="primary",
        use_container_width=True,
        key="goto_pipeline_btn",
    ):
        # 如果已有 JSON 则传递，否则直接跳转（制作台支持手动输入）
        st.switch_page("pages/pipeline.py")

    st.markdown("</div>", unsafe_allow_html=True)


# ── 主入口 ────────────────────────────────────────────────────────────────────
render_topbar()

_step = st.session_state["intake_step"]

if _step == 1:
    st.markdown(
        "<div class='nn-hero'>"
        "<div class='nn-hero-eyebrow'>NianNian Memorial Studio</div>"
        "<div class='nn-hero-title'>让他们的故事<br/><em>永远存留，被美好铭记</em></div>"
        "<div class='nn-hero-divider'></div>"
        "<div class='nn-hero-sub'>一个温柔的空间，用于收集记忆、整理素材，"
        "并由 AI 生成专属的追思影像。全程约 10 分钟，我们会一步步引导您完成。</div>"
        "</div>",
        unsafe_allow_html=True,
    )

if   _step == 1: render_step1()
elif _step == 2: render_step2()
elif _step == 3: render_step3()
elif _step == 4: render_step4()
elif _step == 5: render_step5()
else:            render_preview()
