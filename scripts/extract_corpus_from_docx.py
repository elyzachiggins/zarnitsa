"""Extract the user's `GROUNDING for RRTA.docx` into atomic corpus entries.

Usage:
    python scripts/extract_corpus_from_docx.py \
        --docx "C:/Users/elyza/OneDrive/Documents/Wargaming/Capstone Project/GROUNDING for RRTA.docx" \
        --out data/corpus/snapshots/2026-05/

This is a placeholder. The production version will:
  1. Unzip the .docx and parse word/document.xml
  2. Segment into entries by major heading / source attribution boundaries
  3. Classify each segment's source_tier (manual review prompt OR rule-based on heading)
  4. Extract keywords (TF-IDF over the corpus)
  5. Emit one markdown file per entry with the required frontmatter

For now: extract the plain text only, leave segmentation/classification for manual work.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_text(docx_path: Path) -> str:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        zip_path = tmp / "src.zip"
        shutil.copy(docx_path, zip_path)
        with ZipFile(zip_path) as z:
            z.extractall(tmp / "x")
        xml = ET.parse(tmp / "x" / "word" / "document.xml")
        paragraphs: list[str] = []
        for p in xml.iterfind(".//w:p", NS):
            text = "".join(t.text or "" for t in p.iterfind(".//w:t", NS))
            paragraphs.append(text)
        return "\n".join(paragraphs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    text = extract_text(args.docx)
    args.out.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out.parent.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / (args.docx.stem + ".txt")
    raw_file.write_text(text, encoding="utf-8")
    print(f"Wrote raw text ({len(text)} chars) to {raw_file}")
    print("Next step: segment manually or via downstream classifier into atomic entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
