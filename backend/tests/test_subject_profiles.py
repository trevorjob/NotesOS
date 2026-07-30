"""
Subject profiles (B4) — the family→behaviour map that replaced the per-mode
``subject_weight`` strings.

Pure, DB-free tests: every family resolves to a profile, the STEM profile leans on
worked-example (pretest) + self-graded calibration (quiz), ``preferred_mode`` picks the
family's best among a candidate set, and every registered mode has an affinity in every
profile (the coverage guard that keeps a new mode from silently falling through).
"""

import pytest

from app.models.subject import SubjectFamily
from app.services.retrieval import registry
from app.services.retrieval.subject_profiles import (
    GRADE_AI,
    GRADE_SELF_CALIBRATION,
    KNOWN_MODES,
    RENDER_MATH,
    assert_modes_covered,
    mode_affinity,
    preferred_mode,
    profile_for,
)


def test_every_family_has_a_profile():
    for family in SubjectFamily:
        assert profile_for(family).family == family


def test_stem_profile_is_worked_example_plus_self_graded():
    stem = profile_for(SubjectFamily.STEM)
    assert stem.render == RENDER_MATH
    assert stem.grading == GRADE_SELF_CALIBRATION
    # Pretest (worked-example / applied) and quiz (calibration) are the STEM leads.
    assert stem.mode_mix["pretest"] == pytest.approx(1.0)
    assert stem.mode_mix["quiz"] == pytest.approx(1.0)
    assert stem.mode_mix["ramble"] < stem.mode_mix["quiz"]


def test_non_stem_families_grade_with_ai():
    assert profile_for(SubjectFamily.LANGUAGE).grading == GRADE_AI
    assert profile_for(SubjectFamily.HUMANITIES).grading == GRADE_AI
    assert profile_for(SubjectFamily.SOCIAL_SCIENCE).grading == GRADE_AI
    assert profile_for(SubjectFamily.GENERAL).grading == GRADE_AI


def test_social_science_leads_on_teaching_and_holds_recall():
    ss = profile_for(SubjectFamily.SOCIAL_SCIENCE)
    # Explanation-forward like humanities, but cued recall stays solid (named theories/studies).
    assert preferred_mode(SubjectFamily.SOCIAL_SCIENCE, ("quiz", "teach", "ramble")) == "teach"
    assert ss.mode_mix["quiz"] > mode_affinity(SubjectFamily.HUMANITIES, "quiz")


def test_mode_affinity_is_family_specific():
    # Output-first modes lead in LANGUAGE; cued recall leads in STEM.
    assert mode_affinity(SubjectFamily.LANGUAGE, "ramble") > mode_affinity(SubjectFamily.STEM, "ramble")
    assert mode_affinity(SubjectFamily.STEM, "pretest") > mode_affinity(SubjectFamily.LANGUAGE, "pretest")


def test_mode_affinity_unknown_mode_is_neutral():
    assert mode_affinity(SubjectFamily.STEM, "does-not-exist") == 0.5


def test_preferred_mode_picks_the_family_lead():
    candidates = ("quiz", "teach", "ramble")
    # STEM → quiz (worked-example), HUMANITIES → teach, LANGUAGE → ramble.
    assert preferred_mode(SubjectFamily.STEM, candidates) == "quiz"
    assert preferred_mode(SubjectFamily.HUMANITIES, candidates) == "teach"
    assert preferred_mode(SubjectFamily.LANGUAGE, candidates) == "ramble"


def test_preferred_mode_ties_break_toward_candidate_order():
    # A single candidate always wins (the pedagogical-default case, e.g. "new" → pretest).
    assert preferred_mode(SubjectFamily.STEM, ("pretest",)) == "pretest"


def test_preferred_mode_rejects_empty_candidates():
    with pytest.raises(ValueError):
        preferred_mode(SubjectFamily.STEM, ())


def test_all_known_modes_are_covered_by_every_profile():
    # KNOWN_MODES includes recap (a log-level mode, not a registry mode) — every family
    # must still weigh it. This is the guard that fails loudly if a profile forgets one.
    assert_modes_covered(KNOWN_MODES)


def test_registered_modes_are_a_subset_of_known_modes():
    # Anything the registry can run must have a profile affinity defined.
    assert set(registry.available_modes()).issubset(set(KNOWN_MODES))
    assert_modes_covered(registry.available_modes())
