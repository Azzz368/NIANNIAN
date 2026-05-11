
target = r"d:\ustASSIGNMENT\HKGAI\4.1念念集成项目\skillslayersDemo\memorial-pipeline-test\pages\pipeline.py"

code = '''\
# NianNian Memorial Studio \u2013 \u5236\u4f5c\u53f0\uff08MV01-MV03 AI \u5bf9\u8bdd\u5f0f\uff09
import json
from pathlib import Path
from typing import Dict, List
import streamlit as st
import gate_manager
import pipeline_runner
from llm_client import (
    call_freeform, call_structured,
    build_scene_prompts, generate_image_302, generate_video_302,
)

st.set_page_config(page_title="\u5ff5\u5ff5 \u00b7 \u5236\u4f5c\u53f0", layout="wide", initial_sidebar_state="collapsed")
BASE_DIR = Path(__file__).resolve().parent.parent

_CSS = """<style>
@import url(\'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,600&family=Noto+Sans+SC:wght@300;400;500;700&family=Noto+Serif+SC:wght@400;500;600&display=swap\');
:root{--bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;--border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);--gold:#9C7A45;--gold-l:#B8934F;--gold-dim:rgba(156,122,69,.08);--gold-glow:rgba(156,122,69,.18);--ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;--green:#5A9A72;}
html,body,[class*="css"]{font-family:\'Noto Sans SC\',sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;font-size:16px!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
[data-testid="stSidebarNav"],section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:820px!important;padding:0 20px 120px!important;margin:0 auto!important;}
.pp-topbar{display:flex;align-items:center;justify-content:space-between;padding:22px 0 20px;border-bottom:1px solid var(--border);margin-bottom:28px;}
.pp-logo{display:flex;align-items:center;gap:12px;}
.pp-logo-orb{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#B8934F);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;font-family:\'Cormorant Garamond\',serif;}
.pp-logo-name{font-family:\'Cormorant Garamond\',serif;font-size:1.3rem;font-weight:600;color:var(--ink);}
.pp-logo-sub{font-size:.72rem;color:var(--muted-l);letter-spacing:.05em;}
.pp-progress{display:flex;align-items:center;gap:8px;margin-bottom:32px;}
.pp-pill{display:flex;align-items:center;gap:7px;padding:7px 16px;border-radius:999px;font-size:.8rem;font-weight:500;background:var(--surf2);border:1px solid var(--border);color:var(--muted-l);}
.pp-pill.active{background:var(--surf3);border-color:var(--border-h);color:var(--gold);font-weight:700;}
.pp-pill.done{color:var(--green);border-color:rgba(90,154,114,.3);background:rgba(90,154,114,.06);}
.pp-pill-num{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;background:var(--surf);border:1px solid var(--border);color:var(--muted-l);}
.pp-pill.active .pp-pill-num{background:var(--gold);border-color:var(--gold);color:#fff;}
.pp-pill.done .pp-pill-num{background:var(--green);border-color:var(--green);color:#fff;}
.pp-divider{flex:1;height:1px;background:var(--border);max-width:40px;}
.nn-chat-wrap{display:flex;flex-direction:column;gap:20px;padding-bottom:8px;}
.nn-chat-ai{display:flex;align-items:flex-start;gap:12px;}
.nn-ai-avatar{width:42px;height:42px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#C4964A 0%,#E8C57A 50%,#9C7A45 100%);background-size:200% 200%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;font-family:\'Cormorant Garamond\',serif;box-shadow:0 2px 12px rgba(156,122,69,.28);animation:avatar-grad 6s ease infinite;}
@keyframes avatar-grad{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.nn-ai-bubble-wrap{display:flex;flex-direction:column;gap:4px;flex:1;}
.nn-ai-name{font-size:.72rem;font-weight:700;color:var(--gold);letter-spacing:.05em;}
.nn-ai-bubble{background:var(--surf);border:1px solid var(--border);border-radius:4px 20px 20px 20px;padding:16px 20px;font-size:1rem;line-height:1.78;color:var(--ink);box-shadow:0 2px 12px rgba(0,0,0,.05);white-space:pre-wrap;}
.nn-chat-user{display:flex;justify-content:flex-end;}
.nn-user-bubble{background:var(--gold);color:#fff;border-radius:20px 4px 20px 20px;padding:14px 20px;max-width:70%;font-size:1rem;line-height:1.7;box-shadow:0 2px 12px rgba(156,122,69,.28);}
@keyframes orb-pulse{0%,100%{transform:scale(1);}50%{transform:scale(1.1);}}
@keyframes ring-out{0%{transform:scale(1);opacity:.6;}100%{transform:scale(2.1);opacity:0;}}
@keyframes dot-bounce{0%,80%,100%{transform:translateY(0);opacity:.35;}40%{transform:translateY(-7px);opacity:1;}}
@keyframes grad-shift{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.nn-think-row{display:flex;align-items:flex-start;gap:12px;margin-bottom:20px;}
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
.scene-card{background:var(--surf);border:1px solid var(--border);border-radius:16px;padding:20px 24px;margin-bottom:12px;box-shadow:0 1px 8px rgba(0,0,0,.04);}
.scene-num{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:var(--gold);color:#fff;font-size:.78rem;font-weight:700;flex-shrink:0;}
.scene-title{font-weight:700;font-size:1rem;color:var(--ink);}
.scene-time{font-size:.78rem;color:var(--muted-l);}
.scene-desc{font-size:.92rem;color:var(--ink-m);line-height:1.7;margin-top:8px;}
.scene-narr{font-size:.88rem;color:var(--muted-l);font-style:italic;line-height:1.65;margin-top:6px;padding:10px 14px;background:var(--bg2);border-radius:10px;}
div.stButton>button{border-radius:999px!important;font-family:\'Noto Sans SC\',sans-serif!important;font-size:.9rem!important;font-weight:600!important;padding:10px 22px!important;transition:all .2s!important;border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;color:var(--ink)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;border-color:var(--gold-l)!important;}
[data-testid="stChatInput"]{max-width:820px!important;margin:0 auto!important;padding:0!important;}
[data-testid="stChatInput"] > div{background:#fff!important;border:1.5px solid var(--border-h)!important;border-radius:999px!important;box-shadow:none!important;padding:4px 6px 4px 20px!important;}
[data-testid="stChatInput"] > div > div{background:#fff!important;border:none!important;box-shadow:none!important;padding:0!important;}
[data-testid="stChatInput"] textarea{background:#fff!important;border:none!important;outline:none!important;box-shadow:none!important;font-size:.95rem!important;color:var(--ink)!important;padding:10px 0!important;resize:none!important;}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted)!important;font-style:italic!important;}
[data-testid="stChatInput"] button{all:unset!important;cursor:pointer!important;width:32px!important;height:32px!important;border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;flex-shrink:0!important;}
[data-testid="stChatInput"] button:hover{background:var(--gold-dim)!important;}
[data-testid="stChatInput"] button svg{fill:var(--gold)!important;stroke:var(--gold)!important;width:16px!important;height:16px!important;}
[data-testid="stAlert"]{background:var(--surf2)!important;border-radius:12px!important;border:1px solid var(--border)!important;}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

_THINK_HTML = (
    "<div class=\'nn-think-row\'>"
    "<div class=\'nn-think-avatar-wrap\'>"
    "<div class=\'nn-think-orb\'></div>"
    "<div class=\'nn-think-ring\'></div>"
    "<div class=\'nn-think-ring nn-think-ring-2\'></div>"
    "</div>"
    "<div class=\'nn-think-bubble\'>"
    "<div class=\'nn-think-dots\'><span></span><span></span><span></span></div>"
    "<div class=\'nn-think-label\'>\u5ff5\u5ff5\u6b63\u5728\u4e3a\u60a8\u5236\u4f5c\u5f71\u50cf\u65b9\u6848...</div>"
    "</div></div>"
)

_SUMMARY_SYS = (
    "\u4f60\u662f\u5ff5\u5ff5\u8ffd\u601d\u5f71\u50cf\u5236\u4f5c\u52a9\u624b\uff0c\u5e2e\u5bb6\u5c5e\u7528\u6700\u6e29\u67d4\u53e3\u8bed\u5316\u7684\u4e2d\u6587\u63cf\u8ff0\u5f71\u50cf\u5236\u4f5c\u8fdb\u5c55\u3002"
    "\u6536\u5230 JSON \u6570\u636e\u540e\uff0c\u7528 100-150 \u5b57\u7684\u81ea\u7136\u8bed\u8a00\u3001\u5206\u6bb5\uff0c\u544a\u8bc9\u5bb6\u5c5e\uff1a\u6211\u4eec\u4e86\u89e3\u4e86\u54ea\u4e9b\u4fe1\u606f\uff0c"
    "\u5f71\u50cf\u4f1a\u5448\u73b0\u4ec0\u4e48\u6837\u7684\u611f\u89c9\u3002\u4e0d\u8981\u51fa\u73b0\u4efb\u4f55\u6280\u672f\u8bcd\u6c47\u3001\u5b57\u6bb5\u540d\u3001JSON\u3002\u8bed\u6c14\u6e29\u6696\u8d34\u5fc3\u3002"
)

_SCENE_SYS = (
    "\u4f60\u662f\u5ff5\u5ff5\u8ffd\u601d\u5f71\u50cf\u5236\u4f5c\u52a9\u624b\u3002\u6839\u636e\u5206\u955c JSON\uff0c\u7528\u6700\u901a\u4fd7\u81ea\u7136\u7684\u4e2d\u6587\uff0c"
    "\u4e3a\u6bcf\u4e2a\u5206\u955c\u5199\u4e00\u53e5\u8bdd\u63cf\u8ff0\uff0820-40\u5b57\uff09\uff0c\u8bf4\u660e\u8fd9\u4e2a\u955c\u5934\u4f1a\u5448\u73b0\u4ec0\u4e48\u753b\u9762\u548c\u611f\u53d7\u3002"
    "\u683c\u5f0f\uff1a\u6bcf\u884c\u4e00\u4e2a\u955c\u5934\uff0c\u524d\u9762\u52a0\u5e8f\u53f7\u3002\u4e0d\u8981\u4efb\u4f55 JSON \u6216\u6280\u672f\u8bcd\u6c47\u3002"
)

_MODIFY_SYS = (
    "\u4f60\u662f\u8ffd\u601d\u5f71\u50cf\u5206\u955c\u8c03\u6574\u52a9\u624b\u3002\u6839\u636e\u7528\u6237\u7684\u4fee\u6539\u610f\u89c1\uff0c\u5bf9\u5206\u955c JSON \u8fdb\u884c\u8c03\u6574\u5e76\u8f93\u51fa\uff1a"
    "1) updated_scenes: \u66f4\u65b0\u540e\u7684\u5b8c\u6574\u5206\u955c\u5217\u8868\uff08\u4fdd\u7559\u539f\u6709\u5b57\u6bb5\u7ed3\u6784\uff09"
    "2) reply: \u4e00\u53e5\u6e29\u67d4\u7684\u786e\u8ba4\u56de\u590d\uff0830-60\u5b57\uff09"
    "\u53ea\u8f93\u51fa\u5408\u6cd5 JSON\uff0c\u5305\u542b\u8fd9\u4e24\u4e2a\u5b57\u6bb5\u3002"
)


def _init():
    defaults = {
        "pipe_phase": "idle",
        "pipe_chat": [],
        "pipe_scenes": [],
        "pipe_scene_images": {},
        "pipe_scene_vidprompts": {},
        "pipe_scene_videos": {},
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init()


def _bubble_ai(content):
    return (
        "<div class=\'nn-chat-ai\'><div class=\'nn-ai-avatar\'>\u5ff5</div>"
        "<div class=\'nn-ai-bubble-wrap\'><div class=\'nn-ai-name\'>\u5ff5\u5ff5 AI</div>"
        f"<div class=\'nn-ai-bubble\'>{content}</div></div></div>"
    )

def _bubble_user(content):
    return f"<div class=\'nn-chat-user\'><div class=\'nn-user-bubble\'>{content}</div></div>"

def _scenes_to_list(scenes) -> List[Dict]:
    if isinstance(scenes, list):
        return [s for s in scenes if isinstance(s, dict)]
    if isinstance(scenes, dict):
        return [scenes[k] for k in sorted(scenes.keys()) if isinstance(scenes[k], dict)]
    return []

def _friendly_summary(mv_id: str, output: dict) -> str:
    try:
        return call_freeform(_SUMMARY_SYS, json.dumps(output, ensure_ascii=False))
    except Exception as e:
        return f"{mv_id} \u4fe1\u606f\u5df2\u6574\u7406\u5b8c\u6210\u3002"

def _scene_descriptions(scenes: List[Dict]) -> str:
    try:
        return call_freeform(_SCENE_SYS, json.dumps(scenes, ensure_ascii=False))
    except:
        return "\\n".join(
            f"{i+1}. {s.get(\'description\', \'(\u6682\u65e0\u63cf\u8ff0)\')}"
            for i, s in enumerate(scenes)
        )


def run_pipeline():
    chat = st.session_state["pipe_chat"]
    mv01_input = {}
    if "mv01_intake_json" in st.session_state:
        try:
            mv01_input = json.loads(st.session_state["mv01_intake_json"])
        except:
            pass
    if not mv01_input:
        p = pipeline_runner.read_output("MV01")
        if p: mv01_input = p
    if mv01_input:
        pipeline_runner.save_output("MV01", mv01_input)
        gate_manager.approve("MV01")
        chat.append({"role": "ai", "content": _friendly_summary("MV01", mv01_input)})
    else:
        chat.append({"role": "ai", "content": "\u6682\u65f6\u6ca1\u6709\u627e\u5230\u60a8\u586b\u5199\u7684\u4fe1\u606f\uff0c\u8bf7\u8fd4\u56de\u9996\u9875\u91cd\u65b0\u586b\u5199\u3002"})
        st.session_state["pipe_phase"] = "done"
        return
    try:
        pipeline_runner.run_step("MV02")
        gate_manager.approve("MV02")
        mv02_out = pipeline_runner.read_output("MV02") or {}
        chat.append({"role": "ai", "content": _friendly_summary("MV02", mv02_out)})
    except Exception as e:
        chat.append({"role": "ai", "content": "\u4fe1\u606f\u6838\u5bf9\u5df2\u5b8c\u6210\uff0c\u6211\u4eec\u7ee7\u7eed\u4e3a\u60a8\u89c4\u5212\u5f71\u50cf\u5206\u955c\u3002"})
    try:
        pipeline_runner.run_step("MV03")
        gate_manager.approve("MV03")
        mv03_out = pipeline_runner.read_output("MV03") or {}
        scenes = _scenes_to_list(mv03_out.get("scenes", []))
        st.session_state["pipe_scenes"] = scenes
        st.session_state["_mv03_out"] = mv03_out
        if scenes:
            scene_desc = _scene_descriptions(scenes)
            chat.append({
                "role": "ai",
                "content": (
                    "\u597d\u7684\uff01\u6211\u5df2\u7ecf\u4e3a\u60a8\u89c4\u5212\u4e86\u5f71\u50cf\u7684\u5206\u955c\u6545\u4e8b\uff0c\u5171\u6709 {} \u4e2a\u753b\u9762\u3002\n\n"
                    "\u6bcf\u4e2a\u753b\u9762\u7684\u6784\u60f3\u662f\u8fd9\u6837\u7684\uff1a\n\n{}\n\n"
                    "\u60a8\u53ef\u4ee5\u5728\u4e0b\u65b9\u544a\u8bc9\u6211\u54ea\u91cc\u9700\u8981\u8c03\u6574\uff0c\u6216\u8005\u70b9\u51fb\u753b\u9762\u5361\u7247\u751f\u6210\u9884\u89c8\u56fe\u3002"
                ).format(len(scenes), scene_desc)
            })
        else:
            chat.append({"role": "ai", "content": "\u5f71\u50cf\u6846\u67b6\u5df2\u89c4\u5212\u5b8c\u6210\uff0c\u8bf7\u5f80\u4e0b\u67e5\u770b\u5206\u955c\u8be6\u60c5\u3002"})
    except Exception as e:
        chat.append({"role": "ai", "content": f"\u5206\u955c\u89c4\u5212\u9047\u5230\u4e86\u95ee\u9898\uff0c\u8bf7\u544a\u8bc9\u6211\u60f3\u8981\u7684\u753b\u9762\u98ce\u683c\uff0c\u6211\u6765\u91cd\u65b0\u89c4\u5212\u3002\uff08{e}\uff09"})
    st.session_state["pipe_phase"] = "done"


def render_topbar():
    st.markdown(
        "<div class=\'pp-topbar\'>"
        "<div class=\'pp-logo\'>"
        "<div class=\'pp-logo-orb\'>\u5ff5</div>"
        "<div><div class=\'pp-logo-name\'>\u5ff5\u5ff5</div>"
        "<div class=\'pp-logo-sub\'>NianNian Memorial Studio</div></div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    _, col_r = st.columns([4, 1])
    with col_r:
        if st.button("\u8fd4\u56de\u4fee\u6539\u4fe1\u606f", use_container_width=True):
            st.switch_page("app.py")


def render_progress():
    phase = st.session_state["pipe_phase"]
    scenes = st.session_state["pipe_scenes"]
    has_any_img = any(st.session_state["pipe_scene_images"].get(s.get("scene_id","")) for s in scenes)
    s1 = "done" if phase == "done" else "active"
    s2 = "done" if (phase == "done" and scenes) else ("active" if phase == "done" else "")
    s3 = "done" if has_any_img else ""
    pills = [("1", "\u4fe1\u606f\u6574\u7406", s1), ("2", "\u5206\u955c\u89c4\u5212", s2), ("3", "\u9884\u89c8\u751f\u6210", s3)]
    html = "<div class=\'pp-progress\'>"
    for i, (num, lbl, cls) in enumerate(pills):
        if i > 0: html += "<div class=\'pp-divider\'></div>"
        html += f"<div class=\'pp-pill {cls}\'><span class=\'pp-pill-num\'>{num}</span><span>{lbl}</span></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_scene_cards():
    scenes = st.session_state["pipe_scenes"]
    mv03_out = st.session_state.get("_mv03_out", {})
    character_bible = mv03_out.get("character_bible", {}) if isinstance(mv03_out, dict) else {}
    scene_library = mv03_out.get("scene_library", []) if isinstance(mv03_out, dict) else []
    if not scenes:
        return
    st.markdown(
        "<div style=\'margin:28px 0 16px;\'>"
        "<div style=\'font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:8px;\'>\u5206\u955c\u9884\u89c8</div>"
        "<div style=\'font-family:\"Cormorant Garamond\",\"Noto Serif SC\",serif;font-size:1.5rem;font-weight:600;color:var(--ink);\'>\u5f71\u50cf\u5206\u955c\u6545\u4e8b\u677f</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id") or f"scene_{i+1:02d}"
        timecode = scene.get("time") or scene.get("timecode") or ""
        shot = scene.get("shot_type") or ""
        desc = scene.get("description") or ""
        narr = scene.get("voice_script") or scene.get("narration") or ""
        prompt_raw = scene.get("mj_prompt") or scene.get("prompt_global") or desc
        imgs = st.session_state["pipe_scene_images"].get(sid, [])
        time_shot = " \u00b7 ".join(filter(None, [timecode, shot]))
        st.markdown(
            f"<div class=\'scene-card\'>"
            f"<div style=\'display:flex;align-items:center;gap:10px;margin-bottom:6px;\'>"
            f"<span class=\'scene-num\'>{i+1}</span>"
            f"<span class=\'scene-title\'>{sid}</span>"
            f"<span class=\'scene-time\'>{time_shot}</span>"
            f"</div>"
            f"<div class=\'scene-desc\'>{desc}</div>"
            + (f"<div class=\'scene-narr\'>\u300c{narr}\u300d</div>" if narr else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        if imgs:
            img_cols = st.columns(min(len(imgs), 3), gap="small")
            for j, b64 in enumerate(imgs[:3]):
                with img_cols[j]:
                    st.image("data:image/png;base64," + b64, use_container_width=True)
                    vid_prompt = st.session_state["pipe_scene_vidprompts"].get(sid, "")
                    vr = st.session_state["pipe_scene_videos"].get(f"{sid}_{j}")
                    if vr and vr.get("url"):
                        st.video(vr["url"])
                    elif vr and vr.get("task_id") and not vr.get("url"):
                        if st.button("\u67e5\u8be2\u89c6\u9891\u8fdb\u5ea6", key=f"qvid_{sid}_{j}", use_container_width=True):
                            import requests as _rq
                            from llm_client import _302_API_KEY as _AK
                            _pr = _rq.get(f"https://api.302.ai/klingai/task/{vr[\'task_id\']}/fetch",
                                headers={"Authorization": f"Bearer {_AK}"}, timeout=20)
                            _pd = _pr.json().get("data", {})
                            _ws = _pd.get("works") or _pd.get("taskWorks") or []
                            if _pd.get("status") == 99 and _ws:
                                _vurl = (_ws[0].get("resource") or {}).get("resource") or ""
                                st.session_state["pipe_scene_videos"][f"{sid}_{j}"] = {"url": _vurl, "task_id": vr["task_id"]}
                                st.rerun()
                            else:
                                st.info(f"\u751f\u6210\u4e2d\uff0c\u72b6\u6001\uff1a{_pd.get(\'status\', \'?\')}")
                    elif vid_prompt:
                        if st.button("\u751f\u6210\u89c6\u9891", key=f"genvid_{sid}_{j}", use_container_width=True):
                            with st.spinner("\u63d0\u4ea4\u53ef\u7075\u4efb\u52a1..."):
                                vr2 = generate_video_302(vid_prompt, image_url="data:image/png;base64," + imgs[j], duration=5, poll=False)
                            st.session_state["pipe_scene_videos"][f"{sid}_{j}"] = vr2
                            st.rerun()
        gen_col, _ = st.columns([1, 3])
        with gen_col:
            if st.button("\u91cd\u65b0\u751f\u6210\u56fe\u7247" if imgs else "\u751f\u6210\u9884\u89c8\u56fe",
                         key=f"genimg_{sid}", use_container_width=True):
                with st.spinner(f"AI \u6b63\u5728\u7ed8\u5236\u7b2c {i+1} \u4e2a\u753b\u9762..."):
                    try:
                        prompts = build_scene_prompts(scene, character_bible, scene_library)
                        smart_img = prompts.get("image_prompt") or prompt_raw
                        smart_vid = prompts.get("video_prompt") or desc
                        st.session_state["pipe_scene_vidprompts"][sid] = smart_vid
                        b64, err = generate_image_302(smart_img)
                        if b64:
                            cur = st.session_state["pipe_scene_images"].get(sid, [])
                            st.session_state["pipe_scene_images"][sid] = cur + [b64]
                            st.rerun()
                        else:
                            st.error(f"\u56fe\u7247\u751f\u6210\u5931\u8d25\uff1a{err}")
                    except Exception as ex:
                        st.error(str(ex))
        st.markdown("<div style=\'height:4px\'></div>", unsafe_allow_html=True)


# Main
render_topbar()
render_progress()
phase = st.session_state["pipe_phase"]
if phase == "idle":
    st.session_state["pipe_phase"] = "running"
    st.rerun()
if phase == "running":
    think_ph = st.empty()
    think_ph.markdown(_THINK_HTML, unsafe_allow_html=True)
    run_pipeline()
    think_ph.empty()
    st.rerun()
chat = st.session_state["pipe_chat"]
if chat:
    html = "<div class=\'nn-chat-wrap\'>"
    for m in chat:
        html += _bubble_ai(m["content"]) if m["role"] == "ai" else _bubble_user(m["content"])
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
if phase == "done":
    render_scene_cards()
    st.markdown("<div style=\'height:16px\'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style=\'font-size:.82rem;color:var(--muted-l);margin-bottom:8px;\'>"
        "\u60a8\u53ef\u4ee5\u5728\u4e0b\u65b9\u76f4\u63a5\u544a\u8bc9\u6211\u9700\u8981\u8c03\u6574\u7684\u5730\u65b9\uff0c"
        "\u4f8b\u5982\uff1a\u300c\u5220\u6389\u7b2c3\u4e2a\u955c\u5934\u300d\u300c\u628a\u98ce\u683c\u6539\u5f97\u66f4\u6e29\u6696\u4e00\u4e9b\u300d</div>",
        unsafe_allow_html=True,
    )
    user_msg = st.chat_input("\u544a\u8bc9\u5ff5\u5ff5\u60a8\u60f3\u4fee\u6539\u7684\u5730\u65b9...\u6309 Enter \u53d1\u9001")
    if user_msg and user_msg.strip():
        msg = user_msg.strip()
        chat.append({"role": "user", "content": msg})
        scenes = st.session_state["pipe_scenes"]
        mv03_out = st.session_state.get("_mv03_out", {})
        with st.spinner("\u5ff5\u5ff5\u6b63\u5728\u4fee\u6539\u5206\u955c..."):
            payload = {"current_scenes": scenes, "user_request": msg,
                       "project_info": {k: v for k, v in mv03_out.items() if k != "scenes"}}
            try:
                result = call_structured(_MODIFY_SYS, json.dumps(payload, ensure_ascii=False))
                new_scenes = result.get("updated_scenes")
                reply = result.get("reply", "\u597d\u7684\uff0c\u5df2\u6839\u636e\u60a8\u7684\u610f\u89c1\u8c03\u6574\u4e86\u5206\u955c\u3002")
                if new_scenes and isinstance(new_scenes, list):
                    st.session_state["pipe_scenes"] = new_scenes
                    mv03_out["scenes"] = {s.get("scene_id", f"scene_{i+1:02d}"): s for i, s in enumerate(new_scenes)}
                    st.session_state["_mv03_out"] = mv03_out
                    try: pipeline_runner.save_output("MV03", mv03_out)
                    except: pass
                    chat.append({"role": "ai", "content": reply})
                    st.session_state["pipe_scene_images"] = {}
                    st.session_state["pipe_scene_vidprompts"] = {}
                    st.session_state["pipe_scene_videos"] = {}
                else:
                    chat.append({"role": "ai", "content": reply or "\u597d\u7684\uff0c\u6211\u5df2\u4e86\u89e3\u60a8\u7684\u610f\u89c1\u3002"})
            except Exception as ex:
                chat.append({"role": "ai", "content": f"\u4fee\u6539\u9047\u5230\u4e86\u95ee\u9898\uff0c\u8bf7\u518d\u8bd5\u4e00\u6b21\u3002\uff08{ex}\uff09"})
        st.rerun()
'''

with open(target, 'w', encoding='utf-8') as f:
    f.write(code)

import ast
ast.parse(code)
print("Written and syntax OK, lines:", len(code.splitlines()))
