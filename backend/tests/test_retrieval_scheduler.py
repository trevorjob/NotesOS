"""
FSRS scheduler wrapper — behavioural tests (version-agnostic).

We assert properties the algorithm guarantees, not exact intervals, so a future
FSRS bump doesn't break the suite while still catching a broken integration.
"""

from datetime import datetime, timezone

import pytest

from app.services.retrieval import scheduler


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_new_card_is_serializable():
    card = scheduler.new_card()
    assert isinstance(card, dict)
    # Round-trips through a review without error.
    result = scheduler.apply_review(card, "good", now=NOW)
    assert isinstance(result.card, dict)


def test_review_sets_due_in_the_future():
    result = scheduler.apply_review(None, "good", now=NOW)
    assert result.due is not None
    assert result.due > NOW.replace(tzinfo=None)  # stored naive UTC


def test_due_is_stored_naive_utc():
    result = scheduler.apply_review(None, "good", now=NOW)
    assert result.due.tzinfo is None
    assert result.last_review is not None and result.last_review.tzinfo is None


def test_better_grade_schedules_further_out():
    good = scheduler.apply_review(None, "good", now=NOW)
    again = scheduler.apply_review(None, "again", now=NOW)
    # Remembering well pushes the next review further away than forgetting.
    assert good.due > again.due


def test_repeated_success_grows_the_interval():
    card = scheduler.new_card()
    first = scheduler.apply_review(card, "good", now=NOW)
    # Review again at its due date — stability (durability) should climb.
    second = scheduler.apply_review(first.card, "good", now=first.due.replace(tzinfo=timezone.utc))
    assert second.stability >= first.stability


def test_unknown_grade_raises():
    with pytest.raises(ValueError):
        scheduler.apply_review(None, "sorta", now=NOW)
