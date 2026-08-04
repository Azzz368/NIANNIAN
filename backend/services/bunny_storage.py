"""Minimal server-only Bunny Storage adapter for temporary provider media."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict
from urllib.parse import quote, urlparse

import requests


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


class BunnyStorageError(RuntimeError):
    pass


def is_configured() -> bool:
    return all(
        os.getenv(name, "").strip()
        for name in ("BUNNY_STORAGE_ZONE", "BUNNY_ACCESS_KEY", "BUNNY_PULL_ZONE_URL")
    )


def _config() -> Dict[str, str]:
    values = {
        "storage_zone": os.getenv("BUNNY_STORAGE_ZONE", "").strip(),
        "access_key": os.getenv("BUNNY_ACCESS_KEY", "").strip(),
        "region": os.getenv("BUNNY_STORAGE_REGION", "sg").strip() or "sg",
        "pull_zone_url": os.getenv("BUNNY_PULL_ZONE_URL", "").strip().rstrip("/"),
    }
    missing = [
        env_name
        for env_name, field in (
            ("BUNNY_STORAGE_ZONE", "storage_zone"),
            ("BUNNY_ACCESS_KEY", "access_key"),
            ("BUNNY_PULL_ZONE_URL", "pull_zone_url"),
        )
        if not values[field]
    ]
    if missing:
        raise BunnyStorageError("缺少 Bunny Storage 配置：" + "、".join(missing))
    parsed = urlparse(values["pull_zone_url"])
    if parsed.scheme != "https" or not parsed.netloc:
        raise BunnyStorageError("BUNNY_PULL_ZONE_URL 必须是公网 HTTPS 地址")
    return values


def safe_segment(value: str, fallback: str = "item") -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("-", str(value or "")).strip("-._")
    return cleaned[:100] or fallback


def _storage_path(remote_path: str) -> str:
    parts = [safe_segment(part) for part in str(remote_path or "").replace("\\", "/").split("/") if part]
    if not parts:
        raise BunnyStorageError("Bunny remote_path 不能为空")
    return "/".join(parts)


def _storage_url(config: Dict[str, str], storage_path: str) -> str:
    encoded_zone = quote(config["storage_zone"], safe="")
    encoded_path = "/".join(quote(part, safe="-._~") for part in storage_path.split("/"))
    return f"https://{config['region']}.storage.bunnycdn.com/{encoded_zone}/{encoded_path}"


def upload_bytes(
    content: bytes,
    remote_path: str,
    content_type: str,
    *,
    wait_until_public: bool = True,
) -> Dict[str, Any]:
    if not content:
        raise BunnyStorageError("Bunny 上传内容为空")
    config = _config()
    storage_path = _storage_path(remote_path)
    response = requests.put(
        _storage_url(config, storage_path),
        headers={
            "AccessKey": config["access_key"],
            "Content-Type": content_type or "application/octet-stream",
            "Content-Length": str(len(content)),
        },
        data=content,
        timeout=max(10, int(os.getenv("BUNNY_UPLOAD_TIMEOUT_SECONDS", "180") or 180)),
    )
    if not 200 <= response.status_code < 300:
        detail = (response.text or "").strip()[:500]
        raise BunnyStorageError(
            f"Bunny 上传失败（HTTP {response.status_code}）"
            + (f"：{detail}" if detail else "")
        )
    cdn_url = f"{config['pull_zone_url']}/{storage_path}"
    if wait_until_public:
        attempts = max(1, int(os.getenv("BUNNY_CDN_READY_ATTEMPTS", "8") or 8))
        interval = max(0.25, float(os.getenv("BUNNY_CDN_READY_INTERVAL_SECONDS", "1.5") or 1.5))
        ready = False
        last_status = 0
        for attempt in range(attempts):
            try:
                check = requests.get(
                    cdn_url,
                    headers={"Range": "bytes=0-0", "Accept": "image/*,*/*"},
                    timeout=15,
                    stream=True,
                )
                last_status = check.status_code
                ready = check.status_code in (200, 206)
                check.close()
            except requests.RequestException:
                ready = False
            if ready:
                break
            if attempt < attempts - 1:
                time.sleep(interval)
        if not ready:
            raise BunnyStorageError(
                f"Bunny CDN 在 {attempts} 次检查后仍不可访问"
                + (f"（HTTP {last_status}）" if last_status else "")
            )
    return {"cdn_url": cdn_url, "storage_key": storage_path, "size_bytes": len(content)}


def delete_file(remote_path: str) -> None:
    config = _config()
    storage_path = _storage_path(remote_path)
    response = requests.delete(
        _storage_url(config, storage_path),
        headers={"AccessKey": config["access_key"]},
        timeout=max(10, int(os.getenv("BUNNY_REQUEST_TIMEOUT_SECONDS", "120") or 120)),
    )
    if response.status_code == 404:
        return
    if not 200 <= response.status_code < 300:
        detail = (response.text or "").strip()[:500]
        raise BunnyStorageError(
            f"Bunny 删除失败（HTTP {response.status_code}）"
            + (f"：{detail}" if detail else "")
        )
