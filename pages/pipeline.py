# NianNian Memorial Studio – 前期确认台（MV01-MV03 AI 对话式）
import json
from pathlib import Path
from typing import Dict
import streamlit as st
import gate_manager
import pipeline_runner
from llm_client import call_freeform, call_structured

st.set_page_config(page_title='念念 · 制作台', layout='wide', initial_sidebar_state='collapsed')
BASE_DIR = Path(__file__).resolve().parent.parent

_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,600&family=Noto+Sans+SC:wght@300;400;500;700&family=Noto+Serif+SC:wght@400;500;600&display=swap');
:root{--bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;--border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);--gold:#9C7A45;--gold-l:#B8934F;--gold-dim:rgba(156,122,69,.08);--gold-glow:rgba(156,122,69,.18);--ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;--green:#5A9A72;}
html,body,[class*='css']{font-family:'Noto Sans SC',sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;font-size:16px!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
[data-testid='stSidebarNav'],section[data-testid='stSidebar'],[data-testid='collapsedControl']{display:none!important;}
.block-container{max-width:820px!important;padding:0 20px 120px!important;margin:0 auto!important;}
.pp-topbar{display:flex;align-items:center;justify-content:space-between;padding:22px 0 20px;border-bottom:1px solid var(--border);margin-bottom:28px;}
.pp-logo{display:flex;align-items:center;gap:12px;}
.pp-logo-orb{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#B8934F);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;font-family:'Cormorant Garamond',serif;}
.pp-logo-name{font-family:'Cormorant Garamond',serif;font-size:1.3rem;font-weight:600;color:var(--ink);}
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
.nn-ai-avatar{width:42px;height:42px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#C4964A 0%,#E8C57A 50%,#9C7A45 100%);background-size:200% 200%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;font-family:'Cormorant Garamond',serif;box-shadow:0 2px 12px rgba(156,122,69,.28);animation:avatar-grad 6s ease infinite;}
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
div.stButton>button{border-radius:999px!important;font-family:'Noto Sans SC',sans-serif!important;font-size:.9rem!important;font-weight:600!important;padding:10px 22px!important;transition:all .2s!important;border:1px solid var(--border)!important;background:var(--surf2)!important;color:var(--ink-m)!important;}
div.stButton>button:hover{border-color:var(--border-h)!important;color:var(--ink)!important;background:var(--surf3)!important;}
div.stButton>button[kind='primary']{background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;}
div.stButton>button[kind='primary']:hover{background:var(--gold-l)!important;border-color:var(--gold-l)!important;}
[data-testid='stChatInput']{max-width:820px!important;margin:0 auto!important;padding:0!important;}
[data-testid='stChatInput'] > div{background:#fff!important;border:1.5px solid var(--border-h)!important;border-radius:999px!important;box-shadow:none!important;padding:4px 6px 4px 20px!important;}
[data-testid='stChatInput'] > div > div{background:#fff!important;border:none!important;box-shadow:none!important;padding:0!important;}
[data-testid='stChatInput'] textarea{background:#fff!important;border:none!important;outline:none!important;box-shadow:none!important;font-size:.95rem!important;color:var(--ink)!important;padding:10px 0!important;resize:none!important;}
[data-testid='stChatInput'] textarea::placeholder{color:var(--muted)!important;font-style:italic!important;}
[data-testid='stChatInput'] button{all:unset!important;cursor:pointer!important;width:32px!important;height:32px!important;border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;flex-shrink:0!important;}
[data-testid='stChatInput'] button:hover{background:var(--gold-dim)!important;}
[data-testid='stChatInput'] button svg{fill:var(--gold)!important;stroke:var(--gold)!important;width:16px!important;height:16px!important;}
[data-testid='stAlert']{background:var(--surf2)!important;border-radius:12px!important;border:1px solid var(--border)!important;}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

_THINK_HTML = (
    "<div class='nn-think-row'>"
    "<div class='nn-think-avatar-wrap'>"
    "<div class='nn-think-orb'></div>"
    "<div class='nn-think-ring'></div>"
    "<div class='nn-think-ring nn-think-ring-2'></div>"
    "</div>"
    "<div class='nn-think-bubble'>"
    "<div class='nn-think-dots'><span></span><span></span><span></span></div>"
    "<div class='nn-think-label'>念念正在为您制作影像方案...</div>"
    "</div></div>"
)

_SUMMARY_SYS = (
    '你是念念追思影像制作助手，帮家属用最温柔口语化的中文描述影像制作进展。'
    '收到 JSON 数据后，用 80-120 字的自然语言告诉家属：我们了解了哪些信息，'
    '影像会呈现什么样的感觉。不要出现任何技术词汇、字段名、JSON。语气温暖贴心。'
    '只输出一段话，不要分点、不要标题。'
)
_BIBLE_SYS = (
    '你是念念追思影像制作助手。根据影像三要素 JSON，用最温柔自然的中文，'
    '用 80-120 字告诉家属：我们为这部影像确定了什么样的基调、主角形象和画面氛围。'
    '不要出现任何 JSON、字段名或技术词汇。语气温暖，像在讲述一个美好的计划。'
    '必须使用 JSON 中真实的人物姓名，绝对不得使用任何无关的示例名称。只输出一段话，不要分点。'
)


def _init():
    defaults = {
        'pipe_phase': 'idle',   # idle → running → done
        'pipe_chat': [],
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init()


def _bubble_ai(content):
    return (
        "<div class='nn-chat-ai'><div class='nn-ai-avatar'>念</div>"
        "<div class='nn-ai-bubble-wrap'><div class='nn-ai-name'>念念 AI</div>"
        f"<div class='nn-ai-bubble'>{content}</div></div></div>"
    )


def _bubble_user(content):
    return f"<div class='nn-chat-user'><div class='nn-user-bubble'>{content}</div></div>"


def _safe_summary(mv_id: str, output: dict, sys_prompt: str) -> str:
    try:
        return call_freeform(sys_prompt, json.dumps(output, ensure_ascii=False))
    except Exception:
        return f'{mv_id} 已处理完成。'


def run_pipeline():
    chat = st.session_state['pipe_chat']

    # ── MV01 访谈结构化 ──
    mv01_input: dict = {}
    if 'mv01_intake_json' in st.session_state:
        try:
            mv01_input = json.loads(st.session_state['mv01_intake_json'])
        except Exception:
            pass
    if not mv01_input:
        mv01_input = pipeline_runner.read_output('MV01') or {}
    # 优先用 form_data 补全 mv01_input（确保使用当前用户数据）
    form_data = st.session_state.get('form_data', {})
    if not mv01_input and form_data:
        mv01_input = form_data

    if not mv01_input:
        chat.append({'role': 'ai', 'content': '暂时没有找到您填写的信息，请返回首页重新填写。'})
        st.session_state['pipe_phase'] = 'done'
        return

    pipeline_runner.save_output('MV01', mv01_input)
    gate_manager.approve('MV01')

    # ── MV02 修改建议（静默运行，不产生独立气泡）──
    try:
        pipeline_runner.run_step('MV02')
        gate_manager.approve('MV02')
    except Exception:
        pass

    # ── 气泡①：整体信息摘要（基于 MV01 原始信息）──
    chat.append({'role': 'ai', 'content': _safe_summary('MV01', mv01_input, _SUMMARY_SYS)})

    # ── MV03 三要素锁定 ──
    # 检查缓存是否与当前用户一致，不一致则强制重新生成
    current_name = str(form_data.get('deceased_name', '')).strip()
    mv03_cached = pipeline_runner.read_output('MV03') or {}
    cached_name = (
        mv03_cached.get('character_bible', {}).get('display_name', '')
        or mv03_cached.get('deceased_name', '')
    )
    if mv03_cached.get('scenes') and current_name and current_name in cached_name:
        mv03_out = mv03_cached
        gate_manager.approve('MV03')
    else:
        # 缓存不存在或人物不匹配 → 重新生成
        try:
            pipeline_runner.run_step('MV03')
            gate_manager.approve('MV03')
            mv03_out = pipeline_runner.read_output('MV03') or {}
        except Exception as e:
            mv03_out = {}
            chat.append({'role': 'ai', 'content': f'影像方案整理时遇到了一些问题，我们已记录，稍后为您重新整理。（{e}）'})
            st.session_state['pipe_phase'] = 'done'
            return

    # 存储供 MV04 使用
    st.session_state['mv03_output'] = mv03_out

    # ── 气泡②：三要素锁定总结（主角形象 + 画面氛围）──
    # 将当前用户真实姓名注入 payload，防止 LLM 引用旧缓存人名
    mv03_summary_payload = dict(mv03_out)
    mv03_summary_payload['_current_deceased_name'] = current_name
    chat.append({'role': 'ai', 'content': _safe_summary('MV03', mv03_summary_payload, _BIBLE_SYS)})

    st.session_state['pipe_phase'] = 'done'


def render_topbar():
    st.markdown(
        "<div class='pp-topbar'>"
        "<div class='pp-logo'>"
        "<div class='pp-logo-orb'>念</div>"
        "<div><div class='pp-logo-name'>念念</div>"
        "<div class='pp-logo-sub'>NianNian Memorial Studio</div></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    _, col_r = st.columns([4, 1])
    with col_r:
        if st.button('返回修改信息', use_container_width=True):
            st.switch_page('app.py')


def render_progress():
    phase = st.session_state['pipe_phase']
    # 三个步骤：访谈结构化 / AI智能核对 / 方案确认
    s1 = 'done' if phase == 'done' else 'active'
    s2 = 'done' if phase == 'done' else ('active' if phase == 'running' else '')
    s3 = 'done' if phase == 'done' else ''
    pills = [('1', '访谈整理', s1), ('2', 'AI 核对', s2), ('3', '方案确认', s3)]
    html = "<div class='pp-progress'>"
    for i, (num, lbl, cls) in enumerate(pills):
        if i > 0:
            html += "<div class='pp-divider'></div>"
        html += f"<div class='pp-pill {cls}'><span class='pp-pill-num'>{num}</span><span>{lbl}</span></div>"
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_scene_cards():
    scenes = st.session_state['pipe_scenes']


# ── Main ──
render_topbar()
render_progress()
phase = st.session_state['pipe_phase']

if phase == 'idle':
    st.session_state['pipe_phase'] = 'running'
    st.rerun()

if phase == 'running':
    think_ph = st.empty()
    think_ph.markdown(_THINK_HTML, unsafe_allow_html=True)
    run_pipeline()
    think_ph.empty()
    st.rerun()

# 渲染对话气泡
chat = st.session_state['pipe_chat']
if chat:
    html = "<div class='nn-chat-wrap'>"
    for m in chat:
        html += _bubble_ai(m['content']) if m['role'] == 'ai' else _bubble_user(m['content'])
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# 方案确认完成 → 进入制作台
if phase == 'done':
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='background:var(--surf);border:1px solid var(--border);border-radius:20px;"
        "padding:28px 32px;text-align:center;box-shadow:0 2px 16px rgba(0,0,0,.05);'>"
        "<div style='font-size:1.5rem;margin-bottom:8px;'>✅</div>"
        "<div style='font-family:\"Cormorant Garamond\",serif;font-size:1.4rem;font-weight:600;"
        "color:var(--ink);margin-bottom:10px;'>影像方案已确认</div>"
        "<div style='font-size:.9rem;color:var(--muted-l);line-height:1.7;'>"
        "三要素已锁定，念念将为您进入分镜制作阶段。<br/>接下来您可以预览每个画面、生成影像。"
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        if st.button('进入分镜制作台 →', type='primary', use_container_width=True):
            st.switch_page('pages/studio.py')
