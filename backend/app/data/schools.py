"""
School canonicalisation helpers + curated Nigerian university seed.

`normalize_school_name` is a pure function with no app dependencies so it can be
imported both by the runtime service and by Alembic migrations without pulling in
the database layer. The seed list is the initial curated catalogue students pick
from; typing a new school runs through the same normalisation to avoid duplicates
("Unilag" / "UNILAG" / "University of Lagos" collapse to one row).

Aliases are stored pre-normalised so alias matching is a plain containment check.
"""

import re

# Similarity above which a typed name is treated as an existing school rather
# than a new one. Tuned loose-ish; schools are objective enough to auto-merge
# (unlike courses, where the user always chooses — see the proximity check).
SCHOOL_MATCH_THRESHOLD = 0.6


def normalize_school_name(raw: str) -> str:
    """Fold a raw school name to a comparable key: lowercase, alnum-only, single-spaced."""
    s = (raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Curated seed. `aliases` are raw; they get normalised at seed/lookup time.
_RAW_NIGERIAN_UNIVERSITIES: list[dict] = [
    {"name": "University of Lagos", "aliases": ["Unilag"]},
    {"name": "University of Ibadan", "aliases": ["UI"]},
    {"name": "University of Nigeria, Nsukka", "aliases": ["UNN", "Unizik Nsukka"]},
    {"name": "Ahmadu Bello University", "aliases": ["ABU", "ABU Zaria"]},
    {"name": "Obafemi Awolowo University", "aliases": ["OAU", "Great Ife", "Ife"]},
    {"name": "University of Benin", "aliases": ["Uniben"]},
    {"name": "University of Ilorin", "aliases": ["Unilorin"]},
    {"name": "University of Port Harcourt", "aliases": ["Uniport"]},
    {"name": "Bayero University Kano", "aliases": ["BUK"]},
    {"name": "University of Nigeria", "aliases": ["UNN"]},
    {"name": "Covenant University", "aliases": ["CU"]},
    {"name": "Lagos State University", "aliases": ["LASU"]},
    {"name": "Federal University of Technology, Akure", "aliases": ["FUTA"]},
    {"name": "Federal University of Technology, Minna", "aliases": ["FUTMINNA", "FUT Minna"]},
    {"name": "Federal University of Technology, Owerri", "aliases": ["FUTO"]},
    {"name": "Nnamdi Azikiwe University", "aliases": ["UNIZIK", "Nnamdi Azikiwe University Awka"]},
    {"name": "University of Calabar", "aliases": ["Unical"]},
    {"name": "University of Jos", "aliases": ["Unijos"]},
    {"name": "University of Maiduguri", "aliases": ["Unimaid"]},
    {"name": "Ladoke Akintola University of Technology", "aliases": ["LAUTECH"]},
    {"name": "Ekiti State University", "aliases": ["EKSU"]},
    {"name": "Rivers State University", "aliases": ["RSU"]},
    {"name": "Delta State University", "aliases": ["DELSU"]},
    {"name": "Ambrose Alli University", "aliases": ["AAU", "Ambrose Alli University Ekpoma"]},
    {"name": "University of Abuja", "aliases": ["Uniabuja"]},
    {"name": "Babcock University", "aliases": ["Babcock"]},
    {"name": "Landmark University", "aliases": ["Landmark"]},
    {"name": "Afe Babalola University", "aliases": ["ABUAD"]},
    {"name": "Federal University Oye-Ekiti", "aliases": ["FUOYE"]},
    {"name": "Michael Okpara University of Agriculture", "aliases": ["MOUAU", "Michael Okpara University of Agriculture Umudike"]},
    {"name": "University of Uyo", "aliases": ["Uniuyo"]},
    {"name": "Enugu State University of Science and Technology", "aliases": ["ESUT"]},
    {"name": "Kwara State University", "aliases": ["KWASU"]},
    {"name": "Osun State University", "aliases": ["UNIOSUN"]},
    {"name": "Pan-Atlantic University", "aliases": ["PAU"]},
]


def seed_schools() -> list[dict]:
    """Return seed rows with normalised names + normalised alias arrays."""
    rows: list[dict] = []
    for u in _RAW_NIGERIAN_UNIVERSITIES:
        rows.append(
            {
                "name": u["name"],
                "normalized_name": normalize_school_name(u["name"]),
                "country": "NG",
                "aliases": sorted(
                    {normalize_school_name(a) for a in u.get("aliases", []) if a.strip()}
                ),
            }
        )
    return rows
