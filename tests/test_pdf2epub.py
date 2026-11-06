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


# --- Markdown input ----------------------------------------------------------------

def test_authored_lone_h1_title_is_dropped_and_sections_become_chapters():
    md = "# My Notes\n\n## One\n\ntext\n\n## Two\n\n### Detail\n"
    out = p2e.normalize_authored_headings(md, "My Notes")
    assert headings(out) == ["# One", "# Two", "## Detail"]


def test_authored_multiple_h1_are_the_authors_chapters():
    md = "# Starter\n\n## Feeding\n\n# Baking\n\n# Appendix\n"
    assert p2e.normalize_authored_headings(md, "Field Guide") == md


def test_authored_h1_kept_when_it_is_not_the_title():
    md = "# Something else\n\n## One\n"
    assert p2e.normalize_authored_headings(md, "Front matter title") == md


def test_authored_yaml_comments_are_not_headings():
    md = "---\ntitle: X\n# a yaml comment\n---\n\n## One\n\n## Two\n"
    out = p2e.normalize_authored_headings(md, "X")
    assert "# a yaml comment" in out
    assert headings(out)[1:] == ["# One", "# Two"]


def test_lone_h1():
    assert p2e.lone_h1("# Title\n\n## a\n") == "Title"
    assert p2e.lone_h1("## a\n\n# Late\n") is None
    assert p2e.lone_h1("# A\n\n# B\n") is None


def obsidian(md, files=None):
    files = files or {}
    missing = []
    out = p2e.obsidian_to_markdown(md, lambda name: files.get(name), missing)
    return out, missing


def test_obsidian_links_become_text():
    out, _ = obsidian("See [[Note]], [[Other|the other]] and [[Deep#Section]] and [[#Local]].")
    assert out == "See Note, the other and Deep and Local."


def test_obsidian_image_embeds_resolve_and_width_is_not_alt_text():
    files = {"a.png": Path("/v/a.png"), "b.png": Path("/v/x/b.png")}
    out, missing = obsidian("![[a.png]]\n![[b.png|300]]\n![[c.png|caption]]", files)
    assert out.split("\n")[:2] == ["![](</v/a.png>)", "![](</v/x/b.png>)"]
    assert missing == ["c.png"]


def test_obsidian_note_embeds_become_text():
    out, missing = obsidian("![[Another note]]")
    assert out == "Another note" and missing == []


def test_obsidian_callouts_comments_and_code():
    md = "> [!warning] Budget\n> over\n\n> [!tip]\n%% secret %%\n%%\nblock secret\n%%\n" \
         "`x[[0]]`\n```\ny[[1]]\n```"
    out, _ = obsidian(md)
    assert "> **Budget**\n>\n> over" in out
    assert "> **Tip**" in out
    assert "secret" not in out
    assert "`x[[0]]`" in out and "y[[1]]" in out


def test_attachment_finder_searches_the_vault(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "notes").mkdir()
    (tmp_path / "files" / "deep").mkdir(parents=True)
    img = tmp_path / "files" / "deep" / "Pasted image.png"
    img.write_bytes(b"png")
    note = tmp_path / "notes" / "n.md"
    note.write_text("x")
    find = p2e.attachment_finder(note)
    assert find("Pasted image.png") == img
    assert find("nope.png") is None


def test_attachment_finder_outside_a_vault_only_looks_next_to_the_file(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "far.png").write_bytes(b"png")
    (tmp_path / "near.png").write_bytes(b"png")
    find = p2e.attachment_finder(tmp_path / "doc.md")
    assert find("near.png") == (tmp_path / "near.png").resolve()
    assert find("far.png") is None


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


def test_check_input(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n...")
    md = tmp_path / "notes.md"
    md.write_text("# hi")
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    fake = tmp_path / "image.md"
    fake.write_bytes(b"\x89PNG\x00\x00")
    assert p2e.check_input(pdf) == ("pdf", None)
    assert p2e.check_input(md) == ("markdown", None)
    assert p2e.check_input(txt) == (None, "is not a PDF or Markdown (.md) file")
    assert p2e.check_input(fake)[0] is None
    assert p2e.check_input(tmp_path / "missing.pdf") == (None, "no such file")
    assert "folder" in p2e.check_input(tmp_path)[1]
