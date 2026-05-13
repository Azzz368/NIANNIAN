# NianNian Memorial Studio — 分镜制作台（MV04-MV06）
import json
from pathlib import Path
from typing import Dict, List
import streamlit as st
import gate_manager
import pipeline_runner
from llm_client import build_scene_prompts, generate_image_302, generate_video_302

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

# ─── 参考照片状态栏 ───────────────────────────────────────────────────────────
_anc_b64 = st.session_state.get("ancestor_photo_b64")
_anc_name = st.session_state.get("ancestor_photo_filename", "")
if _anc_b64:
    _col_photo, _col_info, _col_del = st.columns([1, 5, 1])
    with _col_photo:
        st.image("data:image/jpeg;base64," + _anc_b64, width=64)
    with _col_info:
        st.markdown(
            f"<div style='padding:10px 0;'>"
            f"<div style='font-size:.82rem;font-weight:700;color:#065F46;'>逝者参考照片已载入</div>"
            f"<div style='font-size:.76rem;color:#6B7280;margin-top:2px;'>{_anc_name} · 含逝者的分镜将使用此照片锚定形象</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with _col_del:
        if st.button("移除", key="del_anc_photo", use_container_width=True):
            st.session_state.pop("ancestor_photo_b64", None)
            st.session_state.pop("ancestor_photo_filename", None)
            st.rerun()
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
else:
    st.markdown(
        "<div style='display:flex;align-items:center;gap:8px;padding:10px 14px;"
        "background:#FEF3C7;border:1px solid #FDE68A;border-radius:10px;margin-bottom:10px;'>"
        "<span style='font-size:.84rem;color:#92400E;'>提示：在首页上传逝者照片后，分镜生成时将自动锚定其面部形象</span></div>",
        unsafe_allow_html=True,
    )

# ─── 图床上传连通性测试（开发调试用）──────────────────────────────────────────
import os as _os
_imgbb_key = _os.getenv("IMGBB_API_KEY", "")
with st.expander("🔧 调试：测试图床上传连通性", expanded=False):
    st.caption("依次测试 0x0.st → tmpfiles.org → litterbox，确认哪个可用")
    if st.button("立即测试图床上传", key="test_imgbb"):
        import requests as _rq, base64 as _b64
        _test_bytes = _b64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        # 测试 0x0.st
        try:
            _r = _rq.post("https://0x0.st",
                          files={"file": ("test.png", _test_bytes, "image/png")}, timeout=15)
            if _r.status_code == 200 and _r.text.strip().startswith("https://"):
                st.success(f"✅ 0x0.st 成功：{_r.text.strip()}")
            else:
                st.error(f"❌ 0x0.st 失败 status={_r.status_code}：{_r.text[:200]}")
        except Exception as _e:
            st.error(f"❌ 0x0.st 异常：{_e}")
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

# ─── MV04 分镜故事板 ──────────────────────────────────────────────────────────
st.markdown(
    "<div class='step-row'><span class='step-dot'>4</span>"
    "<div><div class='step-name'>分镜故事板</div>"
    "<div class='step-desc'>工业级分镜 · Prompt 引擎</div></div></div>",
    unsafe_allow_html=True,
)

phase = st.session_state["studio_phase"]

if phase == "idle":
    cached = pipeline_runner.read_output("MV04")
    if cached and cached.get("scenes"):
        st.session_state["studio_scenes"] = _scenes_to_list(cached.get("scenes", []))
        st.session_state["studio_mv04"] = cached
        st.session_state["studio_phase"] = "done"
        st.rerun()
    else:
        st.session_state["studio_phase"] = "running"
        st.rerun()

if phase == "running":
    ph = st.empty()
    ph.markdown(_THINKING_HTML, unsafe_allow_html=True)
    try:
        pipeline_runner.run_step("MV04")
        gate_manager.approve("MV04")
        mv04_out = pipeline_runner.read_output("MV04") or {}
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
                _ref_kws_batch   = ["逝者","爷爷","奶奶","父亲","母亲","grandfather",
                                    "elderly man","elderly woman","deceased","他","她"]
                if _batch_dec_name:
                    _ref_kws_batch.append(_batch_dec_name)
                for idx, sc in enumerate(scenes):
                    _sid = sc.get("scene_id") or f"scene_{idx+1:02d}"
                    _pr  = sc.get("mj_prompt") or sc.get("prompt_global") or sc.get("description") or ""
                    try:
                        _pm  = build_scene_prompts(sc, character_bible, scene_library)
                        _img_prompt = _pm.get("image_prompt") or _pr
                        # 判断该分镜是否涉及逝者，若是则传入参考照片
                        _use_ref_batch = False
                        if _batch_anc_b64:
                            _subj_lc = str(sc.get("subject", "")).lower()
                            _desc_lc = str(sc.get("description", "")).lower()
                            _use_ref_batch = any(kw in _subj_lc or kw in _desc_lc for kw in _ref_kws_batch)
                        _b64, _ = generate_image_302(
                            _img_prompt,
                            reference_b64=_batch_anc_b64 if _use_ref_batch else None,
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
                            st.markdown(
                                f"<div style='margin:4px 0 6px;'>"
                                f"<span class='vid-badge {label_cls}'>{label_txt}</span>"
                                f"<span style='font-size:.72rem;color:var(--muted-l);margin-left:8px;'>"
                                f"task: {vr['task_id'][-8:]}</span></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button("刷新视频状态", key=f"qvid_{vid_key}", use_container_width=True):
                                import requests as _rq
                                from llm_client import _302_API_KEY as _AK
                                try:
                                    _r2 = _rq.get(
                                        f"https://api.302.ai/klingai/task/{vr['task_id']}/fetch",
                                        headers={"Authorization": f"Bearer {_AK}"}, timeout=20,
                                    )
                                    _pd = _r2.json().get("data", {})
                                    _new_status = _pd.get("status", cur_status)
                                    if _new_status == 99:
                                        # taskWorks[0].resource.resource  OR  works[0].resource.url
                                        _vurl = ""
                                        _tw = _pd.get("taskWorks") or []
                                        _wk = _pd.get("works") or []
                                        if _tw:
                                            _vurl = (_tw[0].get("resource") or {}).get("resource") or ""
                                        if not _vurl and _wk:
                                            _vurl = (_wk[0].get("resource") or {}).get("url") or ""
                                        st.session_state["studio_scene_videos"][vid_key] = {
                                            "url": _vurl, "task_id": vr["task_id"], "status": 99
                                        }
                                    else:
                                        st.session_state["studio_scene_videos"][vid_key] = {**vr, "status": _new_status}
                                    st.rerun()
                                except Exception as _e:
                                    st.warning(f"查询失败：{_e}")
                        elif vid_prompt:
                            if st.button("生成视频", key=f"genvid_{vid_key}", use_container_width=True):
                                with st.spinner("正在上传首帧图并提交视频任务..."):
                                    # 若有逝者参考照片且该分镜涉及逝者，在 prompt 前注入外貌一致性指令
                                    _vid_anc = st.session_state.get("ancestor_photo_b64")
                                    _vid_final_prompt = vid_prompt
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
                                                + vid_prompt
                                            )
                                    vr2 = generate_video_302(
                                        _vid_final_prompt,
                                        image_url="data:image/png;base64," + imgs[j],
                                        duration=5, poll=False,
                                    )
                                if vr2.get("error"):
                                    # 区分「图床上传失败」和「可灵 API 失败」，给出明确提示
                                    _err_msg = vr2["error"]
                                    if "图片上传" in _err_msg or "公共图床" in _err_msg:
                                        st.error(f"❌ 首帧图上传失败（图床故障）：{_err_msg}\n\n"
                                                 "请检查 IMGBB_API_KEY 是否已在 Secrets 中配置。")
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
                            pm  = build_scene_prompts(scene, character_bible, scene_library)
                            img_prompt = pm.get("image_prompt") or pr_raw

                            # ── 判断该分镜是否出现逝者，若有则传入参考照片 ──────
                            _ancestor_b64 = st.session_state.get("ancestor_photo_b64")
                            _use_ref = False
                            if _ancestor_b64:
                                _subject = str(scene.get("subject", "")).lower()
                                _desc_lc = str(desc).lower()
                                _deceased_name = str(
                                    st.session_state.get("form_data", {}).get("deceased_name", "")
                                ).lower()
                                # 分镜主体含逝者相关词则使用参考照片
                                _ref_kws = ["逝者", "爷爷", "奶奶", "父亲", "母亲", "grandfather",
                                            "elderly man", "elderly woman", "deceased", "他", "她"]
                                if _deceased_name:
                                    _ref_kws.append(_deceased_name)
                                _use_ref = any(kw in _subject or kw in _desc_lc for kw in _ref_kws)

                            b64, err = generate_image_302(
                                img_prompt,
                                reference_b64=_ancestor_b64 if _use_ref else None,
                            )
                            if b64:
                                st.session_state["studio_scene_images"][sid] = \
                                    st.session_state["studio_scene_images"].get(sid, []) + [b64]
                                st.session_state["studio_scene_vidprompts"][sid] = \
                                    pm.get("video_prompt") or desc
                                if _use_ref:
                                    st.caption("已使用逝者参考照片生成，形象已锁定")
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