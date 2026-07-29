"""Reciprocal-rank fusion tests.

Fusion is pure arithmetic over rank positions, so it is testable without downloading
an embedding model — which is the point of using RRF rather than score blending.
"""

from __future__ import annotations

from zarnitsa.corpus.embeddings import fuse, reciprocal_rank_fusion


def test_item_ranked_first_by_both_wins() -> None:
    fused = reciprocal_rank_fusion([[7, 1, 2], [7, 2, 1]])
    assert max(fused, key=lambda k: fused[k]) == 7


def test_appearing_in_both_beats_appearing_in_one() -> None:
    """The actual robustness property RRF provides.

    Note what it does NOT provide: ranked-2nd-by-both does not beat
    ranked-1st-and-3rd. Since 1/x is convex, 1/(k+1) + 1/(k+3) > 2/(k+2) — the
    extreme pair always edges out the middle pair. The margin is ~3e-5 at k=60, so
    those cases are effectively ties, which is the correct behaviour for two rankings
    that disagree about ordering but agree about membership.
    """
    fused = reciprocal_rank_fusion([[3, 1], [1, 3]])
    only_one = reciprocal_rank_fusion([[3, 1], []])
    assert fused[1] > only_one[1]


def test_fuse_respects_top_k() -> None:
    assert len(fuse([0, 1, 2, 3], [3, 2, 1, 0], top_k=2)) == 2


def test_fuse_returns_descending_scores() -> None:
    scores = [s for _, s in fuse([0, 1, 2], [0, 1, 2], top_k=3)]
    assert scores == sorted(scores, reverse=True)


def test_item_in_only_one_ranking_still_scores() -> None:
    fused = reciprocal_rank_fusion([[1], [2]])
    assert fused[1] > 0 and fused[2] > 0


def test_empty_rankings_are_safe() -> None:
    assert reciprocal_rank_fusion([]) == {}
    assert fuse([], [], top_k=5) == []
