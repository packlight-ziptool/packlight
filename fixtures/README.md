# Fixture Zoo

The fixture zoo is generated at runtime by the unit tests and the local loop instead of being committed as a folder full of junk files.

Current generated cases include:

- macOS metadata: `.DS_Store`, `__MACOSX`, AppleDouble-style sidecars
- development clutter: `.git`, `__pycache__`, bytecode, temp files
- old artifacts: existing `.zip` files, logs, backups
- professional handoff risks: `.env`, private-key-like names, symlinks
- path shape checks: spaces, unicode filenames, nested folders, one-root enforcement
- audit-file conflicts: existing `MANIFEST.txt` and `SHA256SUMS` when audit files are requested

Run:

```bash
python3 -m unittest discover -s tests -v
./scripts/release-loop packlight
```
