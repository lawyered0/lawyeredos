"""Tests for the apply command's refusal paths.

2026-10-07: the CLI exited 0 after a NOT FOUND and still built the summary,
markdown and PDF from the JSON, so the schedule listed a change the tracked
DOCX did not contain. Any unapplied change now exits 2 and leaves no output.
"""

import json
import sys

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from legal_redline.cli import main


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["legal-redline", "apply", *argv])
    with pytest.raises(SystemExit) as exc:
        main()
    return exc.value.code


def _source(tmp_dir, *paragraphs, cell=None):
    path = tmp_dir / "source.docx"
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    if cell is not None:
        doc.add_table(rows=1, cols=1).cell(0, 0).text = cell
    doc.save(str(path))
    return path


def _outputs(tmp_dir):
    return {
        "docx": tmp_dir / "redlined.docx",
        "summary": tmp_dir / "summary.pdf",
        "markdown": tmp_dir / "redlines.md",
    }


def _args(src, out, redlines_path):
    return [str(src), str(out["docx"]), "--author", "Test Reviewer",
            "--from-json", str(redlines_path),
            "--summary-pdf", str(out["summary"]), "--markdown", str(out["markdown"])]


def test_unapplied_change_exits_2_and_writes_nothing(tmp_dir, monkeypatch, capsys):
    """A table-cell span is unique but out of the engine's reach."""
    src = _source(tmp_dir, "The fee is set out below.", cell="$500 per hour")
    redlines = tmp_dir / "redlines.json"
    redlines.write_text(json.dumps([
        {"type": "replace", "old": "$500 per hour", "new": "$450 per hour"},
        {"type": "replace", "old": "set out below", "new": "set out in Schedule A"},
    ]))
    out = _outputs(tmp_dir)
    assert _run(monkeypatch, *_args(src, out, redlines)) == 2
    printed = capsys.readouterr().out
    assert "FAILED: 1 of 2 change(s) not applied" in printed
    assert "[NOT FOUND]" in printed and "body paragraphs only" in printed
    assert not any(path.exists() for path in out.values())


def test_preexisting_revision_is_refused_before_output(tmp_dir, monkeypatch, capsys):
    src = tmp_dir / "del.docx"
    doc = Document()
    para = doc.add_paragraph("The Supplier shall ")
    rev = OxmlElement("w:del")
    rev.set(qn("w:id"), "1")
    rev.set(qn("w:author"), "Opposing Counsel")
    rev.set(qn("w:date"), "2026-01-01T00:00:00Z")
    run = OxmlElement("w:r")
    text = OxmlElement("w:delText")
    text.text = "not "
    run.append(text)
    rev.append(run)
    para._p.append(rev)
    para.add_run("be liable for indirect damages.")
    doc.save(str(src))
    redlines = tmp_dir / "redlines.json"
    redlines.write_text(json.dumps([
        {"type": "replace", "old": "shall be liable", "new": "shall be liable only"},
    ]))
    out = _outputs(tmp_dir)
    assert _run(monkeypatch, *_args(src, out, redlines)) == 2
    printed = capsys.readouterr().out
    assert "pre-existing revision/comment markup" in printed
    assert "body paragraphs only" not in printed
    assert not any(path.exists() for path in out.values())


def test_repeated_span_is_refused_before_any_output(tmp_dir, monkeypatch, capsys):
    src = _source(tmp_dir, "Invoices are payable within 30 days.",
                  "A party may cure a breach within 30 days.")
    redlines = tmp_dir / "redlines.json"
    redlines.write_text(json.dumps([
        {"type": "replace", "old": "30 days", "new": "60 days", "section": "9.2"},
    ]))
    out = _outputs(tmp_dir)
    assert _run(monkeypatch, *_args(src, out, redlines)) == 2
    printed = capsys.readouterr().out
    assert "[REFUSED]" in printed and "occurs 2 times" in printed
    assert "--- .docx with tracked changes ---" not in printed
    assert not any(path.exists() for path in out.values())


def test_span_repeated_inside_a_content_control_is_refused(tmp_dir, monkeypatch, capsys):
    """2026-10-07: the copy inside the content control was not counted, so the
    run exited 0 and changed clause 1 under a schedule labelled 9.2."""
    src = tmp_dir / "sdt.docx"
    doc = Document()
    doc.add_paragraph("1. Payment. Invoices are payable within 30 days of receipt.")
    para = doc.add_paragraph("9.2 Cure. A party may cure a breach within ")
    sdt = OxmlElement("w:sdt")
    content = OxmlElement("w:sdtContent")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "30 days"
    run.append(text)
    content.append(run)
    sdt.append(content)
    para._p.append(sdt)
    para.add_run(" of notice.")
    doc.save(str(src))
    redlines = tmp_dir / "redlines.json"
    redlines.write_text(json.dumps([
        {"type": "replace", "old": "30 days", "new": "60 days", "section": "9.2"},
    ]))
    out = _outputs(tmp_dir)
    assert _run(monkeypatch, *_args(src, out, redlines)) == 2
    printed = capsys.readouterr().out
    assert "[REFUSED]" in printed and "occurs 2 times" in printed
    assert not any(path.exists() for path in out.values())


def test_output_must_not_be_the_input(tmp_dir, monkeypatch):
    """A failed run removes its partial output, which must never be the source."""
    src = _source(tmp_dir, "Invoices are payable within 30 days.")
    before = src.read_bytes()
    code = _run(monkeypatch, str(src), str(src), "--author", "Test Reviewer",
                "--replace", "30 days", "60 days")
    assert code == 1
    assert src.read_bytes() == before


def test_existing_or_symlink_output_is_refused_before_any_output(tmp_dir, monkeypatch, capsys):
    src = _source(tmp_dir, "Invoices are payable within 30 days.")
    redlines = tmp_dir / "redlines.json"
    redlines.write_text(json.dumps([
        {"type": "replace", "old": "30 days", "new": "60 days"},
    ]))
    out = _outputs(tmp_dir)
    out["summary"].write_bytes(b"existing summary")
    assert _run(monkeypatch, *_args(src, out, redlines)) == 2
    assert out["summary"].read_bytes() == b"existing summary"
    assert not out["docx"].exists()
    assert not out["markdown"].exists()
    assert "output already exists" in capsys.readouterr().out

    out["summary"].unlink()
    victim = tmp_dir / "victim.docx"
    victim.write_bytes(b"source-like bytes")
    out["docx"].symlink_to(victim)
    assert _run(monkeypatch, *_args(src, out, redlines)) == 2
    assert victim.read_bytes() == b"source-like bytes"
    assert out["docx"].is_symlink()
    assert not out["summary"].exists()
    assert not out["markdown"].exists()


def test_full_apply_writes_every_requested_output(tmp_dir, monkeypatch, capsys):
    src = _source(tmp_dir, "Invoices are payable within 30 days.",
                  "A party may cure a breach within 30 days.")
    redlines = tmp_dir / "redlines.json"
    redlines.write_text(json.dumps([
        {"type": "replace", "old": "breach within 30 days",
         "new": "breach within 60 days", "section": "9.2"},
    ]))
    out = _outputs(tmp_dir)
    monkeypatch.setattr(sys, "argv", ["legal-redline", "apply", *_args(src, out, redlines)])
    main()
    assert "Applied: 1/1 redlines" in capsys.readouterr().out
    assert all(path.exists() for path in out.values())
