# Include mode (beta) — testing notes

Branch: `include-mode` · Version: `0.9.0-beta1`

This branch adds a **Recording mode** selector to the panel. It is not released; it is
here so people can try it and report back before it goes into a normal version.

**Take a backup of your Home Assistant configuration before testing.**

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

Both lists are stored side by side in `.storage/gui_recorder.data`
(`excluded_entities` and `included_entities`). Only the active one is written to
`gui_recorder.yaml`; the other stays untouched and comes back if you switch again.

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
6. The generated `gui_recorder.yaml` looks right in both modes — in include mode it must
   contain no `exclude.entities` block.

Report anything odd on the issue tracker or the community thread, mentioning that you are
running the `include-mode` branch.
