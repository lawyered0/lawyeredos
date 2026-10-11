"""Tests for tracked change application."""

import copy

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from legal_redline.apply import (
    _SETTINGS_AFTER_TRACK_REVISIONS,
    SpanCrossesHiddenContent,
    apply_redlines,
    apply_tracked_replacement,
    apply_tracked_deletion,
    apply_tracked_insertion,
    apply_tracked_add_section,
    enable_track_revisions,
    placement_problems,
    span_occurrences,
)


AUTHOR = "Test Reviewer"
DATE = "2025-01-01T00:00:00Z"
MC_ALTERNATE_CONTENT = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"


def test_apply_refuses_existing_and_symlink_outputs(tmp_dir):
    source = tmp_dir / "source.docx"
    doc = Document()
    doc.add_paragraph("Invoices are payable within 30 days.")
    doc.save(str(source))
    redlines = [{"type": "replace", "old": "30 days", "new": "60 days"}]

    existing = tmp_dir / "existing.docx"
    existing.write_bytes(b"do not replace")
    with pytest.raises(ValueError, match="output already exists"):
        apply_redlines(str(source), str(existing), redlines, author=AUTHOR)
    assert existing.read_bytes() == b"do not replace"

    victim = tmp_dir / "victim.docx"
    victim.write_bytes(b"victim")
    linked = tmp_dir / "linked.docx"
    linked.symlink_to(victim)
    with pytest.raises(ValueError, match="output already exists"):
        apply_redlines(str(source), str(linked), redlines, author=AUTHOR)
    assert victim.read_bytes() == b"victim"


def _para_xml_tags(para):
    """Get tag names of child elements in a paragraph."""
    return [child.tag.split("}")[-1] for child in para._element]


def _get_para_text(para):
    """Get full text including tracked changes."""
    texts = []
    for child in para._element:
        tag = child.tag.split("}")[-1]
        if tag == "r":
            t = child.find(qn("w:t"))
            if t is not None and t.text:
                texts.append(t.text)
        elif tag in ("ins", "del"):
            for r in child.findall(qn("w:r")):
                t = r.find(qn("w:t"))
                dt = r.find(qn("w:delText"))
                if t is not None and t.text:
                    texts.append(t.text)
                if dt is not None and dt.text:
                    texts.append(dt.text)
    return "".join(texts)


class TestTrackedReplacement:
    def test_basic_replacement(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_replacement(
            doc, "Acme Corp and its affiliates",
            "Acme Corp and its subsidiaries", AUTHOR, DATE
        )
        assert ok is True

    def test_replacement_creates_del_and_ins(self, sample_docx):
        doc = Document(str(sample_docx))
        apply_tracked_replacement(
            doc, "Acme Corp and its affiliates",
            "Acme Corp and its subsidiaries", AUTHOR, DATE
        )
        # Find the paragraph that had the replacement
        for para in doc.paragraphs:
            tags = _para_xml_tags(para)
            if "del" in tags and "ins" in tags:
                # del should come before ins
                assert tags.index("del") < tags.index("ins")
                return
        raise AssertionError("No paragraph found with both del and ins")

    def test_replacement_preserves_surrounding_text(self, sample_docx):
        doc = Document(str(sample_docx))
        apply_tracked_replacement(
            doc, "Acme Corp and its affiliates",
            "Acme Corp and its subsidiaries", AUTHOR, DATE
        )
        for para in doc.paragraphs:
            full = _get_para_text(para)
            if "subsidiaries" in full:
                # Should still have the leading text
                assert "Service Provider" in full
                return
        raise AssertionError("Replacement text not found")

    def test_replacement_not_found_returns_false(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_replacement(
            doc, "text that does not exist anywhere",
            "replacement", AUTHOR, DATE
        )
        assert ok is False

    def test_replacement_with_smart_quotes(self, smart_quote_docx):
        doc = Document(str(smart_quote_docx))
        # Search with straight quotes — should match smart quotes in doc
        ok = apply_tracked_replacement(
            doc, '"Service Provider" shall not exceed',
            '"Vendor" shall not exceed', AUTHOR, DATE
        )
        assert ok is True


class TestTrackedDeletion:
    def test_basic_deletion(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_deletion(
            doc, "Each party shall indemnify the other", AUTHOR, DATE
        )
        assert ok is True

    def test_deletion_creates_del_element(self, sample_docx):
        doc = Document(str(sample_docx))
        apply_tracked_deletion(
            doc, "Each party shall indemnify the other", AUTHOR, DATE
        )
        for para in doc.paragraphs:
            tags = _para_xml_tags(para)
            if "del" in tags:
                return
        raise AssertionError("No del element found")

    def test_deletion_not_found(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_deletion(doc, "nonexistent text", AUTHOR, DATE)
        assert ok is False


class TestTrackedInsertion:
    def test_basic_insertion(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_insertion(
            doc, "thirty (30) days written notice",
            " and a fifteen (15) day cure period", AUTHOR, DATE
        )
        assert ok is True

    def test_insertion_creates_ins_element(self, sample_docx):
        doc = Document(str(sample_docx))
        apply_tracked_insertion(
            doc, "thirty (30) days written notice",
            " and a cure period", AUTHOR, DATE
        )
        for para in doc.paragraphs:
            tags = _para_xml_tags(para)
            if "ins" in tags:
                return
        raise AssertionError("No ins element found")

    def test_insertion_not_found(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_insertion(
            doc, "nonexistent anchor", "new text", AUTHOR, DATE
        )
        assert ok is False


class TestAddSection:
    def test_basic_add_section(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_add_section(
            doc,
            "governed by the laws of the State of Delaware",
            "Disputes shall be resolved by arbitration.",
            AUTHOR, DATE, new_section_number="5.1"
        )
        assert ok is True

    def test_add_section_not_found(self, sample_docx):
        doc = Document(str(sample_docx))
        ok = apply_tracked_add_section(
            doc, "nonexistent section reference",
            "new text", AUTHOR, DATE
        )
        assert ok is False

    def test_add_section_empty_anchor_refused(self, sample_docx):
        """An empty anchor is contained in every paragraph; it must match none."""
        doc = Document(str(sample_docx))
        assert apply_tracked_add_section(doc, "", "new text", AUTHOR, DATE) is False
        assert apply_tracked_add_section(doc, "  ", "new text", AUTHOR, DATE) is False

    def test_add_section_ambiguous_anchor_refused(self, sample_docx):
        """'this Agreement' is in three paragraphs; the last one used to win."""
        doc = Document(str(sample_docx))
        before = len(doc.paragraphs)
        ok = apply_tracked_add_section(doc, "this Agreement", "new text", AUTHOR, DATE)
        assert ok is False
        assert len(doc.paragraphs) == before


class TestEnableTrackRevisions:
    def test_adds_track_revisions(self, sample_docx):
        doc = Document(str(sample_docx))
        enable_track_revisions(doc)
        settings = doc.settings.element
        assert settings.find(qn("w:trackRevisions")) is not None

    def test_idempotent(self, sample_docx):
        doc = Document(str(sample_docx))
        enable_track_revisions(doc)
        enable_track_revisions(doc)
        settings = doc.settings.element
        elements = settings.findall(qn("w:trackRevisions"))
        assert len(elements) == 1

    def test_inserted_in_schema_order(self, sample_docx):
        """CT_Settings is a strict sequence: w:trackRevisions must come before
        w:defaultTabStop and friends, not at the end of <w:settings>."""
        doc = Document(str(sample_docx))
        enable_track_revisions(doc)
        settings = doc.settings.element
        tags = [child.tag for child in settings]
        idx = tags.index(qn("w:trackRevisions"))
        successors = {qn(tag) for tag in _SETTINGS_AFTER_TRACK_REVISIONS}
        assert not (successors & set(tags[:idx]))
        assert tags[idx + 1] in successors

    def test_appends_when_no_successor_present(self):
        """With nothing after it in the sequence, the flag goes last."""
        doc = Document()
        settings = doc.settings.element
        for child in list(settings):
            settings.remove(child)
        settings.append(OxmlElement("w:zoom"))
        enable_track_revisions(doc)
        tags = [child.tag for child in settings]
        assert tags == [qn("w:zoom"), qn("w:trackRevisions")]


class TestApplyRedlines:
    def test_all_types_applied(self, sample_docx, sample_redlines, tmp_dir):
        output = tmp_dir / "output.docx"
        results = apply_redlines(
            str(sample_docx), str(output), sample_redlines, author=AUTHOR
        )
        assert output.exists()
        ok_count = sum(1 for status, _ in results if status == "OK")
        assert ok_count == 5

    def test_missing_type_field(self, sample_docx, tmp_dir):
        output = tmp_dir / "output.docx"
        redlines = [{"old": "something", "new": "else"}]  # no type
        results = apply_redlines(
            str(sample_docx), str(output), redlines, author=AUTHOR
        )
        assert results[0][0] == "ERROR"
        assert "missing 'type'" in results[0][1]

    def test_missing_required_field(self, sample_docx, tmp_dir):
        output = tmp_dir / "output.docx"
        redlines = [{"type": "replace", "old": "something"}]  # no 'new'
        results = apply_redlines(
            str(sample_docx), str(output), redlines, author=AUTHOR
        )
        assert results[0][0] == "ERROR"
        assert "missing required field" in results[0][1]

    def test_not_found_status(self, sample_docx, tmp_dir):
        output = tmp_dir / "output.docx"
        redlines = [{"type": "replace", "old": "xyz123", "new": "abc"}]
        results = apply_redlines(
            str(sample_docx), str(output), redlines, author=AUTHOR
        )
        assert results[0][0] == "NOT FOUND"

    def test_default_author(self, sample_docx, tmp_dir):
        """Default author should be 'Reviewer', not a personal name."""
        output = tmp_dir / "output.docx"
        redlines = [{"type": "replace", "old": "Acme Corp", "new": "Beta Corp"}]
        apply_redlines(str(sample_docx), str(output), redlines)
        doc = Document(str(output))
        for para in doc.paragraphs:
            for child in para._element:
                author = child.get(qn("w:author"))
                if author:
                    assert author == "Reviewer"
                    return
        # If no tracked change found, the redline didn't match — that's separate

    def test_output_saved_even_with_errors(self, sample_docx, tmp_dir):
        output = tmp_dir / "output.docx"
        redlines = [{"type": "replace"}]  # will error
        apply_redlines(str(sample_docx), str(output), redlines, author=AUTHOR)
        assert output.exists()


def _revision_tags(path):
    """(w:ins count, w:del count) in the saved document body."""
    body = Document(str(path)).element.body
    return len(body.findall(".//" + qn("w:ins"))), len(body.findall(".//" + qn("w:del")))


def _docx(tmp_dir, name, *paragraphs, cell=None):
    path = tmp_dir / name
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    if cell is not None:
        doc.add_table(rows=1, cols=1).cell(0, 0).text = cell
    doc.save(str(path))
    return path


class TestPlacementUniqueness:
    """A span that occurs more than once must not be placed at its first match.

    2026-10-07: "30 days" tagged section 9.2 changed the payment term in
    clause 1 and reported OK; `section` never placed anything.
    """

    PAYMENT = "1. Payment. Invoices are payable within 30 days of receipt."
    CURE = "9.2 Cure. A party may cure a breach within 30 days of notice."

    def test_span_in_two_paragraphs_is_ambiguous(self, tmp_dir):
        src = _docx(tmp_dir, "two.docx", self.PAYMENT, self.CURE)
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "30 days", "new": "60 days", "section": "9.2"},
        ], author=AUTHOR)
        assert results[0][0] == "AMBIGUOUS"
        assert "occurs 2 times" in results[0][1]
        assert _revision_tags(out) == (0, 0)
        assert [p.text for p in Document(str(out)).paragraphs] == [self.PAYMENT, self.CURE]

    def test_span_twice_in_one_paragraph_is_ambiguous(self, tmp_dir):
        src = _docx(tmp_dir, "one.docx",
                    "Cure within 30 days of notice, failing which within 30 days "
                    "the party may terminate.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "within 30 days", "new": "within 45 days"},
        ], author=AUTHOR)
        assert results[0][0] == "AMBIGUOUS"
        assert _revision_tags(out) == (0, 0)

    def test_table_cells_count_as_occurrences(self, tmp_dir):
        """The appliers only reach body paragraphs, so a span that is also in a
        table would otherwise change the body copy even when the cell was meant."""
        src = _docx(tmp_dir, "table.docx", "Fees are payable within 30 days.",
                    cell="Late fees accrue after 30 days.")
        doc = Document(str(src))
        assert span_occurrences(doc, "30 days") == 2
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "delete", "text": "30 days"},
        ], author=AUTHOR)
        assert results[0][0] == "AMBIGUOUS"

    def test_longer_unique_span_applies_to_the_intended_clause(self, tmp_dir):
        src = _docx(tmp_dir, "two.docx", self.PAYMENT, self.CURE)
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "breach within 30 days",
             "new": "breach within 60 days", "section": "9.2"},
        ], author=AUTHOR)
        assert results[0][0] == "OK"
        paras = Document(str(out)).paragraphs
        assert paras[0].text == self.PAYMENT
        assert "del" in _para_xml_tags(paras[1])

    def test_add_section_bare_number_is_ambiguous(self, tmp_dir):
        src = _docx(tmp_dir, "sections.docx", "12. Notices",
                    "Fees of $12,000 are payable.", "13. Term",
                    "IN WITNESS WHEREOF signed the 12th day of March.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "add_section", "after_section": "12",
             "text": "Governing law is Ontario.", "new_section_number": "12A"},
        ], author=AUTHOR)
        assert results[0][0] == "AMBIGUOUS"
        assert _revision_tags(out) == (0, 0)

    def test_add_section_unique_anchor_lands_immediately_after_it(self, tmp_dir):
        src = _docx(tmp_dir, "sections.docx", "12. Notices",
                    "Fees of $12,000 are payable.", "13. Term",
                    "IN WITNESS WHEREOF signed the 12th day of March.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "add_section", "after_section": "12. Notices",
             "text": "Governing law is Ontario.", "new_section_number": "12A"},
        ], author=AUTHOR)
        assert results[0][0] == "OK"
        paras = Document(str(out)).paragraphs
        assert paras[0].text == "12. Notices"
        assert _get_para_text(paras[1]) == "12A. Governing law is Ontario."

    def test_add_section_empty_or_missing_anchor_is_an_error(self, tmp_dir):
        src = _docx(tmp_dir, "sections.docx", "1. Term", "2. Signatures")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "add_section", "after_section": "", "text": "New."},
            {"type": "add_section", "text": "New."},
        ], author=AUTHOR)
        assert [status for status, _ in results] == ["ERROR", "ERROR"]
        assert _revision_tags(out) == (0, 0)

    def test_placement_problems_names_every_span_not_found_exactly_once(self, tmp_dir):
        src = _docx(tmp_dir, "two.docx", self.PAYMENT, self.CURE)
        problems = placement_problems(Document(str(src)), [
            {"type": "replace", "old": "30 days", "new": "60 days"},
            {"type": "replace", "old": "breach within 30 days", "new": "x"},
            {"type": "delete", "text": "not in the document"},
            {"type": "insert_after", "anchor": "within 30 days", "text": " x",
             "as_paragraph": True},
            {"type": "add_section", "after_section": "", "text": "x"},
        ])
        assert [i for i, _ in problems] == [0, 2, 3, 4]
        assert "occurs 2 times" in problems[0][1]
        assert "occurs 0 times" in problems[1][1]

    # 2026-10-07: span_occurrences read only para.runs, so a second copy inside a
    # content control, a counterparty's inserted clause or a hyperlink was not
    # counted and the change landed on the copy the appliers can see, with OK.

    def test_occurrence_inside_a_content_control_counts(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "sdt.docx", [_sdt("30 days")],
                            before="9.2 Cure. A party may cure a breach within ",
                            after=" of notice.", extra=[self.PAYMENT])
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "30 days", "new": "60 days", "section": "9.2"},
        ], author=AUTHOR)
        assert results[0][0] == "AMBIGUOUS"
        assert "occurs 2 times" in results[0][1]
        assert _revision_tags(out) == (0, 0)
        assert Document(str(out)).paragraphs[1].text == self.PAYMENT

    def test_occurrence_inside_a_counterparty_insertion_counts(self, tmp_dir):
        late = "9.3 Late fees. Late fees are payable within 30 days of receipt."
        src = tmp_dir / "ins.docx"
        doc = Document()
        doc.add_paragraph(self.PAYMENT)
        doc.add_paragraph()._p.append(_counterparty("w:ins", late))
        doc.save(str(src))
        assert span_occurrences(Document(str(src)), "payable within 30 days",
                                whole_paragraph=True) == 2
        out = tmp_dir / "out.docx"
        with pytest.raises(ValueError, match="pre-existing revision/comment"):
            apply_redlines(str(src), str(out), [
                {"type": "replace", "old": "payable within 30 days of receipt",
                 "new": "payable within 45 days of receipt", "section": "9.3"},
            ], author=AUTHOR)
        assert not out.exists()

    def test_occurrence_inside_a_hyperlink_counts(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "link.docx", [_hyperlink("legal@example.test")],
                            before="15. Notices. Notices go to ", after=".",
                            extra=["Questions go to legal@example.test by email."])
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "legal@example.test",
             "new": "notices@example.test", "section": "15"},
        ], author=AUTHOR)
        assert results[0][0] == "AMBIGUOUS"
        assert _revision_tags(out) == (0, 0)

    def test_existing_deletion_refuses_a_new_redline(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "deleted.docx",
                            [_counterparty("w:del", "within 30 days ")],
                            before="Late fees accrue ", after="after notice.",
                            extra=[self.PAYMENT])
        assert span_occurrences(Document(str(src)), "within 30 days") == 1
        out = tmp_dir / "out.docx"
        with pytest.raises(ValueError, match="pre-existing revision/comment"):
            apply_redlines(str(src), str(out), [
                {"type": "replace", "old": "within 30 days", "new": "within 45 days"},
            ], author=AUTHOR)
        assert not out.exists()

    def test_non_string_span_is_an_error_not_a_crash(self, tmp_dir):
        src = _docx(tmp_dir, "sections.docx", "12. Notices", "13. Term")
        redlines = [
            {"type": "add_section", "after_section": 13, "text": "x"},
            {"type": "replace", "old": None, "new": "x"},
        ]
        assert [i for i, _ in placement_problems(Document(str(src)), redlines)] == [0, 1]
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), redlines, author=AUTHOR)
        assert [status for status, _ in results] == ["ERROR", "ERROR"]
        assert _revision_tags(out) == (0, 0)


def _bridged_docx(tmp_dir, name, hidden, before="The Supplier shall ",
                  after="be liable for indirect damages.", extra=()):
    """One paragraph: run, an inline element python-docx's para.runs cannot see, run."""
    path = tmp_dir / name
    doc = Document()
    para = doc.add_paragraph()
    para.add_run(before)
    for element in hidden:
        para._p.append(element)
    para.add_run(after)
    for text in extra:
        doc.add_paragraph(text)
    doc.save(str(path))
    return path


def _counterparty(tag, text):
    """A w:ins or w:del by another author, holding one run of text."""
    rev = OxmlElement(tag)
    rev.set(qn("w:id"), "1")
    rev.set(qn("w:author"), "Opposing Counsel")
    rev.set(qn("w:date"), "2026-01-01T00:00:00Z")
    r = OxmlElement("w:r")
    t = OxmlElement("w:delText" if tag == "w:del" else "w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    rev.append(r)
    return rev


def _hyperlink(text):
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), "notices")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    link.append(r)
    return link


def _text_run(text):
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r


def _sdt(text):
    """An inline content control (a template variable) holding one run."""
    sdt = OxmlElement("w:sdt")
    sdt.append(OxmlElement("w:sdtPr"))
    content = OxmlElement("w:sdtContent")
    content.append(_text_run(text))
    sdt.append(content)
    return sdt


def _content_run(tag, **attrs):
    """A run holding one non-text element: fldChar, instrText, a note reference."""
    r = OxmlElement("w:r")
    child = OxmlElement(tag)
    for name, value in attrs.items():
        child.set(qn(f"w:{name}"), value)
    r.append(child)
    return r


def _ref_field(result):
    """A complex REF field: begin, instruction, separate, result run, end."""
    instr = _content_run("w:instrText")
    instr[0].text = " REF _Ref1 \\r \\h "
    return [_content_run("w:fldChar", fldCharType="begin"), instr,
            _content_run("w:fldChar", fldCharType="separate"), _text_run(result),
            _content_run("w:fldChar", fldCharType="end")]


def _count(path, tag):
    return len(Document(str(path)).element.body.findall(".//" + qn(tag)))


class TestHiddenInlineContent:
    """A span must not be rebuilt across content para.runs cannot see.

    2026-10-07: replacing "shall be liable" across a counterparty's tracked
    deletion of "not " moved that deletion to the end of the sentence.
    """

    def test_replace_across_counterparty_deletion_is_refused(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "del.docx", [_counterparty("w:del", "not ")])
        out = tmp_dir / "out.docx"
        with pytest.raises(ValueError, match="pre-existing revision/comment"):
            apply_redlines(str(src), str(out), [
                {"type": "replace", "old": "shall be liable", "new": "shall be liable only"},
            ], author=AUTHOR)
        assert not out.exists()

    def test_counterparty_insertion_and_hyperlink_are_refused(self, tmp_dir):
        cases = [
            ("ins.docx", [_counterparty("w:ins", "not ")],
             {"type": "delete", "text": "shall be liable"}),
            ("link.docx", [_hyperlink("legal@example.test")],
             {"type": "insert_after", "anchor": "shall be liable", "text": " only"}),
        ]
        for name, hidden, redline in cases:
            src = _bridged_docx(tmp_dir, name, hidden)
            out = tmp_dir / f"out-{name}"
            if name == "ins.docx":
                with pytest.raises(ValueError, match="pre-existing revision/comment"):
                    apply_redlines(str(src), str(out), [redline], author=AUTHOR)
                assert not out.exists()
            else:
                results = apply_redlines(str(src), str(out), [redline], author=AUTHOR)
                assert results[0][0] == "ERROR", name
                assert len(Document(str(out)).paragraphs[0]._element) == 3, name

    def test_refusal_does_not_fall_through_to_a_later_clause(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "later.docx", [_counterparty("w:del", "not ")],
                            extra=["Neither party shall be liable for delay."])
        doc = Document(str(src))
        try:
            apply_tracked_replacement(doc, "shall be liable", "is liable", AUTHOR, DATE)
        except SpanCrossesHiddenContent:
            pass
        else:
            raise AssertionError("bridging span was not refused")
        assert _para_xml_tags(doc.paragraphs[1]) == ["r"]

    def test_span_across_proofing_and_bookmark_markers_still_applies(self, tmp_dir):
        proof = OxmlElement("w:proofErr")
        proof.set(qn("w:type"), "spellStart")
        mark = OxmlElement("w:bookmarkStart")
        mark.set(qn("w:id"), "0")
        mark.set(qn("w:name"), "liability")
        src = _bridged_docx(tmp_dir, "markers.docx", [proof, mark])
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "shall be liable", "new": "shall be liable only"},
        ], author=AUTHOR)
        assert results[0][0] == "OK"
        assert _revision_tags(out) == (1, 1)

    # 2026-10-07: the field's begin/instruction/separate/end runs and a footnote
    # reference run sit between the span's runs and were removed untracked.

    def test_span_across_a_complex_field_is_refused(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "field.docx", _ref_field("12.1"),
                            before="Subject to Section ",
                            after=" of this Agreement, the Supplier is liable.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "Section 12.1 of this Agreement",
             "new": "Section 12.2 of this Agreement"},
        ], author=AUTHOR)
        assert results[0][0] == "ERROR"
        assert "straddles an existing tracked change" in results[0][1]
        assert _revision_tags(out) == (0, 0)
        assert _count(out, "w:fldChar") == 3 and _count(out, "w:instrText") == 1

    def test_span_across_a_footnote_reference_is_refused(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "note.docx",
                            [_content_run("w:footnoteReference", id="1")],
                            before="The Supplier shall indemnify", after=" the Client fully.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "indemnify the Client",
             "new": "indemnify and hold harmless the Client"},
        ], author=AUTHOR)
        assert results[0][0] == "ERROR"
        assert _revision_tags(out) == (0, 0)
        assert _count(out, "w:footnoteReference") == 1

    def test_span_across_a_text_box_anchor_is_refused(self, tmp_dir):
        """Word wraps a text box or image in mc:AlternateContent inside its run."""
        anchor = OxmlElement("w:r")
        etree.SubElement(anchor, MC_ALTERNATE_CONTENT)
        src = _bridged_docx(tmp_dir, "textbox.docx", [anchor],
                            before="The Supplier shall indemnify", after=" the Client fully.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "delete", "text": "indemnify the Client"},
        ], author=AUTHOR)
        assert results[0][0] == "ERROR"
        body = Document(str(out)).element.body
        assert len(body.findall(".//" + MC_ALTERNATE_CONTENT)) == 1

    def test_span_beside_a_field_or_note_reference_still_applies(self, tmp_dir):
        src = _bridged_docx(tmp_dir, "beside.docx",
                            _ref_field("12.1") + [_content_run("w:footnoteReference", id="1")],
                            before="Subject to Section ",
                            after=" of this Agreement, the Supplier is liable.")
        out = tmp_dir / "out.docx"
        results = apply_redlines(str(src), str(out), [
            {"type": "replace", "old": "the Supplier is liable",
             "new": "the Supplier is solely liable"},
            {"type": "replace", "old": "Subject to", "new": "Except as set out in"},
        ], author=AUTHOR)
        assert [status for status, _ in results] == ["OK", "OK"]
        assert _revision_tags(out) == (2, 2)
        assert _count(out, "w:fldChar") == 3 and _count(out, "w:footnoteReference") == 1
