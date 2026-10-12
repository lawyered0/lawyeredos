"""Fictional fixtures for preserving formatting and tracking paragraph marks."""
import copy

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from legal_redline.apply import (
    SpanCrossesHiddenContent,
    apply_tracked_add_section, apply_tracked_deletion,
    apply_tracked_insertion, apply_tracked_replacement,
)

AUTHOR = "Fictional Reviewer"
DATE = "2026-01-01T00:00:00Z"


@pytest.mark.parametrize("operation", ["replace", "delete"])
def test_span_preserves_suffix_and_each_deleted_run_format(operation):
    doc = Document()
    para = doc.add_paragraph()
    para.add_run("Before old ").bold = True
    para.add_run("clause suffix").italic = True
    original = [copy.deepcopy(r._r.rPr) for r in para.runs]
    if operation == "replace":
        assert apply_tracked_replacement(doc, "old clause", "new clause", AUTHOR, DATE)
    else:
        assert apply_tracked_deletion(doc, "old clause", AUTHOR, DATE)
    assert para.runs[0].text == "Before "
    assert para.runs[0].bold
    assert para.runs[-1].text == " suffix"
    assert para.runs[-1].italic
    deleted = para._p.find(qn("w:del")).findall(qn("w:r"))
    assert ["".join(r.itertext()) for r in deleted] == ["old ", "clause"]
    properties = lambda root: [(node.tag, dict(node.attrib), node.text) for node in root.iter()]
    assert [properties(r.find(qn("w:rPr"))) for r in deleted] == [properties(props) for props in original]


@pytest.mark.parametrize("operation", ["replace", "delete"])
def test_unchanged_tabs_and_breaks_are_not_flattened(operation):
    doc = Document()
    para = doc.add_paragraph()
    run = para.add_run("Before\told clause\nAfter")
    run.underline = True
    if operation == "replace":
        assert apply_tracked_replacement(doc, "old clause", "new clause", AUTHOR, DATE)
    else:
        assert apply_tracked_deletion(doc, "old clause", AUTHOR, DATE)
    assert para.runs[0].text == "Before\t"
    assert para.runs[-1].text == "\nAfter"
    assert para.runs[0]._r.find(qn("w:tab")) is not None
    assert para.runs[-1]._r.find(qn("w:br")) is not None
    assert all(run.underline for run in para.runs)


@pytest.mark.parametrize("text_node, character", [("ptab", "\t"), ("noBreakHyphen", "-")])
def test_textual_layout_nodes_keep_character_offsets(text_node, character):
    doc = Document()
    para = doc.add_paragraph()
    run = para.add_run("Before")
    run._r.append(OxmlElement("w:" + text_node))
    text = OxmlElement("w:t")
    text.text = "old suffix"
    run._r.append(text)
    assert apply_tracked_replacement(doc, "old", "new", AUTHOR, DATE)
    assert para.runs[0].text == "Before" + character
    assert para.runs[-1].text == " suffix"
    assert para.runs[0]._r.find(qn("w:" + text_node)) is not None


@pytest.mark.parametrize("operation", ["insert_after", "add_section"])
def test_inserted_paragraph_mark_is_tracked(operation):
    doc = Document()
    doc.add_paragraph("Unique fictional anchor.")
    if operation == "insert_after":
        assert apply_tracked_insertion(doc, "fictional anchor", "Fictional addition.", AUTHOR, DATE, as_paragraph=True)
    else:
        assert apply_tracked_add_section(doc, "fictional anchor", "Fictional addition.", AUTHOR, DATE)
    added = doc.paragraphs[1]._p
    paragraph_mark = added.find("./" + qn("w:pPr") + "/" + qn("w:rPr") + "/" + qn("w:ins"))
    assert paragraph_mark is not None
    assert paragraph_mark.get(qn("w:author")) == AUTHOR
    assert paragraph_mark.get(qn("w:date")) == DATE
    assert added.find(qn("w:ins")) is not None


@pytest.mark.parametrize("operation", ["replace", "delete"])
@pytest.mark.parametrize("break_type", ["page", "column"])
@pytest.mark.parametrize("separate_run", [False, True])
def test_reject_layout_break_spans_without_mutation(operation, break_type, separate_run):
    doc = Document()
    para = doc.add_paragraph()
    run = para.add_run("old " if separate_run else "old")
    if separate_run:
        run = para.add_run()
    marker = OxmlElement("w:br")
    marker.set(qn("w:type"), break_type)
    run._r.append(marker)
    if separate_run:
        para.add_run("clause")
    original = para._p.xml
    with pytest.raises(SpanCrossesHiddenContent):
        if operation == "replace":
            apply_tracked_replacement(doc, "old clause" if separate_run else "old", "new", AUTHOR, DATE)
        else:
            apply_tracked_deletion(doc, "old clause" if separate_run else "old", AUTHOR, DATE)
    assert para._p.xml == original


@pytest.mark.parametrize("previous_marker", ["ins", "del"])
def test_inserted_paragraph_does_not_copy_anchor_revision_identity(previous_marker):
    doc = Document()
    para = doc.add_paragraph("Unique fictional anchor.")
    props = para._p.get_or_add_pPr()
    run_props = OxmlElement("w:rPr")
    run_props.append(OxmlElement("w:b"))
    previous = OxmlElement("w:" + previous_marker)
    previous.set(qn("w:id"), "42")
    run_props.append(previous)
    props.append(run_props)
    assert apply_tracked_insertion(doc, "fictional anchor", "Addition.", AUTHOR, DATE, as_paragraph=True)
    added_props = doc.paragraphs[1]._p.pPr.find(qn("w:rPr"))
    markers = [node for node in added_props if node.tag in {qn("w:ins"), qn("w:del")}]
    assert len(markers) == 1
    assert markers[0].tag == qn("w:ins")
    assert markers[0].get(qn("w:id")) != "42"
    assert added_props.find(qn("w:b")) is not None
