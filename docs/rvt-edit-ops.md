# RVT editing through the gate: writer ops (c5x-rvtgap, 2026-11)

Two save routes exist for an .rvt/.rfa/.rte (both through `savegate.save`, the gate stays on, the original is backed up first):

1. **Field edit** (`wledit.Editor.modify/set_strings`, same-size and string edits): manifest `{'modified': ['stream:Partitions/N', 'el:ID'], 'derived_ok': True?}`. The gate compares the decoded element view and
   the bytes: only the declared element(s) may change; `derived_ok` additionally allows dependents to differ in their DERIVED view only (raw records identical, byte-exact window rule passes).
2. **Writer ops** (`savegate.rvt_writer_ops.run(src_path, ops, dst_path)` returns the new element ids): the write lab's deterministic writer (`rvtgen.Gen`, Revit-validated in the lab) makes the file; manifest
   `{'writer_ops': ops, 'added': ['el:NEW', ...], 'deleted': ['el:OLD', ...]}`. The gate RECOMPUTES the writer result from the source and demands **byte equality**; declared added/deleted ids must equal what the
   ops add/delete; deleted ids must have no referrer (reader record cache scan, ~13 s on a 28 MB project). Damage after the writer, or any output that is not the writer's, is refused.

## Ops (all in `rvt_writer_ops.py`)
| op | fields | what moves together |
|---|---|---|
| `delete` | `id` | header entry, record, zone records, ElemTable row, counts (refused when referenced) |
| `add_textnote` | `template` (an existing rich-text-only TextNote id), `x`, `y`, `text` | new id (`Gen.nextid`), record clone, header, zone item, ElemTable row; leader points shift with the note |
| `move_element` / `move_instance` | `id`, `dx`, `dy`, `dz` (feet) | every Trf.m_or / Plane.m_origin / GLine.m_origin triple, m_instOrigin if set, header Outline.m_minmax if present, zone (x,y) pair |
| `rotate_instance` | `id`, `deg` (about Z, own origin) | Trf.m_3x3, FamilyInstance.m_RefDir, header bbox of the rotated corners |
| `resize_wall` | `id`, `height` and/or `length_delta` (axis-aligned straight walls) | parameter -1001105, face Envelope.m_corners, GCurve.m_endParams, header bbox |
| `move_textnote` | `id`, `dx`, `dy` (view feet) | TextElement.m_orig and Leader.m_end/m_elbow/m_anchor |

## Status (2026-11-07)
Gate-level only, on the Autodesk Snowdon Towers Structural 2024 sample (and 2026 in progress). NONE of these outputs has a Revit-VM verdict yet (remote-host has no VM); the dashboard counts only VM-verified results.
Files for the VM: remote-host `~/c5x/oracle4/`, requests in `~/demo-state/NEEDS-FROM-ORACLE.md`.

## Known limits
- Only delete/add/move/rotate/resize of the listed classes; walls with joins, hosted openings and other dependents are NOT updated (the gate does not check them for moves/resizes).
- The writer lab supports 2024 and 2026; other years refuse in the gate (writable years).
- `add_textnote` needs a template note with an empty fragment array (text only in the RTF stream); other templates raise.
- Gate cost: 2-6 min per save on a 28 MB project (the element-view route builds the view twice); the writer-op route is 2-3 min.
- A full temp volume makes the gate refuse (safe); `TMPDIR` should point to a volume with 2-3 x the model size free.
