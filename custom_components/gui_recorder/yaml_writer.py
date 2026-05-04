from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_write_yaml(hass: HomeAssistant) -> str:
    data = hass.data[DOMAIN]["data"]
    generated_path = data.get("generated_path", "gui_recorder.yaml")
    excluded_entities = sorted(set(data.get("excluded_entities", [])))
    purge_keep_days = int(data.get("purge_keep_days", 10))
    auto_purge = bool(data.get("auto_purge", True))
    auto_repack = bool(data.get("auto_repack", True))
    commit_interval = int(data.get("commit_interval", 5))

    path = Path(hass.config.path(generated_path))

    lines: list[str] = []
    lines.append("# This file is managed by the GUI Recorder integration.")
    lines.append("# Manual edits will be overwritten.")
    lines.append("")
    lines.append(f"auto_purge: {'true' if auto_purge else 'false'}")
    lines.append(f"auto_repack: {'true' if auto_repack else 'false'}")
    lines.append(f"purge_keep_days: {purge_keep_days}")
    lines.append(f"commit_interval: {commit_interval}")
    lines.append("")

    if excluded_entities:
        lines.append("exclude:")
        lines.append("  entities:")
        for entity_id in excluded_entities:
            lines.append(f"    - {entity_id}")
    else:
        lines.append("exclude: {}")

    content = "\n".join(lines) + "\n"
    await hass.async_add_executor_job(path.write_text, content, "utf-8")
    return str(path)
