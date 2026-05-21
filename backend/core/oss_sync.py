# backend/core/oss_sync.py — 阿里云 OSS 双写镜像
"""
数据持久化策略：
- 本地 DATA_DIR 仍是工作目录（速度快，零延迟）
- 每次写入后异步推送到 OSS（best-effort，失败不阻塞业务）
- 启动时从 OSS 镜像拉回 DATA_DIR（容器重启/扩容不丢数据）

环境变量：
  OSS_ENABLE              "1" 启用（默认关闭）
  OSS_ACCESS_KEY_ID       阿里云 AK ID
  OSS_ACCESS_KEY_SECRET   阿里云 AK Secret
  OSS_BUCKET              桶名，如 niannian-data
  OSS_ENDPOINT            如 oss-cn-hongkong.aliyuncs.com
  OSS_PREFIX              数据在桶里的前缀，默认 "nian/"
"""
import os
import threading
from pathlib import Path
from typing import Optional

try:
    import oss2  # pip install oss2
except Exception:
    oss2 = None  # type: ignore

_LOCK = threading.RLock()
_bucket = None
_data_dir: Optional[Path] = None


def _env(k: str, default: str = "") -> str:
    return (os.environ.get(k, default) or "").strip()


def enabled() -> bool:
    if _env("OSS_ENABLE", "0") not in ("1", "true", "True", "yes"):
        return False
    if oss2 is None:
        print("[oss] oss2 not installed; pip install oss2")
        return False
    if not (_env("OSS_ACCESS_KEY_ID") and _env("OSS_ACCESS_KEY_SECRET")
            and _env("OSS_BUCKET") and _env("OSS_ENDPOINT")):
        print("[oss] missing env vars (OSS_ACCESS_KEY_ID/SECRET/BUCKET/ENDPOINT)")
        return False
    return True


def _get_bucket():
    global _bucket
    if _bucket is not None:
        return _bucket
    if not enabled():
        return None
    auth = oss2.Auth(_env("OSS_ACCESS_KEY_ID"), _env("OSS_ACCESS_KEY_SECRET"))
    _bucket = oss2.Bucket(auth, _env("OSS_ENDPOINT"), _env("OSS_BUCKET"))
    return _bucket


def _prefix() -> str:
    p = _env("OSS_PREFIX", "nian/")
    if not p.endswith("/"):
        p += "/"
    return p


def init(data_dir: Path):
    """注册本地数据根目录，方便相对路径计算。在 storage.py 启动时调用。"""
    global _data_dir
    _data_dir = data_dir


def _rel_key(local_path: Path) -> Optional[str]:
    if _data_dir is None:
        return None
    try:
        rel = local_path.resolve().relative_to(_data_dir.resolve())
    except Exception:
        return None
    return _prefix() + rel.as_posix()


def push_path(local_path: Path):
    """把单个本地文件推到 OSS。异步、best-effort、不抛异常。"""
    if not enabled():
        return
    if not local_path.exists() or not local_path.is_file():
        return
    key = _rel_key(local_path)
    if not key:
        return

    def _do():
        try:
            b = _get_bucket()
            if b is None:
                return
            b.put_object_from_file(key, str(local_path))
        except Exception as e:
            print(f"[oss push] {key}: {e}")

    threading.Thread(target=_do, daemon=True).start()


def delete_path(local_path: Path):
    """同步删除 OSS 上对应对象（或前缀）。"""
    if not enabled():
        return
    key = _rel_key(local_path)
    if not key:
        return

    def _do():
        try:
            b = _get_bucket()
            if b is None:
                return
            # 如果是目录，删除该前缀下所有 object
            if local_path.is_dir() or key.endswith("/") or not Path(local_path.name).suffix:
                dir_key = key if key.endswith("/") else key + "/"
                for obj in oss2.ObjectIterator(b, prefix=dir_key):
                    try:
                        b.delete_object(obj.key)
                    except Exception:
                        pass
            try:
                b.delete_object(key)
            except Exception:
                pass
        except Exception as e:
            print(f"[oss del] {key}: {e}")

    threading.Thread(target=_do, daemon=True).start()


def bootstrap_pull():
    """启动时把 OSS 上的全部 nian/ 数据拉到本地 DATA_DIR。"""
    if not enabled() or _data_dir is None:
        return
    b = _get_bucket()
    if b is None:
        return
    pfx = _prefix()
    n = 0
    try:
        for obj in oss2.ObjectIterator(b, prefix=pfx):
            key = obj.key
            if key.endswith("/"):
                continue
            rel = key[len(pfx):]
            local = _data_dir / rel
            # 本地已存在且大小一致就跳过（粗略增量）
            if local.exists() and local.is_file() and local.stat().st_size == obj.size:
                continue
            try:
                local.parent.mkdir(parents=True, exist_ok=True)
                b.get_object_to_file(key, str(local))
                n += 1
            except Exception as e:
                print(f"[oss pull] {key}: {e}")
        print(f"[oss] bootstrap pull done, synced {n} files from {pfx}")
    except Exception as e:
        print(f"[oss bootstrap] failed: {e}")


def push_all():
    """全量把本地 DATA_DIR 推到 OSS（首次切换到 OSS 时手动调用）。"""
    if not enabled() or _data_dir is None:
        return 0
    b = _get_bucket()
    if b is None:
        return 0
    n = 0
    for p in _data_dir.rglob("*"):
        if p.is_file():
            key = _rel_key(p)
            if not key:
                continue
            try:
                b.put_object_from_file(key, str(p))
                n += 1
            except Exception as e:
                print(f"[oss push_all] {key}: {e}")
    print(f"[oss] push_all done, uploaded {n} files")
    return n
