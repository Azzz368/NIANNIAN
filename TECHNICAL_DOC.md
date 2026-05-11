# 念念数字人纪念平台 — 技术文档

> **项目版本**：Memorial Pipeline v2.0  
> **更新日期**：2026-05-06  
> **代码仓库**：`NianNianDigitalHumanPlatform / memorial-pipeline-test`

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
   - 4.1 [入口层 — app.py](#41-入口层--apppy)
   - 4.2 [LLM 客户端 — llm_client.py](#42-llm-客户端--llm_clientpy)
   - 4.3 [Pipeline 执行器 — pipeline_runner.py](#43-pipeline-执行器--pipeline_runnerpy)
   - 4.4 [人工闸门 — gate_manager.py](#44-人工闸门--gate_managerpy)
   - 4.5 [技能加载器 — skill_loader.py](#45-技能加载器--skill_loaderpy)
   - 4.6 [分镜制作台 — pages/studio.py](#46-分镜制作台--pagesstudiopy)
   - 4.7 [方案确认页 — pages/pipeline.py](#47-方案确认页--pagespipelinepy)
   - 4.8 [视频剪辑器 — video_editor.py](#48-视频剪辑器--video_editorpy)
5. [六阶 MV Pipeline 详解](#5-六阶-mv-pipeline-详解)
6. [AI 模型调用链](#6-ai-模型调用链)
7. [图像生成与首帧锚定机制](#7-图像生成与首帧锚定机制)
8. [视频生成与图床上传机制](#8-视频生成与图床上传机制)
9. [状态管理与数据流](#9-状态管理与数据流)
10. [配置与环境变量](#10-配置与环境变量)
11. [错误处理与降级策略](#11-错误处理与降级策略)
12. [数据持久化](#12-数据持久化)

---

## 1. 项目概述

念念数字人纪念平台是一套面向追悼会场景的 **AI 全自动纪念视频生成系统**。家属通过对话式采访提供逝者信息后，系统自动流经六个 AI 处理步骤（MV01-MV06），最终输出可在追悼会大屏播放的数字人纪念短片。

**核心能力：**
- 共情式对话采集（AI 访谈，替代冰冷表单）
- 自动结构化分析（信息校验、风格锁定、角色 DNA 提取）
- 工业级分镜生成（逐镜 Prompt 工程）
- AI 图像生成 + 逝者人像参考锚定（面孔一致性）
- AI 视频生成（图生视频，以生成图为首帧）
- 一键视频剪辑合成（用户选片 → 自动拼接 → MP4 下载）

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        Streamlit 前端层                          │
│  app.py (MV01 采访+MV02 确认)  │  pages/pipeline.py (MV03)      │
│                                │  pages/studio.py (MV04-MV06)   │
└───────────────┬────────────────┴──────────────────┬─────────────┘
                │                                   │
                ▼                                   ▼
┌──────────────────────────┐         ┌──────────────────────────────┐
│    pipeline_runner.py    │         │       llm_client.py          │
│  六阶 Pipeline 编排引擎   │◄───────►│   302.ai 统一网关客户端       │
│  · run_step(mv_id)       │         │  · call_skill() 文本推理      │
│  · read_output()         │         │  · generate_image_302() 图像 │
│  · normalize_storyboard()│         │  · generate_video_302() 视频 │
└──────────┬───────────────┘         │  · describe_image() 视觉理解 │
           │                         │  · transcribe_audio() 语音   │
           ▼                         └──────────────┬───────────────┘
┌──────────────────────────┐                        │
│     gate_manager.py      │                        ▼
│  人工审核闸门（G1-G6）    │         ┌──────────────────────────────┐
│  · pending / running     │         │         302.ai 网关           │
│  · awaiting_review       │         │  ┌─────────────────────────┐ │
│  · approved / rejected   │         │  │ claude-sonnet-4-6 (主力) │ │
└──────────────────────────┘         │  │ gpt-5.4 (文本回退)       │ │
           │                         │  │ gpt-4o (分镜专用)        │ │
           ▼                         │  │ gemini-2.5-flash (视觉)  │ │
┌──────────────────────────┐         │  │ nano-banana (图像生成)   │ │
│     skill_loader.py      │         │  │ gpt-4o-image (图像备用)  │ │
│  · 加载 .md Skill Prompt │         │  │ Kling omni3 (视频生成)   │ │
│  · 追加 JSON 约束指令    │         │  │ whisper-1 (语音转写)     │ │
└──────────────────────────┘         │  └─────────────────────────┘ │
                                     └──────────────────────────────┘
                                                    │
                                                    ▼
                                     ┌──────────────────────────────┐
                                     │       video_editor.py        │
                                     │  · download_video() 下载     │
                                     │  · concat_clips() 拼接合成   │
                                     │  · moviepy 2.x + libx264     │
                                     └──────────────────────────────┘
```

---

## 3. 目录结构

```
memorial-pipeline-test/
│
├── app.py                    # 主入口：MV01 采访 + MV02 确认（Streamlit 多页应用根页）
├── llm_client.py             # 所有 AI 调用的统一封装层
├── pipeline_runner.py        # MV Pipeline 编排执行器
├── gate_manager.py           # 人工审核闸门状态机
├── skill_loader.py           # Skill Prompt 加载器
├── video_editor.py           # 视频下载 + 拼接合成
│
├── pages/
│   ├── pipeline.py           # MV03 角色/场景/风格三要素确认页
│   └── studio.py             # MV04 分镜制作台 + MV05 数字人 + MV06 剪辑台
│
├── skills/                   # Skill Prompt 定义文件（.md 格式）
│   ├── MV01-interview.md     # 采访引导 Prompt
│   ├── MV02-validation.md    # 信息校验 Prompt
│   ├── MV03-storyboard.md    # 分镜故事板 Prompt（MV04 使用）
│   ├── MV04-bible-lock.md    # 角色/场景/风格锁定 Prompt（MV03 使用）
│   ├── MV05-avatar-render.md # 数字人驱动 Prompt
│   ├── MV06-final-cut.md     # 最终剪辑编排 Prompt
│   └── mother-skill.md       # 元 Skill（全局约束）
│
├── outputs/                  # Pipeline 各步骤 JSON 输出（持久化）
│   ├── mv01.json ~ mv06.json
│   └── final_cuts/           # 合成成片 .mp4 存放目录
│
├── sample_inputs/
│   └── sample_interview.json # 测试用采访数据样本
│
├── .env                      # 环境变量（API Key 等，不提交 Git）
├── requirements.txt          # Python 依赖
└── TECHNICAL_DOC.md          # 本文档
```

---

## 4. 核心模块详解

### 4.1 入口层 — `app.py`

**职责**：MV01 家属采访 + MV02 信息确认的 Streamlit UI，是整个应用的根页面。

**页面流程（`phase` 状态机）：**

```
form (表单填写)
    │  用户点击"唤起念念 AI"
    ▼
chat (AI 对话采访)
    │  达到结束条件（AI 判断信息足够）
    ▼
confirm (确认结构化输出)
    │  用户点击"确认方案，进入制作"
    ▼
→ 跳转至 pages/pipeline.py
```

**关键 session_state 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `phase` | str | 当前页面阶段：`form` / `chat` / `confirm` |
| `form_data` | dict | Step1+Step2 表单数据（逝者信息、回忆文字、风格） |
| `intake_assets` | list | 上传的多媒体资产列表（图片/音频/视频） |
| `chat_history` | list | AI 对话历史，格式 `[{role, content}]` |
| `mv01_output` | dict | MV01 结构化 JSON 结果 |
| `ancestor_photo_b64` | str | 逝者参考人像的 base64（用于图像生成锚定） |
| `ancestor_photo_filename` | str | 参考人像文件名 |

**人像参考照片自动识别逻辑（Step2 上传时）：**

```python
# 调用 describe_image() 获取图像描述
desc = describe_image(fb, f.name)

# 检测描述或文件名中是否含人像关键词
_person_kws = ("人","脸","男","女","老","portrait","person","face",
               "man","woman","elderly","grandfather","grandmother")

# 若含人像词且尚未设置参考照片 → 存为 ancestor_photo_b64
if not st.session_state.get("ancestor_photo_b64") and any(kw in desc for kw in _person_kws):
    st.session_state["ancestor_photo_b64"] = base64.b64encode(fb).decode()
```

---

### 4.2 LLM 客户端 — `llm_client.py`

**职责**：所有 AI 服务调用的统一封装，通过 **302.ai 统一网关** 访问多个模型。

#### 4.2.1 客户端初始化

```python
PRIMARY_CLIENT = OpenAI(
    api_key  = os.getenv("AI302_API_KEY"),
    base_url = "https://api.302.ai/v1"
)
```

所有模型（文本/图像/视频/音频）均通过同一 base_url + API Key 访问，302.ai 在网关层路由到对应的模型提供商。

#### 4.2.2 模型优先级队列

**文本推理队列**（`_text_model_queue()`）：

```
1. claude-sonnet-4-6  → 主力（强推理、长上下文）
2. gpt-5.4            → 自动回退（API 超时或限流时）
3. 本地 LLM           → 可选备用（需配置 LOCAL_LLM_BASE_URL）
```

**分镜制作专属队列**（`_storyboard_model_queue()`，仅 MV04 使用）：

```
1. gpt-4o    → 结构化输出稳定，Prompt 遵循度高
2. gpt-5.4   → 备用
```

#### 4.2.3 JSON 模式兼容处理

Claude 和 Gemini 不支持 `response_format={"type":"json_object"}`，需手动处理：

```python
_JSON_MODE_UNSUPPORTED = ("claude", "gemini")

def _supports_json_mode(model_name: str) -> bool:
    return not any(model_name.lower().startswith(p) for p in _JSON_MODE_UNSUPPORTED)
```

- **支持 JSON mode**（GPT 系列）：直接设 `response_format`，模型保证输出合法 JSON。
- **不支持 JSON mode**（Claude/Gemini）：在 system prompt 末尾追加强制 JSON 约束指令，并用 `_extract_json()` 从回复中提取 `{ }` 块。

#### 4.2.4 核心函数清单

| 函数 | 模型 | 用途 |
|------|------|------|
| `call_skill(skill_name, system, payload)` | 文本队列（MV04 用分镜队列）| Pipeline 各步执行，返回结构化 JSON |
| `call_memorial_chat(system, messages)` | 文本队列 | 多轮对话采访，返回纯文本 |
| `call_freeform(system, content)` | 文本队列 | 自由文本生成 |
| `call_structured(system, content)` | 文本队列 | 结构化 JSON 生成 |
| `call_storyboard(system, content)` | 分镜队列 | 分镜 Prompt 专用 |
| `describe_image(bytes, filename)` | gemini-2.5-flash | 图像内容理解，返回中文描述 |
| `transcribe_audio(bytes, filename)` | whisper-1 | 语音转写，返回文字 |
| `build_scene_prompts(scene, bible, lib)` | gpt-4o | 从分镜+角色DNA生成 image/video prompt |
| `generate_image_302(prompt, reference_b64)` | nano-banana → gpt-4o-image | 图像生成，支持参考人像 |
| `generate_video_302(prompt, image_url, ...)` | Kling omni3 | 图生视频或文生视频 |
| `_upload_image_to_public(bytes, ext)` | freeimage.host → litterbox | 图片上传至公共图床 |

#### 4.2.5 重试机制

所有 LLM 调用均有内置重试：

```python
for model_name, client in model_queue:
    for attempt in range(1, 4):   # 每个模型最多尝试 3 次
        try:
            response = client.chat.completions.create(...)
            return parse(response)
        except Exception:
            if attempt < 3:
                time.sleep(2)     # 失败后等待 2 秒再重试
# 所有模型全部失败 → 返回 {"error": True, ...}
```

---

### 4.3 Pipeline 执行器 — `pipeline_runner.py`

**职责**：管理六阶 MV Pipeline 的执行顺序、状态跟踪、输入输出链路。

#### 4.3.1 执行顺序

```python
MV_ORDER = ["MV01", "MV02", "MV03", "MV04", "MV05", "MV06"]
```

每一步的输入 = 上一步的 `outputs/mvXX.json` 输出（MV01 例外，输入来自表单）：

```python
def build_payload(mv_id: str, mv01_input=None) -> dict:
    if mv_id == "MV01":
        return mv01_input or {}
    prev_mv = MV_ORDER[MV_ORDER.index(mv_id) - 1]
    return read_output(prev_mv)   # 读取上一步的 JSON 文件
```

#### 4.3.2 Skill 文件映射

> 注意：文件名与逻辑步骤编号存在错位（历史原因），以下是实际对应关系：

| Pipeline 步骤 | Skill 文件 | 实际功能 |
|--------------|-----------|---------|
| MV01 | `MV01-interview.md` | 采访引导 |
| MV02 | `MV02-validation.md` | 信息校验 |
| MV03 | `MV04-bible-lock.md` | 三要素锁定（角色/场景/风格） |
| MV04 | `MV03-storyboard.md` | 分镜故事板生成 |
| MV05 | `MV05-avatar-render.md` | 数字人驱动 |
| MV06 | `MV06-final-cut.md` | 最终剪辑编排 |

#### 4.3.3 单步执行流程 `run_step(mv_id)`

```
1. gate_manager.can_run(mv_id) → 检查上一步是否 approved
2. gate_manager.set_running(mv_id) → 更新状态为 running
3. skill_loader.load_skill(path) → 加载 Prompt
4. build_payload(mv_id) → 从上一步输出构建输入
5. llm_client.call_skill(mv_id, prompt, payload) → 调用 LLM
6. [MV04 特有] normalize_storyboard_output() → 分镜时长规范化
7. _write_output(mv_id, result) → 持久化到 outputs/mvXX.json
8. gate_manager.set_awaiting_review() → 等待人工审核
```

#### 4.3.4 分镜时长规范化 `normalize_storyboard_output()`

将 LLM 输出的 `time` 字段（如 `"0:00-0:08"`）转换为标准时长桶：

```python
解析秒数 → 时长桶
≤ 7 秒  → 5s
≤ 12 秒 → 10s
> 12 秒 → 15s
```

每个 scene 自动补充：
- `duration_sec` — 秒数（整数）
- `duration_bucket` — 桶标签（`"5s"` / `"10s"` / `"15s"`）
- `prompt_global` — 全局 Prompt
- `prompt_start` — 首帧 Prompt
- `prompt_video` — 视频 Prompt（含时长）

#### 4.3.5 局部重执行 `rerun_partial(mv_id, scope, prev_output)`

用于家属仅对部分内容不满意时的局部重生成，避免全链路重跑：

```python
payload = {"scope": scope, "previous_output": prev_output}
result  = call_skill(mv_id, prompt, payload)
merged  = {**prev_output, **result}  # 新结果覆盖旧输出中对应字段
```

---

### 4.4 人工闸门 — `gate_manager.py`

**职责**：实现"人在回路（Human-in-the-Loop）"的五状态闸门机制，每一步必须经过人工审核才能解锁下一步。

#### 4.4.1 状态定义

```
pending         → 尚未执行（初始状态）
running         → 正在执行 LLM 调用
awaiting_review → 已完成，等待家属/操作员审核
approved        → 审核通过，下一步可执行
rejected        → 审核拒绝，需重新执行（支持局部重跑）
```

#### 4.4.2 顺序解锁逻辑

```python
def can_run(gate: str) -> bool:
    index = GATE_ORDER.index(gate)
    if index == 0:
        return True   # MV01 无前置依赖，直接可运行
    prev_gate = GATE_ORDER[index - 1]
    return get_status(prev_gate) == "approved"   # 上一步必须 approved
```

#### 4.4.3 状态存储

所有闸门状态存储于 Streamlit `session_state`（内存级别，刷新丢失）：

```python
st.session_state["gate_status"]     = {"MV01": "approved", "MV02": "pending", ...}
st.session_state["gate_rejections"] = {"MV01": {}, "MV02": {}, ...}
```

> ⚠️ **注意**：gate 状态不持久化。页面刷新后 Pipeline 输出文件（`outputs/*.json`）仍在，但 gate 状态需根据文件存在与否重新初始化。

---

### 4.5 技能加载器 — `skill_loader.py`

**职责**：读取 `.md` Skill Prompt 文件，并统一追加 JSON 输出约束指令。

```python
OUTPUT_CONSTRAINT = "只输出合法JSON对象，禁止任何Markdown代码块、注释和前缀文字。"

def load_skill(path: str) -> str:
    content = Path(path).read_text(encoding="utf-8")
    return f"{content.rstrip()}\n\n{OUTPUT_CONSTRAINT}\n"
```

**设计意图**：Skill 文件本身不含 JSON 约束（保持可读性），由加载器统一注入，避免各 Skill 文件重复维护约束文字，且便于全局修改约束措辞。

---

### 4.6 分镜制作台 — `pages/studio.py`

**职责**：MV04 分镜生成、图像生成、视频生成的可视化操作台，以及一键剪辑合成功能。

#### 4.6.1 Session State 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `studio_phase` | str | `idle` / `running` / `done` |
| `studio_scenes` | list | 当前分镜列表 |
| `studio_mv04` | dict | MV04 完整输出 JSON |
| `studio_scene_images` | dict | `{sid: [b64_str, ...]}` 每个分镜已生成的图片 |
| `studio_scene_vidprompts` | dict | `{sid: prompt_str}` 视频 Prompt |
| `studio_scene_videos` | dict | `{vid_key: {url, task_id, status}}` 视频任务状态 |
| `studio_selected_clips` | dict | `{sid: {url, label}}` 已选用的片段 |

#### 4.6.2 图像生成逻辑

点击"生成预览图"时执行：

```python
# Step 1: 生成 image_prompt 和 video_prompt
pm = build_scene_prompts(scene, character_bible, scene_library)

# Step 2: 判断分镜是否涉及逝者（是否使用参考照片）
_ref_kws = ["逝者","爷爷","奶奶","父亲","母亲","elderly man","deceased", 逝者姓名...]
_use_ref = any(kw in scene["subject"] or kw in desc for kw in _ref_kws)

# Step 3: 生成图像（有参考图走 gpt-4o-image edit，无参考图走 nano-banana）
b64, err = generate_image_302(
    prompt      = pm["image_prompt"],
    reference_b64 = ancestor_photo_b64 if _use_ref else None
)
```

#### 4.6.3 视频生成逻辑

点击"生成视频"时：

```python
vr = generate_video_302(
    prompt    = vid_prompt,
    image_url = "data:image/png;base64," + imgs[j],  # 用生成图作首帧
    duration  = 5,
    poll      = False,   # 异步模式，立即返回 task_id
)
# 存入 session_state，后续点击"刷新视频状态"轮询结果
```

#### 4.6.4 片段选用与剪辑台

```
已完成视频 → "选用此片段" 按钮（绿色高亮已选）
                ↓
studio_selected_clips = {sid: {url, label}}
                ↓
页面底部"一键剪辑合成台"
  → 按分镜顺序排列已选片段
  → 显示 chip 列表（顺序+标签）
  → 点击"一键剪辑合成"
      ↓
    video_editor.concat_clips(urls)
      ↓
    下载按钮（MP4）
```

---

### 4.7 方案确认页 — `pages/pipeline.py`

**职责**：展示 MV01-MV03 的输出结果（角色 DNA、场景库、叙事大纲），供家属逐步确认后进入分镜制作。

采用 AI 对话气泡风格 UI，每一步通过 `gate_manager.approve(mv_id)` 解锁后续流程。

---

### 4.8 视频剪辑器 — `video_editor.py`

**职责**：将多个视频片段从 URL 下载后，用 moviepy 顺序拼接输出 MP4。

#### 4.8.1 关键函数

```python
def concat_clips(video_urls: List[str], output_filename=None, progress_cb=None) -> str:
    """
    1. 遍历 video_urls，逐一 download_video() 到临时目录
    2. VideoFileClip() 加载每个片段
    3. concatenate_videoclips(clips, method="compose") 拼接
    4. write_videofile(codec="libx264", audio_codec="aac") 编码输出
    5. 返回输出 MP4 的绝对路径
    """
```

#### 4.8.2 输出目录

```
outputs/final_cuts/念念成片_{timestamp}.mp4
```

#### 4.8.3 依赖

- `moviepy 2.1.2`（Python 原生视频处理）
- `libx264` + `aac`（通过 ffmpeg，moviepy 自动调用）

---

## 5. 六阶 MV Pipeline 详解

```
MV01 家属采访
  输入：表单数据（逝者信息、回忆文字、风格偏好、上传资产）
  模型：claude-sonnet-4-6
  输出：结构化 JSON（basic_info, core_memories, uploaded_assets, style_profile）
  闸门 G1：家属确认信息准确性
  ↓

MV02 信息校验
  输入：MV01 输出
  模型：claude-sonnet-4-6
  输出：校验报告 + 信息完整度评分 + 补充问题列表
  闸门 G2：确认校验通过
  ↓

MV03 三要素锁定（角色/场景/风格）
  输入：MV02 输出
  模型：claude-sonnet-4-6
  输出：
    · character_bible（角色 DNA：外貌/体型/服装/习惯动作）
    · scene_library（场景库：每个场景的视觉描述符）
    · narrative_outline（叙事大纲：分章节剧情结构）
    · style_profile（风格参数：色调/节奏/情感基调）
  闸门 G3：确认三要素
  ↓

MV04 分镜故事板
  输入：MV03 输出
  模型：gpt-4o（专属队列）
  输出：scenes 列表（每个分镜含 scene_id / time / shot_type /
        description / subject / mj_prompt / narration）
  后处理：normalize_storyboard_output()（时长桶规范化）
  UI：分镜制作台（图像生成 + 视频生成 + 选片剪辑）
  闸门 G4：分镜审核
  ↓

MV05 数字人驱动
  输入：MV04 输出
  模型：claude-sonnet-4-6
  输出：数字人渲染参数（口型驱动、表情序列、动作序列）
  闸门 G5：数字人方案确认
  ↓

MV06 最终剪辑
  输入：MV05 输出
  模型：claude-sonnet-4-6
  输出：时间轴编排方案（每个 clip 的入出点、转场、音轨）
  闸门 G6：最终确认
```

---

## 6. AI 模型调用链

```
用户操作
    │
    ├── 文字采访/分析 ──────────────────► claude-sonnet-4-6
    │   (失败) ──────────────────────────► gpt-5.4
    │   (均失败) ────────────────────────► 本地 LLM（可选）
    │
    ├── 分镜 Prompt 生成 (MV04 专用) ──► gpt-4o
    │   (失败) ──────────────────────────► gpt-5.4
    │
    ├── 图像理解（描述上传照片）────────► gemini-2.5-flash
    │
    ├── 图像生成
    │   ├── 无参考照片 ─────────────────► nano-banana (Wavespeed)
    │   │   (失败) ───────────────────────► gpt-4o-image-generation
    │   └── 有参考照片（逝者锚定）──────► gpt-4o-image-generation (images.edit)
    │       (失败) ───────────────────────► nano-banana（降级，无锚定）
    │
    ├── 视频生成
    │   ├── 图片上传至图床
    │   │   ├── freeimage.host（主力）
    │   │   └── litterbox.catbox.moe（备用）
    │   └── Kling omni3 (m2v_omni_3_video)
    │       body: {prompt, image: "https://...", duration, aspect_ratio, mode}
    │
    └── 语音转写 ─────────────────────────► whisper-1
```

---

## 7. 图像生成与首帧锚定机制

### 7.1 无参考照片（普通生成）

```python
# 主力：nano-banana（Wavespeed 专属端点）
POST https://api.302.ai/ws/api/v3/google/nano-banana/text-to-image
body: {
    "prompt": "...",
    "aspect_ratio": "16:9",
    "output_format": "png",
    "enable_sync_mode": True,
    "enable_base64_output": True
}
→ 返回 base64 图像字符串

# 备用：gpt-4o-image-generation
client.images.generate(model="gpt-4o-image-generation", prompt=..., response_format="b64_json")
```

### 7.2 有参考照片（逝者形象锚定）

当检测到分镜涉及逝者且 `ancestor_photo_b64` 已设置时：

```python
# 使用 images.edit API（参考图 → 新场景，锚定面孔）
prompt = (
    "Use the person in the reference image as the main character. "
    "Keep the character's face, age, and appearance IDENTICAL to the reference photo. "
    f"Generate a new cinematic scene: {scene_prompt}"
)
client.images.edit(
    model  = "gpt-4o-image-generation",
    image  = reference_photo_bytes,   # 逝者照片
    prompt = prompt,
    size   = "1024x1024",
    response_format = "b64_json"
)
```

**关键点**：`images.edit` 与 `images.generate` 的区别在于前者接受一张 `image` 参数，模型会将该图中的人物面孔迁移至新场景，实现"换背景不换脸"效果。

---

## 8. 视频生成与图床上传机制

### 8.1 为什么需要图床

Kling omni3 的 `image` 参数**只接受 HTTPS URL**，不接受 base64 data URL。因此在调用 Kling 之前，必须先将 AI 生成的图片（base64）上传至公共图床获取 HTTPS URL。

> 经实测证明：`images: [base64]`、`image_url: "data:..."` 均被 Kling API **静默忽略**，导致生成纯文生视频（无首帧）。正确字段为 `image: "https://..."` 单个字符串。

### 8.2 图床上传链路

```python
def _upload_image_to_public(img_bytes, ext="jpg") -> Optional[str]:

    # 方案1：freeimage.host（免费，无需注册）
    POST https://freeimage.host/api/1/upload
    data: {key: "6d207e02198a847aa98d0a2a901485a5", source: b64_str, format: "json"}
    → 返回 data.image.url

    # 方案2（备用）：litterbox.catbox.moe（临时1小时）
    POST https://litterbox.catbox.moe/resources/internals/api.php
    data: {reqtype: "fileupload", time: "1h"}
    files: {fileToUpload: image_bytes}
    → 返回纯文本 HTTPS URL
```

### 8.3 Kling 视频提交

```python
POST https://api.302.ai/klingai/m2v_omni_3_video
headers: {Authorization: "Bearer {API_KEY}", Content-Type: "application/json"}
body: {
    "prompt"      : "...",
    "image"       : "https://iili.io/xxxxx.jpg",  # 单个 HTTPS URL
    "duration"    : 5,
    "aspect_ratio": "auto",   # 有首帧时必须 auto
    "mode"        : "pro"
}
→ 返回 data.task.id（task_id）
```

### 8.4 视频状态轮询

```python
GET https://api.302.ai/klingai/task/{task_id}/fetch
→ data.status: 5=排队中, 10=生成中, 99=已完成

# 视频 URL 提取（双路径兼容）：
url = data["taskWorks"][0]["resource"]["resource"]  # 主路径
url = data["works"][0]["resource"]["url"]            # 备用路径
```

---

## 9. 状态管理与数据流

### 9.1 数据流向图

```
表单输入
    │
    ▼
session_state["form_data"]
    │
    ▼ (_form_to_text() 序列化为自然语言)
call_skill("MV01", prompt, form_data)
    │
    ▼
outputs/mv01.json  ──►  call_skill("MV02", ...)
                                │
                                ▼
                         outputs/mv02.json  ──►  call_skill("MV03", ...)
                                                        │
                                                        ▼
                                                 outputs/mv03.json  ──►  call_skill("MV04", ...)
                                                                                │
                                                                                ▼
                                                                         outputs/mv04.json
                                                                                │
                                                        ┌───────────────────────┘
                                                        ▼
                                               studio.py 读取 scenes
                                                        │
                                                        ▼
                                               build_scene_prompts() ──► gpt-4o
                                                        │
                                               generate_image_302()  ──► nano-banana / gpt-4o-image
                                                        │
                                               generate_video_302()  ──► Kling omni3
                                                        │
                                               video_editor.concat_clips()
                                                        │
                                                        ▼
                                               outputs/final_cuts/念念成片.mp4
```

### 9.2 两类状态的生命周期

| 状态类型 | 存储位置 | 生命周期 | 内容 |
|---------|---------|---------|------|
| Pipeline 输出 | `outputs/*.json` 文件 | 持久（重启后存在） | MV01-MV06 结构化结果 |
| UI 交互状态 | Streamlit session_state | 会话级（刷新丢失） | 对话历史、图片 b64、视频任务状态、选片列表 |

---

## 10. 配置与环境变量

`.env` 文件（位于 `memorial-pipeline-test/` 目录）：

```env
# ── 302.ai 统一网关（必填）
AI302_API_KEY=sk-xxxxxxxxxxxxxxxxxx

# ── 文本模型
AI302_TEXT_MODEL=claude-sonnet-4-6       # 主力文本模型
AI302_TEXT_FALLBACK=gpt-5.4             # 回退模型

# ── 图像模型
AI302_VISION_MODEL=gemini-2.5-flash     # 图像理解
AI302_IMAGE_GEN_MODEL=google/nano-banana/text-to-image  # 图像生成（主力）
AI302_IMAGE_GEN_FALLBACK=gpt-4o-image-generation        # 图像生成（备用）

# ── 视频模型
AI302_VIDEO_GEN_MODEL=klingai/m2v_omni_3_video

# ── 音频模型
AI302_AUDIO_MODEL=whisper-1

# ── 本地 LLM 备用（可选，留空不启用）
# LOCAL_LLM_BASE_URL=http://localhost:1234/v1
# LOCAL_LLM_API_KEY=lm-studio
# LOCAL_LLM_MODEL=qwen3:8b
```

---

## 11. 错误处理与降级策略

| 场景 | 主力 | 降级策略 |
|------|------|---------|
| 文本推理 API 超时 | claude-sonnet-4-6 | → gpt-5.4 → 本地 LLM |
| 分镜生成失败 | gpt-4o | → gpt-5.4 |
| 图像生成失败 | nano-banana | → gpt-4o-image-generation |
| 参考图锚定失败 | gpt-4o-image edit | → 无参考图普通生成（仍保留 DNA 文字描述） |
| 图床上传失败 | freeimage.host | → litterbox.catbox.moe → 返回 error |
| 视频生成无首帧 | base64 data URL（已废弃）| 上传图床 → HTTPS URL → 正确传入 `image` 字段 |
| JSON 解析失败 | response_format=json | `_extract_json()` 手动提取 → 降级返回 `{"error": True}` |

---

## 12. 数据持久化

### 12.1 Pipeline 输出

每个 MV 步骤完成后立即写入文件：

```python
outputs/
  mv01.json   # 采访结构化输出
  mv02.json   # 校验报告
  mv03.json   # 三要素（角色/场景/风格）
  mv04.json   # 分镜故事板（含 scenes 列表）
  mv05.json   # 数字人驱动参数
  mv06.json   # 最终剪辑时间轴
```

文件格式：UTF-8 编码 JSON，`ensure_ascii=False`，`indent=2`。

### 12.2 成片输出

```python
outputs/final_cuts/念念成片_{timestamp}.mp4
```

### 12.3 注意事项

- `outputs/*.json` 在应用重启后仍然有效，`studio.py` 启动时会自动加载 `mv04.json` 中的 scenes。
- `gate_manager` 的状态不持久化；重启后若需继续之前的 Pipeline，需要手动在 UI 中点击"已确认"以重置 gate 状态。
- `ancestor_photo_b64` 存储于 session_state，**刷新后丢失**，需重新上传照片。

---

*文档生成时间：2026-05-06 | 作者：念念技术团队*
