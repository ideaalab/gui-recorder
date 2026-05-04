from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_STORAGE, DOMAIN, STORAGE_KEY, STORAGE_VERSION


def _normalize_excluded_entities(values) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        entity_id = str(value).strip()
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        normalized.append(entity_id)
    return sorted(normalized)


def get_store(hass: HomeAssistant) -> Store:
    return Store(hass, STORAGE_VERSION, STORAGE_KEY)


async def async_load_data(hass: HomeAssistant) -> dict:
    store = get_store(hass)
    data = await store.async_load()
    if data is None:
        data = DEFAULT_STORAGE.copy()
        await store.async_save(data)
    else:
        merged = DEFAULT_STORAGE.copy()
        merged.update(data)
        merged["excluded_entities"] = _normalize_excluded_entities(merged.get("excluded_entities"))
        data = merged
    hass.data.setdefault(DOMAIN, {})["store"] = store
    hass.data[DOMAIN]["data"] = data
    return data


async def async_save_data(hass: HomeAssistant, data: dict) -> None:
    store: Store = hass.data[DOMAIN]["store"]
    normalized = DEFAULT_STORAGE.copy()
    normalized.update(data)
    normalized["excluded_entities"] = _normalize_excluded_entities(normalized.get("excluded_entities"))
    await store.async_save(normalized)
    hass.data[DOMAIN]["data"] = normalized


async def async_reload_data(hass: HomeAssistant) -> dict:
    store = get_store(hass)
    data = await store.async_load()
    if data is None:
        data = DEFAULT_STORAGE.copy()
        await store.async_save(data)
    else:
        merged = DEFAULT_STORAGE.copy()
        merged.update(data)
        merged["excluded_entities"] = _normalize_excluded_entities(merged.get("excluded_entities"))
        data = merged
    hass.data.setdefault(DOMAIN, {})["store"] = store
    hass.data[DOMAIN]["data"] = data
    return data
