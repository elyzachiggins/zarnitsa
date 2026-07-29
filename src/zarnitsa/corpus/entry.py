"""Corpus entries — the atomic units of grounding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter
from pydantic import BaseModel, Field, field_validator

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

    @field_validator("source_date", mode="before")
    @classmethod
    def _empty_date_is_none(cls, v: object) -> object:
        """Treat an empty/whitespace `source_date:` as absent.

        Several entries carry `source_date: ""` for undated sources. Pydantic rejects
        an empty string for `date | None`, and because the snapshot loader fails on
        the first bad entry, one such file takes the whole corpus down.
        """
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("keywords", "topics", "cited_by_personas", mode="before")
    @classmethod
    def _none_is_empty_list(cls, v: object) -> object:
        """A key present but empty (`keywords:`) parses as None, not []."""
        return [] if v is None else v

    @classmethod
    def from_file(cls, path: Path) -> CorpusEntry:
        try:
            post = frontmatter.load(path)
        except Exception as e:
            raise CorpusError(f"failed to parse corpus entry {path}: {e}") from e
        return cls.from_post(path, post)

    @classmethod
    def from_post(cls, path: Path, post: Any) -> CorpusEntry:
        """Build an entry from an already-parsed frontmatter post.

        Split out from `from_file` so the snapshot loader, which must read the
        frontmatter anyway to skip non-entry files, doesn't parse each file twice.
        """
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
    return (
        settings.resolved_data_dir
        / "corpus"
        / "snapshots"
        / (snapshot or settings.corpus_snapshot)
    )


@dataclass(frozen=True)
class EntryError:
    """One corpus file that could not be loaded."""

    filename: str
    reason: str

    def __str__(self) -> str:
        return f"{self.filename}: {self.reason}"


@dataclass(frozen=True)
class SnapshotReport:
    """Result of loading a snapshot: what parsed, and what didn't.

    The previous loader aborted on the first unparseable file, so five bad entries
    took all thirty-seven offline. Reporting per-file failures instead means one
    malformed entry costs you that entry, not the corpus — and the failures are
    carried in the return value rather than only reaching a log line.
    """

    entries: list[CorpusEntry]
    errors: list[EntryError]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def degraded(self) -> bool:
        """Some entries loaded, but not all of them."""
        return bool(self.errors) and bool(self.entries)


def load_snapshot_report(snapshot: str | None = None) -> SnapshotReport:
    """Load every entry in a snapshot, isolating per-file failures.

    Raises CorpusError only when the snapshot directory is missing, or when it
    contains candidate entries and *none* of them parsed — i.e. when continuing would
    mean running with no grounding at all.
    """
    base = snapshot_dir(snapshot)
    if not base.exists():
        raise CorpusError(f"corpus snapshot not found: {base}")

    entries: list[CorpusEntry] = []
    errors: list[EntryError] = []

    for p in sorted(base.glob("*.md")):
        try:
            post = frontmatter.load(p)
        except Exception as e:
            errors.append(EntryError(p.name, f"unparseable frontmatter: {e}"))
            continue
        if "tier" not in post.metadata:
            continue  # README.md and other non-entry markdown
        try:
            entries.append(CorpusEntry.from_post(p, post))
        except Exception as e:
            errors.append(EntryError(p.name, str(e)))

    if errors and not entries:
        detail = "; ".join(str(e) for e in errors[:5])
        raise CorpusError(f"no corpus entries could be loaded from {base}: {detail}")

    return SnapshotReport(entries=entries, errors=errors)


def load_snapshot(snapshot: str | None = None) -> list[CorpusEntry]:
    """Entries only. Use load_snapshot_report() when you need the failure list."""
    return load_snapshot_report(snapshot).entries
