# Dependencies and capabilities

| Capability | Required | Implementation |
|---|---|---|
| Claude host | Yes | Claude Desktop for macOS; project folder opened directly through the app |
| Terminal fallback | No | Separately installed and authenticated `claude` command |
| Matter register | Yes | Python 3.11+, SQLite standard library |
| Tracker migration/export | Optional | Standard library; source CSV/JSON/SQLite |
| XLSX tracker projection | Optional | `openpyxl`; absence never blocks core setup |
| Matter orientation | Yes | Local filesystem and configured workspace |
| Guarded output saves | Yes | Local filesystem and SHA-256 preview token |
| DOCX letters | Optional | `python-docx` |
| DOCX visual QA | Recommended | LibreOffice and Poppler `pdftoppm` |
| Contract redlines | Optional | Vendored engine plus `python-docx`, `lxml`, `fpdf2` |
| PDF text extraction | Optional | Poppler `pdftotext` |
| OCR copy | Optional | OCRmyPDF and its platform dependencies |
| Gmail context | Optional | Gmail REST token in an explicitly named environment variable; read-only adapter |
| Calendar reads/writes | Optional | Google Calendar REST token, dedicated calendar ID, explicit mutation approval |
| Memory/decision search | Optional | SQLite FTS5 in the Python runtime |
| Voice lint | Optional | Python standard library; optional JSON rules |
| Practice manager | Optional | No live adapter bundled |
| Adversarial review | Yes | Claude subagents/read-only tools; no external AI |
| Ontario legal profile | Optional | Static boundary/reference guidance only; live primary-law verification remains required |

The plugin never treats an unavailable optional capability as successful. It
reports the missing adapter and continues only with independent work.

Use `requirements-lock.txt` for the tested Python build and runtime dependency
set. It includes `setuptools` and `wheel` so the package can be built locally
without an isolated dependency download. The recommended wizard runs directly
from the extracted package and does not require an editable install. Install
`requirements-test.txt` as well when running the bundled upstream redline test
suite. Neither file installs or pins operating-system commands; record and
manage those versions separately for each host.

The generated launcher records the exact Python used by the approved setup plan
in `LAWYEREDOS_PYTHON`; every bundled skill uses that interpreter. This can be a
stable host Python when the selected modules need no missing third-party
packages, or a retained virtual-environment Python when they do. Preview and
apply must use the same interpreter. Keep whichever runtime was recorded at its
setup path.
