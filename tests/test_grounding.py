"""Grounding-visibility tests.

These are the regression guard for the failure that motivated this work: a broken
corpus produced ungrounded analysis that was indistinguishable, to any consumer of
the API, from grounded analysis. Repairing the five malformed files fixed that
instance; these tests fix the *mechanism*, by asserting that a corpus failure is
always visible in the response rather than absorbed into a log line.
"""

from __future__ import annotations

import pytest

from zarnitsa.corpus.entry import SnapshotReport, load_snapshot_report
from zarnitsa.exceptions import CorpusError, CorpusUnavailable
from zarnitsa.orchestrator import graph
from zarnitsa.orchestrator.grounding import Grounding, GroundingStatus
from zarnitsa.types import CouncilRequest

SCENARIO = "NATO announces accelerated accession timeline."


@pytest.fixture(autouse=True)
def reset_retriever():
    graph._retriever = None
    yield
    graph._retriever = None


# --- partial-corpus loading ------------------------------------------------


def test_one_bad_file_does_not_kill_the_corpus(tmp_path, monkeypatch) -> None:
    """The original loader aborted on the first bad file, taking all 37 entries down."""
    snap = tmp_path / "corpus" / "snapshots" / "test"
    snap.mkdir(parents=True)
    (snap / "good.md").write_text(
        '---\nid: good\ntitle: Good\ntier: primary_doctrine\n---\nBody.', encoding="utf-8"
    )
    (snap / "bad.md").write_text(
        '---\nid: bad\ntitle: "has "inner" quotes"\ntier: primary_doctrine\n---\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(graph.settings, "data_dir", tmp_path)
    monkeypatch.setattr(type(graph.settings), "resolved_data_dir", property(lambda s: tmp_path))
    monkeypatch.setattr(graph.settings, "corpus_snapshot", "test")

    report = load_snapshot_report()
    assert [e.id for e in report.entries] == ["good"]
    assert len(report.errors) == 1
    assert "bad.md" in str(report.errors[0])
    assert report.degraded


def test_all_files_bad_still_raises(tmp_path, monkeypatch) -> None:
    """Zero usable entries is not 'degraded', it's unusable — raise."""
    snap = tmp_path / "corpus" / "snapshots" / "test"
    snap.mkdir(parents=True)
    (snap / "bad.md").write_text(
        '---\nid: bad\ntitle: "has "inner" quotes"\ntier: primary_doctrine\n---\nB.',
        encoding="utf-8",
    )
    monkeypatch.setattr(type(graph.settings), "resolved_data_dir", property(lambda s: tmp_path))
    monkeypatch.setattr(graph.settings, "corpus_snapshot", "test")

    with pytest.raises(CorpusError):
        load_snapshot_report()


def test_real_snapshot_loads_clean() -> None:
    report = load_snapshot_report()
    assert report.ok, f"corpus has unloadable entries: {[str(e) for e in report.errors]}"
    assert len(report.entries) > 20


# --- grounding status ------------------------------------------------------


def test_grounded_when_corpus_matches() -> None:
    _, grounding = graph._retrieve(CouncilRequest(scenario=SCENARIO))
    assert grounding.status is GroundingStatus.GROUNDED
    assert grounding.is_grounded
    assert grounding.warning is None
    assert grounding.entry_ids


def test_no_match_is_not_an_error() -> None:
    """An obscure scenario legitimately retrieves nothing. That isn't a failure."""
    _, grounding = graph._retrieve(CouncilRequest(scenario="zzzqqq xxwv nonsense"))
    assert grounding.status is GroundingStatus.NO_MATCH
    assert not grounding.is_grounded
    assert grounding.warning is not None
    graph._check_grounding(grounding)  # must NOT raise


def test_corpus_unavailable_is_reported(monkeypatch) -> None:
    def boom() -> None:
        raise CorpusError("snapshot missing")

    monkeypatch.setattr(graph, "_get_retriever", boom)
    _, grounding = graph._retrieve(CouncilRequest(scenario=SCENARIO))
    assert grounding.status is GroundingStatus.CORPUS_UNAVAILABLE
    assert "snapshot missing" in grounding.detail
    assert "NO source grounding" in (grounding.warning or "")


def test_degraded_when_some_entries_failed(monkeypatch) -> None:
    real = graph._get_retriever()

    class PartialRetriever:
        def __init__(self) -> None:
            self.entries = real.entries
            self.errors = ["broken.md: unparseable frontmatter"]

        def __len__(self):
            return len(real)

        def search(self, *a, **kw):
            return real.search(*a, **kw)

    monkeypatch.setattr(graph, "_get_retriever", lambda: PartialRetriever())
    _, grounding = graph._retrieve(CouncilRequest(scenario=SCENARIO))
    assert grounding.status is GroundingStatus.DEGRADED
    assert grounding.is_grounded  # partial grounding is still grounding
    assert "failed to load" in (grounding.warning or "")


# --- refusal to produce ungrounded analysis --------------------------------


def test_require_grounding_blocks_ungrounded_run(monkeypatch) -> None:
    monkeypatch.setattr(graph.settings, "require_grounding", True)
    bad = Grounding(status=GroundingStatus.CORPUS_UNAVAILABLE, detail="broken")
    with pytest.raises(CorpusUnavailable):
        graph._check_grounding(bad)


def test_require_grounding_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(graph.settings, "require_grounding", False)
    bad = Grounding(status=GroundingStatus.CORPUS_UNAVAILABLE, detail="broken")
    graph._check_grounding(bad)  # must not raise


async def test_council_refuses_when_corpus_unavailable(monkeypatch, fake_provider) -> None:
    monkeypatch.setattr(graph.settings, "require_grounding", True)
    monkeypatch.setattr(
        graph, "_get_retriever", lambda: (_ for _ in ()).throw(CorpusError("gone"))
    )
    with pytest.raises(CorpusUnavailable):
        await graph.run_council(CouncilRequest(scenario=SCENARIO), provider=fake_provider)


async def test_response_carries_grounding_metadata(fake_provider) -> None:
    resp = await graph.run_council(CouncilRequest(scenario=SCENARIO), provider=fake_provider)
    g = resp.metadata["grounding"]
    assert g["status"] == "grounded"
    assert g["is_grounded"] is True
    assert g["warning"] is None
    assert g["corpus_size"] > 20


async def test_no_match_response_carries_warning(fake_provider) -> None:
    resp = await graph.run_council(
        CouncilRequest(scenario="zzzqqq xxwv nonsense"), provider=fake_provider
    )
    assert resp.metadata["grounding"]["warning"] is not None


def test_snapshot_report_ok_and_degraded_flags() -> None:
    assert SnapshotReport(entries=[], errors=[]).ok
    assert not SnapshotReport(entries=[], errors=[]).degraded
