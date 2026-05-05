DOMAIN = "gui_recorder"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.data"
DEFAULT_STORAGE = {
    "excluded_entities": [],
    "generated_path": "gui_recorder.yaml",
    "mode": "exclude_entities",
    "pending_restart": False,
    "purge_keep_days": 10,
    "auto_purge": True,
    "auto_repack": True,
    "commit_interval": 5,
    "auto_update_data": True,
    "repack_after_manual_purge": False,
    "repack_in_progress": False,
    "legacy_imported_at": None,
    "stats": {
        "entity_counts": {},
        "generated_at": None,
        "db_path": "home-assistant_v2.db",
        "db_size_bytes": 0,
        "error": None,
    },
}
PANEL_URL_PATH = "gui-recorder"
PANEL_TITLE = "GUI Recorder"
PANEL_ICON = "mdi:database-cog"
PANEL_MODULE_URL = "/api/gui_recorder/static/gui-recorder-panel.js"

INTEGRATION_VERSION = "0.8.25"
