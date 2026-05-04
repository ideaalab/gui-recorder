# GUI Recorder

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/ideaalab/gui-recorder)](https://github.com/ideaalab/gui-recorder/releases)

A Home Assistant custom component that adds a sidebar panel to manage your `recorder` configuration (which entities get recorded) and database maintenance (purge, repack, stats) — without editing `configuration.yaml`.

> **SQLite only.** MariaDB and PostgreSQL are explicitly rejected during setup with a clear error message.

## Features

- **Sidebar panel** integrated directly into the Home Assistant navigation bar.
- **Per-device and per-entity control**: enable or disable recording with a toggle — no YAML editing required.
- **Database statistics**: total / current / obsolete records, matched exclusions, disk size (sums `.db` + `.db-wal` + `.db-shm`), SQLite file path.
- **Maintenance actions**:
  - Purge the database (uses global retention setting).
  - Purge excluded entities (full history, ignores retention).
  - Auto-update stats after each purge (optional).
  - Repack after manual purge (optional).
  - Restart Home Assistant.
- **Orphan exclusion detection**: shows entries in `gui_recorder.yaml` that no longer match any entity, with a one-click bulk-remove.
- **Guided migration**: imports your existing `recorder` configuration from `configuration.yaml` in 3 steps (import → disable old block → activate `!include`).
- **Cache busting**: the panel JS is served with `?v=VERSION` to prevent stale versions after updates.

## Installation

### Via HACS (recommended)

1. Go to HACS → Integrations → `⋮` menu → **Custom repositories**.
2. Add `https://github.com/ideaalab/gui-recorder` with category **Integration**.
3. Search for **GUI Recorder**, install it, and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and choose **GUI Recorder**.

### Manual

1. Copy `custom_components/gui_recorder/` into `<config>/custom_components/gui_recorder/`.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → GUI Recorder**.

## Usage

After installing and configuring the integration, a **GUI Recorder** panel appears in the sidebar. From there you can:

- Filter entities by `entity_id`, friendly name, domain, or platform.
- Toggle recording for entire devices or individual entities.
- Run database analysis and purges (global, per-device, or per-entity).
- Import your existing `recorder` config from `configuration.yaml`.

The generated configuration is written to `gui_recorder.yaml`, included from `configuration.yaml` via:

```yaml
recorder: !include gui_recorder.yaml
```

The integration writes that file automatically. If you already had a `recorder:` block in `configuration.yaml`, the panel's migration flow guides you through replacing it.

## Requirements

- Home Assistant **2024.1.0** or later.
- Recorder database on **SQLite** (MariaDB and PostgreSQL are not supported).

## Support

- Issues: https://github.com/ideaalab/gui-recorder/issues

## License

[MIT](LICENSE)
