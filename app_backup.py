import json
import time
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
import copy
from PIL import Image

import streamlit as st
from streamlit_cropper import st_cropper

import gate_manager
import pipeline_runner
import comfyui_client
from llm_client import call_freeform, call_structured, describe_image, transcribe_audio

MV_STEPS = [
    {"id": "MV01", "name": "MV01 家属访谈结构化"},
    {"id": "MV02", "name": "MV02 信息校验与补全"},
    {"id": "MV03", "name": "MV03 三要素定稿"},
    {"id": "MV04", "name": "MV04 分镜制作"},
    {"id": "MV05", "name": "MV05 数字人渲染编排"},
    {"id": "MV06", "name": "MV06 最终时间轴"},
]

STATUS_BADGE = {
    "pending": "⚬ 待命",
    "running": "🟡 运行中",
    "awaiting_review": "🔵 需确认",
    "approved": "✅ 达成",
    "rejected": "✖ 已退回",
}


st.set_page_config(page_title="MV 流水线审核看板", layout="wide")

st.markdown(
    """
<style>
/* 引用类似 LegacyRemembered 的字体与极简风格 */
@import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700&family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Noto+Sans+SC:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Lato', 'Noto Sans SC', sans-serif !important;
    font-size: 16px;
    line-height: 1.5rem;
}

h1, h2, h3, .font-heading {
    font-family: 'Playfair Display', 'Noto Serif SC', serif !important;
}

/* 背景与排版重置 */
.stApp {
    background-color: #FFFFFF;
    color: #232425;
}

/* 卡片样式，参考前端交互审计 (.hover-card) */
.mv-card {
    padding: 24px;
    border-radius: 16px;
    background: #FFFFFF;
    border: 1px solid rgba(0,0,0,0.06);
    margin-bottom: 24px;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.03);
    transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mv-card:hover {
    box-shadow: 0px 8px 24px rgba(0,0,0,0.08);
    transform: translateY(-4px);
    border-color: rgba(0,0,0,0.12);
}

/* 卡片头部 */
.mv-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    border-bottom: 1px solid #f0f0f0;
    padding-bottom: 12px;
}
.mv-header strong, .mv-header h3 {
    margin: 0;
    font-weight: 600;
    color: #111111;
    font-size: 1.25rem;
}

/* 标签胶囊样式 (.mv-pill) */
.mv-pill {
    padding: 6px 14px;
    border-radius: 999px;
    background: #f8f9fa;
    font-size: 13px;
    font-weight: 500;
    color: #4b5563;
    border: 1px solid #e5e7eb;
}

/* 按钮全局覆盖 */
div.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1rem !important;
    transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* 品牌主色调按钮 (Primary Button) */
div.stButton > button[kind="primary"] {
    background-color: #0F7FFF !important;
    color: #FFFFFF !important;
    border: 1px solid #0F7FFF !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #0B61C4 !important;
    border-color: #0B61C4 !important;
}

/* 次要按钮弱化 */
div.stButton > button[kind="secondary"] {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    color: #374151 !important;
}
div.stButton > button[kind="secondary"]:hover {
    border-color: #d1d5db !important;
    background: #f9fafb !important;
    color: #111111 !important;
}

/* 输入框和 Expander 弱化边框 */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background-color: #fafafa;
    transition: border-color 150ms ease-in-out;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #0F7FFF;
    background-color: #ffffff;
}

.streamlit-expanderHeader {
    font-weight: 500;
    color: #374151;
    border-radius: 8px;
}
div[data-testid="stExpander"] {
    border: 1px solid #e5e7eb !important;
    border-radius: 12px !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 24px;
}
.stTabs [data-baseweb="tab"] {
    height: 50px;
    white-space: pre-wrap;
    background-color: transparent;
    border-radius: 0;
    color: #4b5563;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #111111;
    border-bottom: 2px solid #0F7FFF;
}
</style>
""",
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / "sample_inputs" / "sample_interview.json"
COMFYUI_WORKFLOW_DIR = BASE_DIR.parent / "ComfyUIJson"

COMFYUI_WORKFLOWS = {
    "Flux2 文生图 9B": {
        "file": "image_flux2_text_to_image_9b.json",
        "type": "image",
        "nodes": {
            "prompt": "76",
            "negative": "75:67",
            "width": "75:68",
            "height": "75:69",
            "steps": "75:62",
            "cfg": "75:63",
            "sampler": "75:61",
            "seed": "75:73",
        },
    },
    "Flux2 参考图编辑 9B": {
        "file": "image_flux2_klein_image_edit_9b_base.json",
        "type": "image",
        "nodes": {
            "prompt": "92:113",
            "negative": "92:87",
            "cfg": "92:114",
            "steps": "92:115",
            "sampler": "92:102",
            "seed": "92:105",
            "source_image": "76",
            "reference_image": "81",
        },
    },
    "LTX 2.3 视频 T2V": {
        "file": "video_ltx2_3_t2v.json",
        "type": "video",
        "nodes": {
            "prompt": "267:266",
            "negative": "267:247",
            "width": "267:257",
            "height": "267:258",
            "cfg": ["267:213", "267:231"],
            "sampler": ["267:246", "267:209"],
            "seed": ["267:216", "267:237"],
            "lora_strength": "267:232",
        },
    },
    "LTX 2.3 视频 I2V": {
        "file": "video_ltx2_3_i2v.json",
        "type": "video",
        "nodes": {
            "prompt": "267:266",
            "negative": "267:247",
            "width": "267:257",
            "height": "267:258",
            "cfg": ["267:213", "267:231"],
            "sampler": ["267:246", "267:209"],
            "seed": ["267:216", "267:237"],
            "lora_strength": "267:232",
            "source_image": "269",
        },
    },
}

COMFYUI_CANDIDATE_HOSTS = [
    "http://10.79.91.37:8188/",
    "http://10.79.65.44:8188/",
]

MV04_STANDALONE_SAMPLE = {
    "family_memory_text": "爷爷叫张建国，1948年5月12日出生在山东，2023年10月25日去世，享年75岁。追悼会定于10月29日在XX殡仪馆告别厅举行。爷爷最让我们记住的事，是他退休后每天早上5点起床为全家煮小米粥，坚持了40年。还有一件事是他退休后自学木工，亲手为孙女打了一套儿童家具。爷爷参过军，1970年入伍，服役10年。1985年还被评为单位先进工作者。遗愿是希望家人身体健康，孙女能考上好大学。主要致辞人是女儿张敏，偏好温和真诚的风格。",
    "uploaded_assets": [
        {
            "asset_id": "photo_01",
            "type": "portrait",
            "description": "2018年全家合影，爷爷坐在中间，戴银框眼镜，穿深灰色中山装",
            "time_period": "2010s",
        },
        {
            "asset_id": "photo_03",
            "type": "scene",
            "description": "爷爷在厨房煮粥的照片",
            "time_period": "2015",
        },
        {
            "asset_id": "photo_05",
            "type": "scene",
            "description": "爷爷在院子里做木工",
            "time_period": "2020",
        },
        {
            "asset_id": "video_01",
            "type": "video_clip",
            "description": "爷爷帮孙女安装家具的视频",
            "time_period": "2021",
        },
        {
            "asset_id": "audio_01",
            "type": "voice_sample",
            "description": "爷爷70岁生日时的讲话录音",
            "duration_sec": 120,
        },
    ],
    "style_preference": "warm_nostalgia",
    "emotional_intensity": "moderate",
    "ceremony_type": "family_memorial",
    "ceremony_date": "2023-10-29",
    "total_duration_sec": 330,
    "relatives": [
        {
            "relation": "daughter",
            "name": "张敏",
            "is_main_speaker": True,
            "speech_preference": "gentle_and_sincere",
        }
    ],
    "last_wishes": "希望家人身体健康，孙女能考上好大学",
}


def load_comfyui_workflow(file_name: str) -> Dict[str, Any]:
    workflow_path = COMFYUI_WORKFLOW_DIR / file_name
    if not workflow_path.exists():
        st.error(f"找不到工作流文件：{workflow_path}")
        return {}
    return json.loads(workflow_path.read_text(encoding="utf-8"))


def _get_node(workflow: Dict[str, Any], node_id: str) -> Dict[str, Any]:
    node = workflow.get(node_id, {})
    if isinstance(node, dict):
        return node
    return {}


def _get_input_value(workflow: Dict[str, Any], node_id: str, key: str, default: Any) -> Any:
    node = _get_node(workflow, node_id)
    return node.get("inputs", {}).get(key, default)


def get_workflow_defaults(workflow: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    nodes = config["nodes"]
    defaults: Dict[str, Any] = {}
    prompt_node = nodes.get("prompt")
    if prompt_node:
        defaults["prompt"] = _get_input_value(workflow, prompt_node, "value", "")
        if defaults["prompt"] == "":
            defaults["prompt"] = _get_input_value(workflow, prompt_node, "text", "")
    negative_node = nodes.get("negative")
    if negative_node:
        defaults["negative"] = _get_input_value(workflow, negative_node, "text", "")
    width_node = nodes.get("width")
    if width_node:
        defaults["width"] = _get_input_value(workflow, width_node, "value", 1280)
    height_node = nodes.get("height")
    if height_node:
        defaults["height"] = _get_input_value(workflow, height_node, "value", 720)
    steps_node = nodes.get("steps")
    if steps_node:
        defaults["steps"] = _get_input_value(workflow, steps_node, "steps", 20)
    cfg_nodes = nodes.get("cfg")
    if cfg_nodes:
        target = cfg_nodes[0] if isinstance(cfg_nodes, list) else cfg_nodes
        defaults["cfg"] = _get_input_value(workflow, target, "cfg", 5)
    sampler_nodes = nodes.get("sampler")
    if sampler_nodes:
        target = sampler_nodes[0] if isinstance(sampler_nodes, list) else sampler_nodes
        defaults["sampler"] = _get_input_value(workflow, target, "sampler_name", "euler")
    seed_nodes = nodes.get("seed")
    if seed_nodes:
        target = seed_nodes[0] if isinstance(seed_nodes, list) else seed_nodes
        defaults["seed"] = _get_input_value(workflow, target, "noise_seed", 42)
    lora_node = nodes.get("lora_strength")
    if lora_node:
        defaults["lora_strength"] = _get_input_value(workflow, lora_node, "strength_model", 0.5)
    source_image_node = nodes.get("source_image")
    if source_image_node:
        defaults["source_image"] = _get_input_value(workflow, source_image_node, "image", "")
    ref_image_node = nodes.get("reference_image")
    if ref_image_node:
        defaults["reference_image"] = _get_input_value(workflow, ref_image_node, "image", "")
    return defaults


def apply_workflow_inputs(workflow: Dict[str, Any], config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    updated = copy.deepcopy(workflow)
    nodes = config["nodes"]

    def update_nodes(node_ids: Any, key: str, value: Any) -> None:
        if not node_ids:
            return
        targets = node_ids if isinstance(node_ids, list) else [node_ids]
        for node_id in targets:
            node = updated.get(node_id)
            if not isinstance(node, dict):
                continue
            node.setdefault("inputs", {})[key] = value

    prompt_node = nodes.get("prompt")
    if prompt_node:
        node = updated.get(prompt_node, {})
        if node.get("class_type") in {"PrimitiveString", "PrimitiveStringMultiline"}:
            update_nodes(prompt_node, "value", values.get("prompt", ""))
        else:
            update_nodes(prompt_node, "text", values.get("prompt", ""))

    update_nodes(nodes.get("negative"), "text", values.get("negative", ""))
    update_nodes(nodes.get("width"), "value", values.get("width"))
    update_nodes(nodes.get("height"), "value", values.get("height"))
    update_nodes(nodes.get("steps"), "steps", values.get("steps"))
    update_nodes(nodes.get("cfg"), "cfg", values.get("cfg"))
    update_nodes(nodes.get("sampler"), "sampler_name", values.get("sampler"))
    update_nodes(nodes.get("seed"), "noise_seed", values.get("seed"))
    update_nodes(nodes.get("lora_strength"), "strength_model", values.get("lora_strength"))
    update_nodes(nodes.get("source_image"), "image", values.get("source_image"))
    update_nodes(nodes.get("reference_image"), "image", values.get("reference_image"))

    return updated


def build_comfyui_image_payload(
    prompt_text: str,
    workflow_name: str = "Flux2 文生图 9B",
    seed: int | None = None,
) -> Dict[str, Any]:
    workflow_config = COMFYUI_WORKFLOWS.get(workflow_name)
    if not workflow_config:
        raise ValueError("未找到 ComfyUI 文生图工作流")
    workflow = load_comfyui_workflow(workflow_config["file"])
    defaults = get_workflow_defaults(workflow, workflow_config)
    payload_values = {
        "prompt": prompt_text,
        "negative": defaults.get("negative", ""),
        "width": defaults.get("width", 1280),
        "height": defaults.get("height", 720),
        "steps": defaults.get("steps", 20),
        "cfg": defaults.get("cfg", 5),
        "sampler": defaults.get("sampler", "euler"),
        "seed": seed if seed is not None else defaults.get("seed", 42),
        "lora_strength": defaults.get("lora_strength"),
    }
    return apply_workflow_inputs(workflow, workflow_config, payload_values)


def build_comfyui_i2v_payload(prompt_text: str, source_image: str) -> Dict[str, Any]:
    workflow_config = COMFYUI_WORKFLOWS.get("LTX 2.3 视频 I2V")
    if not workflow_config:
        raise ValueError("未找到 ComfyUI 图生视频工作流")
    workflow = load_comfyui_workflow(workflow_config["file"])
    defaults = get_workflow_defaults(workflow, workflow_config)
    payload_values = {
        "prompt": prompt_text,
        "negative": defaults.get("negative", ""),
        "width": defaults.get("width", 1280),
        "height": defaults.get("height", 720),
        "cfg": defaults.get("cfg", 5),
        "sampler": defaults.get("sampler", "euler"),
        "seed": defaults.get("seed", 42),
        "lora_strength": defaults.get("lora_strength"),
        "source_image": source_image,
    }
    return apply_workflow_inputs(workflow, workflow_config, payload_values)


def resolve_comfyui_host(custom_host: str | None = None) -> str:
    candidates = [custom_host] if custom_host else []
    candidates.extend(COMFYUI_CANDIDATE_HOSTS)
    for candidate in candidates:
        if not candidate:
            continue
        if comfyui_client.ping(candidate):
            return candidate
    return custom_host or COMFYUI_CANDIDATE_HOSTS[0]


def render_comfyui_panel() -> None:
    st.markdown("## ComfyUI 生成中心")
    st.caption("连接同一 WiFi 的 5090 主机 ComfyUI，直接调用已准备的工作流。")

    detected_host = resolve_comfyui_host(st.session_state.get("comfyui_host"))
    host = st.text_input(
        "ComfyUI 节点地址",
        value=detected_host,
        help="支持输入 IP 或完整 URL，默认端口 8188。",
    )
    st.session_state["comfyui_host"] = host

    workflow_name = st.selectbox("选择工作流", list(COMFYUI_WORKFLOWS.keys()))
    workflow_config = COMFYUI_WORKFLOWS[workflow_name]
    workflow = load_comfyui_workflow(workflow_config["file"])
    defaults = get_workflow_defaults(workflow, workflow_config)

    with st.form("comfyui_form", clear_on_submit=False):
        prompt = st.text_area("Prompt", value=defaults.get("prompt", ""), height=140)
        negative = st.text_area("Negative Prompt", value=defaults.get("negative", ""), height=90)
        cols = st.columns(4)
        width = cols[0].number_input("宽度", value=int(defaults.get("width", 1280)), step=64)
        height = cols[1].number_input("高度", value=int(defaults.get("height", 720)), step=64)
        steps = cols[2].number_input("步数", value=int(defaults.get("steps", 20)), step=1)
        cfg = cols[3].number_input("CFG", value=float(defaults.get("cfg", 5)), step=0.5)

        sampler = st.text_input("采样器", value=str(defaults.get("sampler", "euler")))
        seed = st.number_input("随机种子", value=int(defaults.get("seed", 42)), step=1)

        lora_strength = None
        if "lora_strength" in defaults:
            lora_strength = st.slider("LoRA 强度", 0.0, 1.0, float(defaults.get("lora_strength", 0.5)), 0.05)

        source_upload = None
        source_image = None
        if "source_image" in defaults:
            st.markdown("**参考图一（源图）**")
            source_upload_raw = st.file_uploader("上传图一", type=["png", "jpg", "jpeg"], key="comfy_source")
            if source_upload_raw is not None:
                st.caption("裁剪源图：")
                img = Image.open(source_upload_raw)
                cropped_img = st_cropper(img, realtime_update=True, box_color='#0F7FFF', aspect_ratio=None, key="cropper_source")
                if cropped_img:
                    import io
                    buf = io.BytesIO()
                    cropped_img.save(buf, format="PNG")
                    buf.name = source_upload_raw.name
                    source_upload = buf
            source_image = st.text_input("或填写图一文件名", value=str(defaults.get("source_image", "")))

        reference_upload = None
        reference_image = None
        if "reference_image" in defaults:
            st.markdown("**参考图二（风格/目标）**")
            reference_upload_raw = st.file_uploader("上传图二", type=["png", "jpg", "jpeg"], key="comfy_reference")
            if reference_upload_raw is not None:
                st.caption("裁剪参考图：")
                img2 = Image.open(reference_upload_raw)
                cropped_img2 = st_cropper(img2, realtime_update=True, box_color='#0F7FFF', aspect_ratio=None, key="cropper_ref")
                if cropped_img2:
                    import io
                    buf2 = io.BytesIO()
                    cropped_img2.save(buf2, format="PNG")
                    buf2.name = reference_upload_raw.name
                    reference_upload = buf2
            reference_image = st.text_input("或填写图二文件名", value=str(defaults.get("reference_image", "")))

        submitted = st.form_submit_button("提交渲染任务")

    if submitted:
        try:
            if source_upload is not None:
                source_image = comfyui_client.upload_image(
                    host,
                    source_upload.getvalue(),
                    source_upload.name,
                )
            if reference_upload is not None:
                reference_image = comfyui_client.upload_image(
                    host,
                    reference_upload.getvalue(),
                    reference_upload.name,
                )
        except Exception as exc:
            st.error(f"上传参考图失败：{exc}")
            return

        payload_values = {
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "sampler": sampler,
            "seed": seed,
            "lora_strength": lora_strength,
            "source_image": source_image,
            "reference_image": reference_image,
        }
        workflow_payload = apply_workflow_inputs(workflow, workflow_config, payload_values)
        try:
            prompt_id = comfyui_client.submit_prompt(host, workflow_payload)
            st.session_state["comfyui_prompt_id"] = prompt_id
            st.success(f"任务已提交，Prompt ID: {prompt_id}")
        except Exception as exc:
            st.error(f"提交失败：{exc}")

    prompt_id = st.session_state.get("comfyui_prompt_id")
    if prompt_id:
        st.markdown(f"当前任务 ID：`{prompt_id}`")
        if st.button("刷新结果"):
            try:
                history = comfyui_client.get_history(host, prompt_id)
                outputs = comfyui_client.extract_outputs(history, prompt_id)
                st.session_state["comfyui_outputs"] = outputs
                if not outputs:
                    st.info("暂未检测到输出，请稍后再试。")
            except Exception as exc:
                st.error(f"读取输出失败：{exc}")

        outputs = st.session_state.get("comfyui_outputs", [])
        st.markdown("### 输出预览")
        if outputs:
            for item in outputs:
                url = comfyui_client.build_view_url(host, item)
                if item.get("kind") == "video":
                    st.video(url)
                else:
                    st.image(url)
                st.caption(url)
        else:
            st.info("暂无输出，请先提交任务或点击刷新结果。")


def load_sample() -> Dict[str, Any]:
    if SAMPLE_PATH.exists():
        return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return {}


def parse_json(text: str) -> Tuple[Dict[str, Any], str]:
    try:
        data = json.loads(text) if text.strip() else {}
        if not isinstance(data, dict):
            return {}, "请输入 JSON 对象作为输入。"
        return data, ""
    except json.JSONDecodeError as exc:
        return {}, f"JSON 解析失败：{exc}"


def parse_json_any(text: str) -> Tuple[Any, str]:
    try:
        data = json.loads(text) if text.strip() else None
        return data, ""
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败：{exc}"

def build_friendly_prompt(mv_id: str) -> str:
    return (
        "你是殡葬纪念视频项目的内容整理助手。"
        "请把给定的 JSON 输出转换成通俗易懂的陈述句，"
        "适合普通用户甚至老人也能理解。"
        "要求：用中文、分点陈述、句子简短、必须包含 JSON 里的关键字段和关键词（人名、地点、时间、情绪、事件等），"
        "不要遗漏关键信息，也不要编造。"
        f"输出标题包含 {mv_id}。"
    )

def build_json_rewrite_prompt(mv_id: str) -> str:
    return (
        "你是殡葬纪念视频项目的结构化输出整理助手。"
        "用户会提供一段可读的中文描述，以及原始 JSON。"
        "请将描述整理回与原始 JSON 结构一致的 JSON。"
        "要求：保留原有字段结构；"
        "描述中没有提到的字段尽量沿用原始值；"
        "不要额外添加不存在的字段。"
        f"输出必须是 {mv_id} 对应的 JSON。"
    )


def build_mv03_revision_prompt(mv03_skill: str) -> str:
    return (
        mv03_skill
        + "\n\n附加要求：根据用户的意见与手工补充的分镜，"
        "重新生成 MV04 的完整分镜 JSON，并输出通俗讲解。"
        "输出必须是 JSON，包含两个字段：\n"
        "1) storyboard_json：严格遵循 MV03 输出规范的 JSON；\n"
        "2) friendly_summary：通俗易懂的陈述句，包含关键人物、时间、地点、情绪与事件。"
        "如果用户手工提供了 scenes，请优先采用其结构与内容，除非与意见冲突。"
    )


def build_mv03_fill_prompt(mv03_skill: str) -> str:
    return (
        mv03_skill
        + "\n\n你将收到当前分镜 JSON、已人工填写的字段，以及整体项目上下文。"
        "请只补全/优化以下字段：shot_type, description, voice_script, mj_prompt, motion。"
        "要求：保持场景语境一致、符合 MV03 模板，不要修改其他字段。"
        "输出必须是 JSON，包含这五个字段。"
    )


def build_intake_prompt() -> str:
    return (
        "你是追悼会/生命回顾视频项目的信息整理助手。"
        "请根据用户输入的文字信息、素材清单与解析备注，整理出 MV01 所需的结构化 JSON。"
        "必须输出 JSON，字段包含："
        "family_memory_text, uploaded_assets, style_preference, emotional_intensity, ceremony_type, "
        "ceremony_date, total_duration_sec, relatives, last_wishes。"
        "uploaded_assets 为数组，每项包含 asset_id, type, description, time_period 或 duration_sec。"
        "如果素材信息不足，请根据文件名和用户描述进行合理概括，不要编造细节。"
        "请自动识别 relatives、style_preference、emotional_intensity 等字段，并与用户语气保持一致。"
        "relatives 是数组，字段包含 relation, name, is_main_speaker, speech_preference。"
    )


def extract_audio_from_video(video_bytes: bytes, suffix: str) -> Tuple[bytes | None, str]:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / f"input{suffix}"
            audio_path = Path(tmpdir) / "audio.wav"
            video_path.write_bytes(video_bytes)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(audio_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0 or not audio_path.exists():
                return None, result.stderr.strip() or "ffmpeg 解析失败"
            return audio_path.read_bytes(), ""
    except FileNotFoundError:
        return None, "未检测到 ffmpeg，无法解析视频"
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


def scenes_to_list(scenes: Any) -> List[Dict[str, Any]]:
    if isinstance(scenes, list):
        return [item for item in scenes if isinstance(item, dict)]
    if isinstance(scenes, dict):
        ordered_keys = sorted(scenes.keys())
        return [scenes[key] for key in ordered_keys if isinstance(scenes[key], dict)]
    return []


def list_to_scene_dict(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    scene_dict: Dict[str, Any] = {}
    for idx, scene in enumerate(scenes, start=1):
        scene_id = scene.get("scene_id") if isinstance(scene, dict) else None
        if not scene_id:
            scene_id = f"scene_{idx:02d}"
            if isinstance(scene, dict):
                scene = {**scene, "scene_id": scene_id}
        scene_dict[scene_id] = scene
    return scene_dict


def sync_mv03_editor_fields(scene: Dict[str, Any]) -> None:
    st.session_state["mv03_edit_time"] = scene.get("time", "")
    st.session_state["mv03_edit_shot_type"] = scene.get("shot_type", "")
    st.session_state["mv03_edit_description"] = scene.get("description", "")
    st.session_state["mv03_edit_voice"] = scene.get("voice_script", "")
    st.session_state["mv03_edit_mj"] = scene.get("mj_prompt", "")
    st.session_state["mv03_edit_motion"] = scene.get("motion", "")
def render_sidebar() -> None:
    st.sidebar.markdown("## 流水线进度")
    for step in MV_STEPS:
        status = gate_manager.get_status(step["id"])
        badge = STATUS_BADGE.get(status, "⚪ 未开始")
        st.sidebar.markdown(f"**{badge}**  {step['id']} · {step['name']}")
    st.sidebar.divider()
    if st.sidebar.button("🔄 重置全部阶段", use_container_width=True):
        pipeline_runner.reset_state()
        st.rerun()


def render_key_cards(output: Dict[str, Any], keys: List[str]) -> None:
    if not output:
        return
    cols = st.columns(len(keys)) if keys else []
    for idx, key in enumerate(keys):
        value = output.get(key, "-")
        with cols[idx]:
            st.markdown(
                f"<div class='mv-card'><strong>{key}</strong><br/>{value}</div>",
                unsafe_allow_html=True,
            )


def render_mv03_scenes(output: Dict[str, Any]) -> None:
    scenes = scenes_to_list(output.get("scenes", []) if isinstance(output, dict) else [])
    if not isinstance(scenes, list) or not scenes:
        st.info("暂无分镜数据。")
        return

    compact_mode = st.toggle("收起分镜详情（紧凑视图）", value=False, key="mv03_compact_view")

    for scene in scenes:
        if not isinstance(scene, dict):
            st.markdown(
                "<div class='mv-card'><div class='mv-header'><strong>分镜摘要</strong></div>",
                unsafe_allow_html=True,
            )
            st.write(scene)
            if st.button("查看详情", key=f"detail_text_{hash(scene)}"):
                st.session_state["mv03_detail_scene"] = {"description": str(scene)}
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        scene_id = scene.get("scene_id") or scene.get("id") or scene.get("scene") or "unknown"
        timecode = scene.get("time") or scene.get("timecode") or "-"
        shot_type = scene.get("shot_type", "-")
        description = scene.get("description", "-")
        if compact_mode:
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:12px; padding:8px 4px;'>"
                f"<span style='font-weight:600; color:#111;'>Scene {scene_id}</span>"
                f"<span style='flex:1; height:1px; background:#e5e7eb;'></span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            continue

        st.markdown(
            f"<div class='mv-card'><div class='mv-header'><strong>Scene {scene_id}</strong></div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**⏱️ {timecode}** · **🎥 {shot_type}**")
        st.markdown(f"<span style='color:#4b5563'>{description}</span>", unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([1, 1, 2])
        with col_a:
            is_open = (
                st.session_state.get("mv03_detail_scene", {}).get("scene_id") == scene_id
            )
            detail_label = "关闭详情" if is_open else "查看详情"
            if st.button(detail_label, key=f"detail_{scene_id}"):
                if is_open:
                    st.session_state.pop("mv03_detail_scene", None)
                else:
                    st.session_state["mv03_detail_scene"] = scene
                st.rerun()
        with col_b:
            if st.button(f"↩️ 退回此镜 {scene_id}", key=f"reject_scene_{scene_id}"):
                gate_manager.reject("MV03", {"ids": [scene_id]})
                st.warning(f"已标记退回镜头：{scene_id}")
        with col_c:
            detail_scene = st.session_state.get("mv03_detail_scene")
            if detail_scene and detail_scene.get("scene_id") == scene_id:
                st.markdown(
                    "<div style='border:1px solid #e5e7eb; border-radius:12px; padding:12px;'>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**分镜详情 · Scene {scene_id}**")
                st.markdown(f"**时间码**：{detail_scene.get('time', detail_scene.get('timecode', '-'))}")
                if detail_scene.get("duration_bucket"):
                    st.markdown(f"**时长规格**：{detail_scene.get('duration_bucket')}")
                st.markdown(f"**景别**：{detail_scene.get('shot_type', '-')}")
                st.markdown(f"**画面描写**：{detail_scene.get('description', '-')}")
                narration = detail_scene.get("voice_script") or detail_scene.get("narration") or detail_scene.get("voice_over")
                if narration:
                    st.markdown(f"**语音旁白**：{narration}")
                st.markdown(f"**资产类型**：{detail_scene.get('asset_type', '-')}")
                st.markdown("**MJ Prompt**")
                st.code(detail_scene.get("mj_prompt", "-"), language="text")
                st.markdown("**全局 Prompt**")
                st.code(detail_scene.get("prompt_global", "-"), language="text")
                st.markdown("**首帧 Prompt**")
                st.code(detail_scene.get("prompt_start", "-"), language="text")
                st.markdown("**视频 Prompt**")
                st.code(detail_scene.get("prompt_video", "-"), language="text")

                st.divider()
                st.markdown("**ComfyUI 渲染**")
                comfy_host = resolve_comfyui_host(st.session_state.get("comfyui_host"))
                prompt_text = detail_scene.get("mj_prompt") or detail_scene.get("description") or ""
                if "mv03_comfy_outputs" not in st.session_state:
                    st.session_state["mv03_comfy_outputs"] = {}
                if "mv03_comfy_prompt_ids" not in st.session_state:
                    st.session_state["mv03_comfy_prompt_ids"] = {}
                if "mv03_comfy_video_prompt_ids" not in st.session_state:
                    st.session_state["mv03_comfy_video_prompt_ids"] = {}
                if "mv03_comfy_video_outputs" not in st.session_state:
                    st.session_state["mv03_comfy_video_outputs"] = {}
                if "mv03_comfy_last_poll" not in st.session_state:
                    st.session_state["mv03_comfy_last_poll"] = {}
                if "mv03_comfy_video_last_poll" not in st.session_state:
                    st.session_state["mv03_comfy_video_last_poll"] = {}

                col_render_a, _ = st.columns([1, 1])
                with col_render_a:
                    if st.button("提交渲染任务", key=f"mv03_comfy_submit_{scene_id}"):
                        if not prompt_text:
                            st.warning("当前分镜没有可用的 Prompt。")
                        else:
                            try:
                                workflow_payload = build_comfyui_image_payload(
                                    prompt_text,
                                    seed=int(time.time() * 1000) % 2_147_483_647,
                                )
                                prompt_id = comfyui_client.submit_prompt(comfy_host, workflow_payload)
                                st.session_state["mv03_comfy_prompt_ids"][scene_id] = prompt_id
                                st.session_state["mv03_comfy_last_poll"][scene_id] = 0.0
                                st.success("已提交渲染任务")
                            except Exception as exc:
                                st.error(f"提交失败：{exc}")

                prompt_id = st.session_state["mv03_comfy_prompt_ids"].get(scene_id)
                if prompt_id:
                    last_poll = st.session_state["mv03_comfy_last_poll"].get(scene_id, 0.0)
                    now = time.time()
                    if now - last_poll > 5:
                        try:
                            history = comfyui_client.get_history(comfy_host, prompt_id)
                            outputs = comfyui_client.extract_outputs(history, prompt_id)
                            st.session_state["mv03_comfy_outputs"][scene_id] = outputs
                            st.session_state["mv03_comfy_last_poll"][scene_id] = now
                        except Exception as exc:
                            st.error(f"读取输出失败：{exc}")

                video_prompt_id = st.session_state["mv03_comfy_video_prompt_ids"].get(scene_id)
                if video_prompt_id:
                    last_poll = st.session_state["mv03_comfy_video_last_poll"].get(scene_id, 0.0)
                    now = time.time()
                    if now - last_poll > 5:
                        try:
                            history = comfyui_client.get_history(comfy_host, video_prompt_id)
                            outputs = comfyui_client.extract_outputs(history, video_prompt_id)
                            st.session_state["mv03_comfy_video_outputs"][scene_id] = outputs
                            st.session_state["mv03_comfy_video_last_poll"][scene_id] = now
                        except Exception as exc:
                            st.error(f"读取视频输出失败：{exc}")

                outputs = st.session_state["mv03_comfy_outputs"].get(scene_id, [])
                if outputs:
                    st.markdown("**渲染队列预览**")
                    thumb_cols = st.columns(5)
                    for idx, item in enumerate(outputs):
                        url = comfyui_client.build_view_url(comfy_host, item)
                        with thumb_cols[idx % 5]:
                            st.image(url, width=120)
                            zoom_key = f"mv03_comfy_zoom_url_{scene_id}"
                            zoom_label = "收起" if st.session_state.get(zoom_key) == url else "放大"
                            if st.button(zoom_label, key=f"mv03_comfy_zoom_{scene_id}_{idx}"):
                                if st.session_state.get(zoom_key) == url:
                                    st.session_state.pop(zoom_key, None)
                                else:
                                    st.session_state[zoom_key] = url

                    zoom_url = st.session_state.get(f"mv03_comfy_zoom_url_{scene_id}")
                    if zoom_url:
                        st.markdown("**大图预览**")
                        st.image(zoom_url, width="stretch")

                image_outputs = [item for item in outputs if item.get("kind") == "image"]
                if image_outputs:
                    st.markdown("**图生视频**")
                    image_options = {
                        f"{item.get('filename')}": item for item in image_outputs
                    }
                    selected_image_name = st.selectbox(
                        "选择首帧图像",
                        options=list(image_options.keys()),
                        key=f"mv03_i2v_select_{scene_id}",
                    )
                    if st.button("生成视频", key=f"mv03_i2v_run_{scene_id}"):
                        try:
                            prompt_for_video = detail_scene.get("prompt_video") or prompt_text
                            workflow_payload = build_comfyui_i2v_payload(
                                prompt_for_video,
                                selected_image_name,
                            )
                            prompt_id = comfyui_client.submit_prompt(comfy_host, workflow_payload)
                            st.session_state["mv03_comfy_video_prompt_ids"][scene_id] = prompt_id
                            st.session_state["mv03_comfy_video_last_poll"][scene_id] = 0.0
                            st.success("已提交视频任务")
                        except Exception as exc:
                            st.error(f"视频任务提交失败：{exc}")

                video_outputs = st.session_state["mv03_comfy_video_outputs"].get(scene_id, [])
                if video_outputs:
                    st.markdown("**视频预览**")
                    for item in video_outputs:
                        if item.get("kind") == "video":
                            url = comfyui_client.build_view_url(comfy_host, item)
                            st.video(url)
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


    with st.expander("MV04 分镜调整（LLM + 手工编辑）", expanded=False):
        feedback_key = "mv03_feedback"
        manual_key = "mv03_manual_scenes"
        if manual_key not in st.session_state:
            st.session_state[manual_key] = json.dumps(scenes, ensure_ascii=False, indent=2)

        st.markdown("### 分镜栏（可选中编辑）")
        scene_ids = [item.get("scene_id", f"scene_{idx:02d}") for idx, item in enumerate(scenes, start=1)]
        def _on_scene_change() -> None:
            current_id = st.session_state.get("mv03_scene_selector")
            current_scene = next((item for item in scenes if item.get("scene_id") == current_id), scenes[0])
            sync_mv03_editor_fields(current_scene)

        selected_scene_id = st.selectbox(
            "选择分镜",
            options=scene_ids,
            key="mv03_scene_selector",
            on_change=_on_scene_change,
        )
        selected_scene = next((item for item in scenes if item.get("scene_id") == selected_scene_id), scenes[0])

        col_scene_left, col_scene_right = st.columns([3, 1])
        with col_scene_left:
            if "mv03_edit_time" not in st.session_state:
                sync_mv03_editor_fields(selected_scene)
            st.text_input("scene_id", value=selected_scene.get("scene_id", ""), key="mv03_edit_scene_id", disabled=True)
            st.text_input("time", key="mv03_edit_time")
            st.text_input("shot_type", key="mv03_edit_shot_type")
            st.text_area("description", key="mv03_edit_description", height=80)
            st.text_area("voice_script", key="mv03_edit_voice", height=90)
            st.text_area("mj_prompt", key="mv03_edit_mj", height=90)
            st.text_input("motion", key="mv03_edit_motion")

        with col_scene_right:
            if st.button("保存本镜", key="mv03_save_scene", use_container_width=True):
                updated_scene = {
                    **selected_scene,
                    "shot_type": st.session_state.get("mv03_edit_shot_type", ""),
                    "description": st.session_state.get("mv03_edit_description", ""),
                    "voice_script": st.session_state.get("mv03_edit_voice", ""),
                    "mj_prompt": st.session_state.get("mv03_edit_mj", ""),
                    "motion": st.session_state.get("mv03_edit_motion", ""),
                    "time": st.session_state.get("mv03_edit_time", ""),
                }
                new_scenes = []
                for item in scenes:
                    if item.get("scene_id") == selected_scene_id:
                        new_scenes.append(updated_scene)
                    else:
                        new_scenes.append(item)
                output["scenes"] = list_to_scene_dict(new_scenes)
                output["total_scenes"] = len(new_scenes)
                pipeline_runner.save_output("MV03", output)
                st.success("已保存分镜修改")
                st.rerun()

            if st.button("一键补全字段", key="mv03_fill_scene", use_container_width=True):
                with st.spinner("正在调用 LLM 补全分镜字段..."):
                    mv03_prompt = pipeline_runner.get_skill_prompt("MV04")
                    system_prompt = build_mv03_fill_prompt(mv03_prompt)
                    payload = {
                        "project_json": output,
                        "current_scene": selected_scene,
                        "edited_fields": {
                            "shot_type": st.session_state.get("mv03_edit_shot_type", ""),
                            "description": st.session_state.get("mv03_edit_description", ""),
                            "voice_script": st.session_state.get("mv03_edit_voice", ""),
                            "mj_prompt": st.session_state.get("mv03_edit_mj", ""),
                            "motion": st.session_state.get("mv03_edit_motion", ""),
                        },
                    }
                    result = call_structured(system_prompt, json.dumps(payload, ensure_ascii=False, indent=2))
                    if result.get("error"):
                        st.error(result.get("message", "补全失败"))
                    else:
                        st.session_state["mv03_edit_shot_type"] = result.get("shot_type", "")
                        st.session_state["mv03_edit_description"] = result.get("description", "")
                        st.session_state["mv03_edit_voice"] = result.get("voice_script", "")
                        st.session_state["mv03_edit_mj"] = result.get("mj_prompt", "")
                        st.session_state["mv03_edit_motion"] = result.get("motion", "")
                        st.success("已补全字段，请检查后保存")

            if st.button("新增分镜", key="mv03_add_scene", use_container_width=True):
                new_id = f"scene_{len(scenes) + 1:02d}"
                new_scene = {
                    "scene_id": new_id,
                    "time": "",
                    "shot_type": "",
                    "description": "",
                    "voice_script": "",
                    "asset_type": selected_scene.get("asset_type", "ai_generated_video"),
                    "mj_prompt": "",
                    "negative_prompt": selected_scene.get("negative_prompt"),
                    "motion": "",
                    "fallback_asset": selected_scene.get("fallback_asset"),
                }
                new_scenes = scenes + [new_scene]
                output["scenes"] = list_to_scene_dict(new_scenes)
                output["total_scenes"] = len(new_scenes)
                pipeline_runner.save_output("MV03", output)
                st.success(f"已新增 {new_id}")
                st.rerun()

            if st.button("删除本镜", key="mv03_delete_scene", use_container_width=True):
                remaining = [item for item in scenes if item.get("scene_id") != selected_scene_id]
                output["scenes"] = list_to_scene_dict(remaining)
                output["total_scenes"] = len(remaining)
                pipeline_runner.save_output("MV03", output)
                st.success(f"已删除 {selected_scene_id}")
                st.rerun()

        st.text_area(
            "对分镜的意见（越具体越好）",
            key=feedback_key,
            height=120,
            placeholder="例如：删掉太悲伤的镜头、增加孙女回忆的镜头、把第2镜时长缩短...",
        )

        st.text_area(
            "手工分镜 JSON（可删除/新增/改写）",
            key=manual_key,
            height=240,
            help="支持 list 或 dict 格式，字段需遵循 MV03 模板。",
        )

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            delete_id = st.text_input("要删除的 scene_id", key="mv03_delete_id")
            if st.button("删除该分镜", key="mv03_delete_btn", use_container_width=True):
                if delete_id:
                    remaining = [item for item in scenes if item.get("scene_id") != delete_id]
                    output["scenes"] = list_to_scene_dict(remaining)
                    output["total_scenes"] = len(remaining)
                    pipeline_runner.save_output("MV03", output)
                    st.success(f"已删除 {delete_id}")
                    st.rerun()
                else:
                    st.warning("请输入要删除的 scene_id")

        with col_b:
            if st.button("应用手工分镜", key="mv03_apply_manual", use_container_width=True):
                manual_text = st.session_state.get(manual_key, "")
                parsed, err = parse_json_any(manual_text)
                if err:
                    st.error(err)
                else:
                    if isinstance(parsed, list):
                        scene_list = [item for item in parsed if isinstance(item, dict)]
                        output["scenes"] = list_to_scene_dict(scene_list)
                        output["total_scenes"] = len(scene_list)
                    elif isinstance(parsed, dict):
                        output["scenes"] = parsed
                        output["total_scenes"] = len(parsed)
                    else:
                        st.error("手工分镜必须是 list 或 dict")
                        return
                    pipeline_runner.save_output("MV03", output)
                    st.success("已应用手工分镜")
                    st.rerun()

        with col_c:
            if st.button("按意见重写分镜", key="mv03_llm_rewrite", use_container_width=True):
                if not output:
                    st.warning("暂无 JSON 输出，无法重写。")
                else:
                    with st.spinner("正在调用 LLM 生成新分镜..."):
                        mv03_prompt = pipeline_runner.get_skill_prompt("MV04")
                        system_prompt = build_mv03_revision_prompt(mv03_prompt)
                        payload = {
                            "original_json": output,
                            "user_feedback": st.session_state.get(feedback_key, ""),
                            "manual_scenes": st.session_state.get(manual_key, ""),
                        }
                        result = call_structured(system_prompt, json.dumps(payload, ensure_ascii=False, indent=2))
                        storyboard = result.get("storyboard_json") if isinstance(result, dict) else None
                        summary = result.get("friendly_summary", "") if isinstance(result, dict) else ""
                        if not isinstance(storyboard, dict):
                            st.error("LLM 返回结果不包含 storyboard_json")
                            return
                        pipeline_runner.save_output("MV04", storyboard)
                        st.session_state["friendly_MV04"] = summary
                        st.success("已生成新的分镜 JSON，并同步通俗讲解")
                        st.rerun()


def render_mv04_bibles(output: Dict[str, Any], approved: bool) -> None:
    cols = st.columns(3)
    with cols[0]:
        st.markdown("### 人物要素")
        st.json(output.get("character_bible", {}))
    with cols[1]:
        st.markdown("### 场景要素")
        st.json(output.get("scene_library", {}))
    with cols[2]:
        st.markdown("### 道具要素")
        st.json(output.get("prop_library", {}))
    if approved:
        st.success("已确认三要素")


def render_step(step: Dict[str, str], mv01_input: Dict[str, Any], input_ok: bool) -> None:
    mv_id = step["id"]
    next_index = pipeline_runner.MV_ORDER.index(mv_id) + 1
    next_gate = pipeline_runner.MV_ORDER[next_index] if next_index < len(pipeline_runner.MV_ORDER) else None
    status = gate_manager.get_status(mv_id)
    state = pipeline_runner.get_status().get(mv_id, {})
    duration = state.get("duration_sec")
    duration_text = f"{duration:.2f}s" if duration else "-"
    badge = STATUS_BADGE.get(status, "⚪ 未开始")

    st.markdown(
        f"""
        <div class='mv-card'>
            <div class='mv-header'>
                <div style="display:flex; align-items:center; gap:12px;">
                    <h3>{mv_id} · {step['name']}</h3>
                    <span class='mv-pill'>{badge}</span>
                </div>
            </div>
            <p style="color:#6b7280; font-size:14px; margin-top:-8px;">耗时记录：{duration_text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    output = pipeline_runner.read_output(mv_id)
    if state.get("error"):
        st.error(state.get("error"))

    if mv_id == "MV03":
        with st.expander("MV03 独立输入（跳过 MV01/MV02）", expanded=False):
            mv03_default = json.dumps(sample_inputs, ensure_ascii=False, indent=2)
            mv03_text = st.text_area(
                "MV03 输入 JSON",
                value=mv03_default,
                height=240,
                key="mv03_standalone_input",
            )
            mv03_payload, mv03_err = parse_json(mv03_text)
            if mv03_err:
                st.warning(mv03_err)
            if st.button("仅用输入生成 MV03 三要素", key="mv03_standalone_run", use_container_width=True):
                if mv03_err:
                    st.warning("请输入有效的 JSON 后再提交。")
                else:
                    with st.spinner("正在生成 MV03 三要素..."):
                        pipeline_runner.run_mv03_from_payload(mv03_payload)
                    st.success("已生成 MV03 三要素")
                    st.rerun()
        render_mv04_bibles(output, status == "approved")
    elif mv_id == "MV04":
        render_mv03_scenes(output)
    else:
        with st.expander("查看 JSON 输出", expanded=True):
            st.json(output or {})

    with st.expander("通俗描述（可编辑）", expanded=False):
        friendly_key = f"friendly_{mv_id}"
        if friendly_key not in st.session_state:
            st.session_state[friendly_key] = ""

        col_left, col_right = st.columns([1, 1])
        with col_left:
            if st.button("生成通俗描述", key=f"gen_friendly_{mv_id}", use_container_width=True):
                if not output:
                    st.warning("暂无 JSON 输出，无法生成描述。")
                else:
                    with st.spinner("正在生成通俗描述..."):
                        prompt = build_friendly_prompt(mv_id)
                        source_text = json.dumps(output, ensure_ascii=False, indent=2)
                        st.session_state[friendly_key] = call_freeform(prompt, source_text)
        with col_right:
            if st.button("用通俗描述回写 JSON", key=f"rewrite_json_{mv_id}", use_container_width=True):
                if not output:
                    st.warning("暂无 JSON 输出，无法回写。")
                else:
                    with st.spinner("正在整理 JSON..."):
                        prompt = build_json_rewrite_prompt(mv_id)
                        payload = json.dumps(
                            {
                                "original_json": output,
                                "edited_text": st.session_state.get(friendly_key, ""),
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        result = call_structured(prompt, payload)
                        if result.get("error"):
                            st.error(result.get("message", "回写失败"))
                        else:
                            pipeline_runner.save_output(mv_id, result)
                            st.success("已更新 JSON 输出。")
                            st.rerun()

        st.text_area(
            "通俗描述内容",
            key=friendly_key,
            height=200,
            placeholder="点击上方按钮生成通俗描述，然后可以直接编辑...",
        )

    if mv_id == "MV05" and output.get("requires_unlock_and_relock") is True:
        st.error("⚠️ 需返回MV03补齐三要素再重跑")

    if mv_id == "MV02" and output.get("status") == "needs_input":
        prompts = output.get("prompts", [])
        st.warning("补全建议：" + ("、".join(prompts) if prompts else "请补全缺失字段"))

    with st.expander("关键字段摘要", expanded=False):
        render_key_cards(output, list(output.keys())[:3])

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        rerun_disabled = (mv_id == "MV01" and not input_ok) or status == "running"
        if st.button("🔁 重新执行", key=f"rerun_{mv_id}", use_container_width=True, disabled=rerun_disabled):
            scope_text = st.session_state.get(f"scope_{mv_id}", "")
            scope_ids = [item.strip() for item in scope_text.split(",") if item.strip()]
            if scope_ids:
                pipeline_runner.rerun_partial(mv_id, {"ids": scope_ids}, output)
            else:
                pipeline_runner.run_step(mv_id, mv01_input if mv_id == "MV01" else None)
            st.rerun()

    with col2:
        scope_text = st.text_input(
            "退回字段/scene_id",
            key=f"scope_{mv_id}",
            placeholder="scene_01, field_name",
            label_visibility="collapsed",
        )
        if st.button("⬅ 退回", key=f"reject_{mv_id}", use_container_width=True):
            scope_ids = [item.strip() for item in scope_text.split(",") if item.strip()]
            scope = {"ids": scope_ids} if scope_ids else {"reason": "manual_reject"}
            gate_manager.reject(mv_id, scope)
            if next_gate:
                gate_manager.reset_from(next_gate)
            st.rerun()

    with col3:
        approve_disabled = status != "awaiting_review" or (mv_id == "MV02" and output.get("status") == "needs_input")
        approve_label = "✅ 通过 →"
        if mv_id == "MV03":
            approve_label = "✅ 确认三要素"
        if mv_id == "MV06":
            approve_label = "✅ 终审通过，导出最终JSON"
        if not (mv_id == "MV05" and output.get("requires_unlock_and_relock") is True):
            if st.button(approve_label, key=f"approve_{mv_id}", use_container_width=True, disabled=approve_disabled):
                gate_manager.approve(mv_id)
                st.rerun()

    if mv_id == "MV06" and status == "approved" and output:
        download_payload = json.dumps(output, ensure_ascii=False, indent=2)
        st.download_button(
            "下载 mv06_final_timeline.json",
            data=download_payload,
            file_name="mv06_final_timeline.json",
            mime="application/json",
        )


sample_inputs = load_sample()
render_sidebar()

tab_pipeline, tab_comfy = st.tabs(["MV 流水线", "ComfyUI 生成中心"])

with tab_pipeline:
    st.title("追悼会 MV 执行层 Demo")

    with st.expander("🧾 信息采集（文本 + 图片/音频/视频上传）", expanded=False):
        st.caption("支持粘贴文字与上传素材，系统会自动整理成 MV01 输入 JSON。")
        intake_text = st.text_area(
            "输入文字信息",
            height=180,
            key="intake_text",
            placeholder="可粘贴生平/回忆/仪式信息...",
        )
        intake_files = st.file_uploader(
            "上传素材（图片/音频/视频，可多选）",
            type=["png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "mp4", "mov", "mkv"],
            accept_multiple_files=True,
            key="intake_files",
        )
        intake_notes = st.text_area(
            "素材补充说明（可选）",
            height=120,
            key="intake_notes",
            placeholder="例如：photo_01 是全家福，photo_02 是厨房煮粥...",
        )
        if st.button("整理成 MV01 JSON", key="intake_to_mv01", use_container_width=True):
            if not intake_text and not intake_files:
                st.warning("请先输入文字或上传图片。")
            else:
                assets = []
                extracted_notes = []
                for idx, file in enumerate(intake_files or [], start=1):
                    file_bytes = file.getvalue()
                    ext = Path(file.name).suffix.lower().lstrip(".")
                    asset_type = "image" if ext in {"png", "jpg", "jpeg", "webp"} else "audio" if ext in {"mp3", "wav", "m4a"} else "video"
                    asset_id = f"{asset_type}_{idx:02d}"
                    asset_info: Dict[str, Any] = {
                        "asset_id": asset_id,
                        "type": asset_type,
                        "filename": file.name,
                    }
                    if asset_type == "image":
                        with st.spinner(f"解析图片 {file.name}..."):
                            description = describe_image(file_bytes, file.name)
                        asset_info["description"] = description
                        extracted_notes.append(f"{asset_id}: {description}")
                    elif asset_type == "audio":
                        with st.spinner(f"转写音频 {file.name}..."):
                            transcript = transcribe_audio(file_bytes, file.name)
                        asset_info["transcript"] = transcript
                        extracted_notes.append(f"{asset_id} 音频转写: {transcript}")
                    else:
                        audio_bytes, err = extract_audio_from_video(file_bytes, f".{ext}")
                        if audio_bytes:
                            with st.spinner(f"转写视频音轨 {file.name}..."):
                                transcript = transcribe_audio(audio_bytes, f"{file.name}.wav")
                            asset_info["transcript"] = transcript
                            extracted_notes.append(f"{asset_id} 视频转写: {transcript}")
                        else:
                            asset_info["warning"] = err or "视频解析失败"
                            extracted_notes.append(f"{asset_id} 视频解析失败: {err}")
                    assets.append(asset_info)

                payload = {
                    "user_text": intake_text,
                    "assets": assets,
                    "notes": intake_notes,
                    "extracted_notes": "\n".join(extracted_notes),
                }
                with st.spinner("正在整理输入信息..."):
                    result = call_structured(build_intake_prompt(), json.dumps(payload, ensure_ascii=False, indent=2))
                if result.get("error"):
                    st.error(result.get("message", "整理失败"))
                else:
                    st.session_state["mv01_text_input"] = json.dumps(
                        result, ensure_ascii=False, indent=2
                    )
                    st.success("已生成 MV01 输入 JSON，并填充到下方输入框。")

    input_default = json.dumps(sample_inputs, ensure_ascii=False, indent=2)
    if "mv01_text_input" not in st.session_state:
        st.session_state["mv01_text_input"] = input_default
    mv01_text = st.text_area(
        "MV01 输入 JSON",
        height=240,
        key="mv01_text_input",
    )
    mv01_input, mv01_error = parse_json(mv01_text)
    if mv01_error:
        st.warning(mv01_error)

    if st.button("▶ 从 MV01 开始执行", type="primary"):
        pipeline_runner.run_step("MV01", mv01_input)
        st.rerun()

    st.divider()

    for step in MV_STEPS:
        if step["id"] != "MV01" and not gate_manager.can_run(step["id"]):
            st.info(f"{step['id']} 需等待上一环节审核通过。")
        render_step(step, mv01_input, not bool(mv01_error))

with tab_comfy:
    render_comfyui_panel()
