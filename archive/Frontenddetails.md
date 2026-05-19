# Frontenddetails — 念念 AI 前后端交互设计文档

> **目的**：完整记录 `app.py` 中前端交互与后端调用的所有设计细节，  
> 为将来将前端迁移至 JavaScript（React/Vue）+ Python 后端（FastAPI/Flask）做迁移参考。

---

## 一、整体架构概述

```
┌─────────────────────────────────────────────────────┐
│                  当前架构（Streamlit）                │
│                                                     │
│   HTML/CSS（内联字符串）  ←→  Python 函数           │
│         ↑                        ↑                  │
│   st.markdown(unsafe_html)   st.session_state       │
│         ↑                        ↑                  │
│   用户交互（Streamlit组件）    后端逻辑调用           │
│   st.button / st.text_input   llm_client / pipeline │
└─────────────────────────────────────────────────────┘
```

Streamlit 的工作机制：**每次用户触发交互，整个 Python 脚本从头重新执行**。  
状态通过 `st.session_state`（等同于服务端 session）在多次执行间保持。

---

## 二、页面路由与状态机

### 2.1 顶层路由

```python
# 控制变量
st.session_state["main_section"]  # 值："home" | "memorial"
```

| 值 | 渲染内容 | 对应 JS 前端路由 |
|----|---------|----------------|
| `"home"` | 全屏 Hero 首页（背景图+两个入口按钮） | `/` 或 `/home` |
| `"memorial"` | 念念影像制作完整流程 | `/memorial` |

**切换逻辑**：
```python
# home → memorial
if st.button("念念影像制作"):
    st.session_state["main_section"] = "memorial"
    st.rerun()  # 触发整页重新渲染

# home → 独立页面（数字人）
if st.button("数字人对话"):
    st.switch_page("pages/wechat_import.py")  # 类似 router.push()
```

**迁移为 JS 时**：将 `st.session_state["main_section"]` 替换为前端路由（React Router / Vue Router），后端只需提供数据 API。

---

### 2.2 Memorial 流程内部状态机

```python
st.session_state["phase"]      # "form" | "chat" | "preview"
st.session_state["form_step"]  # 1 | 2（仅 phase=="form" 时有效）
```

```
┌──────────┐   下一步    ┌──────────┐   唤起AI    ┌──────────┐
│  form/1  │ ──────────► │  form/2  │ ──────────► │   chat   │
│  基本信息 │             │  回忆风格 │             │  AI对话  │
└──────────┘             └──────────┘             └────┬─────┘
                                                       │ 好了，开始制作
                                                       ▼
                                                  ┌──────────┐   确认    ┌─────────────┐
                                                  │  preview │ ────────► │ pipeline.py │
                                                  │  影片预告 │           │  制作台      │
                                                  └──────────┘           └─────────────┘
```

**入口判断（脚本末尾）**：
```python
render_topbar()
if phase == "form":
    if step == 1: render_step1()
    else: render_step2()
elif phase == "preview":
    render_preview()
else:
    render_chat()
```

**迁移为 JS 时**：这套状态机可以直接映射为前端的多步表单组件（如 React `<Stepper>`），每个 `render_xxx()` 对应一个子组件。

---

## 三、全局样式注入机制

### 3.1 CSS 注入方式

Streamlit 无原生样式 API，所有自定义样式通过：
```python
st.markdown("""<style>...</style>""", unsafe_allow_html=True)
```

app.py 中共有 **两块全局 CSS 字符串**：

| 变量名 | 作用域 | 主要内容 |
|--------|--------|---------|
| `_CSS`（行 11-101） | memorial 流程全局 | CSS 变量、排版、卡片、聊天气泡、按钮、表单组件覆盖 |
| `_HOME_CSS`（行 107-193） | 仅 home 页面 | Google Fonts、Hero 全屏布局、玻璃态按钮 |

### 3.2 CSS 设计令牌（Design Tokens）

```css
:root {
  --bg: #F8F5F0;          /* 页面背景：米白 */
  --surf: #FFFFFF;         /* 卡片表面 */
  --surf2: #FAF7F2;        /* 次级表面 */
  --surf3: #F0EBE2;        /* 悬停背景 */
  --border: rgba(180,155,115,.18);   /* 边框 */
  --border-h: rgba(160,120,70,.35);  /* 悬停边框 */
  --gold: #9C7A45;         /* 主色调：金棕 */
  --gold-l: #B8934F;       /* 金色-亮 */
  --gold-dim: rgba(156,122,69,.08); /* 金色-透明背景 */
  --gold-glow: rgba(156,122,69,.18);/* 金色-阴影 */
  --ink: #1E1A14;           /* 主文字 */
  --ink-m: #4A4035;         /* 次级文字 */
  --muted: #B0A494;         /* 弱化文字 */
  --muted-l: #8A7B6A;       /* 标签文字 */
}
```

**迁移为 JS 时**：这些 token 可以直接迁移为 Tailwind 的 `theme.extend.colors` 或 CSS Variables，无需修改。

### 3.3 背景图加载方式

Home 页面背景图使用 base64 内联 `<img>` 标签（非 CSS `background-image`），原因是 Streamlit 会截断超长 CSS 字符串。

```python
# Python 端读取图片 → base64 编码 → 注入 HTML
with open("asset/OurDearFriend.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()
img_src = f"data:image/jpeg;base64,{img_b64}"

# 注入 HTML
st.markdown(f'<img id="nn-bg-img" src="{img_src}" style="position:fixed;...">', unsafe_allow_html=True)
```

**迁移为 JS 时**：直接用 `<img src="/static/OurDearFriend.jpg">` 或 CSS `background-image: url(...)` 即可，无需 base64。

---

## 四、表单数据流

### 4.1 数据存储结构

```python
st.session_state["form_data"] = {
    # Step 1 - 基本信息
    "deceased_name": str,       # 逝者姓名
    "deceased_gender": str,     # "男" | "女" | "不便告知"
    "birth_date": str,          # 出生日期（自由文本）
    "death_date": str,          # 逝世日期（自由文本）
    "occupation": str,          # 职业（可选）
    "ceremony_date": str,       # 追悼会日期
    "ceremony_venue": str,      # 仪式场所
    "total_duration_sec": int,  # 影片时长：180 | 300 | 480

    # Step 2 - 回忆与风格
    "family_memory_text": str,  # 文字回忆（核心字段）
    "speaker_name": str,        # 致辞家属姓名
    "speaker_relation": str,    # 与逝者关系
    "speaker_style": str,       # 致辞风格偏好
    "style_preference": str,    # "warm_nostalgia" | "solemn_formal" | "uplifting_celebration"
    "last_wishes": str,         # 遗愿/补充
}

# 辅助读写函数（简化版 getter/setter）
def save(k, v): st.session_state["form_data"][k] = v
def get(k, d=""): return st.session_state["form_data"].get(k, d)
```

### 4.2 表单验证

Streamlit 没有原生表单验证，当前实现方式为**提交时手动检查**：

```python
# Step 1 "下一步" 按钮回调
if st.button("下一步", type="primary"):
    if not get("deceased_name"):
        st.warning("请填写逝者姓名。")      # 显示警告，不跳转
    elif not get("ceremony_date"):
        st.warning("请填写追悼会日期。")
    else:
        st.session_state["form_step"] = 2  # 通过验证 → 跳下一步
        st.rerun()
```

**迁移为 JS 时**：替换为 React Hook Form / Zod schema 验证，`st.warning()` 对应显示内联错误消息。

### 4.3 文件上传处理

```python
# Step 2 文件上传
uploaded = st.file_uploader(
    type=["png","jpg","jpeg","webp","mp3","wav","mp4","mov"],
    accept_multiple_files=True
)
for f in uploaded:
    file_bytes = f.getvalue()   # 获取二进制内容
    if file_type == "image":
        desc = describe_image(file_bytes, f.name)  # 调用视觉 API 描述图片
        # 若含人像 → 自动设为参考照片
        if contains_person(desc):
            st.session_state["ancestor_photo_b64"] = base64.b64encode(file_bytes).decode()

    st.session_state["intake_assets"].append({
        "asset_id": f"image_01",
        "type": "image" | "audio" | "video",
        "filename": str,
        "description": str,   # AI 生成的描述
        "time_period": str,   # 预留：时间段标记
    })
```

**迁移为 JS 时**：
- 前端：`<input type="file" multiple>` + `FormData` POST 到 `/api/upload`
- 后端：FastAPI `UploadFile` 接收，调用 `describe_image()` 返回 JSON

---

## 五、AI 对话模块（render_chat）

### 5.1 对话历史结构

```python
st.session_state["chat_history"] = [
    {"role": "ai",   "content": "您好，我是念念AI..."},
    {"role": "user", "content": "他最喜欢在院子里种菜"},
    ...
]
```

### 5.2 消息渲染（纯 HTML 气泡）

Streamlit 的 `st.chat_message()` 样式不可定制，因此使用 `st.markdown()` 注入自定义气泡 HTML：

```python
def _bubble(role, content):
    if role == "ai":
        return """
        <div class='nn-chat-ai'>
          <div class='nn-ai-avatar'>念</div>
          <div class='nn-ai-bubble-wrap'>
            <div class='nn-ai-name'>念念 AI</div>
            <div class='nn-ai-bubble'>{content}</div>
          </div>
        </div>"""
    return "<div class='nn-chat-user'><div class='nn-user-bubble'>{content}</div></div>"

# 全部历史一次性渲染（非逐条 append）
html = "<div class='nn-chat-wrap'>"
for m in history:
    html += _bubble(m["role"], m["content"])
html += "</div>"
st.markdown(html, unsafe_allow_html=True)
```

**⚠️ 重要限制**：因为 Streamlit 每次重跑都重新渲染，对话历史必须**每次完整重绘**，没有局部更新能力。这是迁移到 JS 后可以大幅优化的地方。

### 5.3 AI 思考动画

用 `st.empty()` 占位符 + HTML 动画实现"思考中"状态：

```python
think_ph = st.empty()  # 占位符

if st.session_state["ai_thinking"]:
    think_ph.markdown(_THINK_HTML, unsafe_allow_html=True)  # 显示动画
    # ... 调用 LLM API ...
    reply = call_memorial_chat(system, messages)
    think_ph.empty()   # 清除动画
    st.session_state["chat_history"].append({"role": "ai", "content": reply})
    st.rerun()         # 重新渲染显示新消息
```

`_THINK_HTML` 包含 CSS keyframe 动画：脉冲光晕 orb + 三个弹跳圆点。

**迁移为 JS 时**：前端监听 `/api/chat` 的 streaming 响应（SSE），思考动画在 `onStart` 显示，`onComplete` 隐藏。

### 5.4 AI 调用链

```
用户输入 → st.chat_input()
    ↓
session_state["chat_history"].append(user_msg)
session_state["ai_thinking"] = True
st.rerun()
    ↓
重新执行脚本 → 检测到 ai_thinking == True
    ↓
_history_to_openai()  # 格式转换：内部格式 → OpenAI messages 格式
    ↓
call_memorial_chat(system_prompt, messages)  # llm_client.py
    ↓ (HTTP POST to 302.ai)
返回 reply 文本
    ↓
session_state["chat_history"].append({"role": "ai", "content": reply})
session_state["ai_thinking"] = False
st.rerun()  # 最终渲染
```

### 5.5 系统提示词（System Prompt）

```
_NIANNIAN_SYSTEM = """
你是「念念 AI」，温柔体贴的追思影像制作助手。
- 说话像温暖的长者朋友，口语化自然流畅中文
- 每次回复 120-200 字，可换行分段
- 第一次：温暖开场 → 总结已知信息 → 指出1-2个可补充的地方
- 后续：肯定补充 → 信息充分时主动说可以开始了
- 绝对不要输出 JSON、技术参数、星号格式
"""
```

---

## 六、数据提交与 JSON 生成（_gen_json_silently）

### 6.1 触发时机

用户在 chat 阶段点击「好了，开始制作」按钮。

### 6.2 生成流程

```python
def _gen_json_silently():
    # 1. 组装 payload：表单数据 + 素材 + 对话记录
    payload = {
        "form_data": st.session_state["form_data"],
        "assets": [...],
        "chat_conversation": 对话历史文本
    }

    # 2. 调用 LLM 结构化提取
    result = call_structured(
        system=_GEN_SYS,   # 指示输出标准 JSON 的系统提示
        user=json.dumps(payload)
    )

    # 3. 保存输出
    pipeline_runner.save_output("MV01", result)      # 写入 outputs/mv01.json
    st.session_state["mv01_intake_json"] = json.dumps(result)
    st.session_state["mv01_text_input"] = json.dumps(result)
```

### 6.3 输出 JSON 结构（MV01 标准格式）

```json
{
  "deceased_info": {
    "name": "张国强",
    "gender": "男",
    "birth_date": "1945年3月8日",
    "death_date": "2024年11月20日",
    "occupation": "木工匠人"
  },
  "ceremony_info": {
    "date": "2024年11月25日",
    "venue": "家乡镇政府礼堂",
    "duration_sec": 300
  },
  "relatives": [
    {"name": "张明辉", "relation": "儿子", "style": "朴实感恩"}
  ],
  "family_memory_text": "...",
  "style_preference": "warm_nostalgia",
  "emotional_intensity": "medium",
  "last_wishes": "...",
  "assets": [
    {"asset_id": "image_01", "type": "image", "description": "...", "time_period": ""}
  ]
}
```

**迁移为 JS 时**：此函数对应 `POST /api/generate-mv01`，接收 payload 返回结构化 JSON，前端轮询或 WebSocket 接收进度。

---

## 七、分镜预览模块（render_preview）

### 7.1 作用

在正式进入 pipeline.py 制作台之前，用平白语言让家属预先了解影片结构。

### 7.2 调用流程

```python
# 只生成一次，结果缓存到 session_state
if not st.session_state.get("preview_text"):
    intake_json = st.session_state.get("mv01_intake_json") or _form_to_text()
    prompt = f"逝者信息：\n{intake_json}\n\n请用大白话讲讲影片流程。"
    preview_text = call_memorial_chat(_PREVIEW_SYS, [{"role": "user", "content": prompt}])
    st.session_state["preview_text"] = preview_text
    st.rerun()
```

### 7.3 展示方式

将 AI 回复按换行拆分为多段，每段包裹在带金色左边框的卡片里：

```python
for p in paragraphs:
    html += f"""
    <div style="background:rgba(255,250,240,0.9);
                border-left:4px solid #C9A96E;
                border-radius:10px; padding:18px 22px;">
        {p}
    </div>"""
```

---

## 八、页面多文件路由（Streamlit Multi-Page）

```
app.py                    ← 主入口（home + memorial 流程）
pages/
  pipeline.py             ← 制作台（MV02-MV06 流水线）
  wechat_import.py        ← 微信聊天记录上传分析
  dialogue.py             ← 数字人对话界面
  studio.py               ← 图像/视频生成工作室
```

**页面跳转 API**：
```python
st.switch_page("pages/pipeline.py")       # 跳转到制作台
st.switch_page("pages/wechat_import.py")  # 跳转到微信导入
```

跳转时 `st.session_state` 数据自动保留（同一 session）。

**迁移为 JS 时**：每个 `pages/*.py` 对应一个前端路由页面（`/pipeline`、`/wechat`、`/dialogue`），共享同一个后端 session 或通过 token 传递状态。

---

## 九、后端 API 调用层（llm_client.py）

### 9.1 主要函数接口

| 函数名 | 用途 | 对应前后端分离后的 API |
|--------|------|----------------------|
| `call_memorial_chat(system, messages)` | 多轮对话（念念AI） | `POST /api/chat` |
| `call_structured(system, user_text)` | 结构化 JSON 提取 | `POST /api/extract` |
| `describe_image(file_bytes, filename)` | 图片内容识别 | `POST /api/describe-image` |
| `call_skill(skill_text, user_input)` | Skill Prompt 执行 | `POST /api/skill` |

### 9.2 API 网关配置

```python
# 统一走 302.ai 代理网关
client = OpenAI(
    api_key=os.getenv("AI302_API_KEY"),
    base_url="https://api.302.ai/v1"
)
```

### 9.3 迁移时的后端接口设计建议

```
FastAPI / Flask 路由设计：

POST /api/chat
    Body: { system: str, messages: [{role, content}] }
    Response: { reply: str }

POST /api/extract
    Body: { system: str, user_text: str }
    Response: { ...structured_json }

POST /api/upload
    Body: FormData (file)
    Response: { asset_id, type, description, url }

POST /api/generate-mv01
    Body: { form_data, assets, chat_history }
    Response: { mv01_json }

GET /api/pipeline-status/:session_id
    Response: { phase, steps_done, current_output }
```

---

## 十、状态管理总览（session_state 键值清单）

| 键名 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `main_section` | str | `"home"` | 顶层路由 |
| `phase` | str | `"form"` | memorial 流程阶段 |
| `form_step` | int | `1` | 表单步骤 1/2 |
| `form_data` | dict | `{}` | 所有表单字段 |
| `intake_assets` | list | `[]` | 上传的素材列表 |
| `chat_history` | list | `[]` | AI 对话历史 |
| `ai_thinking` | bool | `False` | 是否正在等待 AI 回复 |
| `chat_ready` | bool | `False` | AI 回复生成控制锁 |
| `mv01_intake_json` | str | `""` | 生成的 MV01 JSON 字符串 |
| `mv01_text_input` | str | `""` | pipeline.py 的输入 |
| `preview_text` | str | `""` | 分镜预览文本（缓存） |
| `preview_ready` | bool | `False` | 预览生成状态 |
| `ancestor_photo_b64` | str | `""` | 逝者参考人像（base64） |
| `ancestor_photo_filename` | str | `""` | 参考人像文件名 |
| `persona_dna` | dict | 无 | 数字人风格 DNA（wechat_import） |
| `persona_name` | str | 无 | 数字人姓名 |

**迁移为 JS 时**：`session_state` 对应前端的 Zustand / Redux store 或 React Context，后端用 Redis session 或 JWT 携带必要字段。

---

## 十一、前后端分离迁移映射表

| 当前 Streamlit 写法 | 迁移后 JS + Python |
|---------------------|-------------------|
| `st.markdown(html, unsafe_allow_html=True)` | JSX 组件 |
| `st.session_state["key"] = value` | Zustand store / Redux dispatch |
| `st.rerun()` | React state 更新自动重渲染 |
| `st.button(...)` | `<button onClick={...}>` |
| `st.text_input(...)` | `<input>` + `useState` |
| `st.text_area(...)` | `<textarea>` + `useState` |
| `st.selectbox(...)` | `<select>` |
| `st.radio(...)` | Radio group 组件 |
| `st.file_uploader(...)` | `<input type="file">` + `fetch /api/upload` |
| `st.chat_input(...)` | `<input>` + 回车监听 + `fetch /api/chat` |
| `st.spinner(...)` | Loading 状态组件 |
| `st.warning(...)` | 表单内联错误提示 |
| `st.switch_page(...)` | `router.push("/pipeline")` |
| `call_memorial_chat(...)` | `POST /api/chat`（前端 fetch） |
| `call_structured(...)` | `POST /api/extract`（后端内部调用） |
| `pipeline_runner.save_output(...)` | 后端写数据库 / 文件系统 |

---

*文档生成时间：2026-05-11*  
*对应代码版本：commit 26f624a（NIANNIAN/main）*
