# pages/deep_search.py — 念念 Deep Search Agent
# 根据用户输入的姓名/关键词，联网搜索人物信息并整理为追思影像素材

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from llm_client import PRIMARY_CLIENT, TEXT_MODEL, TEXT_FALLBACK_MODEL

st.set_page_config(
    page_title="念念 · 深度搜索",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 样式 ──────────────────────────────────────────────────────────────────────
_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
:root{
  --bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;
  --border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);
  --gold:#9C7A45;--gold-l:#B8934F;--gold-dim:rgba(156,122,69,.08);
  --ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;
  --green:#5A9A72;
}
html,body,[class*="css"]{font-family:"Noto Sans SC",sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
section[data-testid="stSidebar"],[data-testid="stSidebarNav"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:800px!important;padding:0 20px 100px!important;margin:0 auto!important;}

.ds-topbar{display:flex;align-items:center;justify-content:space-between;padding:22px 0 20px;border-bottom:1px solid var(--border);margin-bottom:28px;}
.ds-logo{display:flex;align-items:center;gap:12px;}
.ds-orb{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#B8934F);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;font-family:"Cormorant Garamond",serif;}
.ds-title{font-family:"Cormorant Garamond",serif;font-size:1.25rem;font-weight:600;color:var(--ink);}
.ds-sub{font-size:.7rem;color:var(--muted-l);letter-spacing:.05em;}
.ds-badge{font-size:.72rem;font-weight:600;letter-spacing:.05em;color:var(--gold);background:var(--gold-dim);border:1px solid var(--border-h);border-radius:999px;padding:5px 14px;}

.ds-search-box{background:var(--surf);border:1px solid var(--border);border-radius:20px;padding:28px 32px;margin-bottom:20px;box-shadow:0 2px 16px rgba(0,0,0,.04);}
.ds-section-label{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--border);}

.ds-chat-wrap{display:flex;flex-direction:column;gap:18px;margin-bottom:24px;}
.ds-chat-ai{display:flex;align-items:flex-start;gap:12px;}
.ds-ai-avatar{width:40px;height:40px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#C4964A 0%,#E8C57A 50%,#9C7A45 100%);display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700;font-family:"Cormorant Garamond",serif;}
.ds-ai-bubble-wrap{display:flex;flex-direction:column;gap:4px;flex:1;}
.ds-ai-name{font-size:.68rem;font-weight:700;color:var(--gold);letter-spacing:.05em;}
.ds-ai-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 18px 18px 18px;padding:14px 18px;font-size:.95rem;line-height:1.78;color:var(--ink);box-shadow:0 2px 10px rgba(0,0,0,.04);white-space:pre-wrap;}
.ds-user-bubble{display:flex;justify-content:flex-end;}
.ds-user-bubble-inner{background:var(--gold);color:#fff;border-radius:18px 4px 18px 18px;padding:12px 18px;max-width:70%;font-size:.95rem;line-height:1.7;}

@keyframes dot-bounce{0%,80%,100%{transform:translateY(0);opacity:.35;}40%{transform:translateY(-7px);opacity:1;}}
@keyframes orb-pulse{0%,100%{transform:scale(1);}50%{transform:scale(1.08);}}
@keyframes ring-out{0%{transform:scale(1);opacity:.6;}100%{transform:scale(2.2);opacity:0;}}
@keyframes grad-shift{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.ds-think-row{display:flex;align-items:flex-start;gap:12px;}
.ds-think-wrap{position:relative;width:40px;height:40px;flex-shrink:0;}
.ds-think-orb{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#C4964A,#F0D590,#9C7A45,#DCA855);background-size:300% 300%;animation:orb-pulse 2s ease-in-out infinite,grad-shift 4s ease infinite;position:relative;z-index:2;}
.ds-think-ring{position:absolute;inset:0;border-radius:50%;border:1.5px solid rgba(184,147,79,.55);animation:ring-out 2s ease-out infinite;z-index:1;}
.ds-think-ring-2{animation-delay:1s;}
.ds-think-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 18px 18px 18px;padding:14px 20px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 10px rgba(0,0,0,.04);}
.ds-think-dots{display:flex;gap:5px;align-items:center;}
.ds-think-dots span{width:7px;height:7px;border-radius:50%;background:var(--gold);display:block;}
.ds-think-dots span:nth-child(1){animation:dot-bounce 1.4s 0s ease infinite;}
.ds-think-dots span:nth-child(2){animation:dot-bounce 1.4s .22s ease infinite;}
.ds-think-dots span:nth-child(3){animation:dot-bounce 1.4s .44s ease infinite;}
.ds-think-label{font-size:.86rem;color:var(--muted-l);font-style:italic;}

.ds-result-card{background:var(--surf);border:1px solid var(--border);border-radius:16px;padding:22px 26px;margin-bottom:14px;box-shadow:0 2px 12px rgba(0,0,0,.04);}
.ds-result-title{font-family:"Cormorant Garamond",serif;font-size:1.1rem;font-weight:600;color:var(--ink);margin-bottom:10px;}
.ds-result-row{display:flex;gap:8px;margin-bottom:7px;align-items:flex-start;}
.ds-result-label{font-size:.72rem;font-weight:700;color:var(--gold);background:var(--gold-dim);border-radius:4px;padding:2px 7px;flex-shrink:0;margin-top:2px;}
.ds-result-val{font-size:.9rem;color:var(--ink-m);line-height:1.6;}

div.stButton>button{border-radius:999px!important;font-size:.9rem!important;font-weight:600!important;padding:10px 24px!important;transition:all .2s!important;border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;}
[data-testid="stAlert"]{background:var(--surf2)!important;border-radius:10px!important;border:1px solid var(--border)!important;}
label,.stTextInput label,.stTextArea label{font-size:.78rem!important;font-weight:600!important;letter-spacing:.04em!important;text-transform:uppercase!important;color:var(--muted-l)!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{background:var(--surf)!important;border:1px solid var(--border)!important;border-radius:12px!important;color:var(--ink)!important;font-size:1rem!important;padding:12px 16px!important;}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{border-color:var(--border-h)!important;box-shadow:0 0 0 3px var(--gold-dim)!important;outline:none!important;}
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

# ── Session 初始化 ─────────────────────────────────────────────────────────────
def _init():
    defaults = {
        "ds_chat": [],
        "ds_searching": False,
        "ds_result": None,
        "ds_query": "",
        "ds_extra_context": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init()

# ── 搜索工具函数 ───────────────────────────────────────────────────────────────
_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
_GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY", "")
_SERPER_API_KEY   = os.getenv("SERPER_API_KEY", "")
_TAVILY_API_KEY   = os.getenv("TAVILY_API_KEY", "")


def _web_search_tavily(query: str, max_results: int = 6) -> List[Dict]:
    """Tavily 搜索 API（推荐，支持中文，含摘要）"""
    if not _TAVILY_API_KEY:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": _TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False,
            },
            timeout=20,
        )
        data = resp.json()
        results = []
        if data.get("answer"):
            results.append({"title": "综合摘要", "snippet": data["answer"], "url": ""})
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("content", ""),
                "url": r.get("url", ""),
            })
        return results
    except Exception as e:
        return [{"title": "搜索失败", "snippet": str(e), "url": ""}]


def _web_search_serper(query: str, max_results: int = 6) -> List[Dict]:
    """Serper.dev Google 搜索 API（备用）"""
    if not _SERPER_API_KEY:
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": _SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": max_results, "gl": "cn", "hl": "zh-cn"},
            timeout=15,
        )
        data = resp.json()
        results = []
        if data.get("answerBox", {}).get("answer"):
            results.append({"title": "快速答案", "snippet": data["answerBox"]["answer"], "url": ""})
        for r in data.get("organic", []):
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "url": r.get("link", ""),
            })
        return results
    except Exception as e:
        return [{"title": "搜索失败", "snippet": str(e), "url": ""}]


def _web_search_google(query: str, max_results: int = 6) -> List[Dict]:
    """Google Custom Search JSON API（备用）"""
    if not _GOOGLE_API_KEY or not _SEARCH_ENGINE_ID:
        return []
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": _GOOGLE_API_KEY, "cx": _SEARCH_ENGINE_ID, "q": query, "num": min(max_results, 10)},
            timeout=15,
        )
        items = resp.json().get("items", [])
        return [{"title": i.get("title",""), "snippet": i.get("snippet",""), "url": i.get("link","")} for i in items]
    except Exception as e:
        return [{"title": "搜索失败", "snippet": str(e), "url": ""}]


def web_search(query: str, max_results: int = 6) -> List[Dict]:
    """按优先级调用搜索 API：Tavily → Serper → Google CSE → 降级提示"""
    if _TAVILY_API_KEY:
        results = _web_search_tavily(query, max_results)
        if results:
            return results
    if _SERPER_API_KEY:
        results = _web_search_serper(query, max_results)
        if results:
            return results
    if _GOOGLE_API_KEY and _SEARCH_ENGINE_ID:
        results = _web_search_google(query, max_results)
        if results:
            return results
    # 没有配置任何搜索 API → 返回占位提示
    return [{
        "title": "未配置搜索 API",
        "snippet": (
            "请在环境变量中配置以下任一搜索接口：\n"
            "TAVILY_API_KEY（推荐，支持中文深度搜索）\n"
            "SERPER_API_KEY（Google 搜索代理）\n"
            "GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID（Google CSE）"
        ),
        "url": "",
    }]


# ── LLM 整理函数 ───────────────────────────────────────────────────────────────
_EXTRACT_SYSTEM = """你是念念追思影像制作助手，专门帮助整理人物的生平资料。

用户提供了对某位人物的网络搜索结果，请你仔细阅读后，用温暖、自然的中文整理出以下内容：

1. **基本信息摘要**：姓名、生卒年月（如有）、主要职业/身份、籍贯（如有）
2. **人生经历亮点**：按时间顺序列出 3-6 个重要人生节点或事件
3. **性格与贡献**：对这个人的性格特点、主要贡献或影响的简短描述
4. **可用于影像的素材线索**：从资料中提炼 2-4 个适合制作追思影像的故事场景或情感记忆点

如果搜索结果中找不到相关人物信息（如是私人人物、信息不足），请如实告知，并建议用户手动补充关键信息。

输出格式：用清晰的小标题分段，语气温暖，像在讲述一位值得被记住的人的故事。
不要输出 JSON，直接用自然语言回答。"""


def _llm_organize(query: str, search_results: List[Dict], extra_context: str = "") -> str:
    """调用 LLM 整理搜索结果为结构化人物介绍"""
    snippets = "\n\n".join(
        f"[{i+1}] {r['title']}\n{r['snippet']}" + (f"\n来源：{r['url']}" if r["url"] else "")
        for i, r in enumerate(search_results)
    )
    user_content = f"搜索关键词：{query}\n\n"
    if extra_context:
        user_content += f"补充背景信息：{extra_context}\n\n"
    user_content += f"以下是搜索结果：\n\n{snippets}"

    for model in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user",   "content": user_content},
                ],
                temperature=0.5,
                max_tokens=1200,
            )
            return resp.choices[0].message.content or "（整理失败，请重试）"
        except Exception:
            continue
    return "抱歉，AI 整理服务暂时不可用，请稍后重试。"


_FILL_SYSTEM = """你是念念追思影像制作助手，根据已整理好的人物资料，帮用户自动提取并填写以下表单字段。

请严格按 JSON 格式输出，只输出 JSON，不加任何解释：
{
  "deceased_name": "姓名",
  "deceased_gender": "男/女/不便告知",
  "birth_date": "出生日期（格式：XXXX年X月X日，不确定则留空）",
  "death_date": "逝世日期（格式：XXXX年X月X日，在世或不确定则留空）",
  "occupation": "主要职业/身份",
  "family_memory_text": "根据搜索资料整理的人生故事与回忆（200-400字，温暖叙事风格）"
}

如某字段信息不足，填空字符串""。"""


def _llm_extract_fields(organized_text: str, query: str) -> Dict:
    """从整理好的文本中提取可自动填入表单的字段"""
    for model in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _FILL_SYSTEM},
                    {"role": "user",   "content": f"搜索词：{query}\n\n整理好的人物资料：\n{organized_text}"},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            raw = resp.choices[0].message.content or "{}"
            # 提取 JSON
            import re
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                return json.loads(m.group())
        except Exception:
            continue
    return {}


# ── 对话气泡渲染 ───────────────────────────────────────────────────────────────
def _bubble_ai(content: str) -> str:
    return (
        "<div class='ds-chat-ai'>"
        "<div class='ds-ai-avatar'>念</div>"
        "<div class='ds-ai-bubble-wrap'>"
        "<div class='ds-ai-name'>念念 AI · 深度搜索</div>"
        f"<div class='ds-ai-bubble'>{content}</div>"
        "</div></div>"
    )

def _bubble_user(content: str) -> str:
    return (
        "<div class='ds-user-bubble'>"
        f"<div class='ds-user-bubble-inner'>{content}</div>"
        "</div>"
    )

# ── 顶栏 ──────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='ds-topbar'>"
    "<div class='ds-logo'>"
    "<div class='ds-orb'>念</div>"
    "<div><div class='ds-title'>念念 · 深度搜索</div>"
    "<div class='ds-sub'>Deep Search Agent</div></div>"
    "</div>"
    "<div class='ds-badge'>联网搜索 · AI 整理</div>"
    "</div>",
    unsafe_allow_html=True,
)

_nav1, _nav2, _ = st.columns([1, 1, 4])
with _nav1:
    if st.button("返回信息填写", use_container_width=True):
        st.switch_page("app.py")
with _nav2:
    if st.button("返回首页", use_container_width=True):
        st.session_state["main_section"] = "home"
        st.switch_page("app.py")

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── 搜索输入区 ────────────────────────────────────────────────────────────────
st.markdown("<div class='ds-search-box'>", unsafe_allow_html=True)
st.markdown("<div class='ds-section-label'>搜索人物</div>", unsafe_allow_html=True)

_col_q, _col_btn = st.columns([5, 1])
with _col_q:
    _query_input = st.text_input(
        "搜索关键词",
        value=st.session_state["ds_query"],
        placeholder="输入姓名，如：陈文斌 上海工程师  /  张国强 木工",
        label_visibility="collapsed",
        key="ds_query_input",
    )
with _col_btn:
    _search_btn = st.button("开始搜索", type="primary", use_container_width=True, key="ds_search_btn")

_extra = st.text_area(
    "补充背景信息（选填）",
    value=st.session_state["ds_extra_context"],
    placeholder="如：1948年生，上海人，曾在机床厂工作，有助于提高搜索精准度",
    height=68,
    key="ds_extra_input",
    label_visibility="visible",
)
st.session_state["ds_extra_context"] = _extra

# 说明
_has_api = any([_TAVILY_API_KEY, _SERPER_API_KEY, (_GOOGLE_API_KEY and _SEARCH_ENGINE_ID)])
if not _has_api:
    st.warning(
        "当前未配置任何搜索 API。请在环境变量中配置 TAVILY_API_KEY（推荐）、"
        "SERPER_API_KEY 或 GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID 后使用深度搜索功能。"
    )

st.markdown("</div>", unsafe_allow_html=True)

# ── 执行搜索 ──────────────────────────────────────────────────────────────────
if _search_btn and _query_input.strip():
    query = _query_input.strip()
    st.session_state["ds_query"] = query
    st.session_state["ds_chat"].append({"role": "user", "content": f"请帮我搜索：{query}"})
    st.session_state["ds_searching"] = True
    st.session_state["ds_result"] = None
    st.rerun()

# ── 搜索执行阶段 ──────────────────────────────────────────────────────────────
if st.session_state["ds_searching"]:
    _think_ph = st.empty()
    _think_ph.markdown(
        _THINK_HTML.format(label="正在联网搜索，请稍候..."),
        unsafe_allow_html=True,
    )
    time.sleep(0.3)

    query = st.session_state["ds_query"]
    extra = st.session_state["ds_extra_context"]

    # Step 1: 多轮搜索（主查询 + 补充查询）
    _think_ph.markdown(
        _THINK_HTML.format(label=f"正在搜索「{query}」..."),
        unsafe_allow_html=True,
    )
    results = web_search(query + " 生平 简介", max_results=5)
    # 补充搜索：加上"回忆 事迹"
    results2 = web_search(query + " 事迹 故事", max_results=3)
    all_results = results + [r for r in results2 if r not in results]

    # Step 2: LLM 整理
    _think_ph.markdown(
        _THINK_HTML.format(label="AI 正在整理搜索结果，提炼人生故事..."),
        unsafe_allow_html=True,
    )
    organized = _llm_organize(query, all_results, extra)

    # Step 3: 提取表单字段
    _think_ph.markdown(
        _THINK_HTML.format(label="正在提取可填入表单的信息..."),
        unsafe_allow_html=True,
    )
    fields = _llm_extract_fields(organized, query)

    st.session_state["ds_result"] = {
        "organized": organized,
        "fields": fields,
        "raw_count": len(all_results),
    }
    st.session_state["ds_chat"].append({"role": "ai", "content": organized})
    st.session_state["ds_searching"] = False
    _think_ph.empty()
    st.rerun()

# ── 对话历史展示 ──────────────────────────────────────────────────────────────
chat = st.session_state["ds_chat"]
if chat:
    html = "<div class='ds-chat-wrap'>"
    for m in chat:
        html += _bubble_ai(m["content"]) if m["role"] == "ai" else _bubble_user(m["content"])
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

# ── 搜索结果操作区 ────────────────────────────────────────────────────────────
result = st.session_state.get("ds_result")
if result:
    fields = result.get("fields", {})

    # 提取到的字段预览
    if any(fields.values()):
        st.markdown("<div class='ds-result-card'>", unsafe_allow_html=True)
        st.markdown("<div class='ds-result-title'>AI 提取的表单信息预览</div>", unsafe_allow_html=True)

        _field_labels = {
            "deceased_name": "姓名",
            "deceased_gender": "性别",
            "birth_date": "出生日期",
            "death_date": "逝世日期",
            "occupation": "职业 / 身份",
            "family_memory_text": "人生故事与回忆",
        }
        _field_html = ""
        for k, label in _field_labels.items():
            v = fields.get(k, "")
            if v:
                _display = v if len(v) < 80 else v[:80] + "..."
                _field_html += (
                    f"<div class='ds-result-row'>"
                    f"<span class='ds-result-label'>{label}</span>"
                    f"<span class='ds-result-val'>{_display}</span>"
                    f"</div>"
                )
        st.markdown(_field_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 操作按钮
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _ca, _cb, _cc = st.columns(3)

    with _ca:
        if st.button("将信息填入表单并继续", type="primary", use_container_width=True, key="ds_fill_btn"):
            # 将提取的字段写入 form_data
            _form_data = st.session_state.get("form_data", {})
            for k, v in fields.items():
                if v:
                    _form_data[k] = v
            st.session_state["form_data"] = _form_data
            # 跳转回主表单
            st.switch_page("app.py")

    with _cb:
        if st.button("重新搜索", use_container_width=True, key="ds_retry_btn"):
            st.session_state["ds_chat"] = []
            st.session_state["ds_result"] = None
            st.rerun()

    with _cc:
        if st.button("继续追问（多轮对话）", use_container_width=True, key="ds_followup_btn"):
            st.session_state["_ds_show_followup"] = True
            st.rerun()

    # 追问输入框
    if st.session_state.get("_ds_show_followup"):
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _fq_col, _fq_btn_col = st.columns([5, 1])
        with _fq_col:
            _followup = st.text_input(
                "追问内容",
                placeholder="例如：他在哪个年代最活跃？有哪些重要奖项或荣誉？",
                key="ds_followup_input",
                label_visibility="collapsed",
            )
        with _fq_btn_col:
            _fq_send = st.button("发送", type="primary", use_container_width=True, key="ds_fq_send")

        if _fq_send and _followup.strip():
            st.session_state["ds_chat"].append({"role": "user", "content": _followup.strip()})
            # 用已有整理文本 + 追问问题直接调 LLM（不再重新搜索）
            _think_ph2 = st.empty()
            _think_ph2.markdown(_THINK_HTML.format(label="念念正在思考..."), unsafe_allow_html=True)
            _followup_reply = ""
            _organized_ctx = result.get("organized", "")
            for _model in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
                try:
                    _resp = PRIMARY_CLIENT.chat.completions.create(
                        model=_model,
                        messages=[
                            {"role": "system", "content": (
                                "你是念念追思影像制作助手。以下是关于某位人物已整理好的资料，"
                                "请根据资料回答用户的追问，语气温暖，如实回答，信息不足时坦诚告知。"
                                f"\n\n已整理资料：\n{_organized_ctx}"
                            )},
                            {"role": "user", "content": _followup.strip()},
                        ],
                        temperature=0.5,
                        max_tokens=600,
                    )
                    _followup_reply = _resp.choices[0].message.content or ""
                    break
                except Exception:
                    continue
            if not _followup_reply:
                _followup_reply = "抱歉，暂时无法回答，请稍后重试。"
            st.session_state["ds_chat"].append({"role": "ai", "content": _followup_reply})
            _think_ph2.empty()
            st.rerun()

# ── 底部说明 ──────────────────────────────────────────────────────────────────
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;font-size:.76rem;color:var(--muted-l);line-height:1.7;'>"
    "深度搜索仅适用于有公开网络资料的人物（如历史名人、公众人物等）。<br/>"
    "对于普通私人人物，建议直接在表单中手动填写家庭回忆与生平信息。"
    "</div>",
    unsafe_allow_html=True,
)
