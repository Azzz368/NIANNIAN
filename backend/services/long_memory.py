import json
import math
import re
import sqlite3
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import storage


MEMORY_DIR = storage.DATA_DIR / "memory"
MEMORY_DB = MEMORY_DIR / "memory.sqlite"
_LOCK = threading.RLock()


PYRAMID_LEVELS = {
    1: {"label": "核心身份与重大意义", "half_life_days": 36500, "description": "长期保留，几乎不自动遗忘"},
    2: {"label": "重要关系与记忆锚点", "half_life_days": 365, "description": "缓慢衰减，除非长期无关才淡化"},
    3: {"label": "具体事件与情绪变化", "half_life_days": 90, "description": "中速衰减，适合形成周记/月记"},
    4: {"label": "普通标签与场景细节", "half_life_days": 30, "description": "较快衰减，只保留可检索线索"},
    5: {"label": "低价值表层碎片", "half_life_days": 7, "description": "快速淡化，优先进入遗忘区"},
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_load(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _connect() -> sqlite3.Connection:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(MEMORY_DB), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # Windows local-dev fallback: this workspace can reject SQLite journal file
    # rotation, so keep the memory DB in autocommit/no-journal mode.
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                date_text TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                content_text TEXT NOT NULL DEFAULT '',
                importance REAL NOT NULL DEFAULT 0.5,
                memory_level INTEGER NOT NULL DEFAULT 3,
                decay_score REAL NOT NULL DEFAULT 1.0,
                retention_state TEXT NOT NULL DEFAULT 'active',
                retention_note TEXT NOT NULL DEFAULT '',
                last_accessed_at TEXT NOT NULL DEFAULT '',
                forgotten_at TEXT NOT NULL DEFAULT '',
                structured_json TEXT NOT NULL DEFAULT '{}',
                persona_json TEXT NOT NULL DEFAULT '{}',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_source
                ON memories(user_id, source_type, source_id);
            CREATE INDEX IF NOT EXISTS idx_memories_user_date
                ON memories(user_id, date_text, updated_at);

            CREATE TABLE IF NOT EXISTS memory_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0.5,
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_memory_indexes_lookup
                ON memory_indexes(user_id, kind, value);
            CREATE INDEX IF NOT EXISTS idx_memory_indexes_memory
                ON memory_indexes(memory_id);

            CREATE TABLE IF NOT EXISTS memory_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                asset_id TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL DEFAULT '',
                mime TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_memory_assets_memory
                ON memory_assets(memory_id);

            CREATE TABLE IF NOT EXISTS persona_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                persona_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );
            """
        )
        _ensure_column(conn, "memories", "memory_level", "INTEGER NOT NULL DEFAULT 3")
        _ensure_column(conn, "memories", "decay_score", "REAL NOT NULL DEFAULT 1.0")
        _ensure_column(conn, "memories", "retention_note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "memories", "last_accessed_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "memories", "forgotten_at", "TEXT NOT NULL DEFAULT ''")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(items: List[Dict[str, Any]], kind: str, values: Any, weight: float) -> None:
    if values is None:
        return
    if not isinstance(values, list):
        values = [values]
    seen = {(item["kind"], item["value"]) for item in items}
    for raw in values:
        value = _clean_text(raw)
        if not value or (kind, value) in seen:
            continue
        items.append({"kind": kind, "value": value, "weight": weight})
        seen.add((kind, value))


def _index_entries(structured: Dict[str, Any], persona: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    card = structured.get("record_card") if isinstance(structured.get("record_card"), dict) else {}
    indexes = structured.get("indexes") if isinstance(structured.get("indexes"), dict) else {}

    _append_unique(entries, "tag", card.get("tags"), 0.68)
    _append_unique(entries, "person", card.get("people"), 0.78)
    _append_unique(entries, "place", card.get("location"), 0.72)
    _append_unique(entries, "place", indexes.get("locations"), 0.72)
    _append_unique(entries, "person", indexes.get("people"), 0.78)
    _append_unique(entries, "event", indexes.get("events"), 0.86)
    _append_unique(entries, "emotion", indexes.get("emotions"), 0.74)
    _append_unique(entries, "keyword", indexes.get("keywords"), 0.62)
    _append_unique(entries, "memory_hook", structured.get("memory_hooks"), 0.9)

    anchors = persona.get("memory_anchors") if isinstance(persona, dict) else []
    anchor_values = []
    if isinstance(anchors, list):
        for anchor in anchors:
            if isinstance(anchor, dict):
                anchor_values.append(anchor.get("title") or anchor.get("label") or anchor.get("description"))
            else:
                anchor_values.append(anchor)
    _append_unique(entries, "persona_anchor", anchor_values, 0.92)
    return entries


def _importance_score(structured: Dict[str, Any], persona: Dict[str, Any], image_count: int) -> float:
    indexes = structured.get("indexes") if isinstance(structured.get("indexes"), dict) else {}
    hooks = structured.get("memory_hooks") if isinstance(structured.get("memory_hooks"), list) else []
    events = indexes.get("events") if isinstance(indexes.get("events"), list) else []
    emotions = indexes.get("emotions") if isinstance(indexes.get("emotions"), list) else []
    people = indexes.get("people") if isinstance(indexes.get("people"), list) else []
    confidence = persona.get("confidence", 0) if isinstance(persona, dict) else 0
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0
    score = 0.36
    score += min(len(events), 4) * 0.08
    score += min(len(hooks), 4) * 0.07
    score += min(len(emotions), 3) * 0.05
    score += min(len(people), 3) * 0.04
    score += min(image_count, 4) * 0.025
    score += min(max(confidence, 0), 1) * 0.12
    return max(0.05, min(1.0, round(score, 3)))


def _pyramid_level(structured: Dict[str, Any], persona: Dict[str, Any], importance: float) -> Tuple[int, str]:
    indexes = structured.get("indexes") if isinstance(structured.get("indexes"), dict) else {}
    hooks = structured.get("memory_hooks") if isinstance(structured.get("memory_hooks"), list) else []
    events = indexes.get("events") if isinstance(indexes.get("events"), list) else []
    emotions = indexes.get("emotions") if isinstance(indexes.get("emotions"), list) else []
    people = indexes.get("people") if isinstance(indexes.get("people"), list) else []
    keywords = indexes.get("keywords") if isinstance(indexes.get("keywords"), list) else []
    core_identity = persona.get("core_identity") if isinstance(persona, dict) else []
    life_context = persona.get("life_context") if isinstance(persona, dict) else []
    anchors = persona.get("memory_anchors") if isinstance(persona, dict) else []

    if importance >= 0.9 or core_identity or life_context:
        return 1, "包含核心身份、长期语境或高重要性记忆"
    if importance >= 0.72 and (hooks or anchors or people):
        return 2, "包含重要人物、关系或记忆锚点"
    if events or emotions or importance >= 0.58:
        return 3, "包含具体事件或情绪变化"
    if keywords or hooks:
        return 4, "主要是普通标签、场景或检索线索"
    return 5, "信息量较低，属于表层碎片"


def _parse_memory_date(date_text: str, fallback_iso: str) -> date:
    text = _clean_text(date_text)
    candidates = [
        r"(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
        r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})",
        r"(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})",
    ]
    for pattern in candidates:
        match = re.search(pattern, text)
        if match:
            return date(int(match.group("y")), int(match.group("m")), int(match.group("d")))
    try:
        return datetime.fromisoformat(fallback_iso.replace("Z", "+00:00")).date()
    except Exception:
        return datetime.now().date()


def _retention_from_score(level: int, score: float) -> Tuple[str, str]:
    if level <= 1:
        return "active", "金字塔顶层核心记忆，不自动遗忘"
    if score >= 0.55:
        return "active", "仍有较强关联，保持活跃"
    if score >= 0.28:
        return "faded", "关联开始减弱，保留摘要和索引"
    if score >= 0.12:
        return "archived", "细节进入归档，默认检索降权"
    return "forgotten", "低相关低强度，进入遗忘区"


def _forgetting_projection(row: sqlite3.Row, as_of: date) -> Dict[str, Any]:
    level = int(row["memory_level"] or 3)
    level_info = PYRAMID_LEVELS.get(level, PYRAMID_LEVELS[3])
    memory_date = _parse_memory_date(row["date_text"], row["created_at"])
    age_days = max(0, (as_of - memory_date).days)
    importance = float(row["importance"] or 0)
    half_life = float(level_info["half_life_days"])
    time_decay = 1.0 if half_life >= 36500 else math.pow(0.5, age_days / half_life)
    decay_score = 1.0 if level <= 1 else max(0.0, min(1.0, importance * time_decay))
    state, note = _retention_from_score(level, decay_score)
    return {
        "memory_id": row["memory_id"],
        "title": row["title"],
        "date": row["date_text"],
        "age_days": age_days,
        "importance": importance,
        "memory_level": level,
        "level_label": level_info["label"],
        "half_life_days": int(half_life),
        "decay_score": round(decay_score, 4),
        "current_state": row["retention_state"],
        "projected_state": state,
        "retention_note": note,
    }


def save_diary_memory(
    *,
    user_id: str,
    diary_id: str,
    title: str,
    date_text: str,
    diary_text: str,
    structured_output: Dict[str, Any],
    digital_persona: Dict[str, Any],
    images: List[Dict[str, Any]],
    pdf_url: str,
    raw_payload: Dict[str, Any],
) -> Dict[str, Any]:
    init_db()
    clean_user = _clean_text(user_id) or "local"
    memory_id = f"diary:{diary_id}"
    card = structured_output.get("record_card") if isinstance(structured_output.get("record_card"), dict) else {}
    summary = _clean_text(card.get("summary")) or diary_text[:140]
    importance = _importance_score(structured_output, digital_persona, len(images))
    memory_level, level_reason = _pyramid_level(structured_output, digital_persona, importance)
    now = _now_iso()
    index_entries = _index_entries(structured_output, digital_persona)

    with _LOCK, _connect() as conn:
        existing = conn.execute(
            "SELECT created_at FROM memories WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO memories (
                memory_id, user_id, source_type, source_id, title, date_text, summary,
                content_text, importance, memory_level, decay_score, retention_state,
                retention_note, structured_json, persona_json,
                raw_json, created_at, updated_at
            )
            VALUES (?, ?, 'diary', ?, ?, ?, ?, ?, ?, ?, 1.0, 'active', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                title = excluded.title,
                date_text = excluded.date_text,
                summary = excluded.summary,
                content_text = excluded.content_text,
                importance = excluded.importance,
                memory_level = excluded.memory_level,
                decay_score = excluded.decay_score,
                retention_state = excluded.retention_state,
                retention_note = excluded.retention_note,
                structured_json = excluded.structured_json,
                persona_json = excluded.persona_json,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            """,
            (
                memory_id,
                clean_user,
                diary_id,
                title,
                date_text,
                summary,
                diary_text,
                importance,
                memory_level,
                level_reason,
                _json_dump(structured_output),
                _json_dump(digital_persona),
                _json_dump(raw_payload),
                created_at,
                now,
            ),
        )
        conn.execute("DELETE FROM memory_indexes WHERE memory_id = ?", (memory_id,))
        conn.executemany(
            "INSERT INTO memory_indexes(memory_id, user_id, kind, value, weight) VALUES (?, ?, ?, ?, ?)",
            [(memory_id, clean_user, item["kind"], item["value"], item["weight"]) for item in index_entries],
        )
        conn.execute("DELETE FROM memory_assets WHERE memory_id = ?", (memory_id,))
        asset_rows = [
            (memory_id, clean_user, "pdf", "", f"{title or diary_id}.pdf", "application/pdf", pdf_url, 0)
        ]
        for image in images:
            asset_rows.append((
                memory_id,
                clean_user,
                "image",
                _clean_text(image.get("image_id")),
                _clean_text(image.get("filename") or image.get("stored_name")),
                _clean_text(image.get("mime")),
                _clean_text(image.get("url")),
                int(image.get("size") or 0),
            ))
        conn.executemany(
            """
            INSERT INTO memory_assets(memory_id, user_id, asset_type, asset_id, filename, mime, url, size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            asset_rows,
        )
        conn.execute("DELETE FROM persona_snapshots WHERE memory_id = ?", (memory_id,))
        if digital_persona and not digital_persona.get("error"):
            conn.execute(
                """
                INSERT INTO persona_snapshots(memory_id, user_id, summary, confidence, persona_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    clean_user,
                    _clean_text(digital_persona.get("summary")),
                    float(digital_persona.get("confidence") or 0),
                    _json_dump(digital_persona),
                    now,
                ),
            )

    return {
        "memory_id": memory_id,
        "user_id": clean_user,
        "importance": importance,
        "memory_level": memory_level,
        "level_label": PYRAMID_LEVELS[memory_level]["label"],
        "index_count": len(index_entries),
        "asset_count": len(asset_rows),
        "db_path": str(MEMORY_DB),
    }


def _memory_from_row(row: sqlite3.Row, include_raw: bool = False) -> Dict[str, Any]:
    data = {
        "memory_id": row["memory_id"],
        "user_id": row["user_id"],
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "title": row["title"],
        "date": row["date_text"],
        "summary": row["summary"],
        "content_text": row["content_text"],
        "importance": row["importance"],
        "memory_level": row["memory_level"],
        "level_label": PYRAMID_LEVELS.get(int(row["memory_level"] or 3), PYRAMID_LEVELS[3])["label"],
        "decay_score": row["decay_score"],
        "retention_state": row["retention_state"],
        "retention_note": row["retention_note"],
        "structured_output": _json_load(row["structured_json"], {}),
        "digital_persona": _json_load(row["persona_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_raw:
        data["raw"] = _json_load(row["raw_json"], {})
    return data


def recent_memories(user_id: str = "local", limit: int = 20) -> List[Dict[str, Any]]:
    init_db()
    clean_user = _clean_text(user_id) or "local"
    limit = max(1, min(int(limit or 20), 100))
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM memories
            WHERE user_id = ? AND retention_state != 'forgotten'
            ORDER BY date_text DESC, updated_at DESC
            LIMIT ?
            """,
            (clean_user, limit),
        ).fetchall()
    return [_memory_from_row(row) for row in rows]


def search_memories(user_id: str = "local", query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    init_db()
    clean_user = _clean_text(user_id) or "local"
    clean_query = _clean_text(query)
    if not clean_query:
        return recent_memories(clean_user, limit)
    like = f"%{clean_query}%"
    limit = max(1, min(int(limit or 20), 100))
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT m.*
            FROM memories m
            LEFT JOIN memory_indexes i ON i.memory_id = m.memory_id
            WHERE m.user_id = ?
              AND m.retention_state != 'forgotten'
              AND (
                m.title LIKE ?
                OR m.summary LIKE ?
                OR m.content_text LIKE ?
                OR i.value LIKE ?
              )
            ORDER BY m.importance DESC, m.date_text DESC, m.updated_at DESC
            LIMIT ?
            """,
            (clean_user, like, like, like, like, limit),
        ).fetchall()
        memories = [_memory_from_row(row) for row in rows]
        for memory in memories:
            matches = conn.execute(
                """
                SELECT kind, value, weight FROM memory_indexes
                WHERE memory_id = ? AND value LIKE ?
                ORDER BY weight DESC, kind ASC
                LIMIT 12
                """,
                (memory["memory_id"], like),
            ).fetchall()
            memory["matched_indexes"] = [dict(item) for item in matches]
    return memories


def memory_stats(user_id: str = "local") -> Dict[str, Any]:
    init_db()
    clean_user = _clean_text(user_id) or "local"
    with _LOCK, _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM memories WHERE user_id = ?", (clean_user,)).fetchone()["n"]
        by_kind = conn.execute(
            """
            SELECT kind, COUNT(*) AS n FROM memory_indexes
            WHERE user_id = ?
            GROUP BY kind
            ORDER BY n DESC
            """,
            (clean_user,),
        ).fetchall()
        top = conn.execute(
            """
            SELECT kind, value, MAX(weight) AS weight, COUNT(*) AS n
            FROM memory_indexes
            WHERE user_id = ?
            GROUP BY kind, value
            ORDER BY weight DESC, n DESC
            LIMIT 20
            """,
            (clean_user,),
        ).fetchall()
    return {
        "user_id": clean_user,
        "db_path": str(MEMORY_DB),
        "memory_count": total,
        "index_counts": [dict(row) for row in by_kind],
        "top_indexes": [dict(row) for row in top],
    }


def pyramid_levels() -> Dict[str, Any]:
    return {
        "levels": [
            {"level": level, **info}
            for level, info in sorted(PYRAMID_LEVELS.items())
        ]
    }


def forgetting_report(user_id: str = "local", as_of: str = "", apply: bool = False) -> Dict[str, Any]:
    init_db()
    clean_user = _clean_text(user_id) or "local"
    if as_of:
        as_of_date = _parse_memory_date(as_of, _now_iso())
    else:
        as_of_date = datetime.now().date()

    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE user_id = ? ORDER BY date_text DESC, updated_at DESC",
            (clean_user,),
        ).fetchall()
        projections = [_forgetting_projection(row, as_of_date) for row in rows]
        if apply:
            now = _now_iso()
            for item in projections:
                forgotten_at = now if item["projected_state"] == "forgotten" else ""
                conn.execute(
                    """
                    UPDATE memories
                    SET retention_state = ?,
                        decay_score = ?,
                        retention_note = ?,
                        forgotten_at = ?,
                        updated_at = ?
                    WHERE memory_id = ?
                    """,
                    (
                        item["projected_state"],
                        item["decay_score"],
                        item["retention_note"],
                        forgotten_at,
                        now,
                        item["memory_id"],
                    ),
                )

    state_counts: Dict[str, int] = {}
    level_counts: Dict[str, int] = {}
    for item in projections:
        state_counts[item["projected_state"]] = state_counts.get(item["projected_state"], 0) + 1
        key = f"{item['memory_level']}:{item['level_label']}"
        level_counts[key] = level_counts.get(key, 0) + 1

    return {
        "user_id": clean_user,
        "as_of": as_of_date.isoformat(),
        "applied": apply,
        "state_counts": state_counts,
        "level_counts": level_counts,
        "items": projections,
    }
