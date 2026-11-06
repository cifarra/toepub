# pdf2epub

Turn PDF books and documents into clean, reflowable EPUBs with one command.

```bash
pdf2epub book.pdf            # -> book.epub
```

You don't need to know what kind of PDF you have. Each page is routed automatically:

| Page | What happens |
|---|---|
| Has a real text layer (born-digital) | Text is read directly: fast and exact |
| Scanned, or a picture of text | OCR (Apple Vision on macOS) |
| Text layer is broken (garbled fonts) | Re-read with full-page OCR |

[Docling](https://github.com/docling-project/docling) then rebuilds the reading order, chapters and sections (from bookmarks, numbering or font sizes), tables and figures. It removes running headers, footers and page numbers. [pandoc](https://pandoc.org) packages the result as an EPUB 3 with a table of contents, a chapter per file and a cover made from the first page.

## Install

You need [uv](https://docs.astral.sh/uv/) and [pandoc](https://pandoc.org/installing.html).

```bash
brew install uv pandoc
git clone https://github.com/cifarra/pdf2epub.git
ln -s "$PWD/pdf2epub/pdf2epub" ~/.local/bin/pdf2epub   # or any folder on your PATH
pdf2epub -h
```

`pdf2epub` is a single self-contained script ([PEP 723](https://peps.python.org/pep-0723/)), so there is no virtualenv to manage. On the first run uv installs Docling and its dependencies (about 1 GB, PyTorch included) into its cache, and Docling downloads its layout models. Later runs start right away.

## Usage

```bash
pdf2epub book.pdf                         # book.epub next to the PDF
pdf2epub *.pdf -o ~/Books                 # batch into a folder
pdf2epub scan.pdf --lang es               # Spanish book: guides OCR, sets the EPUB language
pdf2epub old-scan.pdf --force-ocr         # ignore a bad embedded OCR layer, OCR everything
pdf2epub book.pdf --cover-page 3          # page 1 is a blank binding? pick another cover
pdf2epub book.pdf --pages 1-20 --keep     # quick trial, keep the intermediate markdown
```

It reports which route it took before it starts:

```
[1/1] artofwar.pdf
  264 pages · 257 pages read directly, 7 without text -> OCR
  done in 2m34s -> artofwar.epub  (0.8 MB)
  title: The art of war: the oldest military treatise in the world  ·  author: Sun-tzu, 6th cent. B.C; Giles, Lionel, 1875-1958
```

### Options

| Option | |
|---|---|
| `-o, --output PATH` | Output `.epub`, or a folder (default: next to each PDF) |
| `--title`, `--author` | Override what was found in the PDF metadata or detected on the first page |
| `--lang es` / `--lang en,es` | Languages, most likely first. Guides OCR and sets the EPUB language |
| `--force-ocr` | OCR every page and ignore the text layer (for old scans with poor embedded OCR) |
| `--no-ocr` | Text layer only, never OCR (fastest, for born-digital PDFs) |
| `--pages 1-50` | Convert a page range (`5`, `1-50`, `10-`) |
| `--chapter-level N` | Heading level that starts a new EPUB file (default 1) |
| `--cover-page N` / `--no-cover` | Choose the cover page, or skip the cover |
| `--keep` | Keep the intermediate markdown and images in `<name>.pdf2epub/` |
| `--overwrite` | Replace an existing `.epub` (by default existing ones are skipped) |

If you make a mistake, the full help is printed, followed by the error. Mistyped options get a suggestion (`did you mean --force-ocr?`).

## Performance

On an Apple M4 Pro, a warm run converts a 15-page paper in about 7 s and a 264-page scanned book in about 2.5 min, roughly 0.6 s per page. Pages that need OCR are slower than pages with a text layer.

## Limits

- **Scanned books are only as good as the scan.** Body text is usually clean. Headings come from visual style when there are no bookmarks or numbering, so unusual layouts can add noise to the table of contents, for example bilingual editions or pages of non-Latin script.
- **Math** is kept as text, not rebuilt as equations. Docling has a formula model, but it is slow and is not enabled.
- **Tested on macOS (Apple Silicon).** On Linux and Windows the script falls back to Docling's automatic OCR engine choice; that path is untested.

## Development

```bash
uv run --with pytest pytest -q     # unit tests for pdf2epub's own logic, no models needed
```

## Credits

- [Docling](https://github.com/docling-project/docling) (MIT): layout analysis, OCR routing, structure
- [ocrmac](https://github.com/straussmaximilian/ocrmac) (MIT): Apple Vision OCR on macOS
- [pandoc](https://pandoc.org) (GPL, run as an external program): EPUB writer

## License

[MIT](LICENSE)
