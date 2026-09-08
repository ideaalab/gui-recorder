DOMAIN = "gui_recorder"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.data"
MODE_EXCLUDE = "exclude_entities"
MODE_INCLUDE = "include_entities"

# The two entity lists live in their own files next to the generated yaml, so both
# stay visible on disk and switching mode only changes which one is !include'd.
EXCLUDED_LIST_FILENAME = "gui_recorder_excluded_entities.yaml"
INCLUDED_LIST_FILENAME = "gui_recorder_included_entities.yaml"

DEFAULT_STORAGE = {
    "excluded_entities": [],
    "included_entities": [],
    "manual_exclusions_yaml": "",
    "db_url": None,
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

INTEGRATION_VERSION = "0.9.0-beta1"
