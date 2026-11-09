# Shikai — The Fold

An original geometric identity for the local inference application. Two interlocking
folds suggest an S around a small core. The folds represent input and generated
output; the enclosed core represents computation kept on the local machine. This
is a design interpretation, not a claim about the word's etymology or trademark registration.

| Asset | Use |
|---|---|
| `shikai-mark.svg` | Primary teal/copper vector mark, transparent background |
| `shikai-mark-mono.svg` | Single-color ink mark for print and one-color applications |
| `shikai-mark-reversed.svg` | Light teal/apricot mark for dark backgrounds |
| `shikai-lockup.svg` | Horizontal symbol plus outlined SHIKAI lettering |
| `shikai-mark*.png` | Transparent 2048 px exports; `*-512.png` are smaller exports |
| `shikai-ascii.txt` | Seven-line ASCII interpretation for terminals |
| `shikai-mark.json` | Geometry, colors and terminal source |
| `brand-preview.png` | Presentation of the identity and its small-size applications |

The C++ header is generated into `include/local_llm/brand.hpp`; the application has
no runtime asset-file dependency. Wide interactive terminals display the ASCII
mark; narrow terminals and redirected output use a compact header. `NO_COLOR`
disables ANSI colors. The report draws the same vector geometry directly.

Regenerate the mark SVGs, ASCII and C++ header with the standard library:

```bash
python3 scripts/generate_brand.py
```

The prepared export environment includes Pillow for transparent PNG exports:

```bash
.venv/bin/python scripts/generate_brand.py --png
```

The horizontal lettering is outlined from Noto Sans Mono; it does not require an
installed font when displayed. The symbol is original project artwork. Keep at
least 12 design units clear around the 128-unit mark; do not stretch, rotate or add
a box, glow or gradient. Use the reversed version on dark surfaces. Below 24 px,
prefer the terminal/text name where the central aperture becomes too small.
