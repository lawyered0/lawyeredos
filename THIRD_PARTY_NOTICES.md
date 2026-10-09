# Third-Party Notices

LawyeredOS's original material is licensed under `GPL-3.0-or-later`; see
`LICENSE` and `LICENSE-DECISION.md`. The components below remain under their
own licenses. Nothing in the LawyeredOS license notice replaces those terms or
attributes their work to the LawyeredOS copyright holder.

## legal-redline-tools 0.2.0 derivative

Copyright (c) 2026 Chris Sheehan.

Licensed under the MIT License. The complete license is retained at
`vendor/legal-redline-tools/LICENSE`. The vendored tree is derived from tag
`v0.2.0`, commit `eef61a0cb6afe2867fde70335c179d4a6ad298c8`, and contains
local modifications and added tests documented in
`vendor/legal-redline-tools/VENDOR-MODIFICATIONS.md`. Declared runtime
dependencies are `python-docx`, `lxml`, and `fpdf2`, each subject to its own
license.

## Python dependency inventory

The private clean-room test resolved the exact versions below. License labels
are copied from installed wheel metadata for release review; they are not a
legal conclusion and the dependency code is installed separately rather than
vendored in this archive.

| Package | Version | Metadata-reported license |
|---|---:|---|
| setuptools | 80.9.0 | MIT |
| wheel | 0.45.1 | MIT classifier |
| packaging | 25.0 | Apache and BSD classifiers |
| defusedxml | 0.7.1 | PSFL |
| et-xmlfile | 2.0.0 | MIT |
| fonttools | 4.60.2 | MIT |
| fpdf2 | 2.8.7 | LGPL-3.0-only |
| lxml | 6.0.4 | BSD-3-Clause |
| openpyxl | 3.1.5 | MIT |
| pillow | 12.0.0 | MIT-CMU |
| python-docx | 1.2.0 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |

Test-only dependencies are pytest 9.0.2 (MIT), iniconfig 2.3.0 (MIT),
pluggy 1.6.0 (MIT), and Pygments 2.19.2 (BSD-2-Clause).

The archive does not redistribute these installed packages. Rebuild and
re-review this inventory whenever the lock changes; downstream installations
remain subject to each package's upstream terms.
