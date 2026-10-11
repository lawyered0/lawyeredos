"""CLI entry point for legal-redline-tools."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from docx import Document

from legal_redline.apply import apply_redlines, existing_review_markup, placement_problems
from legal_redline.compare import compare_agreements, format_comparison_report
from legal_redline.diff import diff_documents
from legal_redline.markdown import generate_markdown
from legal_redline.memo import generate_memo_pdf
from legal_redline.remap import remap_redlines
from legal_redline.render import render_redline_pdf
from legal_redline.scan import scan_document
from legal_redline.summary import generate_summary_pdf


class OutputIsInputError(ValueError):
    pass


def main():
    parser = argparse.ArgumentParser(
        prog="legal-redline",
        description="Apply tracked changes to Word documents and generate redline PDFs.",
        epilog="https://github.com/evolsb/legal-redline-tools",
    )
    sub = parser.add_subparsers(dest="command")

    # ── apply (default / legacy behavior) ──
    apply_p = sub.add_parser("apply", help="Apply redlines to a .docx")
    _add_apply_args(apply_p)

    # ── diff ──
    diff_p = sub.add_parser("diff", help="Compare two .docx files and generate redlines")
    diff_p.add_argument("old_docx", help="Original .docx file")
    diff_p.add_argument("new_docx", help="Revised .docx file")
    diff_p.add_argument("-o", "--output", help="Output JSON file for redlines")
    diff_p.add_argument("--context-words", type=int, default=5,
                        help="Context words around changes (default: 5)")

    # ── scan ──
    scan_p = sub.add_parser("scan", help="Scan .docx for blank fields and placeholders")
    scan_p.add_argument("input", help="Input .docx file")
    scan_p.add_argument("-o", "--output", help="Output JSON file")

    # ── remap ──
    remap_p = sub.add_parser("remap", help="Remap redline sections between documents")
    remap_p.add_argument("old_docx", help="Original .docx (redlines were written for)")
    remap_p.add_argument("new_docx", help="New .docx (redlines should target)")
    remap_p.add_argument("--redlines", required=True, help="Redlines JSON file")
    remap_p.add_argument("-o", "--output", help="Output remapped JSON file")
    remap_p.add_argument("--threshold", type=float, default=0.6,
                         help="Fuzzy match threshold 0-1 (default: 0.6)")

    # ── compare ──
    compare_p = sub.add_parser("compare",
                               help="Compare redlines across multiple agreements")
    compare_p.add_argument("--agreements", nargs="+", required=True,
                           metavar="NAME=FILE",
                           help="Agreement redlines as name=file.json pairs")
    compare_p.add_argument("-o", "--output", help="Output markdown file")

    # For backwards compat: if no subcommand, treat args as 'apply'
    # Parse and dispatch
    args, remaining = parser.parse_known_args()

    if args.command is None:
        # Legacy mode: treat everything as apply args
        apply_p2 = argparse.ArgumentParser(prog="legal-redline")
        _add_apply_args(apply_p2)
        args = apply_p2.parse_args()
        args.command = "apply"

    if args.command == "apply":
        _cmd_apply(args)
    elif args.command == "diff":
        _cmd_diff(args)
    elif args.command == "scan":
        _cmd_scan(args)
    elif args.command == "remap":
        _cmd_remap(args)
    elif args.command == "compare":
        _cmd_compare(args)


def _add_apply_args(parser):
    """Add arguments for the apply command."""
    parser.add_argument("input", help="Input .docx file")
    parser.add_argument("output", nargs="?",
                        help="Output .docx file with tracked changes")
    parser.add_argument("--author", required=True,
                        help="Author name for tracked changes "
                             "(stamped on every w:ins/w:del revision)")

    # Redline specifications
    parser.add_argument("--replace", nargs=2, action="append",
                        metavar=("OLD", "NEW"),
                        help="Replace OLD with NEW as tracked change")
    parser.add_argument("--delete", action="append", metavar="TEXT",
                        help="Delete TEXT as tracked change")
    parser.add_argument("--insert-after", nargs=2, action="append",
                        metavar=("ANCHOR", "TEXT"),
                        help="Insert TEXT after ANCHOR as tracked change")
    parser.add_argument("--from-json", metavar="FILE",
                        help="Load redlines from JSON file")

    # Output options
    parser.add_argument("--pdf", metavar="FILE",
                        help="Generate full-document redline PDF")
    parser.add_argument("--summary-pdf", metavar="FILE",
                        help="Generate summary-only redline PDF (external)")
    parser.add_argument("--memo-pdf", metavar="FILE",
                        help="Generate internal analysis memo PDF")
    parser.add_argument("--markdown", metavar="FILE",
                        help="Generate markdown output")
    parser.add_argument("--no-docx", action="store_true",
                        help="Skip .docx output (PDF only)")
    parser.add_argument("--mode", choices=["external", "internal"],
                        default="external",
                        help="Output mode: external (clean) or internal (full analysis)")

    # PDF options
    parser.add_argument("--doc-title", metavar="TITLE",
                        help="Document title for PDF header")
    parser.add_argument("--doc-parties", metavar="PARTIES",
                        help="Parties for PDF header")
    parser.add_argument("--header", metavar="TEXT",
                        help="Header text on every page of full PDF")


def _cmd_apply(args):
    """Run the apply command."""
    if not args.no_docx and not args.output and not args.pdf \
       and not args.summary_pdf and not args.memo_pdf and not args.markdown:
        print("Error: Specify an output: positional output .docx, --pdf, "
              "--summary-pdf, --memo-pdf, --markdown, or --no-docx")
        sys.exit(1)

    # Build redlines list
    redlines = []

    if args.from_json:
        with open(args.from_json) as f:
            redlines = json.load(f)

    if args.replace:
        for old, new in args.replace:
            redlines.append({"type": "replace", "old": old, "new": new})

    if args.delete:
        for text in args.delete:
            redlines.append({"type": "delete", "text": text})

    if args.insert_after:
        for anchor, text in args.insert_after:
            redlines.append({"type": "insert_after", "anchor": anchor, "text": text})

    if not redlines:
        print("Error: No redlines specified. Use --replace, --delete, "
              "--insert-after, or --from-json.")
        sys.exit(1)

    outputs = {
        "docx": None if args.no_docx else args.output,
        "pdf": args.pdf,
        "summary": args.summary_pdf,
        "memo": args.memo_pdf,
        "markdown": args.markdown,
    }
    try:
        _validate_output_targets(args.input, outputs.values())
        review_markers = existing_review_markup(args.input)
    except OutputIsInputError as exc:
        print(f"Error: {exc}. Nothing was generated.")
        sys.exit(1)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}. Nothing was generated.")
        sys.exit(2)
    if review_markers:
        print("Error: input contains pre-existing revision/comment markup; resolve "
              "it before applying a new redline: " + ", ".join(review_markers))
        print("Nothing was generated.")
        sys.exit(2)

    staging = tempfile.TemporaryDirectory(prefix="legal-redline-")
    staged = {
        name: str(Path(staging.name) / f"{name}{Path(path).suffix or '.tmp'}")
        for name, path in outputs.items() if path
    }

    # 2026-10-07: a repeated span changed the first clause holding it while the
    # schedule named the intended section. Refuse before any output is written.
    problems = placement_problems(Document(args.input), redlines)
    if problems:
        for _, msg in problems:
            print(f"  [REFUSED] {msg}")
        print("Error: every old/text/anchor/after_section must occur exactly once "
              "in the input; nothing was generated.")
        sys.exit(2)

    print(f"Input:    {args.input}")
    print(f"Author:   {args.author}")
    print(f"Redlines: {len(redlines)}")
    print()

    # Generate tracked-changes .docx
    if not args.no_docx and args.output:
        # A failed run removes its partial output, so it must never be the source.
        if os.path.exists(args.output) and os.path.samefile(args.input, args.output):
            print("Error: the output .docx is the input file; write the redline to "
                  "a new path. Nothing was generated.")
            sys.exit(1)
        print("--- .docx with tracked changes ---")
        results = apply_redlines(args.input, staged["docx"], redlines, args.author)
        print()
        # 2026-10-07: a partial run exited 0 and the schedule, markdown and PDF
        # were still built from the JSON, listing changes the DOCX did not take.
        unapplied = [(status, desc) for status, desc in results if status != "OK"]
        if unapplied:
            os.remove(staged["docx"])
            print(f"FAILED: {len(unapplied)} of {len(redlines)} change(s) not applied:")
            for status, desc in unapplied:
                print(f"  [{status}] {desc}")
            if any(status == "NOT FOUND" for status, _ in unapplied):
                print("NOT FOUND: the engine reaches body paragraphs only, not table "
                      "cells, headers, footers, footnotes or text boxes.")
            print(f"Removed the partial {args.output}. No PDF, summary, memo or "
                  "markdown was generated.")
            sys.exit(2)

    # Generate full-document redline PDF
    if args.pdf:
        print("--- Full-document redline PDF ---")
        render_redline_pdf(
            args.input, redlines, staged["pdf"],
            header_text=args.header or args.doc_title,
            author=args.author,
        )
        print()

    # Generate summary PDF
    if args.summary_pdf:
        print("--- Summary redline PDF ---")
        generate_summary_pdf(
            redlines, staged["summary"],
            doc_title=args.doc_title,
            author=args.author,
            doc_parties=args.doc_parties,
            mode=args.mode,
        )
        print()

    # Generate internal memo PDF
    if args.memo_pdf:
        print("--- Internal memo PDF ---")
        generate_memo_pdf(
            redlines, staged["memo"],
            doc_title=args.doc_title,
            author=args.author,
            doc_parties=args.doc_parties,
        )
        print()

    # Generate markdown
    if args.markdown:
        print("--- Markdown output ---")
        md = generate_markdown(
            redlines,
            doc_title=args.doc_title,
            author=args.author,
            doc_parties=args.doc_parties,
            mode=args.mode,
        )
        with open(staged["markdown"], "w") as f:
            f.write(md)
        print(f"Markdown: {args.markdown}")

    try:
        _publish_all_new([
            (Path(staged[name]), Path(final_path))
            for name, final_path in outputs.items() if final_path
        ])
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}. Staged outputs were not allowed to overwrite the target.")
        sys.exit(2)
    finally:
        staging.cleanup()


def _reject_symlink_parents(path):
    if path.parent.is_symlink():
        raise ValueError(f"output parent must not be a symlink: {path.parent}")


def _validate_output_targets(input_path, output_paths):
    source = Path(input_path).expanduser().absolute()
    seen = set()
    for raw in output_paths:
        if not raw:
            continue
        path = Path(raw).expanduser().absolute()
        key = os.path.normcase(str(path))
        if key in seen:
            raise ValueError(f"output paths must be distinct: {path}")
        seen.add(key)
        if key == os.path.normcase(str(source)):
            raise OutputIsInputError("an output path is the input file")
        if path.exists() or path.is_symlink():
            raise ValueError(f"output already exists: {path}")
        if not path.parent.is_dir():
            raise ValueError(f"output parent does not exist: {path.parent}")
        _reject_symlink_parents(path)


def _unlink_reserved(output, descriptor):
    try:
        opened = os.fstat(descriptor)
        current = output.stat(follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino):
            output.unlink()
    except OSError:
        pass


def _publish_all_new(items):
    """Reserve every target exclusively before writing any staged bytes."""
    reservations = []
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        for staged, raw_output in items:
            output = raw_output.expanduser().absolute()
            _reject_symlink_parents(output)
            try:
                descriptor = os.open(output, flags, 0o600)
            except FileExistsError as exc:
                raise ValueError(f"output already exists: {output}") from exc
            reservations.append((staged, output, descriptor))
        for staged, _, descriptor in reservations:
            with staged.open("rb") as source:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    remaining = memoryview(chunk)
                    while remaining:
                        written = os.write(descriptor, remaining)
                        remaining = remaining[written:]
                os.fsync(descriptor)
    except BaseException:
        for _, output, descriptor in reservations:
            _unlink_reserved(output, descriptor)
        raise
    finally:
        for _, _, descriptor in reservations:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _cmd_diff(args):
    """Run the diff command."""
    print(f"Comparing: {args.old_docx} vs {args.new_docx}")
    redlines = diff_documents(args.old_docx, args.new_docx,
                              context_words=args.context_words)
    print(f"Found {len(redlines)} changes")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(redlines, f, indent=2)
        print(f"Output: {args.output}")
    else:
        print(json.dumps(redlines, indent=2))


def _cmd_scan(args):
    """Run the scan command."""
    print(f"Scanning: {args.input}")
    report = scan_document(args.input)

    placeholders = report.get("placeholders", [])
    references = report.get("references", {})
    missing = references.get("missing", [])

    print(f"Placeholders found: {len(placeholders)}")
    print(f"Missing references: {len(missing)}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Output: {args.output}")
    else:
        if placeholders:
            print("\nPlaceholders:")
            for p in placeholders:
                print(f"  [{p.get('type', '?')}] {p.get('text', '')[:60]} "
                      f"(para {p.get('paragraph', '?')})")
        if missing:
            print("\nMissing references:")
            for m in missing:
                print(f"  {m}")


def _cmd_remap(args):
    """Run the remap command."""
    with open(args.redlines) as f:
        redlines = json.load(f)

    print(f"Remapping {len(redlines)} redlines")
    print(f"  From: {args.old_docx}")
    print(f"  To:   {args.new_docx}")

    updated, report = remap_redlines(
        args.old_docx, args.new_docx, redlines,
        threshold=args.threshold,
    )

    # Print report summary
    statuses = {}
    for r in report:
        s = r.get("status", "?")
        statuses[s] = statuses.get(s, 0) + 1
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(updated, f, indent=2)
        print(f"Output: {args.output}")
    else:
        print(json.dumps(updated, indent=2))


def _cmd_compare(args):
    """Run the compare command."""
    agreement_redlines = {}
    for pair in args.agreements:
        if "=" not in pair:
            print(f"Error: Expected name=file.json, got: {pair}")
            sys.exit(1)
        name, filepath = pair.split("=", 1)
        with open(filepath) as f:
            agreement_redlines[name] = json.load(f)

    print(f"Comparing {len(agreement_redlines)} agreements: "
          f"{', '.join(agreement_redlines.keys())}")

    result = compare_agreements(agreement_redlines)
    report = format_comparison_report(result)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Output: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
