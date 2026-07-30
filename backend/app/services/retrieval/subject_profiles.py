"""
Subject profiles — the *one* place a subject family becomes retrieval behaviour.

A profile answers three questions for a family (system-spec: profile = rendering +
mode-mix + grading):

  * **mode_mix**  — how strongly each retrieval mode suits the family (0..1). This
                    is the family→mode affinity that used to be smeared across every
                    mode's ``subject_weight`` string-match. Modes no longer know a
                    thing about subjects; the affinity lives here, keyed by mode.
  * **render**    — how the client should render the material (``math`` vs. ``prose``).
  * **grading**   — the grading strategy the family leans on (``self_calibration`` for
                    STEM's worked-example self-grading; ``ai`` open-answer elsewhere).

Adding a family is a one-entry change here plus the ``SubjectFamily`` enum — the
abstraction holds the language/humanities profiles that ship later. Adding a *mode*
means giving it an affinity in every profile; :func:`assert_modes_covered` guards that.
"""

from dataclasses import dataclass

from app.models.subject import SubjectFamily

# Rendering hints (client contract).
RENDER_MATH = "math"
RENDER_PROSE = "prose"
RENDER_DEFAULT = "default"

# Grading strategies.
GRADE_SELF_CALIBRATION = "self_calibration"  # worked-example + predicted-vs-actual (STEM)
GRADE_AI = "ai"                              # open-answer AI grading

# Modality suitability threshold (docs/listen-audio-plan.md §7): below this, a family's
# audio isn't worth generating plain — narration can't carry symbol-heavy material the
# way it carries prose. The UI defers to the worked_example lens (narrating a solved
# problem's steps still works) or declines audio outright for the default lens.
AUDIO_SUITABILITY_THRESHOLD = 0.5

# The retrieval modes an affinity is defined over. Kept explicit so a new mode that
# forgets to register an affinity is caught loudly (see assert_modes_covered).
# recap + brain_dump are log-level modes (orchestrations, not registry plugins) — two
# surfaces of one free-recall machine, so brain_dump mirrors recap's affinities.
KNOWN_MODES = ("quiz", "pretest", "ramble", "teach", "recap", "brain_dump")


@dataclass(frozen=True)
class SubjectProfile:
    """A family's retrieval behaviour: mode affinities + render + grading strategy."""

    family: SubjectFamily
    mode_mix: dict[str, float]  # mode key → affinity 0..1
    render: str
    grading: str
    audio_suitability: float = 1.0  # 0..1 — how well plain narration carries this family


# The family→behaviour map. Weights carry over the exact intent the per-mode strings
# encoded, now in one auditable table:
#   STEM           — worked-example (pretest) + self-graded calibration (quiz) lead.
#   LANGUAGE       — output-first: ramble/teach lead, cued recall (quiz) leans lower.
#   HUMANITIES     — explanation-heavy: teaching leads, ramble close behind.
#   SOCIAL_SCIENCE — theory+evidence: teach leads, quiz solid (named theories/studies),
#                    pretest applies frameworks to scenarios.
#   GENERAL        — balanced; quiz is the safe workhorse.
PROFILES: dict[SubjectFamily, SubjectProfile] = {
    SubjectFamily.STEM: SubjectProfile(
        family=SubjectFamily.STEM,
        mode_mix={"quiz": 1.0, "pretest": 1.0, "ramble": 0.5, "teach": 0.6, "recap": 0.8, "brain_dump": 0.8},
        render=RENDER_MATH,
        grading=GRADE_SELF_CALIBRATION,
        audio_suitability=0.3,  # symbol-heavy notation doesn't narrate; worked_example is the exception
    ),
    SubjectFamily.LANGUAGE: SubjectProfile(
        family=SubjectFamily.LANGUAGE,
        mode_mix={"quiz": 0.7, "pretest": 0.6, "ramble": 1.0, "teach": 0.9,  "recap": 0.8, "brain_dump": 0.8},
        render=RENDER_PROSE,
        grading=GRADE_AI,
        audio_suitability=1.0,  # hearing pronunciation/phrasing is the point
    ),
    SubjectFamily.HUMANITIES: SubjectProfile(
        family=SubjectFamily.HUMANITIES,
        mode_mix={"quiz": 0.8, "pretest": 0.7, "ramble": 0.9, "teach": 1.0, "recap": 1.0, "brain_dump": 1.0},
        render=RENDER_PROSE,
        grading=GRADE_AI,
        audio_suitability=1.0,
    ),
    SubjectFamily.SOCIAL_SCIENCE: SubjectProfile(
        family=SubjectFamily.SOCIAL_SCIENCE,
        mode_mix={"quiz": 0.85, "pretest": 0.7, "ramble": 0.9, "teach": 1.0, "recap": 1.0, "brain_dump": 1.0},
        render=RENDER_PROSE,
        grading=GRADE_AI,
        audio_suitability=1.0,
    ),
    SubjectFamily.GENERAL: SubjectProfile(
        family=SubjectFamily.GENERAL,
        mode_mix={"quiz": 1.0, "pretest": 0.7, "ramble": 0.8, "teach": 0.85, "recap": 1.0, "brain_dump": 1.0},
        render=RENDER_DEFAULT,
        grading=GRADE_AI,
        audio_suitability=0.9,
    ),
}


def profile_for(family: SubjectFamily) -> SubjectProfile:
    """The profile for a family; falls back to GENERAL for anything unmapped."""
    return PROFILES.get(family, PROFILES[SubjectFamily.GENERAL])


def mode_affinity(family: SubjectFamily, mode_key: str) -> float:
    """How strongly ``mode_key`` suits ``family`` (0..1). Unknown mode → neutral 0.5."""
    return profile_for(family).mode_mix.get(mode_key, 0.5)


def is_audio_suitable(family: SubjectFamily) -> bool:
    """Whether a plain narrated explainer suits this family (docs/listen-audio-plan.md §7).

    Below threshold, the generic "explainer" lenses (default/exam_focused/slower) are
    withheld — narration can't carry symbol-heavy material the prose lenses assume.
    worked_example is exempt (narrating solved-problem steps works in audio); personal
    lenses the user explicitly asked for (user_instruction/remediation) are exempt too.
    """
    return profile_for(family).audio_suitability >= AUDIO_SUITABILITY_THRESHOLD


def preferred_mode(family: SubjectFamily, candidates: tuple[str, ...]) -> str:
    """The highest-affinity mode for a family among ``candidates``.

    Ties break toward the candidate order (the caller lists them by pedagogical
    default first), so an equal-affinity family keeps the sensible default.
    """
    if not candidates:
        raise ValueError("preferred_mode needs at least one candidate")
    return max(candidates, key=lambda m: mode_affinity(family, m))


def assert_modes_covered(mode_keys) -> None:
    """Raise if any registered mode lacks an affinity in some profile (a coverage guard)."""
    for family, profile in PROFILES.items():
        missing = [k for k in mode_keys if k not in profile.mode_mix]
        if missing:
            raise ValueError(f"{family.value} profile is missing affinities for {missing}")
