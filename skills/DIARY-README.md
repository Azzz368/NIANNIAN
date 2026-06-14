# 念念日记 PDF Skills 使用说明

这组 Skill 用于实现“用户输入文字 + 上传图片 → 生成图文对应日记 PDF”的内容管线。

## 文件

| 文件 | 作用 |
| --- | --- |
| `DIARY01-media-pairing.md` | 理解文字与图片，将图片分配到相关段落主题 |
| `DIARY02-diary-writer.md` | 根据段落主题写日记正文，并保留段落与图片映射 |
| `DIARY03-pdf-layout.md` | 输出 HTML/CSS/PDF 渲染配置，让每段后展示对应图片 |

## 推荐调用顺序

1. 后端先用视觉模型为每张图片生成 `vision_summary`。
2. 调用 `DIARY01`，得到 `paragraph_plan`。
3. 调用 `DIARY02`，得到结构化日记：`paragraphs` + `image_captions`。
4. 调用 `DIARY03`，得到 `html`、`css`、`render_options`。
5. 工程侧用 Playwright 把 HTML/CSS 渲染成 PDF。

## 关键数据契约

- 每张图片必须有稳定的 `image_id`。
- 每个段落必须有稳定的 `paragraph_id`。
- `paragraphs[].image_ids` 是段落和图片对应关系的唯一来源。
- PDF 渲染时必须把图片放在对应段落之后，不要统一放到文末。

## 安全要求

- Skill 输出不得包含 API Key、token 或 `.env` 内容。
- 前端只接收 PDF 结果或渲染后的静态内容，不接触模型密钥。
- 真实 PDF 生成应在后端完成，避免把私密图片处理逻辑暴露给浏览器。
