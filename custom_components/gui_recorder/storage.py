from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_STORAGE, DOMAIN, STORAGE_KEY, STORAGE_VERSION

_ENTITY_LIST_KEYS = ("excluded_entities", "rescued_entities")


def _normalize_entity_list(values) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        entity_id = str(value).strip()
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        normalized.append(entity_id)
    return sorted(normalized)


def _normalize_entity_lists(data: dict) -> dict:
    for key in _ENTITY_LIST_KEYS:
        data[key] = _normalize_entity_list(data.get(key))
    return data


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
        data = _normalize_entity_lists(merged)
    hass.data.setdefault(DOMAIN, {})["store"] = store
    hass.data[DOMAIN]["data"] = data
    return data


async def async_save_data(hass: HomeAssistant, data: dict) -> None:
    store: Store = hass.data[DOMAIN]["store"]
    normalized = DEFAULT_STORAGE.copy()
    normalized.update(data)
    _normalize_entity_lists(normalized)
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
        data = _normalize_entity_lists(merged)
    hass.data.setdefault(DOMAIN, {})["store"] = store
    hass.data[DOMAIN]["data"] = data
    return data
