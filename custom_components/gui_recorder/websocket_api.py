from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, INTEGRATION_VERSION
from .db_stats import async_analyze_db
from .migration import async_detect_sync_status, async_disable_legacy, async_ensure_gui_enabled, async_import_legacy
from .storage import async_reload_data, async_save_data
from .yaml_writer import async_write_yaml

_LOGGER = logging.getLogger(__name__)
_BLOCK_API_WARNED = False


def _normalize_entity_id(value: str) -> str:
    return str(value).strip()


async def _wait_recorder_idle(hass: HomeAssistant) -> None:
    """Wait until the recorder has finished processing queued tasks (e.g. purges).

    The recorder.purge service returns as soon as the task is enqueued, not when
    the actual DELETE has been committed. We wait for the recorder queue to drain,
    plus a small safety delay so the SQLite WAL checkpoint catches up before any
    read-only analysis runs.
    """
    global _BLOCK_API_WARNED
    try:
        from homeassistant.components.recorder import get_instance
        instance = get_instance(hass)
        block_fn = getattr(instance, "async_block_till_done", None)
        if block_fn is not None:
            await block_fn()
        elif not _BLOCK_API_WARNED:
            _LOGGER.warning(
                "Recorder.async_block_till_done() not available on this HA version; "
                "auto-update after purge may show stale data until the next manual refresh."
            )
            _BLOCK_API_WARNED = True
    except Exception as err:  # noqa: BLE001
        if not _BLOCK_API_WARNED:
            _LOGGER.warning("Could not wait for recorder to be idle: %s", err)
            _BLOCK_API_WARNED = True
    # Small safety margin for SQLite WAL checkpoint visibility on a fresh read-only connection.
    await asyncio.sleep(0.3)


def _normalize_excluded(values) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        entity_id = _normalize_entity_id(value)
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        normalized.append(entity_id)
    return sorted(normalized)


async def _save_and_reload(hass: HomeAssistant, data: dict) -> dict:
    await async_save_data(hass, data)
    await async_write_yaml(hass)
    reloaded = await async_reload_data(hass)
    return reloaded


async def _set_entity_recorded_state(hass: HomeAssistant, entity_id: str, recorded: bool) -> tuple[dict, bool]:
    data = await async_reload_data(hass)
    excluded = set(_normalize_excluded(data.get("excluded_entities", [])))
    entity_id = _normalize_entity_id(entity_id)
    before = set(excluded)

    if recorded:
        excluded.discard(entity_id)
    else:
        excluded.add(entity_id)

    changed = excluded != before
    if not changed:
        return data, False

    data["excluded_entities"] = _normalize_excluded(excluded)
    data["pending_restart"] = True
    reloaded = await _save_and_reload(hass, data)
    return reloaded, True


def _build_stats_payload(hass: HomeAssistant) -> dict:
    data = hass.data[DOMAIN]["data"]
    stats = data.get("stats", {})
    entity_counts = stats.get("entity_counts", {}) or {}
    total_rows = stats.get("total_rows")
    if total_rows is None:
        total_rows = sum(entity_counts.values())
    return {
        "entity_counts": entity_counts,
        "generated_at": stats.get("generated_at"),
        "db_path": stats.get("db_path", "home-assistant_v2.db"),
        "total_rows": total_rows,
        "db_size_bytes": int(stats.get("db_size_bytes", 0) or 0),
        "error": stats.get("error"),
    }


@callback
def _build_rows(hass: HomeAssistant) -> dict:
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    data = hass.data[DOMAIN]["data"]
    excluded = set(data.get("excluded_entities", []))
    stats_payload = _build_stats_payload(hass)
    entity_counts = stats_payload.get("entity_counts", {})

    devices: dict[str, dict] = {}
    orphan_entities: list[dict] = []
    obsolete_entities: list[dict] = []
    current_entity_ids: set[str] = set()

    def row_sort_key(entity: dict) -> tuple:
        return (-int(entity.get("record_count", 0)), entity["entity_id"])

    for entity_entry in entity_registry.entities.values():
        current_entity_ids.add(entity_entry.entity_id)
        row = {
            "entity_id": entity_entry.entity_id,
            "name": entity_entry.original_name or entity_entry.name or entity_entry.entity_id,
            "disabled_by": str(entity_entry.disabled_by) if entity_entry.disabled_by else None,
            "hidden_by": str(entity_entry.hidden_by) if entity_entry.hidden_by else None,
            "platform": entity_entry.platform,
            "domain": entity_entry.domain,
            "device_id": entity_entry.device_id,
            "recorded": entity_entry.entity_id not in excluded,
            "record_count": int(entity_counts.get(entity_entry.entity_id, 0)),
        }

        if entity_entry.device_id:
            device = device_registry.async_get(entity_entry.device_id)
            if device:
                dev = devices.setdefault(
                    device.id,
                    {
                        "device_id": device.id,
                        "name": device.name_by_user or device.name or "Unnamed device",
                        "manufacturer": device.manufacturer,
                        "model": device.model,
                        "entities": [],
                        "record_count": 0,
                    },
                )
                dev["entities"].append(row)
                dev["record_count"] += row["record_count"]
                continue

        orphan_entities.append(row)

    for entity_id, count in entity_counts.items():
        if entity_id in current_entity_ids:
            continue
        obsolete_entities.append(
            {
                "entity_id": entity_id,
                "name": entity_id,
                "platform": entity_id.split(".", 1)[0] if "." in entity_id else "unknown",
                "domain": entity_id.split(".", 1)[0] if "." in entity_id else "unknown",
                "device_id": None,
                "recorded": entity_id not in excluded,
                "record_count": int(count),
                "obsolete": True,
            }
        )

    device_rows = sorted(devices.values(), key=lambda d: (-int(d.get("record_count", 0)), d["name"].lower()))
    for dev in device_rows:
        dev["entities"] = sorted(dev["entities"], key=row_sort_key)

    orphan_entities = sorted(orphan_entities, key=row_sort_key)
    obsolete_entities = sorted(obsolete_entities, key=row_sort_key)

    matched_exclusions = sorted(entity_id for entity_id in excluded if entity_id in current_entity_ids)
    unmatched_exclusions = sorted(entity_id for entity_id in excluded if entity_id not in current_entity_ids)

    current_rows = sum(int(entity_counts.get(entity_id, 0)) for entity_id in current_entity_ids)
    obsolete_rows = sum(int(item["record_count"]) for item in obsolete_entities)
    stats_payload["current_rows"] = current_rows
    stats_payload["obsolete_rows"] = obsolete_rows
    stats_payload["obsolete_entity_count"] = len(obsolete_entities)
    stats_payload["configured_exclusions"] = len(excluded)
    stats_payload["matched_exclusions"] = len(matched_exclusions)
    stats_payload["unmatched_exclusions"] = len(unmatched_exclusions)

    return {
        "devices": device_rows,
        "orphans": orphan_entities,
        "obsolete": obsolete_entities,
        "pending_restart": bool(data.get("pending_restart", False)),
        "purge_keep_days": int(data.get("purge_keep_days", 10)),
        "auto_purge": bool(data.get("auto_purge", True)),
        "auto_repack": bool(data.get("auto_repack", True)),
        "commit_interval": int(data.get("commit_interval", 5)),
        "auto_update_data": bool(data.get("auto_update_data", True)),
        "repack_after_manual_purge": bool(data.get("repack_after_manual_purge", False)),
        "repack_in_progress": bool(data.get("repack_in_progress", False)),
        "stats": stats_payload,
        "migration": hass.data[DOMAIN].get("migration", {}),
        "matched_exclusions": matched_exclusions,
        "unmatched_exclusions": unmatched_exclusions,
        "version": INTEGRATION_VERSION,
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/get_tree"})
@callback
def ws_get_tree(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    connection.send_result(msg["id"], _build_rows(hass))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "gui_recorder/set_entity",
        vol.Required("entity_id"): str,
        vol.Required("recorded"): bool,
    }
)
async def ws_set_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    _, changed = await _set_entity_recorded_state(hass, msg["entity_id"], msg["recorded"])
    connection.send_result(
        msg["id"],
        {
            "ok": True,
            "changed": changed,
            "restart_required": changed,
            "removed": changed if msg["recorded"] else False,
        },
    )


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "gui_recorder/set_device",
        vol.Required("device_id"): str,
        vol.Required("recorded"): bool,
    }
)
async def ws_set_device(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    entity_registry = er.async_get(hass)
    data = await async_reload_data(hass)
    excluded = set(_normalize_excluded(data.get("excluded_entities", [])))
    before = set(excluded)

    for entry in entity_registry.entities.values():
        if entry.device_id != msg["device_id"]:
            continue
        if msg["recorded"]:
            excluded.discard(entry.entity_id)
        else:
            excluded.add(entry.entity_id)

    changed = excluded != before
    generated_file = None
    if changed:
        data["excluded_entities"] = _normalize_excluded(excluded)
        data["pending_restart"] = True
        await async_save_data(hass, data)
        generated_file = await async_write_yaml(hass)

    connection.send_result(msg["id"], {"ok": True, "generated_file": generated_file, "restart_required": changed, "changed": changed})




@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "gui_recorder/remove_exclusion",
        vol.Required("entity_id"): str,
    }
)
async def ws_remove_exclusion(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    _, changed = await _set_entity_recorded_state(hass, msg["entity_id"], True)
    connection.send_result(
        msg["id"],
        {
            "ok": True,
            "removed": changed,
            "restart_required": changed,
        },
    )


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/remove_unmatched_exclusions"})
async def ws_remove_unmatched_exclusions(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    entity_registry = er.async_get(hass)
    current_entity_ids = {entry.entity_id for entry in entity_registry.entities.values()}
    data = await async_reload_data(hass)
    excluded = _normalize_excluded(data.get("excluded_entities", []))
    removed = sorted(entity_id for entity_id in excluded if entity_id not in current_entity_ids)

    if removed:
        remaining = [eid for eid in excluded if eid not in set(removed)]
        data["excluded_entities"] = _normalize_excluded(remaining)
        data["pending_restart"] = True
        await _save_and_reload(hass, data)

    connection.send_result(
        msg["id"],
        {
            "ok": True,
            "removed": removed,
            "restart_required": bool(removed),
        },
    )

@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "gui_recorder/set_global_options",
        vol.Required("purge_keep_days"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3650)),
        vol.Required("auto_purge"): bool,
        vol.Required("auto_repack"): bool,
        vol.Required("commit_interval"): vol.All(vol.Coerce(int), vol.Range(min=0, max=86400)),
    }
)
async def ws_set_global_options(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    data = await async_reload_data(hass)
    data["purge_keep_days"] = int(msg["purge_keep_days"])
    data["auto_purge"] = bool(msg["auto_purge"])
    data["auto_repack"] = bool(msg["auto_repack"]) if bool(msg["auto_purge"]) else False
    data["commit_interval"] = int(msg["commit_interval"])
    data["pending_restart"] = True
    await async_save_data(hass, data)
    generated_file = await async_write_yaml(hass)
    await async_reload_data(hass)

    connection.send_result(
        msg["id"],
        {
            "ok": True,
            "generated_file": generated_file,
            "restart_required": True,
            "global_options": {
                "purge_keep_days": data["purge_keep_days"],
                "auto_purge": data["auto_purge"],
                "auto_repack": data["auto_repack"],
                "commit_interval": data["commit_interval"],
            },
        },
    )


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "gui_recorder/set_auto_update_data",
        vol.Required("auto_update_data"): bool,
    }
)
async def ws_set_auto_update_data(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    data = hass.data[DOMAIN]["data"]
    data["auto_update_data"] = bool(msg["auto_update_data"])
    await async_save_data(hass, data)
    connection.send_result(msg["id"], {"ok": True, "auto_update_data": data["auto_update_data"]})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "gui_recorder/set_repack_after_manual_purge",
        vol.Required("repack_after_manual_purge"): bool,
    }
)
async def ws_set_repack_after_manual_purge(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    data = hass.data[DOMAIN]["data"]
    data["repack_after_manual_purge"] = bool(msg["repack_after_manual_purge"])
    await async_save_data(hass, data)
    connection.send_result(msg["id"], {"ok": True, "repack_after_manual_purge": data["repack_after_manual_purge"]})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/regenerate_yaml"})
async def ws_regenerate_yaml(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    generated_file = await async_write_yaml(hass)
    connection.send_result(msg["id"], {"ok": True, "generated_file": generated_file})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/analyze_db"})
async def ws_analyze_db(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    stats = await async_analyze_db(hass)
    connection.send_result(msg["id"], {"ok": True, "stats": stats})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/purge_all"})
async def ws_purge_all(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    data = hass.data[DOMAIN]["data"]
    keep_days = int(data.get("purge_keep_days", 10))
    repack = bool(data.get("repack_after_manual_purge", False))
    data["repack_in_progress"] = bool(repack)
    if repack:
        await async_save_data(hass, data)
    try:
        await hass.services.async_call("recorder", "purge", {"keep_days": keep_days, "repack": repack}, blocking=True)
        await _wait_recorder_idle(hass)
    finally:
        if data.get("repack_in_progress"):
            data["repack_in_progress"] = False
            await async_save_data(hass, data)
    connection.send_result(msg["id"], {"ok": True, "refresh_required": True, "keep_days": keep_days, "repacked": repack})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/purge_excluded_entities"})
async def ws_purge_excluded_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    data = hass.data[DOMAIN]["data"]
    entity_ids = sorted(set(data.get("excluded_entities", [])))
    repack = bool(data.get("repack_after_manual_purge", False)) and bool(entity_ids)
    data["repack_in_progress"] = bool(repack)
    if repack:
        await async_save_data(hass, data)
    try:
        if entity_ids:
            await hass.services.async_call(
                "recorder",
                "purge_entities",
                {"entity_id": entity_ids, "keep_days": 0},
                blocking=True,
            )
            await _wait_recorder_idle(hass)
        if repack:
            # purge_entities doesn't support repack; run a no-op purge with very high
            # keep_days just to trigger the VACUUM.
            await hass.services.async_call("recorder", "purge", {"keep_days": 36500, "repack": True}, blocking=True)
            await _wait_recorder_idle(hass)
    finally:
        if data.get("repack_in_progress"):
            data["repack_in_progress"] = False
            await async_save_data(hass, data)
    connection.send_result(msg["id"], {"ok": True, "refresh_required": True, "purged_entities": len(entity_ids), "repacked": repack})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/purge_entity", vol.Required("entity_id"): str})
async def ws_purge_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    await hass.services.async_call(
        "recorder",
        "purge_entities",
        {"entity_id": [msg["entity_id"]], "keep_days": 0},
        blocking=True,
    )
    await _wait_recorder_idle(hass)
    connection.send_result(msg["id"], {"ok": True, "refresh_required": True})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/purge_device", vol.Required("device_id"): str})
async def ws_purge_device(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    entity_registry = er.async_get(hass)
    entity_ids = sorted({entry.entity_id for entry in entity_registry.entities.values() if entry.device_id == msg["device_id"]})
    if entity_ids:
        await hass.services.async_call(
            "recorder",
            "purge_entities",
            {"entity_id": entity_ids, "keep_days": 0},
            blocking=True,
        )
        await _wait_recorder_idle(hass)
    connection.send_result(msg["id"], {"ok": True, "refresh_required": True, "purged_entities": len(entity_ids)})




@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/restart_homeassistant"})
async def ws_restart_homeassistant(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    await hass.services.async_call("homeassistant", "restart", {}, blocking=False)
    connection.send_result(msg["id"], {"ok": True, "restart_requested": True})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/get_migration_status"})
async def ws_get_migration_status(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    status = await async_detect_sync_status(hass)
    hass.data[DOMAIN]["migration"] = status
    connection.send_result(msg["id"], status)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/import_legacy"})
async def ws_import_legacy(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    result = await async_import_legacy(hass)
    if result.get("ok"):
        data = hass.data[DOMAIN]["data"]
        await async_save_data(hass, data)
        await async_write_yaml(hass)
        hass.data[DOMAIN]["migration"] = await async_detect_sync_status(hass)
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/disable_legacy"})
async def ws_disable_legacy(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    result = await async_disable_legacy(hass)
    if result.get("ok"):
        data = await async_reload_data(hass)
        data["pending_restart"] = True
        await async_save_data(hass, data)
    hass.data[DOMAIN]["migration"] = await async_detect_sync_status(hass)
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "gui_recorder/enable_gui"})
async def ws_enable_gui(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    result = await async_ensure_gui_enabled(hass)
    if result.get("ok"):
        await async_write_yaml(hass)
        data = await async_reload_data(hass)
        data["pending_restart"] = True
        await async_save_data(hass, data)
    hass.data[DOMAIN]["migration"] = await async_detect_sync_status(hass)
    connection.send_result(msg["id"], result)


async def async_setup_websocket_api(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_tree)
    websocket_api.async_register_command(hass, ws_set_entity)
    websocket_api.async_register_command(hass, ws_set_device)
    websocket_api.async_register_command(hass, ws_remove_exclusion)
    websocket_api.async_register_command(hass, ws_remove_unmatched_exclusions)
    websocket_api.async_register_command(hass, ws_set_global_options)
    websocket_api.async_register_command(hass, ws_set_auto_update_data)
    websocket_api.async_register_command(hass, ws_set_repack_after_manual_purge)
    websocket_api.async_register_command(hass, ws_regenerate_yaml)
    websocket_api.async_register_command(hass, ws_analyze_db)
    websocket_api.async_register_command(hass, ws_purge_all)
    websocket_api.async_register_command(hass, ws_purge_excluded_entities)
    websocket_api.async_register_command(hass, ws_purge_entity)
    websocket_api.async_register_command(hass, ws_purge_device)
    websocket_api.async_register_command(hass, ws_restart_homeassistant)
    websocket_api.async_register_command(hass, ws_get_migration_status)
    websocket_api.async_register_command(hass, ws_import_legacy)
    websocket_api.async_register_command(hass, ws_disable_legacy)
    websocket_api.async_register_command(hass, ws_enable_gui)
