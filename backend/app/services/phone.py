"""
Phone canonicalisation + hashing for contact matching.

Contact-match (see docs/mobile-integration-plan.md §6) compares a hash of each of
the user's device contacts against a stored hash of every registered phone. For a
match, both sides MUST produce the *identical* canonical string for the same number
— a contact saved as "0803 123 4567" has to land on the same value as an account
registered as "+234 803 123 4567".

We use Google's libphonenumber on both sides: `phonenumbers` here, `libphonenumber-js`
in the mobile client (`mobile/src/lib/phone.ts`). Both are ports of the same library
and produce identical E.164 for parseable numbers. For the rare input libphonenumber
can't parse, a tiny deterministic fallback (digits, keep a leading '+') is mirrored in
the TS so hashing stays total and consistent. `DEFAULT_PHONE_REGION` is the region used
to interpret national-format numbers ("0803…"); international ("+234…") ignores it.
"""

import hashlib

import phonenumbers

from app.config import settings


def canonical_phone(raw: str, default_region: str | None = None) -> str:
    """Canonical E.164 form. Mirror of the TS implementation. '' when empty."""
    region = default_region or settings.DEFAULT_PHONE_REGION
    s = (raw or "").strip()
    if not s:
        return ""
    try:
        parsed = phonenumbers.parse(s, region)
        # format (not is_valid) on purpose — we canonicalise even imperfect numbers
        # rather than reject them; matching, not validation, is the job here.
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        plus = s.startswith("+")
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return ""
        return ("+" if plus else "") + digits


def phone_hash(raw: str, default_region: str | None = None) -> str | None:
    """SHA-256 of the canonical phone. ``None`` when there is nothing to hash."""
    canonical = canonical_phone(raw, default_region)
    if not canonical:
        return None
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
