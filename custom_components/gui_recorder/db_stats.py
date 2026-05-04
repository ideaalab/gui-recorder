from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .storage import async_save_data


def _get_recorder_db_url(hass: HomeAssistant) -> str | None:
    """Return the configured recorder db_url, or None if recorder isn't ready."""
    try:
        from homeassistant.components.recorder import get_instance
        instance = get_instance(hass)
        return getattr(instance, "db_url", None)
    except Exception:  # noqa: BLE001 - recorder not loaded yet, etc.
        return None


def is_sqlite_recorder(hass: HomeAssistant) -> bool | None:
    """True if the recorder uses SQLite, False if a different backend, None if unknown."""
    db_url = _get_recorder_db_url(hass)
    if not db_url:
        return None
    return db_url.lower().startswith("sqlite")


def _resolve_sqlite_db_path(hass: HomeAssistant) -> Path:
    """Return the real on-disk SQLite path from recorder.db_url, falling back to default."""
    db_url = _get_recorder_db_url(hass)
    if db_url and db_url.lower().startswith("sqlite"):
        # SQLAlchemy URL formats supported:
        #   sqlite:///relative/path.db
        #   sqlite:////absolute/path.db   (the 4th slash is the root)
        #   sqlite://         -> in-memory (treat as default file)
        try:
            _, _, raw = db_url.partition("://")
            raw = raw.lstrip("/")
            if raw:
                # If the original had 4 slashes ("sqlite:////"), it is absolute.
                if db_url.startswith("sqlite:////"):
                    return Path("/" + raw)
                return Path(hass.config.path(raw))
        except Exception:  # noqa: BLE001
            pass
    return Path(hass.config.path("home-assistant_v2.db"))


def _sqlite_total_size_bytes(db_path: Path) -> int:
    """Sum the .db, .db-wal and .db-shm sidecar files (WAL mode is the HA default)."""
    total = 0
    for suffix in ("", "-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix) if suffix else db_path
        try:
            total += sidecar.stat().st_size
        except FileNotFoundError:
            pass
        except Exception:  # noqa: BLE001
            pass
    return total


def _analyze_sqlite_db(db_path: str) -> dict:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        table_names = {
            row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        if "states_meta" in table_names:
            rows = cursor.execute(
                """
                SELECT sm.entity_id, COUNT(*)
                FROM states s
                JOIN states_meta sm ON sm.metadata_id = s.metadata_id
                GROUP BY sm.entity_id
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()
        else:
            rows = cursor.execute(
                """
                SELECT entity_id, COUNT(*)
                FROM states
                GROUP BY entity_id
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()

        total = sum(count for _, count in rows)
        return {
            "entity_counts": {entity_id: count for entity_id, count in rows},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_path": str(path),
            "db_size_bytes": _sqlite_total_size_bytes(path),
            "total_rows": total,
            "error": None,
        }
    finally:
        conn.close()


async def async_analyze_db(hass: HomeAssistant) -> dict:
    data = hass.data[DOMAIN]["data"]
    db_path = str(_resolve_sqlite_db_path(hass))

    try:
        stats = await hass.async_add_executor_job(_analyze_sqlite_db, db_path)
    except Exception as err:  # noqa: BLE001
        stats = {
            "entity_counts": {},
            "generated_at": None,
            "db_path": db_path,
            "db_size_bytes": 0,
            "total_rows": 0,
            "error": str(err),
        }

    data["stats"] = stats
    await async_save_data(hass, data)
    return stats
