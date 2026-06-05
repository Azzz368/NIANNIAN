# 开发日志

## 2026-05-31

本次开发会话集中在“个人传记”生成功能的前后端联动上，目标是让前端点击生成后：

- 自动按 BIO 流程执行所有步骤
- 前端轮询后端状态并显示 step 进度
- 结果不再直接以 Markdown 原文显示，而是转换成 HTML 预览
- 生成完成后写入用户存储路径 `data/users/{user_id}/memorials/{memorial_id}/biography.md`
- 确保前端请求体包含 `user_id` 和 `memorial_id`
- 传记展示区域避免左右滚动、自动换行、右侧与保存按钮对齐
- 修正生成完成标签不要居中显示

### 已修改文件

- `frontend/library.html`
  - 新增“生成传记” tab 和界面显示区域
  - 添加开始生成、进度展示、取消、重复生成、下载 Markdown 等交互按钮

- `frontend/js/library.js`
  - 添加 `btnStartBio` 点击后按 `BIO01` 至 `BIO05` 顺序发起后端执行
  - 添加 `pollBioStatus()` 轮询逻辑，显示当前 step 与 progress
  - 修改 `showBioResult()`，将 Markdown 解析为 HTML 并渲染到 `.bio-html` 中
  - 修正 Markdown 主标题 `# 标题` 的解析，避免原始 `#` 文本直出
  - 增加 `user_id`/`memorial_id` 到 biography 启动请求

- `frontend/css/library.css`
  - 增加 `.bio-html h2.bio-title` 样式，生成预览标题样式化显示
  - 增加 `.bio-html p` 段落样式，提升 HTML 预览可读性
  - 将 `.bio-section h4` 改为左对齐，避免标题居中

- `backend/services/__init__.py`
  - 修复 services 包导出，使 `from ..services import service_manager, session_store` 正常工作

- `backend/services/service_manager.py`
  - 添加最终 Markdown 保存到 `data/users/{user_id}/memorials/{memorial_id}/biography.md` 的逻辑
  - 修复单步执行流程中 `BIO05` 完成后的保存行为

- `backend/routers/biography.py`
  - 增强 `status` 接口返回字段，包含 `current_step`、`status`、`progress`、`error`
  - 添加日志输出，便于调试 BIO 生成流程

### 进展与验证

- 已实现前端对 BIO 流程的按步骤执行，并在每步完成后更新进度条
- Markdown 结果已转换为 HTML，避免直接展示原始 Markdown 文件内容
- 样式调整已完成，预览区内容宽度占满更合理，标题风格统一

### 后续建议

- 继续验证后端 `BIO05` 完成后是否确实写入 `data/users/.../biography.md`
- 如果需要，可进一步增强 Markdown 转换逻辑，支持更多格式（如列表、加粗、斜体）
- 按需补充前端进度条显示中的 step 详情文本和错误提示信息

## 2026-06-01

今日开发要点：

- 将传记生成界面重构为三步式流程（Step1 上传，Step2 审核/配置，Step3 生成与预览），前端文件主要修改：`frontend/biography.html`、`frontend/js/biography.js`、`frontend/css/style.css`。
- 在 Step3 中新增结果展示区 `bioContent` 与标题输入 `bioTitle`，并将“下载 / 重新生成”按钮移至结果区右上角（仅在生成完成后显示）。
- 实现按步骤推进的进度条：修改 `pollStepsAndShowResult()`，按 5 个步骤等分进度条（每步开始与完成时更新进度和标签），保留 `pollBioStatus()` 以接收后端更细粒度的进度信息。
- 上传弹窗与元数据：上传模态已与首页保持一致，保存时会把用户填写的“这是什么”描述随文件一并上传到后端（后端 `POST /api/memorials/{mid}/upload` 已支持 `description` 字段并存入资产元数据）。
- 修复并统一样式与交互：修正了之前的 CSS 选择器问题（导致模态显示异常）、统一模态的 `.show` 行为、优化上传预览为缩略信息（图标/名称/大小）。

已修改文件（概览）：

- `frontend/biography.html`：新增 Step3 结果区、移动工具栏按钮、输入和保存按钮布局调整。
- `frontend/js/biography.js`：新增/修改 `pollStepsAndShowResult()`（按步更新进度）、`showBioResult()`（结果渲染与状态切换）、上传相关流程函数（预览/确认/上传）。
- `frontend/css/style.css`：新增 `.bio-actions-top` 顶部工具栏样式、修复 `.new-mem-modal` 等显示问题、上传缩略图样式调整。
- `backend/routers/uploads.py`：上传接口已保存 `description` 到资产元数据（如需检查，可查看最近提交）。

下一步建议：

- 在浏览器中进行端到端验证：上传含描述的文件、触发生成并观察 Step3 的进度条与最后显示的工具栏按钮。
- 如需，我可以继续把浏览器验证步骤写成检查清单并在本分支运行一次简单的手动测试说明。

## 2026-06-03

本次会话主要围绕“传记生成”链路的第六步排版能力、前端渲染统一、以及导出稳定性进行了较大范围重构。

### 已完成的关键工作

- 将 BIO 排版技能从 `BIO066-layout-css.md` 重命名并重构为 `BIO06-layout-css.md`，改为真正的“内容感知型”排版步骤：
  - 输入 BIO05 的最终传记 Markdown
  - 结合 `form_data`、图片资产和渲染目标
  - 输出这篇传记专属的 `bio_css` 与布局建议，而不是写死固定 CSS
- 把 BIO06 接入传记后端 pipeline：
  - `backend/services/service_manager.py` 的 BIO 流程已扩展到 `BIO01 ~ BIO06`
  - `BIO06` 作为最终排版步骤执行，并把生成结果写入 session 状态
  - BIO05 / BIO06 完成后，分别把 `biography.md` 与 `biography.css` 写到同一 memorial 目录
- 让传记结果接口携带排版信息：
  - `GET /api/biography/result/{sid}` 现在返回 `biography_final` 与 `bio_css`
  - 前端结果区会优先注入后端返回的 `bio_css`，不再仅依赖本地固定样式
- 前端结果渲染区改为完全使用后端 CSS：
  - `frontend/js/biography.js` 中 `showBioResult()` 读取 `bio_css`
  - `applyServerBioCss()` 将 CSS 注入到页面 head
  - `bioContent` 作为内容渲染容器，样式完全由后端返回的 `bio_css` 驱动
- 前端进度条改为六步：
  - Step1 基本信息
  - Step2 回忆 & 风格
  - Step3 素材整理
  - Step4 初稿生成
  - Step5 质量润色
  - Step6 排版渲染
- 导出链路统一读取同一份结果信息：
  - PDF / DOCX 导出都从后端结果接口读取 `bio_css` / `biography_final`
  - PDF 导出走 Playwright 打印链路
  - DOCX 导出走后端生成逻辑，尽量统一段落层级、图片、caption 等布局信息

### 主要涉及文件

- `skills/BIO06-layout-css.md`
  - 改写为 AI 生成式排版技能定义，要求结合 BIO05 结果输出专属 CSS
- `backend/services/service_manager.py`
  - 扩展 BIO 流程到 `BIO06`
  - `BIO05` 产出 `bio_final`
  - `BIO06` 产出 `bio_css` / `bio_layout_notes`
  - 完成后把 `biography.md` / `biography.css` 落盘到 memorial 目录
- `backend/routers/biography.py`
  - 结果接口补充 `bio_css`
  - 使用 BIO06 skill 生成 CSS（带回退兜底）
  - PDF / DOCX 导出继续走真实后端导出流程
- `frontend/biography.html`
  - 传记结果区域接入 `bio-prose-classic` 容器
  - 导出菜单保留 PDF / DOCX / HTML
- `frontend/js/biography.js`
  - 结果页注入后端 CSS
  - 进度展示改为六步
  - 导出按钮统一读取同一份结果信息

### 当前状态与后续方向

- 当前已完成“BIO06 进入 pipeline”和“前端结果区用后端 CSS”两部分。
- 接下来还需要继续做两件事：
  1. 清理 `frontend/js/biography.js` 的 lint warning，保证脚本更干净稳定。
  2. 继续收紧 PDF / DOCX 的排版转换，让导出效果与前端预览更一致。

### 备注

- 本次开发过程中，曾多次从“固定 CSS 函数”调整为“AI 内容感知排版步骤”，最终按用户要求回归为真正的 BIO06 pipeline。
- 前端导出、结果展示、后端落盘三条线已开始统一到同一份 `bio_css` / `biography_final` 数据上。

## 2026-06-03（补充）

本次对话后续继续围绕传记流程做了多轮修正，补充的开发内容如下：

### 传记深搜与回填链路

- 修复 `deep_search` 结果在 `biography` 场景中“跳转了但没填入”的问题：
  - 在 `frontend/js/deep_search.js` 中把深搜结果先缓存到 `localStorage`
  - `frontend/js/biography.js` 在页面初始化时自动读取缓存并回填表单
  - `family_memory_text` 会进入 Step2，`deceased_name` / `birth_date` / `death_date` / `occupation` 会进入 Step1
- 补齐两个入口链接的目标区分：
  - `biography.html` 的 AI 搜索入口带 `?target=biography`
  - `memorial.html` 的 AI 搜索入口带 `?target=memorial`

### 导出稳定性与格式重构

- 调整后端 `biography` 导出接口，使 PDF / DOCX 真正走后端真实生成流程，而不是前端假文件：
  - PDF 使用 Playwright 浏览器打印方式
  - DOCX 使用 `python-docx` 生成
- 对 DOCX 生成链路做了重写：
  - 先将 Markdown 转 HTML
  - 再按 HTML 结构写入 Word
  - 显式设置字体、字号、段落、引用、图片与 caption 样式
  - 处理图片 base64 嵌入，避免直接显示 Markdown 原文
- 对 PDF 样式做了加强：
  - 引入更明确的排版 CSS
  - 兼容中文字体优先级
  - 保留图片不变形与页面断行控制
- 后端 `GET /api/biography/result/{sid}` 增加 `bio_css` 字段，前端根据该 CSS 渲染结果区。

### 前端结果渲染与导出 UI

- 前端结果区 `bioContent` 已改为以后端返回的 `bio_css` 为准：
  - `showBioResult()` 会调用 `applyServerBioCss(d.bio_css || '')`
  - 再由 `renderBioContent()` 负责 Markdown 渲染
- 导出按钮调整为统一读取同一份结果数据，导出菜单保留 PDF / DOCX / HTML 三种导出方式。

### 进度条与步骤数量调整

- 前端进度条改成 6 步，和后端 BIO 流程对齐：
  - 基本信息
  - 回忆 & 风格
  - 素材整理
  - 初稿生成
  - 质量润色
  - 排版渲染
- 这使前端展示与后端 BIO01~BIO06 更一致。

### 排版技能与 pipeline 结构调整

- 重新把 `BIO06` 定义为“AI 结合 BIO05 结果做排版”的技能，而不是固定 CSS 函数。
- 后端 pipeline 中，BIO05 负责产出最终传记正文，BIO06 负责基于正文与图片数据输出专属 CSS 与布局建议。
- 传记正文与 CSS 都写入 memorial 同目录，便于前端渲染与后续导出统一使用。

### 其他修正

- `frontend/js/biography.js` 中增加 `applyServerBioCss()`，通过注入 `<style id="bio-server-css">` 将后端 CSS 应用到页面。
- 调试模式下的导出行为也进行了多轮修改，以便测试生成结果。
- 期间还尝试过多种 PDF / DOCX 导出路径（如 HTML 预览版、`.doc` 兼容格式等），最后回归到后端真实导出链路为主。

### 当前状态

- 传记生成链路已完成从深搜回填、BIO05 内容生成、BIO06 排版、结果渲染、导出稳定性的多轮修正。
- 前端与后端基本统一到同一份 `biography_final + bio_css` 数据上。
- 仍需继续关注前端脚本 lint warning 的清理，以及导出排版在真实环境中的进一步一致性。