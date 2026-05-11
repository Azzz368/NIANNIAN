# pages/dialogue.py — 数字人多轮对话界面（双栏布局：左侧人设编辑器 + 右侧对话）
import json
import sys
from pathlib import Path

import streamlit as st

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from llm_client import call_memorial_chat, DIALOGUE_MODEL

st.set_page_config(
    page_title="念念 · 数字人对话",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
:root{
  --bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;
  --border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);
  --gold:#9C7A45;--gold-l:#B8934F;--gold-dim:rgba(156,122,69,.08);--gold-glow:rgba(156,122,69,.18);
  --ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;
}
html,body,[class*="css"]{font-family:"Noto Sans SC",sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
section[data-testid="stSidebar"],[data-testid="stSidebarNav"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:100%!important;padding:20px 32px 140px!important;}

.dh-topbar{display:flex;align-items:center;padding:14px 0 12px;border-bottom:1px solid var(--border);margin-bottom:20px;gap:12px;}
.dh-orb{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#C4964A);
  display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;
  font-family:"Cormorant Garamond",serif;flex-shrink:0;}
.dh-title{font-family:"Cormorant Garamond",serif;font-size:1.15rem;font-weight:600;color:var(--ink);}
.dh-sub{font-size:.68rem;color:var(--muted-l);letter-spacing:.05em;}

.panel-box{background:var(--surf);border:1px solid var(--border-h);border-radius:16px;padding:18px 16px 20px;}
.panel-title{font-family:"Cormorant Garamond",serif;font-size:1.0rem;font-weight:600;color:var(--ink);
  padding-bottom:10px;border-bottom:1px solid var(--border);margin-bottom:14px;}
.panel-label{font-size:.75rem;color:var(--muted-l);margin-bottom:5px;font-weight:500;}
.persona-status{font-size:.72rem;padding:3px 10px;border-radius:999px;display:inline-block;margin-bottom:10px;}
.status-active{background:rgba(100,160,80,.12);color:#5A9050;border:1px solid rgba(100,160,80,.25);}
.status-default{background:var(--gold-dim);color:var(--gold);border:1px solid var(--border-h);}
.merge-preview{background:var(--bg);border:1px solid var(--border);border-radius:8px;
  padding:9px 11px;font-size:.78rem;color:var(--ink-m);line-height:1.65;
  max-height:130px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;margin-bottom:10px;}
.panel-hint{font-size:.7rem;color:#B0A494;line-height:1.6;margin-top:12px;}

.persona-card{background:linear-gradient(135deg,var(--surf2),var(--surf));
  border:1px solid var(--border-h);border-radius:14px;padding:14px 18px;
  display:flex;align-items:center;gap:14px;margin-bottom:18px;
  box-shadow:0 2px 10px rgba(156,122,69,.07);}
.persona-avatar{width:46px;height:46px;border-radius:50%;background:linear-gradient(135deg,#C4964A,#E8C57A);
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:1.2rem;font-family:"Cormorant Garamond",serif;font-weight:600;flex-shrink:0;}
.persona-name{font-family:"Cormorant Garamond",serif;font-size:1.1rem;font-weight:600;color:var(--ink);}
.persona-meta{font-size:.75rem;color:var(--muted-l);margin-top:2px;}
.persona-tag{display:inline-block;background:var(--gold-dim);border:1px solid var(--border-h);
  border-radius:999px;padding:2px 9px;font-size:.7rem;color:var(--gold);margin:2px 3px;}

[data-testid="stChatMessage"]{padding:5px 0!important;}
[data-testid="stChatMessageContent"]{font-size:.93rem!important;line-height:1.75!important;}
[data-testid="stChatMessageContent"]>div{background:transparent!important;}
[data-testid="stMarkdownContainer"]{background:transparent!important;}

/* 头像圆形裁剪 */
[data-testid="chatAvatarIcon-assistant"],
[data-testid="chatAvatarIcon-user"]{
  border-radius:50%!important;
  border:none!important;
  box-shadow:none!important;
  overflow:hidden!important;
  padding:0!important;
}

/* 优化底部输入区 - 设为sticky跟随内容到底部并悬浮 */
[data-testid="stChatInput"]{
  position: sticky !important;
  bottom: 0px !important;
  z-index: 999 !important;
  background: var(--bg) !important; 
  padding: 10px 0 20px!important;
}

/* 强制清除所有内部 Streamlit/BaseWeb 默认的灰色背景 */
[data-testid="stChatInput"] div[data-baseweb],
[data-testid="stChatInput"] div[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] div[class*="st-"] {
  background-color: transparent !important;
}

/* 输入框外壳：从胶囊形过渡到圆角矩形，丝滑动画 */
[data-testid="stChatInput"]>div{
  background: var(--surf) !important;
  border:1px solid var(--border-h)!important;
  border-radius:28px!important;
  box-shadow:0 4px 20px rgba(156,122,69,.08)!important;
  transition:border-radius .25s ease, box-shadow .25s ease, border-color .2s ease!important;
}
[data-testid="stChatInput"]>div:focus-within{
  border-color:var(--gold)!important;
  box-shadow:0 8px 30px rgba(156,122,69,.18)!important;
  border-radius:20px!important;
}

/* textarea：向上平滑拓展 */
[data-testid="stChatInput"] textarea{
  font-size:.95rem!important;
  color:var(--ink)!important;
  background:transparent!important;
  line-height:1.6!important;
  min-height:24px!important;
  max-height:280px!important;
  resize:none!important;
  overflow-y:auto!important;
  padding:12px 0 12px 16px!important;
  scrollbar-width:none!important;
}
[data-testid="stChatInput"] textarea::-webkit-scrollbar {
  display: none!important;
}

/* 发送按钮 */
[data-testid="stChatInput"] button{
  background:var(--gold)!important;
  border-radius:50%!important;
  width:34px!important;height:34px!important;
  margin-right:8px!important;
  margin-bottom:6px!important;
  align-self:flex-end!important;
  transition:background .2s ease, transform .2s ease!important;
  flex-shrink:0!important;
}
[data-testid="stChatInput"] button:hover{
  background:var(--gold-l)!important;
  transform:scale(1.08)!important;
}
[data-testid="stChatInput"] button svg{fill:#fff!important;stroke:#fff!important;}

div.stButton>button{border-radius:10px!important;font-size:.82rem!important;padding:7px 14px!important;
  border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{background:var(--gold)!important;border-color:var(--gold)!important;
  color:#fff!important;box-shadow:0 3px 12px var(--gold-glow)!important;}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;}
hr{border-color:var(--border)!important;margin:14px 0!important;}

/* 左侧文本输入区（人设编辑器）优化：去灰底并加上明显的边框 */
[data-testid="stTextArea"] > div > div {
  background-color: var(--surf) !important;
  border: 1px solid var(--border-h) !important;
  border-radius: 12px !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stTextArea"] > div > div:focus-within {
  border-color: var(--gold) !important;
  box-shadow: 0 0 0 1px var(--gold) !important;
}
[data-testid="stTextArea"] textarea {
  background-color: transparent !important;
  color: var(--ink) !important;
  font-size: 0.9rem !important;
  line-height: 1.6 !important;
}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

PERSONA_OUTPUT = _BASE / "outputs" / "wechat_persona.json"


# ── 自定义头像（SVG data URI，纯色圆形+首字，色卡配色）────────────────────────
import base64 as _b64

def _make_avatar(bg: str, char: str) -> str:
    """生成一个纯色圆形头像 data URI，用于 st.chat_message(avatar=...)"""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36">'
        f'<circle cx="18" cy="18" r="18" fill="{bg}"/>'
        f'<text x="18" y="24" text-anchor="middle" '
        f'font-family="serif" font-size="17" font-weight="600" fill="#fff">{char}</text>'
        f'</svg>'
    )
    b64 = _b64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"

# 颜色取自色卡：暖金 / 灰棕
_AVATAR_AI   = _make_avatar("#C4964A", "念")   # 暖金 — AI 数字人
_AVATAR_USER = _make_avatar("#8A7B6A", "我")   # 灰棕 — 用户


def merge_persona_with_llm(dna: dict, current_override: str, new_input: str) -> str:
    dna_summary = (
        f"语气基调: {dna.get('tone', '')}, "
        f"常用口头禅: {'、'.join(dna.get('speech_patterns', [])[:5])}, "
        f"常聊话题: {'、'.join(dna.get('typical_topics', [])[:3])}, "
        f"幽默程度: {dna.get('humor_level', 3)}/5, "
        f"回应风格: {dna.get('response_style', '')}"
    )
    merge_prompt = (
        f"你是一个角色人设管理助手。用户正在为数字人动态调整人设描述。\n\n"
        f"【已有角色 DNA 摘要】\n{dna_summary}\n\n"
        f"【当前角色背景描述】\n{current_override if current_override.strip() else '（暂无）'}\n\n"
        f"【用户新增/修改内容】\n{new_input}\n\n"
        f"请智能融合：保留有用旧设定，以新内容优先，去除矛盾重复，"
        f"用自然流畅中文描述，不超过250字。"
        f"直接返回融合后文本，不要任何解释或前缀。"
    )
    try:
        result = call_memorial_chat(
            system_prompt="你是角色人设管理助手，只返回融合结果文本，不解释。",
            messages=[{"role": "user", "content": merge_prompt}],
            model=DIALOGUE_MODEL,
        )
        return result.strip()
    except Exception:
        return (current_override + "\n\n[新增] " + new_input).strip()


def build_persona_system_prompt(dna: dict, name: str, extra_desc: str = "") -> str:
    speech_patterns = "、".join(dna.get("speech_patterns", [])[:10])
    signatures = "\n".join(f"  - {p}" for p in dna.get("signature_phrases", []))
    topics    = "、".join(dna.get("typical_topics", [])[:5])
    emo_words = "、".join(dna.get("emotional_words", [])[:8])
    habits    = dna.get("special_habits", "")
    extra_section = f"\n【角色背景补充】\n{extra_desc}\n" if extra_desc.strip() else ""
    return (
        f"你现在扮演一个真实存在过的人：{name}。\n\n"
        f"你的任务是完全以 {name} 的口吻和风格与用户对话，让用户感受到 TA 仍然在陪伴着自己。"
        f"{extra_section}\n"
        f"【{name} 的语言风格特征】\n"
        f"- 常用词/口头禅：{speech_patterns}\n"
        f"- 句子长度风格：{dna.get('avg_sentence_length', '中等')}\n"
        f"- 情感基调：{dna.get('tone', '温和')}\n"
        f"- 幽默程度：{dna.get('humor_level', 3)}/5\n"
        f"- 常聊话题：{topics}\n"
        f"- 常用情感词：{emo_words}\n"
        f"- 特殊语言习惯：{habits}\n"
        f"- 标志性句式：\n{signatures}\n"
        f"- 回应风格：{dna.get('response_style', '自然随和')}\n\n"
        f"【角色扮演守则】\n"
        f"1. 始终保持角色，不要说「我是AI」或打破扮演\n"
        f"2. 回复长度符合 TA 原本的风格\n"
        f"3. 适当使用口头禅和标志性句式，但不要每句都重复\n"
        f"4. 语气温暖真实，像真正的对话而不是朗诵\n"
        f"5. 如果用户问到不知道的事，以 {name} 的性格自然回应\n"
        f"6. 每次回复后可自然地反问或延续话题\n"
        f"7. 不使用 Markdown 格式符号，保持口语化\n"
        f"8. 每次回复控制在1-4句话，除非用户要求详细"
    )


# ── 加载 persona_dna ──────────────────────────────────────────────────────────
persona_dna  = st.session_state.get("persona_dna")
persona_name = st.session_state.get("persona_name")
role_desc    = st.session_state.get("wi_role_extra", "")

if not persona_dna and PERSONA_OUTPUT.exists():
    try:
        saved = json.loads(PERSONA_OUTPUT.read_text(encoding="utf-8"))
        persona_dna  = saved.get("persona_dna")
        persona_name = saved.get("target_name")
        role_desc    = saved.get("role_description", "")
        st.session_state["persona_dna"]   = persona_dna
        st.session_state["persona_name"]  = persona_name
        st.session_state["wi_role_extra"] = role_desc
    except Exception:
        pass

if "persona_override" not in st.session_state:
    st.session_state["persona_override"] = role_desc

# ── 全宽顶栏 ──────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='dh-topbar'>"
    "<div class='dh-orb'>念</div>"
    "<div><div class='dh-title'>数字人 · 对话</div>"
    "<div class='dh-sub'>Digital Human · Conversation</div></div>"
    "</div>",
    unsafe_allow_html=True,
)
nav_c1, nav_c2, _ = st.columns([1, 1, 8])
with nav_c1:
    if st.button("返回分析", use_container_width=True):
        st.switch_page("pages/wechat_import.py")
with nav_c2:
    if st.button("返回主页", use_container_width=True):
        st.session_state["main_section"] = "home"
        st.switch_page("app.py")

if not persona_dna:
    st.markdown(
        "<div style='text-align:center;padding:60px 0;color:#8A7B6A;'>"
        "<div style='font-size:1rem;margin-bottom:20px;'>尚未完成风格分析，请先上传聊天记录</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("前往上传聊天记录", type="primary"):
        st.switch_page("pages/wechat_import.py")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# 双栏主区域
# ══════════════════════════════════════════════════════════════════════════════
col_panel, col_chat = st.columns([1, 2.4], gap="large")

# ── 左栏：人设编辑器 ──────────────────────────────────────────────────────────
with col_panel:
    st.markdown("<div class='panel-box'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>人设编辑器</div>", unsafe_allow_html=True)

    current_override = st.session_state.get("persona_override", "")
    status_cls  = "status-active" if current_override.strip() else "status-default"
    status_text = "人设已生效" if current_override.strip() else "使用默认 DNA"
    st.markdown(f"<span class='persona-status {status_cls}'>{status_text}</span>", unsafe_allow_html=True)

    if current_override.strip():
        st.markdown("<div class='panel-label'>当前生效人设</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='merge-preview'>{current_override}</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel-label'>新增 / 修改人设</div>", unsafe_allow_html=True)
    new_persona_input = st.text_area(
        label="人设输入",
        label_visibility="collapsed",
        placeholder="例如：\n· 补充：TA 特别喜欢聊美食\n· 修改：更沉稳，少用哈哈\n· 删除：不要再说「救命」",
        height=150,
        key="persona_new_text",
    )

    btn_c1, btn_c2 = st.columns(2)
    with btn_c1:
        update_clicked = st.button("更新人设", type="primary", use_container_width=True, key="btn_update_persona")
    with btn_c2:
        clear_clicked = st.button("清空人设", use_container_width=True, key="btn_clear_persona")

    if update_clicked:
        if new_persona_input.strip():
            with st.spinner("AI 融合中…"):
                merged = merge_persona_with_llm(
                    persona_dna,
                    st.session_state.get("persona_override", ""),
                    new_persona_input.strip(),
                )
            st.session_state["persona_override"]     = merged
            st.session_state["persona_merge_done"]   = True
            st.session_state["persona_updated_flag"] = True
            st.rerun()
        else:
            st.warning("请先输入内容")

    if clear_clicked:
        st.session_state["persona_override"]     = ""
        st.session_state["persona_merge_done"]   = False
        st.session_state["persona_updated_flag"] = False
        st.rerun()

    st.markdown(
        "<div class='panel-hint'>"
        "更新后对下一条回复立即生效。<br>"
        "可多次叠加调整。<br>"
        "「清空人设」恢复原始 DNA 风格。"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── 右栏：对话区 ──────────────────────────────────────────────────────────────
with col_chat:
    _tone     = persona_dna.get("tone", "")
    _humor    = persona_dna.get("humor_level", "")
    _style    = persona_dna.get("response_style", "")
    _patterns = persona_dna.get("speech_patterns", [])[:5]
    _tags_html = "".join(f"<span class='persona-tag'>{p}</span>" for p in _patterns)
    st.markdown(
        f"<div class='persona-card'>"
        f"<div class='persona-avatar'>{persona_name[0] if persona_name else '念'}</div>"
        f"<div>"
        f"<div class='persona-name'>{persona_name}</div>"
        f"<div class='persona-meta'>{_tone} · 幽默 {_humor}/5 · {_style}</div>"
        f"<div style='margin-top:5px;'>{_tags_html}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("persona_updated_flag"):
        st.markdown(
            "<div style='background:rgba(156,122,69,.1);border:1px solid rgba(156,122,69,.3);"
            "border-radius:10px;padding:8px 14px;font-size:.8rem;color:#7A5C2A;margin-bottom:12px;'>"
            "人设已更新，下一条回复即刻生效</div>",
            unsafe_allow_html=True,
        )
        st.session_state["persona_updated_flag"] = False

    SYSTEM_PROMPT = build_persona_system_prompt(
        persona_dna,
        persona_name or "TA",
        st.session_state.get("persona_override", role_desc),
    )

    if "dialogue_history" not in st.session_state:
        st.session_state["dialogue_history"] = []

    if not st.session_state["dialogue_history"]:
        _first = _patterns[0] if _patterns else ""
        opening = f"你来啦～{_first + '，' if _first else ''}最近怎么样？"
        st.session_state["dialogue_history"].append({"role": "assistant", "content": opening})

    for msg in st.session_state["dialogue_history"]:
        _av = _AVATAR_AI if msg["role"] == "assistant" else _AVATAR_USER
        with st.chat_message(msg["role"], avatar=_av):
            st.markdown(msg["content"])

    user_input = st.chat_input(f"和 {persona_name} 说点什么…")
    if user_input:
        with st.chat_message("user", avatar=_AVATAR_USER):
            st.markdown(user_input)
        st.session_state["dialogue_history"].append({"role": "user", "content": user_input})
        with st.chat_message("assistant", avatar=_AVATAR_AI):
            with st.spinner(""):
                reply = call_memorial_chat(
                    system_prompt=SYSTEM_PROMPT,
                    messages=st.session_state["dialogue_history"][-20:],
                    model=DIALOGUE_MODEL,
                )
            st.markdown(reply)
        st.session_state["dialogue_history"].append({"role": "assistant", "content": reply})

    st.markdown("---")
    t1, t2, t3 = st.columns(3)
    with t1:
        if st.button("清空对话", use_container_width=True):
            st.session_state["dialogue_history"] = []
            st.rerun()
    with t2:
        if st.session_state.get("dialogue_history"):
            history_text = "\n\n".join(
                f"{'我' if m['role'] == 'user' else persona_name}：{m['content']}"
                for m in st.session_state["dialogue_history"]
            )
            st.download_button(
                "保存对话记录",
                data=history_text.encode("utf-8"),
                file_name=f"与{persona_name}的对话.txt",
                mime="text/plain",
                use_container_width=True,
            )
    with t3:
        if st.button("重新分析风格", use_container_width=True):
            st.switch_page("pages/wechat_import.py")
