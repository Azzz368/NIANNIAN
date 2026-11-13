import base64
import ipaddress
import os
import time
from urllib.parse import quote, urlsplit

import requests


def _config():
    key = os.getenv("APIMART_API_KEY", "").strip()
    if not key:
        raise ValueError("请先配置 APIMART_API_KEY")
    base = os.getenv("APIMART_BASE_URL", "").strip() or "https://api.apimart.ai/v1"
    return base.rstrip("/"), {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _payload(response):
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get("error") or body.get("code", 200) != 200:
        raise ValueError(f"APIMart 请求失败：{body}")
    return body


def _public_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or host == "localhost" or host.endswith(".local"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def upload_image(image_bytes, filename="reference.png", mime_type="image/png"):
    base, headers = _config()
    if not image_bytes or len(image_bytes) > 30 * 1024 * 1024:
        raise ValueError("参考图片为空或超过 30MB")
    result = _payload(requests.post(
        base + "/uploads/images", headers={"Authorization": headers["Authorization"]},
        params={"retention_days": 3}, files={"file": (filename, image_bytes, mime_type)}, timeout=60))
    url = result.get("url")
    if not _public_url(url):
        raise ValueError("APIMart 上传未返回有效图片 URL")
    return url


def generate_image_apimart(prompt, reference_b64=None, max_wait=900):
    try:
        base, headers = _config()
        body = {"model": "gpt-image-2.5-flare", "prompt": prompt, "size": "16:9",
                "resolution": "1k", "quality": "medium", "n": 1}
        if reference_b64:
            raw = base64.b64decode(reference_b64, validate=True)
            body["image_urls"] = [upload_image(raw)]
        submitted = _payload(requests.post(base + "/images/generations", headers=headers, json=body, timeout=60))
        items = submitted.get("data")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict) or not items[0].get("task_id"):
            raise ValueError("APIMart 图片生成未返回 task_id")
        task_id = str(items[0]["task_id"])
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            time.sleep(min(5, max(0, deadline - time.monotonic())))
            try:
                response = requests.get(base + "/tasks/" + quote(task_id, safe=""), headers=headers, timeout=30)
                if response.status_code == 429 or response.status_code >= 500:
                    continue
                data = _payload(response).get("data", {})
            except (requests.Timeout, requests.ConnectionError):
                continue
            if not isinstance(data, dict):
                raise ValueError("APIMart 图片任务响应格式无效")
            if data.get("status") == "completed":
                images = data.get("result", {}).get("images", [])
                urls = images[0].get("url") if images else None
                url = urls[0] if isinstance(urls, list) and urls else urls
                if not _public_url(url):
                    raise ValueError("APIMart 图片任务完成但未返回有效 URL")
                with requests.get(url, timeout=120, stream=True) as downloaded:
                    downloaded.raise_for_status()
                    chunks = bytearray()
                    for chunk in downloaded.iter_content(256 * 1024):
                        chunks.extend(chunk)
                        if len(chunks) > 30 * 1024 * 1024:
                            raise ValueError("生成图片超过 30MB")
                    if not chunks:
                        raise ValueError("生成图片下载为空")
                return base64.b64encode(chunks).decode("ascii"), None
            if data.get("status") in ("failed", "cancelled", "canceled"):
                raise ValueError(f"APIMart 图片任务失败：{data.get('error') or '未知错误'}")
        return None, f"APIMart 图片等待超时，任务 {task_id} 可能仍在生成，请先查询任务再重试"
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        return None, f"APIMart 图片生成失败：{exc}"


def generate_video_apimart(prompt, image_url, duration=5, ratio="16:9",
                           image_tail_url=None, resolution="1080P", poll=True,
                           max_wait=900, progress=None):
    common = {"source": "apimart", "model": "MiniMax-H3-Max"}
    try:
        base, headers = _config()
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 7000:
            raise ValueError("视频提示词须为 1 至 7000 字符")
        if isinstance(duration, bool) or not isinstance(duration, int) or not 5 <= duration <= 15:
            raise ValueError("MiniMax-H3-Max 时长须为 5 至 15 秒整数")
        if resolution not in ("480P", "768P", "1080P"):
            raise ValueError("MiniMax-H3-Max 仅支持 480P、768P、1080P")
        if not _public_url(image_url) or (image_tail_url and not _public_url(image_tail_url)):
            raise ValueError("首尾帧须使用公网 HTTPS URL，请配置 Bunny 或 PUBLIC_BASE_URL")
        body = {"model": common["model"], "prompt": prompt, "first_frame_image": image_url,
                "duration": duration, "resolution": resolution, "aspect_ratio": ratio}
        if image_tail_url:
            body["last_frame_image"] = image_tail_url
        submitted = _payload(requests.post(base + "/videos/generations", headers=headers, json=body, timeout=60))
        items = submitted.get("data")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict) or not items[0].get("task_id"):
            raise ValueError("APIMart 未返回 task_id")
        common["task_id"] = str(items[0]["task_id"])
        common["status"] = "processing"
        if progress:
            progress({**common, "provider_status": "submitted"})
        if not poll:
            return {**common, "status": "submitted"}
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            time.sleep(min(5, max(0, deadline - time.monotonic())))
            try:
                response = requests.get(base + "/tasks/" + quote(common["task_id"], safe=""), headers=headers, timeout=30)
                if response.status_code == 429 or response.status_code >= 500:
                    continue
                data = _payload(response).get("data", {})
            except (requests.Timeout, requests.ConnectionError):
                continue
            if not isinstance(data, dict):
                raise ValueError("APIMart 视频任务响应格式无效")
            status = data.get("status")
            if progress:
                progress({**common, "provider_status": status or "processing"})
            if status == "completed":
                videos = data.get("result", {}).get("videos", [])
                urls = videos[0].get("url") if videos else None
                url = urls[0] if isinstance(urls, list) and urls else urls
                if not _public_url(url):
                    raise ValueError("APIMart 任务完成但未返回有效视频 URL")
                return {**common, "url": url, "status": "succeeded"}
            if status in ("failed", "cancelled", "canceled"):
                common["status"] = "failed"
                raise ValueError(f"APIMart 视频任务失败：{data.get('error') or '未知错误'}")
        return {**common, "status": "processing", "error": "APIMart 视频等待超时，可按 task_id 查询"}
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        return {**common, "error": str(exc)}