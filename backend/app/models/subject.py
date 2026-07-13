"""
Subject family — the closed vocabulary a topic is classified into.

A *family* is the coarse shape of a subject (STEM vs. a language vs. a
humanities reading course), inferred once at synthesis and stored on the topic.
It's what the retrieval engine reads to pick a mode mix, a rendering style, and a
grading strategy (see ``services/retrieval/subject_profiles``). Deliberately small
and closed — this replaces the loose free-text ``subject_type`` strings the modes
used to string-match. Adding a family is a schema + profile-map change, on purpose.
"""

import enum


class SubjectFamily(str, enum.Enum):
    STEM = "STEM"              # math / science / engineering — worked examples, calibration
    LANGUAGE = "LANGUAGE"      # language acquisition — output-first (speak / produce)
    HUMANITIES = "HUMANITIES"  # reading / argument-heavy — explanation, teaching
    GENERAL = "GENERAL"        # the safe default when nothing more specific fits
