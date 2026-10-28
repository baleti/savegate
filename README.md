# savegate

Stdlib-only library that makes Save / Save As / overwrite of .dwg and .rvt files safe.

- atomic write: temp file in the target directory, fsync file and directory, `os.replace` (Windows retry/backoff, long paths)
- versioned backup of the original before any overwrite (`.savegate/`), `restore`
- concurrent-modification guard (size + mtime + hash at load) and a lock file
- crash-recovery edit journal
- verify hook: the output is re-parsed and diffed against the source; any difference outside the declared edit aborts the save and leaves the original untouched (DWG AC1015-AC1032, RVT streams / elements)
- oracle gate: overwrite stays closed per format+version until the matrix evidence file exists

```
import savegate as sg
with sg.open_doc(path) as doc:
    sg.save_as(doc, new_bytes, newpath, manifest)      # never touches the source
    sg.save(doc, new_bytes, manifest)                  # overwrite: needs Config(allow_overwrite=True) and an open gate
python -m savegate info FILE | backups FILE | restore FILE [N] | recover | gate open|close FMT VERSION [--evidence F]
```

Tests: `python3 -m pytest -q tests` (DWG/RVT tests need ~/dwg-write, otherwise they skip). Design, command contract and test matrix:
`demo-state/savegate-design.md`, `savegate-contract.md`, `savegate-matrix-plan.md`. Rust port spec: `docs/rust-port.md`.
Synthetic data only in tests; never commit client or Autodesk files.
