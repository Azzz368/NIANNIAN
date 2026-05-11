# pages/wechat_import.py — 微信聊天记录上传 & 风格分析
"""
职责：微信聊天记录上传、解析、AI 风格分析
依赖：llm_client.call_skill() / skill_loader.load_skill()（均已存在，直接 import）
支持格式：
  - CSV：WeChatMsg / 留痕 导出格式
  - JSON：标准 JSON 聊天记录
  - TXT：纯文本格式（两种常见布局）
"""
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import List, Dict

import streamlit as st

# ── 路径修正：pages/ 子目录下需要把父目录加入 sys.path ─────────────────────
_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from llm_client import call_skill
from skill_loader import load_skill

st.set_page_config(page_title="念念 · 数字人分析", layout="wide", initial_sidebar_state="collapsed")

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
[data-testid="stSidebarNav"],section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:820px!important;padding:0 20px 100px!important;margin:0 auto!important;}
.dh-topbar{display:flex;align-items:center;padding:20px 0 16px;border-bottom:1px solid var(--border);margin-bottom:24px;gap:12px;}
.dh-orb{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#C4964A);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:700;font-family:"Cormorant Garamond",serif;flex-shrink:0;}
.dh-title{font-family:"Cormorant Garamond",serif;font-size:1.25rem;font-weight:600;color:var(--ink);}
.dh-sub{font-size:.7rem;color:var(--muted-l);letter-spacing:.05em;}
.step-card{background:var(--surf);border:1px solid var(--border);border-radius:16px;padding:22px 26px;margin-bottom:16px;box-shadow:0 2px 10px rgba(156,122,69,.05);}
.step-label{font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:14px;display:flex;align-items:center;gap:8px;}
.step-label::before{content:'';display:block;width:18px;height:1px;background:var(--gold);opacity:.5;}
.dna-tag{display:inline-block;background:var(--gold-dim);border:1px solid var(--border-h);border-radius:999px;padding:3px 12px;font-size:.8rem;color:var(--gold);margin:3px 4px;}
.phrase-box{background:var(--surf2);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin:6px 0;font-size:.9rem;color:var(--ink-m);font-style:italic;}
/* 分析中转圈 */
@keyframes spin{to{transform:rotate(360deg);}}
@keyframes pulse-ring{0%,100%{opacity:.4;transform:scale(1);}50%{opacity:.9;transform:scale(1.08);}}
.analyzing-wrap{display:flex;flex-direction:column;align-items:center;padding:40px 0 32px;gap:20px;}
.spin-ring{width:56px;height:56px;border-radius:50%;border:3px solid var(--gold-dim);border-top:3px solid var(--gold);animation:spin 1s linear infinite;}
.analyzing-title{font-family:"Cormorant Garamond",serif;font-size:1.25rem;font-weight:600;color:var(--ink);}
.analyzing-sub{font-size:.85rem;color:var(--muted-l);text-align:center;line-height:1.6;}
/* 成功卡片 */
.success-banner{background:linear-gradient(135deg,#FEFCF7,#FAF5EC);
  border:1.5px solid var(--border-h);border-radius:16px;padding:22px 26px;
  margin-bottom:16px;box-shadow:0 4px 20px var(--gold-glow);}
.success-title{font-family:"Cormorant Garamond",serif;font-size:1.15rem;font-weight:600;
  color:var(--gold);margin-bottom:4px;}
.success-sub{font-size:.85rem;color:var(--muted-l);margin-bottom:16px;}
/* 按钮 */
div.stButton>button{border-radius:10px!important;font-family:"Noto Sans SC",sans-serif!important;font-size:.9rem!important;font-weight:500!important;padding:10px 22px!important;border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;transition:all .18s!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;box-shadow:0 4px 16px var(--gold-glow)!important;font-size:.95rem!important;padding:13px 28px!important;}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

PERSONA_OUTPUT = _BASE / "outputs" / "wechat_persona.json"
PERSONA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
SKILL_PATH = _BASE / "skills" / "WECHAT01-style-analysis.md"


# ── 顶栏 ──────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='dh-topbar'>"
    "<div class='dh-orb'>念</div>"
    "<div><div class='dh-title'>数字人 · 聊天记录分析</div>"
    "<div class='dh-sub'>Digital Human · Style Analysis</div></div>"
    "</div>",
    unsafe_allow_html=True,
)

nav_c1, nav_c2, _ = st.columns([1.2, 1.2, 5])
with nav_c1:
    if st.button("返回主页", use_container_width=True):
        st.session_state["main_section"] = "home"
        st.switch_page("app.py")
with nav_c2:
    if st.button("进入对话", use_container_width=True):
        st.switch_page("pages/dialogue.py")

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:.92rem;color:var(--muted-l);line-height:1.7;margin-bottom:20px;'>"
    "上传微信聊天记录，AI 将自动提取 TA 的说话风格，为数字人注入灵魂。"
    "支持 CSV（WeChatMsg/留痕）、JSON、TXT 三种格式。"
    "</div>",
    unsafe_allow_html=True,
)

# ── session_state 初始化 ──────────────────────────────────────────────────────
st.session_state.setdefault("wi_analyzing",  False)   # 正在分析
st.session_state.setdefault("wi_done",       False)   # 分析完成
st.session_state.setdefault("wi_error",      "")      # 错误信息
st.session_state.setdefault("wi_target",     "")      # 本次分析的姓名
st.session_state.setdefault("wi_msg_count",  0)

# 如果从 dialogue 页面返回，保持 done 状态（session_state 会保留）


# ── 解析函数 ──────────────────────────────────────────────────────────────────
def parse_wechat_file(file_bytes: bytes, filename: str, target: str) -> List[Dict]:
    messages: List[Dict] = []
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            sender    = row.get("StrTalker") or row.get("sender") or row.get("NickName", "")
            is_sender = str(row.get("IsSender", "0"))
            msg_type  = str(row.get("Type", "1"))
            content   = row.get("StrContent") or row.get("content", "")
            if is_sender == "0" and msg_type == "1" and target in sender and content.strip():
                messages.append({"sender": sender, "content": content.strip(),
                                  "timestamp": row.get("CreateTime", "")})
    elif ext == "json":
        data = json.loads(file_bytes.decode("utf-8", errors="replace"))
        # 兼容多种 JSON 结构：顶层列表 / messages键 / msg键 / 嵌套dict
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # xwechat 可能把聊天记录放在任何一个列表值里
            items = (data.get("messages") or data.get("msg") or
                     data.get("records") or data.get("data") or [])
            if not items:
                # 尝试找第一个 list 类型的值
                for v in data.values():
                    if isinstance(v, list) and v:
                        items = v
                        break
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            # 优先用标准字段，兼容 WeChatMsg/xwechat 导出的字段名
            sender  = (item.get("sender") or item.get("from") or
                       item.get("NickName") or item.get("talker") or
                       item.get("StrTalker") or "")
            content = (item.get("content") or item.get("text") or
                       item.get("StrContent") or item.get("msg") or "")
            ts      = (item.get("timestamp") or item.get("CreateTime") or
                       item.get("createTime") or item.get("time") or "")
            is_sender = str(item.get("IsSender", item.get("isSender", "")))
            msg_type  = str(item.get("Type", item.get("type", "1")))

            # xwechat IsSender==1 表示自己发的消息，0 表示对方
            # 若有 IsSender 字段，只取 IsSender==0（对方消息）
            if is_sender == "1":
                continue
            # 过滤非文字消息（Type!=1 通常是图片/语音等）
            if is_sender == "0" and msg_type not in ("1", ""):
                continue

            content = str(content).strip()
            if not content:
                continue
            # 姓名为空时接受所有消息（用户可能上传单人聊天导出）
            if not target or target in sender:
                messages.append({"sender": sender, "content": content, "timestamp": str(ts)})
    elif ext == "txt":
        text = file_bytes.decode("utf-8", errors="replace")
        pattern = re.compile(
            r'(?:\[([^\]]+)\]\s+)?([^\n:：\(]+)[：:\(]\s*([^\n]+(?:\n(?!\[|\d{4})[^\n]+)*)',
            re.MULTILINE,
        )
        for m in pattern.finditer(text):
            sender  = m.group(2).strip()
            content = m.group(3).strip()
            if (not target or target in sender) and content:
                messages.append({"sender": sender, "content": content,
                                  "timestamp": m.group(1) or ""})
    return messages


# ══════════════════════════════════════════════════════════════════════════════
# 状态 A：分析完成 → 展示结果 + 进入对话
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["wi_done"] and st.session_state.get("persona_dna"):
    _dna  = st.session_state["persona_dna"]
    _name = st.session_state.get("persona_name", "TA")

    # 成功横幅
    st.markdown(
        f"<div class='success-banner'>"
        f"<div class='success-title'>风格档案已生成 · {_name}</div>"
        f"<div class='success-sub'>共分析 {st.session_state['wi_msg_count']} 条消息 · 数字人已就绪</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 主 CTA
    if st.button("进入数字人对话", type="primary", use_container_width=True, key="goto_dialogue_done"):
        st.switch_page("pages/dialogue.py")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # 风格详情展示
    with st.expander("查看风格分析详情", expanded=True):
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("情感基调", _dna.get("tone", "-"))
            st.metric("幽默程度", f"{_dna.get('humor_level', '-')} / 5")
        with m2:
            st.metric("句子风格", _dna.get("avg_sentence_length", "-"))
            st.metric("分析置信度", _dna.get("confidence", "-"))
        with m3:
            st.metric("回应风格", _dna.get("response_style", "-"))
            habits = str(_dna.get("special_habits", "-"))
            st.metric("特殊习惯", habits[:12] + "…" if len(habits) > 12 else habits)

        st.markdown("<br>**常用词 / 口头禅**", unsafe_allow_html=True)
        tags_html = "".join(
            f"<span class='dna-tag'>{kw}</span>"
            for kw in _dna.get("speech_patterns", [])
        )
        st.markdown(tags_html or "<span style='color:var(--muted-l)'>暂无</span>", unsafe_allow_html=True)

        phrases = _dna.get("signature_phrases", [])
        if phrases:
            st.markdown("<br>**标志性句式**", unsafe_allow_html=True)
            for phrase in phrases:
                st.markdown(f"<div class='phrase-box'>「{phrase}」</div>", unsafe_allow_html=True)

    st.markdown("---")
    # 重新上传入口
    if st.button("重新上传聊天记录", use_container_width=False, key="re_upload"):
        for k in ("wi_done", "wi_analyzing", "wi_error", "wi_target", "wi_msg_count",
                  "persona_dna", "persona_name"):
            st.session_state.pop(k, None)
        PERSONA_OUTPUT.unlink(missing_ok=True)
        st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# 已有历史档案（首次进入且文件已存在）
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state["wi_analyzing"] and PERSONA_OUTPUT.exists():
    try:
        saved = json.loads(PERSONA_OUTPUT.read_text(encoding="utf-8"))
        _saved_dna  = saved.get("persona_dna")
        _saved_name = saved.get("target_name")
        if _saved_dna and _saved_name:
            st.session_state.setdefault("persona_dna",  _saved_dna)
            st.session_state.setdefault("persona_name", _saved_name)
            st.session_state.setdefault("wi_msg_count", saved.get("message_count", 0))
            st.markdown(
                f"<div class='success-banner'>"
                f"<div class='success-title'>检测到已保存的风格档案 · {_saved_name}</div>"
                f"<div class='success-sub'>共 {saved.get('message_count','?')} 条消息 · 可直接进入对话</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            _cc1, _cc2 = st.columns(2)
            with _cc1:
                if st.button("直接进入对话", type="primary", use_container_width=True, key="use_saved"):
                    st.session_state["wi_done"] = True
                    st.switch_page("pages/dialogue.py")
            with _cc2:
                if st.button("重新上传聊天记录", use_container_width=True, key="discard_saved"):
                    PERSONA_OUTPUT.unlink(missing_ok=True)
                    for k in ("persona_dna", "persona_name", "wi_done", "wi_msg_count"):
                        st.session_state.pop(k, None)
                    st.rerun()
            st.markdown("---")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 状态 B：上传表单
# ══════════════════════════════════════════════════════════════════════════════

# ── Step 0：角色基本信息（上传前填写）────────────────────────────────────────
st.markdown("<div class='step-card'>", unsafe_allow_html=True)
st.markdown("<div class='step-label'>Step 1 · 填写角色信息</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:.85rem;color:var(--muted-l);margin-bottom:14px;'>"
    "帮助 AI 更准确地还原人物性格，越详细效果越好</div>",
    unsafe_allow_html=True,
)

target_name = st.text_input(
    "姓名 / 称谓",
    placeholder="例：爸爸 · 张伟 · 奶奶 — 也用于从聊天记录中筛选发言",
    key="wi_target_input",
)
role_extra = st.text_area(
    "角色补充描述（可选）",
    placeholder="例：50岁，温和幽默，爱开玩笑，常聊工作和家里的事，说话直接不绕弯子，偶尔用方言词汇",
    key="wi_role_extra",
    height=88,
)
st.markdown("</div>", unsafe_allow_html=True)

# ── Step 1（原）：文件上传 ────────────────────────────────────────────────────
st.markdown("<div class='step-card'>", unsafe_allow_html=True)
st.markdown("<div class='step-label'>Step 2 · 上传聊天记录</div>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "拖拽文件到此，或点击选择",
    type=["csv", "json", "txt"],
    label_visibility="collapsed",
    key="wi_uploader",
)
_legacy_target_compat = target_name  # 兼容下方解析逻辑
st.markdown("</div>", unsafe_allow_html=True)

# ── 解析 & 预览 ────────────────────────────────────────────────────────────────
raw_messages: List[Dict] = []
if uploaded_file:
    raw_messages = parse_wechat_file(uploaded_file.getvalue(), uploaded_file.name, target_name.strip())

    st.markdown("<div class='step-card'>", unsafe_allow_html=True)
    st.markdown("<div class='step-label'>Step 3 · 解析预览</div>", unsafe_allow_html=True)

    if raw_messages:
        _name_label = target_name.strip() or "全部发言人"
        st.success(f"共提取到 **{len(raw_messages)}** 条发言")
        with st.expander("预览前 10 条消息"):
            for msg in raw_messages[:10]:
                ts = f"[{msg['timestamp']}] " if msg.get("timestamp") else ""
                st.markdown(f"<div class='phrase-box'>{ts}{msg['content']}</div>",
                            unsafe_allow_html=True)
        if len(raw_messages) < 5:
            st.warning("消息数量过少，建议 50 条以上以获得更准确分析")
    else:
        st.warning(
            f"未找到{'「' + target_name.strip() + '」的' if target_name.strip() else ''}发言，"
            "请检查姓名是否与文件中一致，或留空姓名提取所有发言"
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ── 开始分析按钮（只要有消息就显示）────────────────────────────────────────────
if raw_messages and len(raw_messages) >= 3:
    st.markdown("<div class='step-card'>", unsafe_allow_html=True)
    st.markdown("<div class='step-label'>Step 4 · AI 风格分析</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:.9rem;color:var(--muted-l);margin-bottom:16px;'>"
        f"将对 <b>{len(raw_messages)}</b> 条消息进行分析，提取说话风格、口头禅、情感基调等特征。"
        f"预计耗时 20–40 秒。</div>",
        unsafe_allow_html=True,
    )

    if st.button("开始 AI 风格分析", type="primary", key="btn_analyze", use_container_width=True):
        st.markdown(
            "<div class='analyzing-wrap'>"
            "<div class='spin-ring'></div>"
            "<div class='analyzing-title'>AI 正在分析说话风格…</div>"
            "<div class='analyzing-sub'>正在提取口头禅、情感基调、句式习惯<br>请稍候，约 20–40 秒</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        sample = raw_messages[-300:] if len(raw_messages) > 300 else raw_messages
        sample_text = "\n".join(m["content"] for m in sample)
        _tname = target_name.strip() or "目标人物"
        _extra = st.session_state.get("wi_role_extra", "").strip()

        prompt = load_skill(str(SKILL_PATH))
        payload = {
            "target_name": _tname,
            "messages": sample_text,
            "message_count": len(raw_messages),
        }
        if _extra:
            payload["role_description"] = _extra

        result = call_skill("WECHAT01", prompt, payload)

        if result.get("error"):
            st.session_state["wi_error"] = result.get("message", "未知错误")
            st.error(f"分析失败：{st.session_state['wi_error']}")
        else:
            save_data = {
                "target_name": _tname,
                "role_description": _extra,
                "persona_dna": result,
                "message_count": len(raw_messages),
            }
            PERSONA_OUTPUT.write_text(
                json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            st.session_state["persona_dna"]   = result
            st.session_state["persona_name"]  = _tname
            st.session_state["wi_done"]       = True
            st.session_state["wi_msg_count"]  = len(raw_messages)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
elif uploaded_file and raw_messages and len(raw_messages) < 3:
    st.info("消息数量不足 3 条，无法进行分析。请检查文件内容或修改姓名筛选条件。")
