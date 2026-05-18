# NianNian Memorial Studio — 分镜制作台（MV04-MV06）
import json
from pathlib import Path
from typing import Dict, List
import streamlit as st
import gate_manager
import pipeline_runner
from llm_client import build_scene_prompts, generate_image_302, generate_image_302_ref, generate_video_302, _parse_gemini_image_response as _parse_gemini_image_resp

st.set_page_config(page_title="念念 · 分镜制作台", layout="wide", initial_sidebar_state="collapsed")

_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
:root{
  --bg:#F8F5F0;--bg2:#F2EDE5;--surf:#FFFFFF;--surf2:#FAF7F2;--surf3:#F0EBE2;
  --border:rgba(180,155,115,.18);--border-h:rgba(160,120,70,.35);
  --gold:#9C7A45;--gold-l:#B8934F;
  --ink:#1E1A14;--ink-m:#4A4035;--muted:#B0A494;--muted-l:#8A7B6A;
}
html,body,[class*="css"]{font-family:"Noto Sans SC",sans-serif!important;color:var(--ink)!important;background:var(--bg)!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{display:none!important;}
[data-testid="stSidebarNav"],section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{max-width:900px!important;padding:0 20px 80px!important;margin:0 auto!important;}

/* 顶栏 */
.topbar{display:flex;align-items:center;padding:22px 0 18px;border-bottom:1px solid var(--border);margin-bottom:26px;}
.topbar-orb{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#9C7A45,#B8934F);
  display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:700;
  font-family:"Cormorant Garamond",serif;flex-shrink:0;margin-right:12px;}
.topbar-title{font-family:"Cormorant Garamond",serif;font-size:1.25rem;font-weight:600;color:var(--ink);}
.topbar-sub{font-size:.7rem;color:var(--muted-l);letter-spacing:.05em;}

/* 步骤标题 */
.step-row{display:flex;align-items:center;gap:12px;margin:30px 0 16px;}
.step-dot{width:28px;height:28px;border-radius:50%;background:var(--gold);color:#fff;
  display:inline-flex;align-items:center;justify-content:center;font-size:.78rem;font-weight:700;flex-shrink:0;}
.step-name{font-family:"Cormorant Garamond",serif;font-size:1.25rem;font-weight:600;color:var(--ink);}
.step-desc{font-size:.78rem;color:var(--muted-l);margin-top:1px;}

/* 分镜卡片 */
.s-card{background:var(--surf);border:1px solid var(--border);border-radius:14px;
  padding:18px 22px;margin-bottom:10px;box-shadow:0 1px 6px rgba(0,0,0,.03);}
.s-num{width:24px;height:24px;border-radius:50%;background:var(--gold);color:#fff;
  display:inline-flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:700;flex-shrink:0;}
.s-id{font-weight:700;font-size:.92rem;color:var(--ink);}
.s-meta{font-size:.74rem;color:var(--muted-l);}
.s-desc{font-size:.88rem;color:var(--ink-m);line-height:1.7;margin-top:7px;}
.s-narr{font-size:.82rem;color:var(--muted-l);font-style:italic;line-height:1.65;
  margin-top:6px;padding:8px 12px;background:var(--bg2);border-radius:8px;}

/* 视频状态徽章 */
.vid-badge{display:inline-block;font-size:.75rem;padding:3px 10px;border-radius:999px;
  font-weight:600;letter-spacing:.04em;}
.vid-queue{background:#FEF3C7;color:#92400E;}
.vid-running{background:#DBEAFE;color:#1E40AF;}
.vid-done{background:#D1FAE5;color:#065F46;}

/* 按钮全局 */
/* 剪辑台样式 */
.cut-bar{background:var(--surf);border:1px solid var(--border);border-radius:14px;
  padding:20px 24px;margin:28px 0 10px;box-shadow:0 2px 12px rgba(0,0,0,.04);}
.cut-title{font-family:"Cormorant Garamond",serif;font-size:1.15rem;font-weight:600;color:var(--ink);margin-bottom:12px;}
.cut-chip{display:inline-flex;align-items:center;gap:6px;background:var(--bg2);
  border:1px solid var(--border);border-radius:999px;padding:4px 12px;
  font-size:.78rem;color:var(--ink-m);margin:3px 4px;}
.cut-chip-idx{width:18px;height:18px;border-radius:50%;background:var(--gold);color:#fff;
  display:inline-flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:700;}
.btn-select-on{background:#D1FAE5!important;border-color:#059669!important;color:#065F46!important;}
.btn-select-off{background:var(--surf2)!important;}
  font-size:.85rem!important;font-weight:500!important;padding:8px 18px!important;
  transition:all .18s!important;border:1px solid var(--border)!important;
  background:var(--surf2)!important;color:var(--ink-m)!important;
}
div.stButton>button:hover{border-color:var(--border-h)!important;background:var(--surf3)!important;}
div.stButton>button[kind="primary"]{
  background:var(--gold)!important;border-color:var(--gold)!important;color:#fff!important;
}
div.stButton>button[kind="primary"]:hover{background:var(--gold-l)!important;border-color:var(--gold-l)!important;}
[data-testid="stAlert"]{background:var(--surf2)!important;border-radius:10px!important;border:1px solid var(--border)!important;}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

_THINKING_HTML = (
    "<div style='display:flex;align-items:center;gap:14px;padding:18px 22px;"
    "background:#fff;border:1px solid rgba(180,155,115,.18);border-radius:12px;margin:16px 0;'>"
    "<div style='width:8px;height:8px;border-radius:50%;background:#9C7A45;opacity:.6;'></div>"
    "<span style='font-size:.88rem;color:#8A7B6A;font-style:italic;'>念念正在为您生成分镜故事板，请稍候...</span>"
    "</div>"
)

_VID_STATUS_LABEL = {5: ("排队中", "vid-queue"), 10: ("生成中", "vid-running"), 99: ("已完成", "vid-done")}


def _scenes_to_list(scenes) -> List[Dict]:
    if isinstance(scenes, list):
        return [s for s in scenes if isinstance(s, dict)]
    if isinstance(scenes, dict):
        return [scenes[k] for k in sorted(scenes.keys()) if isinstance(scenes[k], dict)]
    return []


def _init():
    defaults = {
        "studio_phase": "idle",
        "studio_scenes": [],
        "studio_mv04": {},
        "studio_scene_images": {},
        "studio_scene_vidprompts": {},
        "studio_scene_videos": {},
        "studio_selected_clips": {},   # {sid: {"url": ..., "label": ...}}
        "studio_error": "",
        "cast_roles": [],              # [{id, name, role_label, description, photo_b64}]
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init()

# ─── 顶栏 ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='topbar'>"
    "<div class='topbar-orb'>念</div>"
    "<div><div class='topbar-title'>念念 · 分镜制作台</div>"
    "<div class='topbar-sub'>NianNian Memorial Studio</div></div>"
    "</div>",
    unsafe_allow_html=True,
)
nav1, nav2, _ = st.columns([1, 1, 4])
with nav1:
    if st.button("返回方案确认", use_container_width=True):
        st.switch_page("pages/pipeline.py")
with nav2:
    if st.button("返回首页", use_container_width=True):
        st.switch_page("app.py")

st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

# ─── 角色摘要（只读，编辑请返回首页 Step 2）────────────────────────────────────
_anc_b64  = st.session_state.get("ancestor_photo_b64")
_dec_name = str(st.session_state.get("form_data", {}).get("deceased_name", "逝者"))
_cast_ro  = st.session_state.get("cast_roles", [])

with st.expander(
    f"🎭 电影角色 · 主角：{_dec_name}"
    + (f"  +  {len(_cast_ro)} 位配角" if _cast_ro else "  （无配角）"),
    expanded=False,
):
    _rc1, _rc2 = st.columns([1, 6])
    with _rc1:
        if _anc_b64:
            st.image("data:image/jpeg;base64," + _anc_b64, width=56)
    with _rc2:
        st.markdown(
            f"<span style='font-size:.78rem;font-weight:700;color:#9C7A45;"
            f"background:#FEF3C7;padding:2px 8px;border-radius:999px;'>主角</span>"
            f"&nbsp;<b>{_dec_name}</b>&nbsp;"
            + ("✅" if _anc_b64 else "⚠️ 未上传参考照片"),
            unsafe_allow_html=True,
        )
    for _cr in _cast_ro:
        _n = _cr.get("name") or "（未填）"
        _rl = _cr.get("role_label","")
        _has_photo = "📷" if _cr.get("photo_b64") else ""
        st.markdown(f"&nbsp;&nbsp;· **{_n}**（{_rl}）{_has_photo}", unsafe_allow_html=True)
    st.caption("如需修改角色信息，请返回首页 Step 2 编辑。")



# ─── 图床上传连通性测试（开发调试用）──────────────────────────────────────────
import os as _os
_imgbb_key = _os.getenv("IMGBB_API_KEY", "")
with st.expander("🔧 调试：测试图床上传连通性", expanded=False):
    st.caption("依次测试 tmpfiles.org → litterbox，确认哪个可用")
    if st.button("立即测试图床上传", key="test_imgbb"):
        import requests as _rq, base64 as _b64
        _test_bytes = _b64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        # 测试 tmpfiles.org
        try:
            _r2 = _rq.post("https://tmpfiles.org/api/v1/upload",
                           files={"file": ("test.png", _test_bytes, "image/png")}, timeout=15)
            if _r2.status_code == 200:
                _u = _r2.json().get("data", {}).get("url", "")
                st.success(f"✅ tmpfiles.org 成功：{_u}")
            else:
                st.error(f"❌ tmpfiles.org 失败 status={_r2.status_code}：{_r2.text[:200]}")
        except Exception as _e2:
            st.error(f"❌ tmpfiles.org 异常：{_e2}")
        # 测试 litterbox
        try:
            _r3 = _rq.post("https://litterbox.catbox.moe/resources/internals/api.php",
                           data={"reqtype": "fileupload", "time": "1h"},
                           files={"fileToUpload": ("test.png", _test_bytes, "image/png")}, timeout=15)
            if _r3.status_code == 200 and _r3.text.strip().startswith("https://"):
                st.success(f"✅ litterbox 成功：{_r3.text.strip()}")
            else:
                st.error(f"❌ litterbox 失败 status={_r3.status_code}：{_r3.text[:200]}")
        except Exception as _e3:
            st.error(f"❌ litterbox 异常：{_e3}")

# ─── 首帧图上传 + 可灵提交全流程调试台 ────────────────────────────────────────
with st.expander("🎬 调试：首帧图上传→可灵提交全流程追踪", expanded=False):
    st.caption("选择一张已生成的分镜图片，追踪：上传图床 → 提交可灵 → 获取 task_id 的每一步")
    _dbg_imgs = {}
    for _sc in st.session_state.get("studio_scenes", []):
        _sid2 = _sc.get("scene_id") or "unknown"
        _imgs2 = st.session_state.get("studio_scene_images", {}).get(_sid2, [])
        for _j2, _b in enumerate(_imgs2):
            _dbg_imgs[f"{_sid2} · 版本{_j2+1}"] = _b
    if not _dbg_imgs:
        st.info("请先生成至少一张分镜图片，再使用此调试台。")
    else:
        _dbg_sel = st.selectbox("选择分镜图片", list(_dbg_imgs.keys()), key="dbg_scene_sel")
        _dbg_prompt = st.text_input("视频 Prompt（可修改）",
                                    value="cinematic slow motion, warm nostalgic atmosphere",
                                    key="dbg_vid_prompt")
        if st.button("🚀 开始全流程追踪", key="dbg_run_trace", type="primary"):
            import requests as _rq2, base64 as _b64_2
            from llm_client import _kling_jwt as _kjwt, _KLING_OFFICIAL_BASE as _KBASE, _upload_image_to_public as _upl

            _dbg_b64 = _dbg_imgs[_dbg_sel]
            _dbg_img_bytes = _b64_2.b64decode(_dbg_b64)

            st.markdown("---")
            # ── Step 1: 生成 JWT ──────────────────────────────────────────────
            st.markdown("**Step 1 · 生成可灵官方 JWT Token**")
            import os as _os
            _kid = _os.getenv("KLING_ACCESS_KEY_ID", "")
            _ksec = _os.getenv("KLING_ACCESS_KEY_SECRET", "")
            st.caption(f"读到的 KEY_ID：`{_kid[:6]}...{_kid[-4:]}` （共{len(_kid)}字符）| SECRET：`{'已配置' if _ksec else '❌ 未配置'}`（共{len(_ksec)}字符）")
            try:
                _tok = _kjwt()
                st.success(f"✅ JWT 生成成功（前30字符）：`{_tok[:30]}...`")
            except Exception as _je:
                st.error(f"❌ JWT 生成失败：{_je}\n\n请检查 KLING_ACCESS_KEY_ID / KLING_ACCESS_KEY_SECRET 是否已在 Secrets 中配置")
                st.stop()

            # ── Step 1.5: 上传首帧图到图床 ────────────────────────────────────
            st.markdown("**Step 1.5 · 上传首帧图到图床（获取 HTTPS URL）**")
            _s15 = st.empty()
            _s15.info("⏳ 上传中...")
            _pub_url = _upl(_dbg_img_bytes, "png")
            if _pub_url:
                _s15.success(f"✅ 上传成功：`{_pub_url}`")
            else:
                _s15.error("❌ 图床上传失败，无法继续")
                st.stop()

            # ── Step 2: 提交可灵官方 API ──────────────────────────────────────
            st.markdown("**Step 2 · 提交可灵官方 API（kling-v3 首帧模式）**")
            _s2 = st.empty()
            _s2.info("⏳ 正在提交...")
            _submit_url = f"{_KBASE}/v1/videos/image2video"
            _body = {
                "model_name": "kling-v3",
                "prompt": _dbg_prompt,
                "negative_prompt": "",
                "duration": "5",
                "mode": "pro",
                "aspect_ratio": "16:9",
                "sound": "off",
                "callback_url": "",
                "external_task_id": "",
                "image": _pub_url,
            }
            st.code(__import__("json").dumps(_body, ensure_ascii=False, indent=2), language="json")
            try:
                _tok2 = _kjwt()
                _kr = _rq2.post(
                    _submit_url,
                    headers={"Authorization": f"Bearer {_tok2}", "Content-Type": "application/json"},
                    json=_body, timeout=60,
                )
                # 先显示原始 HTTP 状态，方便排查
                st.caption(f"HTTP status: {_kr.status_code}  |  Content-Type: {_kr.headers.get('content-type','?')}")
                _raw_text = _kr.text
                try:
                    _kdata = _kr.json()
                except Exception:
                    _kdata = None
                if _kdata is None:
                    _s2.error(f"❌ 响应不是 JSON（status={_kr.status_code}）")
                    st.code(_raw_text[:500], language="text")
                elif _kdata.get("code") == 0:
                    _task_id = _kdata.get("data", {}).get("task_id", "")
                    _s2.success(f"✅ 提交成功！task_id：`{_task_id}`")
                    st.markdown("**Step 3 · 完整 API 响应**")
                    st.json(_kdata)
                else:
                    _s2.error(f"❌ 提交失败 code={_kdata.get('code')}：{_kdata.get('message','')}")
                    st.json(_kdata)
            except Exception as _ke:
                _s2.error(f"❌ 可灵请求异常：{_ke}")
                import traceback as _tb
                st.code(_tb.format_exc(), language="text")

# ─── 逝者参考图 → 分镜图生成 全流程调试台 ──────────────────────────────────────
with st.expander("🖼️ 调试：逝者参考图 → 分镜图生成全流程追踪", expanded=False):
    st.caption("追踪：读取逝者参考图 → 上传图床获取 URL → 调用 gemini-3-pro-image-preview → 解析图片结果")

    import base64 as _b64_ref, os as _os_ref, requests as _rq_ref

    # ── 读取逝者参考图 ────────────────────────────────────────────────────────
    _ref_b64_dbg = st.session_state.get("ancestor_photo_b64") or st.session_state.get("anc_photo_b64")
    _anc_keys = [k for k in st.session_state if "anc" in k.lower() or "ancestor" in k.lower() or "photo" in k.lower()]
    st.caption(f"Session 中与参考图相关的 key：`{_anc_keys}`")

    if _ref_b64_dbg:
        _ref_bytes_preview = _b64_ref.b64decode(_ref_b64_dbg)
        st.success(f"✅ 找到逝者参考图（{len(_ref_bytes_preview)//1024} KB）")
        st.image(_ref_bytes_preview, caption="逝者参考图预览", width=180)
    else:
        st.warning("⚠️ 当前 session 中未找到逝者参考图，请先在上方上传逝者照片后再测试。")

    _ref_prompt_dbg = st.text_input(
        "测试用分镜 Prompt",
        value="老人在阳光斑驳的院子里静坐，回忆往事，电影质感，暖色调",
        key="dbg_ref_prompt",
    )

    if st.button("🚀 开始参考图生图追踪", key="dbg_ref_run", type="primary"):
        if not _ref_b64_dbg:
            st.error("❌ 没有参考图，无法测试。请先上传逝者照片。")
        else:
            from llm_client import _upload_image_to_public as _upl_ref, IMAGE_REF_MODEL as _ref_model, PRIMARY_CLIENT as _ref_client

            _ref_img_bytes = _b64_ref.b64decode(_ref_b64_dbg)
            st.markdown("---")

            # ── Step 1: 确认模型配置 ─────────────────────────────────────────
            st.markdown("**Step 1 · 确认模型配置**")
            st.caption(f"AI302_IMAGE_REF_MODEL env = `{_os_ref.getenv('AI302_IMAGE_REF_MODEL', '（未设置，用默认值）')}`")
            st.caption(f"实际使用 IMAGE_REF_MODEL = `{_ref_model}`")
            st.caption(f"302.ai BASE_URL = `{_ref_client.base_url}`")

            # ── Step 2: 上传参考图到图床 ─────────────────────────────────────
            st.markdown("**Step 2 · 上传参考图到图床**")
            _s_upl = st.empty()
            _s_upl.info("⏳ 上传中...")
            _pub_ref_url = _upl_ref(_ref_img_bytes, "png")
            if _pub_ref_url:
                _s_upl.success(f"✅ 上传成功：`{_pub_ref_url}`")
            else:
                _s_upl.error("❌ 图床上传失败，无法继续")
                st.stop()

            # ── Step 3: 构造请求体并调用 gemini ─────────────────────────────
            st.markdown("**Step 3 · 调用 gemini-3-pro-image-preview（via 302.ai）**")
            _full_prompt_dbg = (
                f"请严格保留参考图中人物的面部特征、年龄、肤色和外貌，将其作为画面主角。"
                f"生成一幅电影感的追思纪念场景：{_ref_prompt_dbg}。"
                f"风格：电影质感、暖色调、16:9 构图。请直接输出生成的图片。"
            )
            _req_body_preview = {
                "model": _ref_model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _full_prompt_dbg},
                        {"type": "image_url", "image_url": {"url": _pub_ref_url}},
                    ],
                }],
            }
            st.code(__import__("json").dumps(_req_body_preview, ensure_ascii=False, indent=2), language="json")

            _s3 = st.empty()
            _s3.info("⏳ 请求中，gemini 生图通常需要 10-30 秒...")
            try:
                _ref_resp = _ref_client.chat.completions.create(
                    model=_ref_model,
                    messages=_req_body_preview["messages"],
                    stream=False,
                )
                _s3.success("✅ API 响应已收到")
            except Exception as _ref_exc:
                _s3.error(f"❌ API 调用失败：{_ref_exc}")
                import traceback as _tb_ref
                st.code(_tb_ref.format_exc(), language="text")
                st.stop()

            # ── Step 4: 解析响应 ─────────────────────────────────────────────
            st.markdown("**Step 4 · 解析响应内容**")
            _raw_content = _ref_resp.choices[0].message.content
            st.caption(f"content 类型：`{type(_raw_content).__name__}`")
            if isinstance(_raw_content, str):
                st.caption(f"content 前200字：`{_raw_content[:200]}`")
            elif isinstance(_raw_content, list):
                st.caption(f"content 列表长度：{len(_raw_content)}，各 type：{[p.get('type','?') if isinstance(p,dict) else type(p).__name__ for p in _raw_content]}")

            # 展示完整 model_dump（便于诊断 302.ai 非标准字段）
            with st.expander("🔬 原始响应 model_dump（debug）"):
                import json as _dbg_json
                try:
                    _dump = _ref_resp.model_dump() if hasattr(_ref_resp, "model_dump") else {}
                    # 截断超长 base64 字符串以免界面卡死
                    _dump_str = _dbg_json.dumps(_dump, ensure_ascii=False, indent=2)
                    if len(_dump_str) > 8000:
                        _dump_str = _dump_str[:8000] + "\n... (截断)"
                    st.code(_dump_str, language="json")
                except Exception as _de:
                    st.warning(f"model_dump 失败：{_de}")

            _gen_b64_dbg, _gen_err_dbg = _parse_gemini_image_resp(_ref_resp, "[调试台]")
            if _gen_b64_dbg:
                st.success(f"✅ 解析成功（base64 长度={len(_gen_b64_dbg)}）")
                st.image(_b64_ref.b64decode(_gen_b64_dbg), caption="生成图片预览", width="stretch")
            else:
                st.error(f"❌ 解析失败：{_gen_err_dbg}")
                st.text_area("原始 content", value=str(_raw_content)[:500], height=120)

# ─── MV04 分镜故事板 ──────────────────────────────────────────────────────────

# 辅助：将 cast_roles 中有 photo_b64 的角色上传图床，返回含 photo_url 的新列表（懒加载缓存）
def _resolve_cast_urls() -> list:
    """上传 cast_roles 中未上传的配角照片，返回带 photo_url 的列表（原 list 同步更新）。"""
    from llm_client import _upload_image_to_public as _upl_cast
    import base64 as _b64c
    cast = st.session_state.get("cast_roles", [])
    for cr in cast:
        if cr.get("photo_b64") and not cr.get("photo_url"):
            try:
                _img_bytes = _b64c.b64decode(cr["photo_b64"])
                _url = _upl_cast(_img_bytes, "png")
                if _url:
                    cr["photo_url"] = _url
            except Exception:
                pass
    return cast


def _build_storyboard_payload_from_form(form_data: dict) -> dict:
    """从用户 form_data 构建分镜生成的 payload，确保 LLM 使用真实用户数据而非缓存样本。"""
    deceased_name   = form_data.get("deceased_name", "逝者")
    gender          = form_data.get("deceased_gender", "男")
    birth_date      = form_data.get("birth_date", "")
    death_date      = form_data.get("death_date", "")
    occupation      = form_data.get("occupation", "")
    memory_text     = form_data.get("family_memory_text", "")
    last_wishes     = form_data.get("last_wishes", "")
    style_pref      = form_data.get("style_preference", "warm_nostalgia")
    speaker_name    = form_data.get("speaker_name", "")
    speaker_rel     = form_data.get("speaker_relation", "")
    speaker_style   = form_data.get("speaker_style", "")
    duration_sec    = int(form_data.get("total_duration_sec", 300))

    return {
        "deceased_name": deceased_name,
        "deceased_gender": gender,
        "birth_date": birth_date,
        "death_date": death_date,
        "occupation": occupation,
        "family_memory_text": memory_text,
        "last_wishes": last_wishes,
        "style_preference": style_pref,
        "speaker_name": speaker_name,
        "speaker_relation": speaker_rel,
        "speaker_style": speaker_style,
        "target_duration_sec": duration_sec,
        "instruction": (
            f"请严格根据以上真实用户信息为【{deceased_name}】生成 3-5 个定制化分镜画面，"
            f"每个分镜的场景描述、旁白口播必须完全来源于此人的真实生平故事和家庭回忆，"
            f"禁止使用任何与此人无关的通用示例场景（如钓鱼、刨木头等与此人无关的情节）。"
        ),
    }


def _run_storyboard_with_form_data() -> dict:
    """读取 form_data，直接调用分镜 LLM 生成定制化故事板，并写入 mv04.json。"""
    from llm_client import call_skill
    form_data = st.session_state.get("form_data", {})
    payload = _build_storyboard_payload_from_form(form_data)
    prompt = pipeline_runner.get_skill_prompt("MV04")
    result = call_skill("MV04", prompt, payload)
    if not result.get("error"):
        result = pipeline_runner.normalize_storyboard_output(result)
        pipeline_runner.save_output("MV04", result)
        gate_manager.approve("MV04")
    return result


st.markdown(
    "<div class='step-row'><span class='step-dot'>4</span>"
    "<div><div class='step-name'>分镜故事板</div>"
    "<div class='step-desc'>定制化分镜 · 基于真实用户信息生成</div></div></div>",
    unsafe_allow_html=True,
)

phase = st.session_state["studio_phase"]

if phase == "idle":
    cached = pipeline_runner.read_output("MV04")
    current_name = str(st.session_state.get("form_data", {}).get("deceased_name", "")).strip()
    # 获取缓存中的人物名称（支持多种 JSON 结构）
    cached_name = ""
    if cached:
        cached_name = (
            cached.get("character_bible", {}).get("display_name", "")
            or cached.get("deceased_name", "")
            or cached.get("character_bible", {}).get("character_id", "")
        )
    # 只有缓存存在且人物名称与当前用户一致时才使用缓存
    if cached and cached.get("scenes") and current_name and current_name in cached_name:
        st.session_state["studio_scenes"] = _scenes_to_list(cached.get("scenes", []))
        st.session_state["studio_mv04"] = cached
        st.session_state["studio_phase"] = "done"
        st.rerun()
    else:
        # 缓存不存在或人物不匹配 → 强制根据当前用户重新生成
        st.session_state["studio_phase"] = "running"
        st.rerun()

if phase == "running":
    ph = st.empty()
    ph.markdown(_THINKING_HTML, unsafe_allow_html=True)
    try:
        mv04_out = _run_storyboard_with_form_data()
        if mv04_out.get("error"):
            raise RuntimeError(mv04_out.get("message", "分镜生成失败"))
        st.session_state["studio_scenes"] = _scenes_to_list(mv04_out.get("scenes", []))
        st.session_state["studio_mv04"] = mv04_out
        st.session_state["studio_phase"] = "done"
        st.session_state["studio_error"] = ""
    except Exception as e:
        st.session_state["studio_error"] = str(e)
        st.session_state["studio_phase"] = "error"
    ph.empty()
    st.rerun()

if phase == "error":
    st.error(f"分镜生成遇到问题：{st.session_state['studio_error']}")
    if st.button("重新生成分镜", type="primary"):
        st.session_state["studio_phase"] = "running"
        st.rerun()

if phase == "done":
    scenes: List[Dict] = st.session_state["studio_scenes"]
    mv04_out: dict = st.session_state["studio_mv04"]
    character_bible = mv04_out.get("character_bible", {}) if isinstance(mv04_out, dict) else {}
    scene_library   = mv04_out.get("scene_library",   []) if isinstance(mv04_out, dict) else []

    # 重新生成按钮（右对齐）
    _regen_col, _ = st.columns([2, 5])
    with _regen_col:
        if st.button("🔄 重新生成分镜故事板", use_container_width=True, key="regen_storyboard"):
            pipeline_runner.save_output("MV04", {})  # 清除缓存
            st.session_state["studio_scenes"] = []
            st.session_state["studio_mv04"] = {}
            st.session_state["studio_scene_images"] = {}
            st.session_state["studio_phase"] = "running"
            st.rerun()

    if not scenes:
        st.warning("分镜数据为空，请重新生成。")
        if st.button("重新生成分镜", type="primary"):
            st.session_state["studio_phase"] = "running"
            st.rerun()
    else:
        st.markdown(
            f"<div style='font-size:.82rem;color:var(--muted-l);margin-bottom:18px;'>"
            f"共 <b style='color:var(--gold);'>{len(scenes)}</b> 个分镜画面</div>",
            unsafe_allow_html=True,
        )

        # 批量生成按钮
        c_all, _ = st.columns([1.6, 4])
        with c_all:
            if st.button("一键生成全部预览图", use_container_width=True, key="genall"):
                bar = st.progress(0, text="批量生成中...")
                _batch_anc_b64   = st.session_state.get("ancestor_photo_b64")
                _batch_dec_name  = str(st.session_state.get("form_data", {}).get("deceased_name", "")).lower()
                # 上传配角图床（只做一次）
                _batch_cast = _resolve_cast_urls()
                for idx, sc in enumerate(scenes):
                    _sid = sc.get("scene_id") or f"scene_{idx+1:02d}"
                    _pr  = sc.get("mj_prompt") or sc.get("prompt_global") or sc.get("description") or ""
                    try:
                        _pm  = build_scene_prompts(sc, character_bible, scene_library, cast_roles=_batch_cast)
                        _img_prompt = _pm.get("image_prompt") or _pr
                        # 有逝者参考图时，所有分镜都传入参考图（face-lock 由 generate_image_302_ref 内部保证）
                        _b64, _ = generate_image_302(
                            _img_prompt,
                            reference_b64=_batch_anc_b64 if _batch_anc_b64 else None,
                        )
                        if _b64:
                            _cur = st.session_state["studio_scene_images"].get(_sid, [])
                            st.session_state["studio_scene_images"][_sid] = _cur + [_b64]
                            st.session_state["studio_scene_vidprompts"][_sid] = _pm.get("video_prompt") or sc.get("description", "")
                    except Exception:
                        pass
                    bar.progress((idx + 1) / len(scenes), text=f"已完成 {idx+1}/{len(scenes)}")
                st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ── 分镜卡片循环 ──
        for i, scene in enumerate(scenes):
            sid      = scene.get("scene_id")      or f"scene_{i+1:02d}"
            timecode = scene.get("time")           or scene.get("timecode") or ""
            shot     = scene.get("shot_type")      or ""
            desc     = scene.get("description")    or ""
            narr     = scene.get("voice_script")   or scene.get("narration") or ""
            pr_raw   = scene.get("mj_prompt")      or scene.get("prompt_global") or desc
            imgs: List[str] = st.session_state["studio_scene_images"].get(sid, [])
            time_shot = " · ".join(filter(None, [timecode, shot]))

            st.markdown(
                f"<div class='s-card'>"
                f"<div style='display:flex;align-items:center;gap:9px;margin-bottom:6px;'>"
                f"<span class='s-num'>{i+1}</span>"
                f"<span class='s-id'>{sid}</span>"
                f"<span class='s-meta'>{time_shot}</span></div>"
                f"<div class='s-desc'>{desc}</div>"
                + (f"<div class='s-narr'>「{narr}」</div>" if narr else "")
                + "</div>",
                unsafe_allow_html=True,
            )

            # 已生成图片及视频区域
            if imgs:
                n_cols = min(len(imgs), 3)
                img_cols = st.columns(n_cols, gap="small")
                for j, b64 in enumerate(imgs[:3]):
                    with img_cols[j]:
                        st.image("data:image/png;base64," + b64, use_container_width=True)
                        vid_key = f"{sid}_{j}"
                        vr  = st.session_state["studio_scene_videos"].get(vid_key)
                        vid_prompt = st.session_state["studio_scene_vidprompts"].get(sid, "")

                        if vr and vr.get("url"):
                            # 视频已完成
                            st.video(vr["url"])
                            # ── 选用按钮 ──────────────────────────────────────
                            selected = st.session_state["studio_selected_clips"].get(sid, {})
                            already  = selected.get("url") == vr["url"]
                            btn_lbl  = "已选用 ✓" if already else "选用此片段"
                            btn_type = "primary" if already else "secondary"
                            if st.button(btn_lbl, key=f"sel_{vid_key}", type=btn_type, use_container_width=True):
                                if already:
                                    # 取消选用
                                    st.session_state["studio_selected_clips"].pop(sid, None)
                                else:
                                    # 选用此片段
                                    st.session_state["studio_selected_clips"][sid] = {
                                        "url": vr["url"],
                                        "label": f"{sid} · 版本{j+1}",
                                    }
                                st.rerun()
                        elif vr and vr.get("task_id") and not vr.get("url"):
                            # 视频排队/生成中
                            cur_status = vr.get("status", 5)
                            label_txt, label_cls = _VID_STATUS_LABEL.get(cur_status, ("进行中", "vid-running"))
                            _vid_source = vr.get("source", "kling")
                            _source_badge = "302.ai" if _vid_source == "302ai" else "可灵官方"
                            st.markdown(
                                f"<div style='margin:4px 0 6px;'>"
                                f"<span class='vid-badge {label_cls}'>{label_txt}</span>"
                                f"<span style='font-size:.72rem;color:var(--muted-l);margin-left:8px;'>"
                                f"[{_source_badge}] task: {vr['task_id'][-10:]}</span></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button("刷新视频状态", key=f"qvid_{vid_key}", use_container_width=True):
                                import requests as _rq
                                _vid_source2 = vr.get("source", "kling")
                                if _vid_source2 == "302ai":
                                    # ── 302.ai 轮询 ───────────────────────────
                                    from llm_client import _302_VIDEO_FETCH_URL as _FETCH_URL, _302_API_KEY as _API302
                                    try:
                                        _pr = _rq.get(
                                            _FETCH_URL,
                                            headers={"Authorization": f"Bearer {_API302}"},
                                            params={"task_id": vr["task_id"]},
                                            timeout=20,
                                        )
                                        _pd = _pr.json()
                                        _new_status = _pd.get("data", {}).get("status", 5)
                                        if _new_status == 99:
                                            _works = _pd.get("data", {}).get("works", [])
                                            _vurl = _works[0].get("resource", "") if _works else ""
                                            st.session_state["studio_scene_videos"][vid_key] = {
                                                "url": _vurl, "task_id": vr["task_id"],
                                                "status": 99, "source": "302ai",
                                            }
                                        elif _new_status == 50:
                                            st.session_state["studio_scene_videos"][vid_key] = {
                                                **vr, "status": 50,
                                                "error": "302.ai 任务失败（已自动退款）"
                                            }
                                        else:
                                            st.session_state["studio_scene_videos"][vid_key] = {
                                                **vr, "status": _new_status
                                            }
                                        st.rerun()
                                    except Exception as _e:
                                        st.warning(f"302.ai 查询失败：{_e}")
                                else:
                                    # ── 可灵官方轮询 ───────────────────────────
                                    from llm_client import _kling_jwt as _kjwt2, _KLING_OFFICIAL_BASE as _KB2
                                    try:
                                        _poll_url = f"{_KB2}/v1/videos/image2video/{vr['task_id']}"
                                        _r2 = _rq.get(
                                            _poll_url,
                                            headers={"Authorization": f"Bearer {_kjwt2()}"},
                                            timeout=20,
                                        )
                                        _pd = _r2.json()
                                        _task_data = _pd.get("data", {})
                                        _new_status = _task_data.get("task_status", "processing")
                                        if _new_status == "succeed":
                                            _videos = _task_data.get("task_result", {}).get("videos", [])
                                            _vurl = _videos[0].get("url", "") if _videos else ""
                                            st.session_state["studio_scene_videos"][vid_key] = {
                                                "url": _vurl, "task_id": vr["task_id"],
                                                "status": 99, "source": "kling",
                                            }
                                        elif _new_status == "failed":
                                            st.session_state["studio_scene_videos"][vid_key] = {
                                                **vr, "status": "failed",
                                                "error": _task_data.get("task_status_msg", "失败")
                                            }
                                        else:
                                            st.session_state["studio_scene_videos"][vid_key] = {
                                                **vr, "status": "processing"
                                            }
                                        st.rerun()
                                    except Exception as _e:
                                        st.warning(f"可灵查询失败：{_e}")
                        elif vid_prompt:
                            # ── Prompt 编辑框 + 时长选择 ──────────────────────
                            _vp_key   = f"vid_prompt_edit_{vid_key}"
                            _vd_key   = f"vid_dur_{vid_key}"
                            _cur_vp   = st.session_state.get(_vp_key, vid_prompt)
                            _cur_dur  = st.session_state.get(_vd_key, 5)

                            _edited_prompt = st.text_area(
                                "可灵 Prompt（可修改）",
                                value=_cur_vp,
                                key=_vp_key,
                                height=80,
                                label_visibility="collapsed",
                                placeholder="输入发给可灵的视频描述，确认后点击生成视频",
                            )
                            _dur_col, _btn_col = st.columns([1, 2])
                            with _dur_col:
                                _sel_dur = st.selectbox(
                                    "时长",
                                    options=[5, 10],
                                    index=0 if _cur_dur == 5 else 1,
                                    key=_vd_key,
                                    format_func=lambda x: f"{x} 秒",
                                    label_visibility="collapsed",
                                )
                            with _btn_col:
                              if st.button("生成视频 →", key=f"genvid_{vid_key}", use_container_width=True, type="primary"):
                                with st.spinner("正在上传首帧图并提交视频任务..."):
                                    _vid_anc = st.session_state.get("ancestor_photo_b64")
                                    _vid_final_prompt = _edited_prompt or vid_prompt
                                    if _vid_anc:
                                        _vid_subj = str(scene.get("subject", "")).lower()
                                        _vid_desc = str(desc).lower()
                                        _vid_dec_name = str(st.session_state.get("form_data", {}).get("deceased_name", "")).lower()
                                        _vid_ref_kws = ["逝者","爷爷","奶奶","父亲","母亲","grandfather",
                                                        "elderly man","elderly woman","deceased","他","她"]
                                        if _vid_dec_name:
                                            _vid_ref_kws.append(_vid_dec_name)
                                        _vid_use_ref = any(kw in _vid_subj or kw in _vid_desc for kw in _vid_ref_kws)
                                        if _vid_use_ref:
                                            _vid_final_prompt = (
                                                "Keep the main character's face and appearance IDENTICAL to the first frame image. "
                                                "Do NOT alter the person's face, age, or features. "
                                                + _vid_final_prompt
                                            )
                                    vr2 = generate_video_302(
                                        _vid_final_prompt,
                                        image_url="data:image/png;base64," + imgs[j],
                                        duration=_sel_dur, poll=False,
                                    )
                                if vr2.get("error"):
                                    _err_msg = vr2["error"]
                                    if "KLING_ACCESS_KEY" in _err_msg or "JWT" in _err_msg:
                                        st.error(f"❌ 可灵官方 API 鉴权失败：{_err_msg}\n\n请在 Streamlit Secrets 中填写 KLING_ACCESS_KEY_ID 和 KLING_ACCESS_KEY_SECRET")
                                    else:
                                        st.error(f"❌ 视频提交失败：{_err_msg}")
                                else:
                                    st.session_state["studio_scene_videos"][vid_key] = vr2
                                    st.rerun()

            # 按钮行
            bc1, bc2, _ = st.columns([1.3, 1.3, 3.4])
            with bc1:
                btn_txt = "重新生成图片" if imgs else "生成预览图"
                if st.button(btn_txt, key=f"genimg_{sid}", use_container_width=True):
                    with st.spinner(f"正在绘制第 {i+1} 个画面..."):
                        try:
                            _single_cast = _resolve_cast_urls()
                            pm  = build_scene_prompts(scene, character_bible, scene_library, cast_roles=_single_cast)
                            img_prompt = pm.get("image_prompt") or pr_raw

                            # ── 有逝者参考图时所有分镜都传入，face-lock 由 generate_image_302_ref 保证 ──
                            _ancestor_b64 = st.session_state.get("ancestor_photo_b64")

                            b64, err = generate_image_302(
                                img_prompt,
                                reference_b64=_ancestor_b64 if _ancestor_b64 else None,
                            )
                            if b64:
                                st.session_state["studio_scene_images"][sid] = \
                                    st.session_state["studio_scene_images"].get(sid, []) + [b64]
                                st.session_state["studio_scene_vidprompts"][sid] = \
                                    pm.get("video_prompt") or desc
                                if _ancestor_b64:
                                    st.success("✅ 已使用逝者参考照片生成，形象已锁定")
                                st.rerun()
                            else:
                                st.error(f"图片生成失败：{err}")
                        except Exception as ex:
                            st.error(str(ex))

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # 底部重新生成
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        rc, _ = st.columns([1.4, 4])
        with rc:
            if st.button("重新生成全部分镜", use_container_width=True):
                for k in ("studio_phase", "studio_scenes", "studio_scene_images",
                          "studio_scene_vidprompts", "studio_scene_videos"):
                    st.session_state[k] = "running" if k == "studio_phase" else ([] if k == "studio_scenes" else {})
                st.rerun()

# ─── MV05 数字人驱动 ──────────────────────────────────────────────────────────
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
st.markdown("---")
st.markdown(
    "<div class='step-row'><span class='step-dot'>5</span>"
    "<div><div class='step-name'>数字人驱动</div>"
    "<div class='step-desc'>MV05 · 头像渲染与数字人代码生成</div></div></div>",
    unsafe_allow_html=True,
)
mv05_out = pipeline_runner.read_output("MV05") or {}
if mv05_out:
    st.success("数字人方案已生成")
    with st.expander("查看数字人参数"):
        st.json(mv05_out)
else:
    st.info("分镜确认后可启动数字人驱动。")
    if st.session_state.get("studio_phase") == "done" and st.session_state.get("studio_scenes"):
        if st.button("启动数字人渲染", type="primary", key="run_mv05"):
            with st.spinner("正在生成数字人驱动方案..."):
                try:
                    pipeline_runner.run_step("MV05")
                    gate_manager.approve("MV05")
                    st.success("数字人方案已生成")
                    st.rerun()
                except Exception as e:
                    st.error(f"MV05 执行失败：{e}")

# ─── MV06 最终剪辑 ────────────────────────────────────────────────────────────
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
st.markdown("---")
st.markdown(
    "<div class='step-row'><span class='step-dot'>6</span>"
    "<div><div class='step-name'>最终剪辑输出</div>"
    "<div class='step-desc'>MV06 · 自动化时间轴与成片导出</div></div></div>",
    unsafe_allow_html=True,
)
mv06_out = pipeline_runner.read_output("MV06") or {}
if mv06_out:
    st.success("最终剪辑方案已生成")
    with st.expander("查看剪辑方案"):
        st.json(mv06_out)
else:
    st.info("数字人方案完成后可启动最终剪辑。")
    if pipeline_runner.read_output("MV05"):
        if st.button("启动最终剪辑", type="primary", key="run_mv06"):
            with st.spinner("正在编排最终时间轴..."):
                try:
                    pipeline_runner.run_step("MV06")
                    gate_manager.approve("MV06")
                    st.success("最终剪辑方案已生成")
                    st.rerun()
                except Exception as e:
                    st.error(f"MV06 执行失败：{e}")

st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)

# ─── 一键剪辑合成台 ───────────────────────────────────────────────────────────
selected_clips: Dict = st.session_state.get("studio_selected_clips", {})
all_scenes: List[Dict] = st.session_state.get("studio_scenes", [])

# 按分镜顺序排列已选片段
ordered_clips = []
for sc in all_scenes:
    _sid = sc.get("scene_id") or sc.get("id") or sc.get("shot_id", "")
    if _sid and _sid in selected_clips:
        ordered_clips.append((_sid, selected_clips[_sid]))

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown("---")
st.markdown(
    "<div class='step-row'><span class='step-dot' style='background:#6B5B3E;'>✂</span>"
    "<div><div class='step-name'>一键剪辑合成</div>"
    "<div class='step-desc'>将各分镜选用片段按顺序拼接，导出最终成片</div></div></div>",
    unsafe_allow_html=True,
)

with st.container():
    if not ordered_clips:
        st.info("请在上方各分镜的已完成视频下方点击「选用此片段」，选好后在此处一键合成。")
    else:
        st.markdown("<div class='cut-bar'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='cut-title'>已选 {len(ordered_clips)} 个片段，准备合成</div>",
            unsafe_allow_html=True,
        )
        chips_html = "".join(
            f"<span class='cut-chip'><span class='cut-chip-idx'>{idx+1}</span>{label}</span>"
            for idx, (_sid, info) in enumerate(ordered_clips)
            for label in [info.get("label", _sid)]
        )
        st.markdown(chips_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        col_btn, col_info = st.columns([1.6, 4])
        with col_btn:
            do_cut = st.button("一键剪辑合成", type="primary", key="do_final_cut", use_container_width=True)

        if do_cut:
            urls = [info["url"] for _, info in ordered_clips]
            labels = [info.get("label", sid) for sid, info in ordered_clips]

            prog_box = st.empty()
            prog_bar = st.progress(0)
            log_msgs = []

            def _prog(msg: str):
                log_msgs.append(msg)
                prog_box.markdown(
                    f"<div style='font-size:.84rem;color:#6B5B3E;padding:6px 0;'>{msg}</div>",
                    unsafe_allow_html=True,
                )
                prog_bar.progress(min(len(log_msgs) / (len(urls) + 2), 0.95))

            try:
                from video_editor import concat_clips
                import time as _time

                output_path = concat_clips(
                    video_urls=urls,
                    output_filename=f"念念成片_{int(_time.time())}.mp4",
                    progress_cb=_prog,
                )
                prog_bar.progress(1.0)
                prog_box.success(f"合成完成！已保存至：{output_path}")

                # 提供下载按钮
                with open(output_path, "rb") as _f:
                    st.download_button(
                        label="下载最终成片 (MP4)",
                        data=_f.read(),
                        file_name=Path(output_path).name,
                        mime="video/mp4",
                        type="primary",
                        key="dl_final",
                    )
            except Exception as _e:
                prog_bar.empty()
                st.error(f"合成失败：{_e}")

st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)