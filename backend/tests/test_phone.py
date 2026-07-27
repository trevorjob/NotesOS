"""
Phone canonicalisation — the join key for contact matching.

The contract: numbers that a human would consider "the same" must canonicalise to
the same string (so their hashes match), regardless of national vs. international
formatting or cosmetic separators.
"""

from app.services.phone import canonical_phone, phone_hash


def test_national_and_international_forms_canonicalise_equal():
    intl = canonical_phone("+2348031234567")
    national = canonical_phone("08031234567")
    spaced = canonical_phone("0803 123 4567")
    assert intl == national == spaced == "+2348031234567"


def test_hash_matches_across_formats():
    assert phone_hash("+2348031234567") == phone_hash("0803 123 4567")


def test_different_numbers_do_not_collide():
    assert canonical_phone("08031234567") != canonical_phone("08031234568")


def test_empty_is_none():
    assert canonical_phone("") == ""
    assert canonical_phone("   ") == ""
    assert phone_hash("") is None
    assert phone_hash("not a phone") is None


def test_unparseable_but_digit_bearing_falls_back_consistently():
    # Reaches the fallback (libphonenumber can't parse a bare '+' with junk region
    # inference), but still hashes deterministically rather than throwing.
    a = phone_hash("+234123456789")
    b = phone_hash("+234123456789")
    assert a is not None and a == b


def test_hash_is_sha256_hex():
    h = phone_hash("+2348031234567")
    assert h is not None
    assert len(h) == 64
    assert all(ch in "0123456789abcdef" for ch in h)
