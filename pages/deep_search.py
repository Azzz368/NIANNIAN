# pages/deep_search.py — 念念 Deep Search Agent
# 全程使用 302.ai 统一网关（AI302_API_KEY）
# 搜索阶段：perplexity/sonar-pro（联网检索）→ 自动降级 claude-sonnet-4-6 / gpt-5.4
# 整理/提取阶段：claude-sonnet-4-6 / gpt-5.4
# 无需任何额外 API Key

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

import streamlit as st

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from llm_client import PRIMARY_CLIENT, TEXT_MODEL, TEXT_FALLBACK_MODEL

# 302.ai 上支持联网的搜索模型（按优先级）
_SEARCH_MODELS: List[str] = [
    "perplexity/sonar-pro",
    "perplexity/sonar",
    "gpt-4o-search-preview",
]

st.set_page_config(
    page_title="念念 · 深度搜索",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────── 样式 ────────────────────────────────────────────
_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
:root{
  --bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;
  --border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);
  --gold:#9C7A45;--gold-l:#B8934F;--gold-dim:rgba(156,122,69,.08);
  --ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;
}
html,body,[class*="css"]{font-family:"Noto Sans SC",sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
section[data-testid="stSidebar"],[data-testid="stSidebarNav"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:800px!important;padding:0 20px 100px!important;margin:0 auto!important;}

.ds-topbar{display:flex;align-items:center;justify-content:space-between;padding:22px 0 18px;border-bottom:1px solid var(--border);margin-bottom:26px;}
.ds-logo{display:flex;align-items:center;gap:12px;}
.ds-orb{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#B8934F);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;font-family:"Cormorant Garamond",serif;}
.ds-title{font-family:"Cormorant Garamond",serif;font-size:1.25rem;font-weight:600;color:var(--ink);}
.ds-sub{font-size:.7rem;color:var(--muted-l);letter-spacing:.05em;}
.ds-badge{font-size:.72rem;font-weight:600;letter-spacing:.05em;color:var(--gold);background:var(--gold-dim);border:1px solid var(--border-h);border-radius:999px;padding:5px 14px;}

.ds-search-box{background:var(--surf);border:1px solid var(--border);border-radius:20px;padding:26px 30px;margin-bottom:22px;box-shadow:0 2px 16px rgba(0,0,0,.04);}
.ds-section-label{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--border);}
.ds-hint{font-size:.8rem;color:var(--muted-l);line-height:1.65;margin-top:10px;}

.ds-chat-wrap{display:flex;flex-direction:column;gap:18px;margin-bottom:24px;}
.ds-chat-ai{display:flex;align-items:flex-start;gap:12px;}
.ds-ai-avatar{width:40px;height:40px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#C4964A 0%,#E8C57A 50%,#9C7A45 100%);display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700;font-family:"Cormorant Garamond",serif;}
.ds-ai-bubble-wrap{display:flex;flex-direction:column;gap:4px;flex:1;}
.ds-ai-name{font-size:.68rem;font-weight:700;color:var(--gold);letter-spacing:.05em;}
.ds-ai-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 18px 18px 18px;padding:14px 18px;font-size:.95rem;line-height:1.85;color:var(--ink);box-shadow:0 2px 10px rgba(0,0,0,.04);white-space:pre-wrap;}
.ds-user-bubble{display:flex;justify-content:flex-end;}
.ds-user-bubble-inner{background:var(--gold);color:#fff;border-radius:18px 4px 18px 18px;padding:12px 18px;max-width:72%;font-size:.95rem;line-height:1.7;}

@keyframes dot-bounce{0%,80%,100%{transform:translateY(0);opacity:.35;}40%{transform:translateY(-7px);opacity:1;}}
@keyframes orb-pulse{0%,100%{transform:scale(1);}50%{transform:scale(1.08);}}
@keyframes ring-out{0%{transform:scale(1);opacity:.6;}100%{transform:scale(2.2);opacity:0;}}
@keyframes grad-shift{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.ds-think-row{display:flex;align-items:flex-start;gap:12px;margin-bottom:6px;}
.ds-think-wrap{position:relative;width:40px;height:40px;flex-shrink:0;}
.ds-think-orb{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#C4964A,#F0D590,#9C7A45,#DCA855);background-size:300% 300%;animation:orb-pulse 2s ease-in-out infinite,grad-shift 4s ease infinite;}
.ds-think-ring{position:absolute;inset:0;border-radius:50%;border:1.5px solid rgba(184,147,79,.55);animation:ring-out 2s ease-out infinite;}
.ds-think-ring-2{animation-delay:1s;}
.ds-think-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 18px 18px 18px;padding:14px 20px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 10px rgba(0,0,0,.04);}
.ds-think-dots{display:flex;gap:5px;align-items:center;}
.ds-think-dots span{width:7px;height:7px;border-radius:50%;background:var(--gold);display:block;}
.ds-think-dots span:nth-child(1){animation:dot-bounce 1.4s 0s ease infinite;}
.ds-think-dots span:nth-child(2){animation:dot-bounce 1.4s .22s ease infinite;}
.ds-think-dots span:nth-child(3){animation:dot-bounce 1.4s .44s ease infinite;}
.ds-think-label{font-size:.86rem;color:var(--muted-l);font-style:italic;}

.ds-result-card{background:var(--surf);border:1px solid var(--border);border-radius:16px;padding:20px 26px;margin-bottom:14px;box-shadow:0 2px 12px rgba(0,0,0,.04);}
.ds-result-title{font-family:"Cormorant Garamond",serif;font-size:1.05rem;font-weight:600;color:var(--ink);margin-bottom:12px;}
.ds-result-row{display:flex;gap:8px;margin-bottom:7px;align-items:flex-start;}
.ds-result-label{font-size:.72rem;font-weight:700;color:var(--gold);background:var(--gold-dim);border-radius:4px;padding:2px 7px;flex-shrink:0;margin-top:2px;white-space:nowrap;}
.ds-result-val{font-size:.9rem;color:var(--ink-m);line-height:1.65;}

div.stButton>button{border-radius:999px!important;font-size:.9rem!important;font-weight:600!important;padding:10px 24px!important;transition:all .2s!important;border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;}
label,.stTextInput label,.stTextArea label{font-size:.78rem!important;font-weight:600!important;letter-spacing:.04em!important;text-transform:uppercase!important;color:var(--muted-l)!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{background:var(--surf)!important;border:1px solid var(--border)!important;border-radius:12px!important;color:var(--ink)!important;font-size:1rem!important;padding:12px 16px!important;}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{border-color:var(--border-h)!important;box-shadow:0 0 0 3px var(--gold-dim)!important;outline:none!important;}
[data-testid="stAlert"]{background:var(--surf2)!important;border-radius:10px!important;border:1px solid var(--border)!important;}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

_THINK_HTML = (
    "<div class='ds-think-row'>"
    "<div class='ds-think-wrap'>"
    "<div class='ds-think-orb'></div>"
    "<div class='ds-think-ring'></div>"
    "<div class='ds-think-ring ds-think-ring-2'></div>"
    "</div>"
    "<div class='ds-think-bubble'>"
    "<div class='ds-think-dots'><span></span><span></span><span></span></div>"
    "<div class='ds-think-label'>{label}</div>"
    "</div></div>"
)

# ─────────────────────────── Session 初始化 ───────────────────────────────────
for _k, _v in {
    "ds_chat": [],
    "ds_searching": False,
    "ds_result": None,
    "ds_query": "",
    "ds_extra_context": "",
    "_ds_show_followup": False,
    "_ds_used_model": "",
}.items():
    st.session_state.setdefault(_k, _v)

# ─────────────────────────── LLM 核心调用 ────────────────────────────────────
_SEARCH_SYSTEM = """你是念念追思影像制作助手，具备联网实时搜索能力。

用户想了解某位人物的生平资料，以便制作追思影像。请联网搜索后，用温暖自然的中文整理以下内容：

### 一、基本信息
- 全名、生卒年月（如有）、主要职业/身份、籍贯或主要活动地域

### 二、人生经历亮点
按时间顺序列出 3-6 个重要人生节点、事件或成就。

### 三、性格与精神遗产
性格特点、价值观、主要贡献或对他人的影响（100字以内）。

### 四、适合追思影像的素材线索
从资料中提炼 2-4 个最具画面感的场景、故事或情感记忆点。

若该人物无公开网络资料，请如实告知，建议用户手动填写家庭回忆。
输出语气温暖，像在讲述一位值得被记住的人，不要使用"根据搜索结果"等机械表述。"""

_FILL_SYSTEM = """你是念念追思影像助手。根据整理好的人物资料，提取以下字段，严格输出 JSON，不加任何解释：
{
  "deceased_name": "姓名（仅人名）",
  "deceased_gender": "男 或 女 或 不便告知",
  "birth_date": "出生日期，格式 XXXX年X月X日，不确定留空",
  "death_date": "逝世日期，格式 XXXX年X月X日，在世或不确定留空",
  "occupation": "主要职业或身份，简短",
  "family_memory_text": "改写为家属视角的温暖回忆叙述，200-350字"
}
信息不足的字段填空字符串。"""


def _call_302_search(query: str, extra: str = "") -> tuple:
    """
    调用 302.ai 联网搜索模型整理人物信息。
    优先级：perplexity/sonar-pro → perplexity/sonar → gpt-4o-search-preview
    全部不可用时降级为 TEXT_MODEL（知识库模式，加注说明）。
    返回 (整理文本, 使用的模型名)
    """
    user_msg = f"请帮我搜索并整理：{query}"
    if extra.strip():
        user_msg += f"\n\n补充背景：{extra.strip()}"

    # ── 优先：联网搜索模型 ──────────────────────────────────────────────────
    for model in _SEARCH_MODELS:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SEARCH_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=1400,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content, model
        except Exception:
            continue

    # ── 降级：知识库模式（无联网，加注提示）──────────────────────────────────
    _kb_prefix = (
        "【提示：联网搜索模型暂时不可用，以下内容来自 AI 知识库，"
        "可能存在知识截止日期限制，建议核实后再填写。】\n\n"
    )
    _kb_system = _SEARCH_SYSTEM.replace(
        "具备联网实时搜索能力。",
        "请根据已有知识回答（知识截止日期有限制，请告知用户核实）。",
    )
    for model in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _kb_system},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.5,
                max_tokens=1200,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return _kb_prefix + content, f"{model}（知识库模式）"
        except Exception:
            continue

    return "抱歉，AI 服务暂时不可用，请稍后重试。", "（失败）"


def _extract_fields(organized: str, query: str) -> Dict:
    """从整理文本提取可填表单的字段"""
    for model in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _FILL_SYSTEM},
                    {"role": "user",   "content": f"搜索词：{query}\n\n整理资料：\n{organized}"},
                ],
                temperature=0.2,
                max_tokens=700,
            )
            raw = resp.choices[0].message.content or "{}"
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                return json.loads(m.group())
        except Exception:
            continue
    return {}


# ─────────────────────────── 气泡渲染 ────────────────────────────────────────
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _bubble_ai(content: str) -> str:
    return (
        "<div class='ds-chat-ai'>"
        "<div class='ds-ai-avatar'>念</div>"
        "<div class='ds-ai-bubble-wrap'>"
        "<div class='ds-ai-name'>念念 AI · 深度搜索</div>"
        f"<div class='ds-ai-bubble'>{_esc(content)}</div>"
        "</div></div>"
    )

def _bubble_user(content: str) -> str:
    return (
        "<div class='ds-user-bubble'>"
        f"<div class='ds-user-bubble-inner'>{_esc(content)}</div>"
        "</div>"
    )

# ─────────────────────────── 顶栏 ────────────────────────────────────────────
st.markdown(
    "<div class='ds-topbar'>"
    "<div class='ds-logo'>"
    "<div class='ds-orb'>念</div>"
    "<div><div class='ds-title'>念念 · 深度搜索</div>"
    "<div class='ds-sub'>Deep Search Agent · Powered by 302.ai</div></div>"
    "</div>"
    "<div class='ds-badge'>联网搜索 · AI 整理</div>"
    "</div>",
    unsafe_allow_html=True,
)

_c1, _c2, _ = st.columns([1.3, 1, 5])
with _c1:
    if st.button("返回信息填写", use_container_width=True):
        st.switch_page("app.py")
with _c2:
    if st.button("清空对话", use_container_width=True):
        for _k in ["ds_chat", "ds_result", "_ds_show_followup", "_ds_used_model"]:
            st.session_state[_k] = [] if _k == "ds_chat" else None if _k == "ds_result" else False if _k == "_ds_show_followup" else ""
        st.session_state["ds_query"] = ""
        st.rerun()

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ─────────────────────────── 搜索输入区 ──────────────────────────────────────
st.markdown("<div class='ds-search-box'>", unsafe_allow_html=True)
st.markdown("<div class='ds-section-label'>搜索人物</div>", unsafe_allow_html=True)

_cq, _cbtn = st.columns([5, 1])
with _cq:
    _query_input = st.text_input(
        "搜索关键词",
        value=st.session_state["ds_query"],
        placeholder="输入姓名，如：钱学森  /  李小龙  /  陈文斌 上海工程师",
        label_visibility="collapsed",
        key="ds_query_input",
    )
with _cbtn:
    _search_btn = st.button("开始搜索", type="primary", use_container_width=True, key="ds_search_btn")

_extra = st.text_area(
    "补充背景信息（选填，提高准确度）",
    value=st.session_state["ds_extra_context"],
    placeholder="如：1948年生，上海人，国营机床厂工程师；或「我父亲，普通人，无网络公开资料」",
    height=70,
    key="ds_extra_input",
)
st.session_state["ds_extra_context"] = _extra

st.markdown(
    "<div class='ds-hint'>"
    "通过 302.ai 调用 <strong>Perplexity Sonar Pro</strong> 联网搜索，"
    "无需配置任何额外 API Key，直接使用 .env 中已有的 <code>AI302_API_KEY</code>。<br/>"
    "适合有公开资料的历史名人或公众人物；普通私人人物建议直接手动填写表单。"
    "</div>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────── 触发搜索 ────────────────────────────────────────
if _search_btn and _query_input.strip():
    st.session_state["ds_query"] = _query_input.strip()
    st.session_state["ds_chat"].append({"role": "user", "content": f"请帮我搜索：{_query_input.strip()}"})
    st.session_state["ds_searching"] = True
    st.session_state["ds_result"] = None
    st.session_state["_ds_show_followup"] = False
    st.rerun()

# ─────────────────────────── 执行搜索 ────────────────────────────────────────
if st.session_state["ds_searching"]:
    _ph = st.empty()
    _ph.markdown(_THINK_HTML.format(label="正在联网搜索，请稍候（约 10-20 秒）..."), unsafe_allow_html=True)

    _q  = st.session_state["ds_query"]
    _ex = st.session_state["ds_extra_context"]

    organized, used_model = _call_302_search(_q, _ex)

    _ph.markdown(_THINK_HTML.format(label="正在提取表单字段..."), unsafe_allow_html=True)
    fields = _extract_fields(organized, _q)

    st.session_state["ds_result"]      = {"organized": organized, "fields": fields}
    st.session_state["_ds_used_model"] = used_model
    st.session_state["ds_chat"].append({"role": "ai", "content": organized})
    st.session_state["ds_searching"]   = False
    _ph.empty()
    st.rerun()

# ─────────────────────────── 对话历史展示 ────────────────────────────────────
if st.session_state["ds_chat"]:
    _html = "<div class='ds-chat-wrap'>"
    for _m in st.session_state["ds_chat"]:
        _html += _bubble_ai(_m["content"]) if _m["role"] == "ai" else _bubble_user(_m["content"])
    _html += "</div>"
    st.markdown(_html, unsafe_allow_html=True)

    if st.session_state.get("_ds_used_model"):
        st.markdown(
            f"<div style='text-align:right;font-size:.72rem;color:var(--muted-l);"
            f"margin-top:-14px;margin-bottom:16px;'>"
            f"使用模型：{st.session_state['_ds_used_model']}</div>",
            unsafe_allow_html=True,
        )

# ─────────────────────────── 结果操作区 ──────────────────────────────────────
_result = st.session_state.get("ds_result")
if _result:
    _fields = _result.get("fields", {})

    _field_labels = {
        "deceased_name": "姓名",
        "deceased_gender": "性别",
        "birth_date": "出生日期",
        "death_date": "逝世日期",
        "occupation": "职业 / 身份",
        "family_memory_text": "人生故事（节选）",
    }
    _rows_html = ""
    for _fk, _fl in _field_labels.items():
        _fv = _fields.get(_fk, "")
        if _fv:
            _disp = _fv if len(_fv) <= 80 else _fv[:80] + "..."
            _rows_html += (
                f"<div class='ds-result-row'>"
                f"<span class='ds-result-label'>{_fl}</span>"
                f"<span class='ds-result-val'>{_esc(_disp)}</span>"
                f"</div>"
            )
    if _rows_html:
        st.markdown(
            f"<div class='ds-result-card'>"
            f"<div class='ds-result-title'>AI 提取的表单信息预览</div>"
            f"{_rows_html}</div>",
            unsafe_allow_html=True,
        )

    _ba, _bb, _bc = st.columns(3)
    with _ba:
        if st.button("将信息填入表单并继续", type="primary", use_container_width=True, key="ds_fill_btn"):
            _form = st.session_state.get("form_data", {})
            for _fk, _fv in _fields.items():
                if _fv:
                    _form[_fk] = _fv
            st.session_state["form_data"] = _form
            st.switch_page("app.py")
    with _bb:
        if st.button("重新搜索", use_container_width=True, key="ds_retry_btn"):
            st.session_state["ds_chat"]           = []
            st.session_state["ds_result"]         = None
            st.session_state["_ds_show_followup"] = False
            st.rerun()
    with _bc:
        _fup_label = "收起追问" if st.session_state["_ds_show_followup"] else "继续追问"
        if st.button(_fup_label, use_container_width=True, key="ds_followup_btn"):
            st.session_state["_ds_show_followup"] = not st.session_state["_ds_show_followup"]
            st.rerun()

    # ── 追问对话框 ────────────────────────────────────────────────────────────
    if st.session_state["_ds_show_followup"]:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _fq_col, _fq_btn_col = st.columns([5, 1])
        with _fq_col:
            _followup = st.text_input(
                "追问",
                placeholder="例如：他有哪些著名作品？在哪个年代最活跃？",
                key="ds_followup_input",
                label_visibility="collapsed",
            )
        with _fq_btn_col:
            _fq_send = st.button("发送", type="primary", use_container_width=True, key="ds_fq_send")

        if _fq_send and _followup.strip():
            st.session_state["ds_chat"].append({"role": "user", "content": _followup.strip()})
            _ph2 = st.empty()
            _ph2.markdown(_THINK_HTML.format(label="念念正在思考..."), unsafe_allow_html=True)
            _ctx   = _result.get("organized", "")
            _reply = ""
            for _m in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
                try:
                    _r = PRIMARY_CLIENT.chat.completions.create(
                        model=_m,
                        messages=[
                            {"role": "system", "content": (
                                "你是念念追思影像制作助手。以下是关于某位人物已整理好的资料，"
                                "请根据资料回答用户追问，语气温暖，信息不足时坦诚告知。"
                                f"\n\n已整理资料：\n{_ctx}"
                            )},
                            {"role": "user", "content": _followup.strip()},
                        ],
                        temperature=0.5,
                        max_tokens=600,
                    )
                    _reply = (_r.choices[0].message.content or "").strip()
                    if _reply:
                        break
                except Exception:
                    continue
            if not _reply:
                _reply = "抱歉，暂时无法回答，请稍后重试。"
            st.session_state["ds_chat"].append({"role": "ai", "content": _reply})
            _ph2.empty()
            st.rerun()

# ─────────────────────────── 底部说明 ────────────────────────────────────────
st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;font-size:.76rem;color:var(--muted-l);line-height:1.8;'>"
    "深度搜索仅适用于有公开网络资料的人物（历史名人、公众人物等）。<br/>"
    "对于普通私人人物，请直接在表单中手动填写家庭回忆与生平信息。<br/>"
    "所有搜索内容通过 302.ai 网关处理，不会存储个人隐私数据。"
    "</div>",
    unsafe_allow_html=True,
)
