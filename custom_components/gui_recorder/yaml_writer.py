from __future__ import annotations

from pathlib import Path

import yaml

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_ALLOWED_EXCLUDE_KEYS = ("domains", "entity_globs", "event_types")
_ALLOWED_INCLUDE_KEYS = ("domains", "entity_globs")
_ALLOWED_TOP_KEYS = {"exclude": _ALLOWED_EXCLUDE_KEYS, "include": _ALLOWED_INCLUDE_KEYS}


def parse_manual_exclusions(text: str) -> dict[str, dict[str, list[str]]]:
    """Parse and validate the user-provided manual exclusions YAML block.

    Only exclude.{domains,entity_globs,event_types} and include.{domains,entity_globs}
    are accepted here - individual entities stay exclusively managed by the entity
    toggles, so the two systems never fight over the same list. Raises ValueError
    with a user-facing message on anything else.
    """
    text = (text or "").strip()
    if not text:
        return {}

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise ValueError(f"Invalid YAML: {err}") from err

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("The manual exclusions block must be a YAML mapping (e.g. 'exclude:' / 'include:').")

    result: dict[str, dict[str, list[str]]] = {}
    for top_key, value in loaded.items():
        if top_key not in _ALLOWED_TOP_KEYS:
            raise ValueError(f"Unsupported key '{top_key}'. Only 'exclude' and 'include' are allowed here.")
        if not isinstance(value, dict):
            raise ValueError(f"'{top_key}' must be a mapping.")

        section: dict[str, list[str]] = {}
        for sub_key, items in value.items():
            if sub_key not in _ALLOWED_TOP_KEYS[top_key]:
                if sub_key == "entities":
                    raise ValueError(
                        f"'{top_key}.entities' is not allowed here - use the entity toggles in the panel "
                        "for individual entities instead."
                    )
                raise ValueError(
                    f"Unsupported key '{top_key}.{sub_key}'. Allowed: {', '.join(_ALLOWED_TOP_KEYS[top_key])}."
                )
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                raise ValueError(f"'{top_key}.{sub_key}' must be a list of strings.")
            cleaned = sorted({item.strip() for item in items if item.strip()})
            if cleaned:
                section[sub_key] = cleaned

        if section:
            result[top_key] = section

    return result


async def async_write_yaml(hass: HomeAssistant) -> str:
    data = hass.data[DOMAIN]["data"]
    generated_path = data.get("generated_path", "gui_recorder.yaml")
    excluded_entities = sorted(set(data.get("excluded_entities", [])))
    purge_keep_days = int(data.get("purge_keep_days", 10))
    auto_purge = bool(data.get("auto_purge", True))
    auto_repack = bool(data.get("auto_repack", True))
    commit_interval = int(data.get("commit_interval", 5))

    path = Path(hass.config.path(generated_path))

    try:
        manual = parse_manual_exclusions(data.get("manual_exclusions_yaml", ""))
    except ValueError:
        # Already validated when saved; if storage somehow holds something invalid
        # (e.g. edited externally), skip it rather than write a broken recorder config.
        manual = {}

    exclude_block: dict[str, list[str]] = dict(manual.get("exclude", {}))
    if excluded_entities:
        exclude_block["entities"] = excluded_entities
    include_block: dict[str, list[str]] = dict(manual.get("include", {}))

    lines: list[str] = []
    lines.append("# This file is managed by the GUI Recorder integration.")
    lines.append("# Manual edits will be overwritten.")
    lines.append("")
    lines.append(f"auto_purge: {'true' if auto_purge else 'false'}")
    lines.append(f"auto_repack: {'true' if auto_repack else 'false'}")
    lines.append(f"purge_keep_days: {purge_keep_days}")
    lines.append(f"commit_interval: {commit_interval}")
    lines.append("")

    if exclude_block:
        lines.append("exclude:")
        if exclude_block.get("entities"):
            lines.append("  entities:")
            for entity_id in exclude_block["entities"]:
                lines.append(f"    - {entity_id}")
        for key in _ALLOWED_EXCLUDE_KEYS:
            if exclude_block.get(key):
                lines.append(f"  {key}:")
                for item in exclude_block[key]:
                    lines.append(f"    - {item}")
    else:
        lines.append("exclude: {}")

    if include_block:
        lines.append("")
        lines.append("include:")
        for key in _ALLOWED_INCLUDE_KEYS:
            if include_block.get(key):
                lines.append(f"  {key}:")
                for item in include_block[key]:
                    lines.append(f"    - {item}")

    content = "\n".join(lines) + "\n"
    await hass.async_add_executor_job(path.write_text, content, "utf-8")
    return str(path)
