# Include mode (beta) — testing notes

Branch: `include-mode` · Version: `0.9.0-beta2` (includes everything up to 0.8.39)

This branch adds a **Recording mode** selector to the panel. It is not released; it is
here so people can try it and report back before it goes into a normal version.

**Take a backup of your Home Assistant configuration before testing.**

## Installing it

1. **Back up your Home Assistant configuration first.** This is a branch, not a release.
2. Download https://github.com/ideaalab/gui-recorder/archive/refs/heads/include-mode.zip
3. Unzip it somewhere outside your Home Assistant config. You get a folder called
   `gui-recorder-include-mode`.
4. Inside it, go to `custom_components/gui_recorder/`. **That folder, and only that one,**
   replaces the existing `/config/custom_components/gui_recorder/`:

   ```
   gui-recorder-include-mode/custom_components/gui_recorder/   ->   /config/custom_components/gui_recorder/
   ```

   Do not copy the top-level `gui-recorder-include-mode` folder, and do not touch anything
   else inside `/config/custom_components/` — your other integrations live there.
5. Restart Home Assistant. The panel's version pill should read `0.9.0-beta2`.

To go back, redownload GUI Recorder from HACS and restart.

## What it changes

Until now the entity toggles could only write one list: `exclude.entities`, the list of
what is *not* recorded. That breaks in two situations people reported:

- an entity excluded by a manual `exclude.entity_globs` pattern cannot be switched back
  on, because it was never on the exclude list ([#18](https://github.com/ideaalab/gui-recorder/issues/18));
- with an `include:` block present the recorder works as an allowlist, so switching an
  entity on does nothing at all ([#13](https://github.com/ideaalab/gui-recorder/issues/13),
  [#15](https://github.com/ideaalab/gui-recorder/issues/15)).

The panel can now manage either list, and you choose which one:

| | Exclude list (default) | Include list (allowlist) |
| --- | --- | --- |
| The list holds | what is **not** recorded | what **is** recorded |
| Switching an entity off | adds it to `exclude.entities` | removes it from `include.entities` |
| Switching an entity on | removes it from `exclude.entities` | adds it to `include.entities` |
| A new entity appears | it is recorded | it is **not** recorded |

`include.entities` has the highest precedence in the recorder's filter, so in include mode
an entity you switch on is recorded even when one of your own exclude globs matches it.

## Nothing is destroyed when you switch

Each list has its own file in the config folder, and **both are rewritten on every
save, whichever mode is active**:

```
gui_recorder.yaml                      general settings + the filter blocks
gui_recorder_excluded_entities.yaml    the exclude list
gui_recorder_included_entities.yaml    the include list
```

`gui_recorder.yaml` pulls in whichever one the current mode uses:

```yaml
exclude:
  entities: !include gui_recorder_excluded_entities.yaml
```

Switching mode changes that one line. The other file stays on disk with its contents
intact, so you can open the folder and see for yourself that nothing was deleted.
Filters typed in the Manual exclusions field stay in `gui_recorder.yaml` in both modes.

The first time you switch to include mode, the list is seeded with everything you are
recording right now, so the switch does not silently stop recording. Entities that are
unavailable at that moment cannot be seeded and have to be switched on by hand.

Existing installations start in exclude mode and behave exactly as before. You have to
choose include mode explicitly.

## What is worth testing

1. Exclude mode still behaves as it did (toggles, Select all / Deselect all, purges).
2. Switching to include mode seeds the list and, after a restart, recording continues as before.
3. In include mode, switching an entity on that a manual `exclude.entity_globs` matches
   makes it record again after a restart. This is the case from #18.
4. Switching back to exclude mode restores the previous exclude list intact.
5. "Purge non-recorded entities" in include mode targets everything outside the include list.
6. The generated files look right in both modes: in include mode `gui_recorder.yaml`
   must reference `gui_recorder_included_entities.yaml` and contain no
   `exclude.entities`, and **both** entity files must still be there with their content.
7. Deleting one of the two entity files by hand breaks the recorder config until the
   integration rewrites it (it does so on every start and on every save). Worth knowing;
   don't delete them.

Report anything odd on the issue tracker or the community thread, mentioning that you are
running the `include-mode` branch.
