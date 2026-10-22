# Input checks

Put the PDF checks you want to scan in this folder, then run:

```bash
python -m check_reader
```

Results are written to `out/checks.csv` and `out/checks.json`.

Real check PDFs are ignored by git (all files in this folder except this
README and `.gitkeep`). Never commit real checks. Use the files in `examples/`
if you just want to try the tool:

```bash
python -m check_reader --input examples
```
