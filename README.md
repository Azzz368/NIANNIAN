# 念念 · 追思影像制作平台

> **NianNian Memorial Studio** — 让记忆永远留存

基于 Streamlit 构建的 AI 追思影像端到端制作平台，支持从信息采集、风格分析、脚本生成，到分镜制作、数字人对话的完整工作流。

---

## 功能模块

平台由四个主要页面组成，通过 `app.py` 主页统一导航：

### 1. 🎬 念念影像制作（`app.py`）

追思影像的核心制作流程，三步引导式交互：

- **Step 1 · 基本信息**：填写逝者姓名、生卒日期、职业、仪式信息、发言人信息等
- **Step 2 · 回忆 & 风格**：上传照片、输入家庭回忆与事迹、选择风格偏好（`warm_nostalgia` / `solemn_classic` / `gentle_modern`）
- **Step 3 · 念念 AI 对话**：多轮对话引导 AI 逐步完成 MV01 → MV02 管线，输出结构化脚本 JSON

支持**测试模式**，内置陈文斌示例数据，一键填入所有字段快速调试。

---

### 2. 🖼️ 分镜制作台（`pages/studio.py`）

MV04 → MV06 全流程可视化制作台：

- **MV04 分镜锁定**：基于 MV03 分镜 JSON 逐镜锁定画面描述
- **MV05 数字人渲染**：调用 302.ai 图像生成接口，为每个分镜生成画面
  - 支持文生图 / 参考图生图两种模式
  - 支持预览、重新生成、图片下载
- **MV06 最终剪辑**：调用 302.ai 视频生成接口，将图像序列合成为影像片段
  - 支持逐镜生成与批量生成
  - 视频结果可在线预览及下载

---

### 3. 💬 数字人对话（`pages/dialogue.py`）

双栏布局的数字人多轮对话界面：

- **左栏 · 人设编辑器**：加载逝者画像 JSON，自定义数字人姓名、性格、说话风格、记忆片段等
- **右栏 · 对话界面**：与数字人实时多轮对话，AI 以逝者身份回应，复现其语言风格与情感记忆
- 支持重置对话、导出对话记录

---

### 4. 📱 微信导入分析（`pages/wechat_import.py`）

从微信聊天记录中提取逝者语言风格，生成数字人人设画像：

- 支持 CSV（WeChatMsg / 留痕）、JSON、TXT 三种导出格式
- AI 自动分析说话习惯、常用词汇、情感倾向、性格特征
- 分析结果可直接用于数字人对话模块的人设初始化

---

## 目录结构

```
memorial-pipeline-test/
├── app.py                  # 主页 & 念念影像制作（MV01-MV02）
├── pipeline_runner.py      # AI 管线执行器
├── llm_client.py           # LLM / 图像 / 视频接口封装
├── skill_loader.py         # 技能 Prompt 加载器
├── gate_manager.py         # 管线关卡与人工确认管理
├── comfyui_client.py       # ComfyUI 接口（备用）
├── video_editor.py         # 视频编辑工具
├── write_pipeline.py       # 写作管线辅助
├── pages/
│   ├── studio.py           # 分镜制作台（MV04-MV06）
│   ├── dialogue.py         # 数字人对话界面
│   ├── wechat_import.py    # 微信聊天记录导入分析
│   └── pipeline.py         # 管线调试页（开发用）
├── skills/                 # 技能 Prompt 文件（MV01-MV06 等）
├── archiveskills/          # 技能文档归档（SS0-SS10）
├── outputs/                # 各阶段输出 JSON
├── sample_inputs/          # 示例输入文件
├── asset/                  # 静态资源
├── 302ai-skill/            # 302.ai API 技能集成文档
└── requirements.txt
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 主 LLM（支持 OpenAI 兼容接口，如 LM Studio / OpenRouter）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=http://localhost:1234/v1
OPENAI_MODEL=your_model_name

# 备用 LLM（可选）
OPENAI_FALLBACK_BASE_URL=https://openrouter.ai/api/v1
OPENAI_FALLBACK_API_KEY=your_fallback_key
OPENAI_FALLBACK_MODELS=anthropic/claude-3.5-sonnet

# 302.ai（图像/视频生成，分镜制作台必填）
API_302_KEY=your_302ai_key
```

### 3. 启动

```bash
streamlit run app.py --server.port 8501
```

访问 http://localhost:8501

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端框架 | Streamlit >= 1.35 |
| LLM 接口 | OpenAI SDK（兼容 LM Studio / OpenRouter / 任意 OpenAI 兼容格式） |
| 图像生成 | 302.ai Image API（支持参考图） |
| 视频生成 | 302.ai Video API |
| 图像处理 | Pillow、streamlit-cropper |
| 数据格式 | JSON（各阶段结构化输出） |

---

## 测试数据

内置测试人物：**陈文斌**（1948年生，上海机床厂退休工程师）

在「念念影像制作」页面展开「🧪 测试模式」，点击「填入全部测试数据（陈文斌）」即可一键填入所有示例字段，快速进入调试流程。

---

## 输出文件说明

各阶段 AI 输出均保存至 `outputs/` 目录：

| 文件 | 内容 |
|------|------|
| `mv01.json` | MV01 访谈素材整理 |
| `mv02.json` | MV02 内容校验结果 |
| `mv03.json` | MV03 分镜脚本 |
| `mv04.json` | MV04 分镜锁定 |
| `mv05.json` | MV05 图像渲染结果 |
| `mv06.json` | MV06 最终剪辑 |
| `wechat_persona.json` | 微信分析生成的数字人人设 |
