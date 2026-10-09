from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .common import emit


HEADERS = [
    ("file_number", "File #"), ("client", "Client"),
    ("description", "Matter Description"), ("status", "Status"),
    ("next_action", "Next Action"), ("next_action_date", "Next Action Date"),
    ("limitation_date", "Limitation Date"), ("court_deadlines", "Court Deadlines"),
    ("opposing_party", "Opposing Party"), ("other_parties", "Other Parties"),
    ("primary_email", "Primary Email"), ("matter_folder", "Matter Folder"),
    ("updated_at", "Updated At"),
]


def _rows(database: Path, status: str) -> list[dict[str, Any]]:
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(
            "SELECT * FROM matters WHERE status=? ORDER BY file_number", (status,)
        )]


def project(database: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("XLSX output already exists")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.worksheet.table import Table, TableStyleInfo
    except ImportError as exc:
        raise ValueError("openpyxl is required for XLSX projection") from exc
    workbook = Workbook()
    workbook.remove(workbook.active)
    counts: dict[str, int] = {}
    for status, title in (("open", "Open Matters"), ("closed", "Closed Matters")):
        sheet = workbook.create_sheet(title)
        sheet.sheet_view.showGridLines = False
        sheet.freeze_panes = "A2"
        sheet.append([label for _, label in HEADERS])
        rows = _rows(database, status)
        counts[status] = len(rows)
        for row in rows:
            values = []
            for key, _label in HEADERS:
                value = row.get(key, "")
                if key == "court_deadlines":
                    parsed = json.loads(value or "[]")
                    value = "\n".join(
                        " | ".join(str(item.get(name, "")) for name in ("date", "description") if item.get(name))
                        if isinstance(item, dict) else str(item) for item in parsed
                    )
                values.append(value)
            sheet.append(values)
        header = sheet[1]
        for cell in header:
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Arial", size=10, color="222222")
                cell.alignment = Alignment(vertical="top", wrap_text=False)
        widths = [14, 24, 36, 11, 38, 16, 16, 42, 24, 28, 28, 32, 22]
        for index, width in enumerate(widths, 1):
            sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
        if rows:
            reference = f"A1:{sheet.cell(len(rows) + 1, len(HEADERS)).coordinate}"
            table = Table(displayName=f"{status.title()}MattersTable", ref=reference)
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2", showFirstColumn=False,
                showLastColumn=False, showRowStripes=True, showColumnStripes=False,
            )
            sheet.add_table(table)
        sheet.auto_filter.ref = f"A1:{sheet.cell(max(1, len(rows) + 1), len(HEADERS)).coordinate}"
    workbook.properties.creator = ""
    workbook.properties.lastModifiedBy = ""
    workbook.properties.title = "Matter Tracker Projection"
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    return {"ok": True, "output": str(output), "read_only_source": True, "counts": counts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a disposable XLSX projection of the SQLite tracker")
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        emit(project(Path(args.database), Path(args.output)))
        return 0
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
