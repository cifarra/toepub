"""Tests for pdf2epub's own logic (no Docling, no models, runs in a second).

    uv run --with pytest pytest -q
"""

import argparse
import importlib.machinery
import importlib.util
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "pdf2epub"
_loader = importlib.machinery.SourceFileLoader("pdf2epub", str(SCRIPT))
_spec = importlib.util.spec_from_loader("pdf2epub", _loader)
p2e = importlib.util.module_from_spec(_spec)
_loader.exec_module(p2e)


def headings(md: str) -> list[str]:
    return [line for line in md.split("\n") if re.match(r"^#{1,6} ", line)]


def body(*heads: str, filler: int = 10) -> str:
    """Markdown with the given headings spread out by filler paragraphs."""
    out = []
    for h in heads:
        out.append(h)
        out += [f"Paragraph {i}." for i in range(filler)]
    return "\n\n".join(out)


# --- normalize_headings -------------------------------------------------------

def test_sections_shift_up_and_title_copy_is_dropped():
    md = body("### Attention Is All You Need", "## 1 Introduction", "## 2 Background",
              "### 2.1 Detail", "## 3 Model")
    out = p2e.normalize_headings(md, "Attention Is All You Need")
    assert headings(out) == ["# 1 Introduction", "# 2 Background", "## 2.1 Detail", "# 3 Model"]


def test_late_docling_titles_become_plain_text():
    # Docling's '#' means "title"; later ones in a scan are misread footnotes.
    md = body("# The Book", "## Chapter 1", "# fp footnote junk", "## Chapter 2", "## Chapter 3")
    out = p2e.normalize_headings(md, "The Book")
    assert headings(out) == ["# Chapter 1", "# Chapter 2", "# Chapter 3"]
    assert "fp footnote junk" in out


def test_title_page_type_does_not_steal_chapter_level():
    # Big title-page type claims high levels once; chapters repeat through the book.
    md = body("## SUN TZU", "### LIONEL GILES", "#### Captain", "### I. LAYING PLANS",
              "### II. WAGING WAR", "### III. ATTACK BY STRATAGEM", filler=30)
    out = p2e.normalize_headings(md, "The Art of War")
    assert "# II. WAGING WAR" in headings(out)
    assert "# I. LAYING PLANS" in headings(out)


def test_front_matter_is_promoted_to_chapters():
    md = body("## I. One", "##### PREFACE", "##### Introducción", "## II. Two", "## III. Three",
              "#### Appendix A", filler=20)
    out = p2e.normalize_headings(md, "Book")
    hs = headings(out)
    assert "# PREFACE" in hs and "# Introducción" in hs and "# Appendix A" in hs


def test_headings_inside_code_blocks_are_left_alone():
    md = "## Real\n\n```\n## not a heading\n```\n\n## Also real\n\n## Third"
    out = p2e.normalize_headings(md, "x")
    assert "## not a heading" in out
    assert headings(out)[0] == "# Real"


def test_no_headings_is_fine():
    assert p2e.normalize_headings("just text\n\nmore text", "x") == "just text\n\nmore text"


# --- metadata and titles --------------------------------------------------------

@pytest.mark.parametrize("junk", [None, "", "untitled", "Microsoft Word - thesis.docx",
                                  "scan_0001.pdf", "  \x00 "])
def test_clean_meta_rejects_junk(junk):
    assert p2e.clean_meta(junk) is None


def test_clean_meta_keeps_real_titles():
    assert p2e.clean_meta(" The Art of War ") == "The Art of War"


def test_pretty_stem():
    assert p2e.pretty_stem(Path("/x/The_Art_of__War.pdf")) == "The Art of War"


# --- argument parsing --------------------------------------------------------------

@pytest.mark.parametrize("spec, expected", [("5", (5, 5)), ("1-50", (1, 50)), (" 3 - 9 ", (3, 9))])
def test_pages_arg(spec, expected):
    assert p2e.pages_arg(spec) == expected


def test_pages_arg_open_ended():
    start, end = p2e.pages_arg("10-")
    assert start == 10 and end > 10**6


@pytest.mark.parametrize("bad", ["abc", "0", "10-2", "1-2-3", ""])
def test_pages_arg_rejects(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        p2e.pages_arg(bad)


def test_lang_arg():
    assert p2e.lang_arg("es, en-US") == ["es", "en-US"]
    with pytest.raises(argparse.ArgumentTypeError):
        p2e.lang_arg("spanish!!")


def test_output_path(tmp_path):
    pdf = tmp_path / "book.pdf"
    assert p2e.output_path(pdf, None) == tmp_path / "book.epub"
    assert p2e.output_path(pdf, tmp_path / "out") == tmp_path / "out" / "book.epub"
    assert p2e.output_path(pdf, tmp_path / "x.epub") == tmp_path / "x.epub"


def test_check_pdf(tmp_path):
    good = tmp_path / "a.pdf"
    good.write_bytes(b"%PDF-1.7\n...")
    text = tmp_path / "notes.txt"
    text.write_text("hello")
    assert p2e.check_pdf(good) is None
    assert p2e.check_pdf(text) == "is not a PDF"
    assert p2e.check_pdf(tmp_path / "missing.pdf") == "no such file"
    assert "folder" in p2e.check_pdf(tmp_path)
