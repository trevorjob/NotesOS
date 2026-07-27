import * as Crypto from 'expo-crypto';
import { getLocales } from 'expo-localization';
import { CountryCode, parsePhoneNumberFromString } from 'libphonenumber-js';

// Phone canonicalisation — the client half of contact-match. Must produce the
// EXACT same E.164 string (and therefore the same SHA-256 hash) as the backend's
// services/phone.py for a given number, or a real match silently misses.
//
// Global by design: national-format contacts ("(415) 555…", "0803 123…") are
// parsed against the DEVICE's own region, so the same book of contacts works for
// a user in the US, the UK, or Nigeria. International numbers (+…) carry their own
// country code and ignore the region on both sides. NG is only the launch-market
// fallback for when the device reports no region at all — never a hard assumption.

const FALLBACK_REGION: CountryCode = 'NG';

let cachedRegion: CountryCode | null = null;

/** The device's own country, used as the default region for national-format
 *  numbers. Falls back to the launch market when the OS reports nothing. */
export function deviceRegion(): CountryCode {
  if (cachedRegion) return cachedRegion;
  try {
    const code = getLocales()[0]?.regionCode;
    cachedRegion = (code as CountryCode | undefined) ?? FALLBACK_REGION;
  } catch {
    cachedRegion = FALLBACK_REGION;
  }
  return cachedRegion;
}

/** Canonical E.164 for a raw phone string. Mirror of backend `canonical_phone`:
 *  libphonenumber first, then a digit-strip fallback so hashing stays total for
 *  the rare number neither library can parse. Returns '' for empty input. */
export function canonicalPhone(raw: string, region?: CountryCode): string {
  const s = (raw ?? '').trim();
  if (!s) return '';

  const parsed = parsePhoneNumberFromString(s, region ?? deviceRegion());
  if (parsed) return parsed.number; // E.164, e.g. +2348031234567

  const plus = s.startsWith('+');
  const digits = s.replace(/\D/g, '');
  if (!digits) return '';
  return (plus ? '+' : '') + digits;
}

/** SHA-256 hex of the canonical phone — the value the server stored for a
 *  registered user. Lowercase hex, matching Python's `hexdigest()`. Returns null
 *  for input that canonicalises to nothing. */
export async function phoneHash(raw: string, region?: CountryCode): Promise<string | null> {
  const canonical = canonicalPhone(raw, region);
  if (!canonical) return null;
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, canonical);
}
