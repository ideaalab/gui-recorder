from __future__ import annotations

from pathlib import Path

import yaml

from homeassistant.core import HomeAssistant

from .const import DOMAIN, EXCLUDED_LIST_FILENAME, INCLUDED_LIST_FILENAME, MODE_INCLUDE

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


def _dump_entity_list_file(entities: list[str], what: str) -> str:
    """One entity id per line, as a plain YAML list.

    An empty list must be written as an explicit "[]": an empty file makes
    !include return None and the recorder schema expects a list.
    """
    header = (
        f"# Entities {what} - managed by the GUI Recorder integration.\n"
        "# Manual edits will be overwritten. Referenced from gui_recorder.yaml.\n"
    )
    if not entities:
        return header + "[]\n"
    return header + yaml.safe_dump(entities, default_flow_style=False).rstrip() + "\n"


def _emit_filter_block(name: str, include_target: str | None, manual_keys: dict[str, list[str]]) -> str:
    """Render an exclude:/include: block.

    The entities list is an !include of its own file, which safe_dump cannot emit
    (it would quote the tag), so that one line is written by hand and the manual
    keys are dumped underneath it and indented.
    """
    if not include_target and not manual_keys:
        return f"{name}: {{}}"
    lines = [f"{name}:"]
    if include_target:
        lines.append(f"  entities: !include {include_target}")
    if manual_keys:
        dumped = yaml.safe_dump(manual_keys, sort_keys=False, default_flow_style=False).rstrip()
        lines.extend(f"  {line}" for line in dumped.splitlines())
    return "\n".join(lines)

async def async_write_yaml(hass: HomeAssistant) -> str:
    data = hass.data[DOMAIN]["data"]
    generated_path = data.get("generated_path", "gui_recorder.yaml")
    include_mode = data.get("mode") == MODE_INCLUDE
    # Both lists are written to their own file every time; only the active one is
    # referenced from the generated yaml, so switching modes never loses a selection
    # and the user can see both files sitting in the config folder.
    excluded_entities = sorted(set(data.get("excluded_entities", [])))
    included_entities = sorted(set(data.get("included_entities", [])))
    purge_keep_days = int(data.get("purge_keep_days", 10))
    auto_purge = bool(data.get("auto_purge", True))
    auto_repack = bool(data.get("auto_repack", True))
    commit_interval = int(data.get("commit_interval", 5))
    db_url = data.get("db_url")

    path = Path(hass.config.path(generated_path))

    try:
        manual = parse_manual_exclusions(data.get("manual_exclusions_yaml", ""))
    except ValueError:
        # Already validated when saved; if storage somehow holds something invalid
        # (e.g. edited externally), skip it rather than write a broken recorder config.
        manual = {}

    # Build ordered dicts (Python 3.7+ preserves insertion order) so safe_dump
    # emits them in our preferred order: entities first under exclude, then the
    # rest. safe_dump handles quoting for values with YAML-significant chars
    # (e.g. globs starting with '*' which YAML would otherwise parse as alias
    # references and reject — see https://github.com/ideaalab/gui-recorder).
    manual_exclude = manual.get("exclude", {})
    manual_exclude_keys = {key: manual_exclude[key] for key in _ALLOWED_EXCLUDE_KEYS if manual_exclude.get(key)}

    manual_include = manual.get("include", {})
    manual_include_keys = {key: manual_include[key] for key in _ALLOWED_INCLUDE_KEYS if manual_include.get(key)}

    # Only the active list is referenced. In include mode the entities go under
    # include.entities, the highest precedence rule of the recorder filter, so they
    # are recorded even when one of the user's own exclude globs matches them.
    exclude_target = None if include_mode else EXCLUDED_LIST_FILENAME
    include_target = INCLUDED_LIST_FILENAME if include_mode else None

    parts: list[str] = []
    parts.append("# This file is managed by the GUI Recorder integration.")
    parts.append("# Manual edits will be overwritten.")
    if include_mode:
        parts.append("# Mode: include - only the entities listed under include.entities are recorded.")
    parts.append("")
    parts.append(f"auto_purge: {'true' if auto_purge else 'false'}")
    parts.append(f"auto_repack: {'true' if auto_repack else 'false'}")
    parts.append(f"purge_keep_days: {purge_keep_days}")
    parts.append(f"commit_interval: {commit_interval}")
    if isinstance(db_url, str) and db_url.strip():
        # safe_dump quotes the value if the sqlite URL needs it (it usually
        # doesn't, but the ':' and '///' are safest left to the emitter).
        parts.append(yaml.safe_dump({"db_url": db_url.strip()}, default_flow_style=False).rstrip())
    parts.append("")

    parts.append(_emit_filter_block("exclude", exclude_target, manual_exclude_keys))

    if include_target or manual_include_keys:
        parts.append("")
        parts.append(_emit_filter_block("include", include_target, manual_include_keys))

    content = "\n".join(parts) + "\n"

    def _write_all() -> None:
        path.write_text(content, "utf-8")
        (path.parent / EXCLUDED_LIST_FILENAME).write_text(
            _dump_entity_list_file(excluded_entities, "NOT recorded (exclude list)"), "utf-8"
        )
        (path.parent / INCLUDED_LIST_FILENAME).write_text(
            _dump_entity_list_file(included_entities, "recorded (include list)"), "utf-8"
        )

    await hass.async_add_executor_job(_write_all)
    return str(path)
