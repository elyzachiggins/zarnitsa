"""Corpus entries — the atomic units of grounding."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import frontmatter
from pydantic import BaseModel, Field

from zarnitsa.config import settings
from zarnitsa.exceptions import CorpusError
from zarnitsa.types import SourceTier


class CorpusEntry(BaseModel):
    """A single grounding entry, e.g. one doctrinal article or one speech excerpt.

    Frontmatter shape (YAML at top of .md):
        id: 2014-doctrine-art-12
        title: 2014 Military Doctrine, Article 12 (External Threats)
        tier: primary_doctrine
        source_date: 2014-12-26
        source_citation: Военная доктрина РФ, утв. 25.12.2014, ст. 12
        language: ru
        keywords: [НАТО, расширение, угроза, внешняя]
        topics: [doctrine, threats, external]
        cited_by_personas: [chief_of_general_staff, center_military_strategic]
    """

    id: str
    title: str
    tier: SourceTier
    source_date: date | None = None
    source_citation: str = ""
    language: str = "ru"
    keywords: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    cited_by_personas: list[str] = Field(default_factory=list)
    content: str

    @classmethod
    def from_file(cls, path: Path) -> CorpusEntry:
        try:
            post = frontmatter.load(path)
        except Exception as e:
            raise CorpusError(f"failed to parse corpus entry {path}: {e}") from e

        meta = post.metadata
        try:
            tier = SourceTier(meta["tier"])
        except (KeyError, ValueError) as e:
            raise CorpusError(f"{path}: missing/invalid 'tier'") from e

        return cls(
            id=meta.get("id", path.stem),
            title=meta.get("title", path.stem),
            tier=tier,
            source_date=meta.get("source_date"),
            source_citation=meta.get("source_citation", ""),
            language=meta.get("language", "ru"),
            keywords=meta.get("keywords", []),
            topics=meta.get("topics", []),
            cited_by_personas=meta.get("cited_by_personas", []),
            content=post.content.strip(),
        )


def snapshot_dir(snapshot: str | None = None) -> Path:
    return settings.data_dir / "corpus" / "snapshots" / (snapshot or settings.corpus_snapshot)


def load_snapshot(snapshot: str | None = None) -> list[CorpusEntry]:
    base = snapshot_dir(snapshot)
    if not base.exists():
        raise CorpusError(f"corpus snapshot not found: {base}")
    return [CorpusEntry.from_file(p) for p in sorted(base.glob("*.md"))]
