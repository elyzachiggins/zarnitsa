"""Structure-aware chunking of corpus entries for embedding-based retrieval.

Each entry is split along the source document's own structural boundaries —
Russian legal/doctrinal markers (Статья, Глава, Раздел, Roman-numeral sections,
numbered paragraphs) and markdown headers — then consecutive blocks are packed
to a target size. Every chunk carries its source entry id, title, tier,
citation, and a structural anchor (e.g. "Статья 67"), so provenance is attached
by the system, never authored by the model.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from zarnitsa.corpus.entry import CorpusEntry, load_snapshot
from zarnitsa.types import SourceTier

# Lines that open a new structural block.
_BOUNDARY = re.compile(
    r"^(?:"
    r"#{1,6}\s+"                       # markdown header
    r"|Статья\s+\d+"                   # article
    r"|Глава\s+[IVXLCDM\d]+"           # chapter
    r"|Раздел\s+[IVXLCDM\d]+"          # section
    r"|[IVXLCDM]+\.\s+\S"              # roman-numeral section header
    r"|\d{1,3}[.)]\s+\S"               # numbered paragraph
    r")",
    re.UNICODE,
)
# "Major" anchors that should persist as the section label until the next one.
_MAJOR = re.compile(r"^(Статья\s+\d+|Глава\s+[IVXLCDM\d]+|Раздел\s+[IVXLCDM\d]+|[IVXLCDM]+\.)", re.UNICODE)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[А-ЯA-Z])", re.UNICODE)
# Finer atoms for over-long blocks: break after sentence/clause punctuation or newlines.
_ATOM = re.compile(r"(?<=[.!?;])\s+|\n+", re.UNICODE)

_TARGET = 1600   # preferred chunk size (chars)
_MAX = 2800      # hard cap before sentence-splitting a block
_MIN = 250       # below this, keep merging into the next chunk


class Chunk(BaseModel):
    """One retrievable unit with machine-attached provenance."""

    chunk_id: str
    entry_id: str
    title: str
    tier: SourceTier
    source_citation: str = ""
    anchor: str = ""          # structural label, e.g. "Статья 67" or "Раздел III"
    text: str
    ordinal: int = 0          # position within the entry

    def citation_label(self) -> str:
        base = self.source_citation or self.title
        return f"{base} — {self.anchor}" if self.anchor else base


def _short(line: str, n: int = 48) -> str:
    return re.sub(r"\s+", " ", line.strip())[:n].rstrip(" .:")


def _blocks(text: str) -> list[tuple[str, str]]:
    """Split text into (anchor, block_text) at structural boundaries."""
    lines = text.split("\n")
    out: list[tuple[str, str]] = []
    cur: list[str] = []
    anchor = ""
    section = ""  # last major anchor, persists across minor blocks
    for line in lines:
        s = line.strip()
        is_boundary = bool(s) and bool(_BOUNDARY.match(s)) and not s.startswith("# ")
        if is_boundary and cur:
            out.append((anchor or section, "\n".join(cur).strip()))
            cur = []
        if is_boundary:
            if _MAJOR.match(s):
                section = _short(s)
                anchor = section
            else:
                anchor = section or _short(s)
        cur.append(line)
    if cur:
        out.append((anchor or section, "\n".join(cur).strip()))
    return [(a, t) for a, t in out if t]


def _split_oversize(block: str) -> list[str]:
    """Pack an over-long block into <=_MAX pieces, guaranteeing the cap."""
    atoms: list[str] = []
    for atom in _ATOM.split(block):
        atom = (atom or "").strip()
        if not atom:
            continue
        # hard-wrap any single atom that is itself longer than the cap
        while len(atom) > _MAX:
            cut = atom.rfind(" ", _MIN, _MAX)
            if cut == -1:
                cut = _MAX
            atoms.append(atom[:cut].strip())
            atom = atom[cut:].strip()
        if atom:
            atoms.append(atom)
    pieces: list[str] = []
    buf = ""
    for atom in atoms:
        if buf and len(buf) + len(atom) + 1 > _TARGET:
            pieces.append(buf.strip())
            buf = atom
        else:
            buf = f"{buf} {atom}".strip()
    if buf:
        pieces.append(buf.strip())
    return pieces or [block]


def chunk_entry(entry: CorpusEntry) -> list[Chunk]:
    """Structure-aware chunks for a single entry."""
    chunks: list[Chunk] = []
    ordinal = 0

    def emit(anchor: str, text: str) -> None:
        nonlocal ordinal
        text = text.strip()
        if not text:
            return
        chunks.append(
            Chunk(
                chunk_id=f"{entry.id}#{ordinal}",
                entry_id=entry.id,
                title=entry.title,
                tier=entry.tier,
                source_citation=entry.source_citation,
                anchor=anchor,
                text=text,
                ordinal=ordinal,
            )
        )
        ordinal += 1

    buf_anchor = ""
    buf = ""
    for anchor, block in _blocks(entry.content):
        if len(block) > _MAX:
            if buf:
                emit(buf_anchor, buf)
                buf, buf_anchor = "", ""
            for piece in _split_oversize(block):
                emit(anchor, piece)
            continue
        if not buf:
            buf, buf_anchor = block, anchor
        elif len(buf) + len(block) + 1 <= _TARGET or len(buf) < _MIN:
            buf = f"{buf}\n{block}"
        else:
            emit(buf_anchor, buf)
            buf, buf_anchor = block, anchor
    if buf:
        emit(buf_anchor, buf)
    return _merge_tiny(chunks)


def _merge_tiny(chunks: list[Chunk], floor: int = 40) -> list[Chunk]:
    """Fold stray sub-`floor` fragments into a neighbour; renumber ids/ordinals."""
    out: list[Chunk] = []
    for c in chunks:
        if out and len(c.text) < floor:
            out[-1].text = f"{out[-1].text}\n{c.text}".strip()
        else:
            out.append(c)
    if len(out) >= 2 and len(out[0].text) < floor:
        out[1].text = f"{out[0].text}\n{out[1].text}".strip()
        out = out[1:]
    for i, c in enumerate(out):
        c.ordinal = i
        c.chunk_id = f"{c.entry_id}#{i}"
    return out


def chunk_snapshot(snapshot: str | None = None) -> list[Chunk]:
    """Chunk every entry in a corpus snapshot."""
    chunks: list[Chunk] = []
    for entry in load_snapshot(snapshot):
        chunks.extend(chunk_entry(entry))
    return chunks
