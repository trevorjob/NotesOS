import { Contact, ContactField, getPermissionsAsync, requestPermissionsAsync } from 'expo-contacts';
import { api } from '@/lib/api';
import { canonicalPhone, phoneHash } from '@/lib/phone';

// Contact-match client — the final onboarding beat, "see who you know on NotesOS".
// The device reads the address book locally, canonicalises + SHA-256-hashes every
// number, and uploads ONLY the hashes. Raw phone numbers never leave the device
// (privacy model 6.3-A). The server matches hashes → registered users and returns
// the activity-gated courses at your school they're in that you can join.

// Mirror of the server cap (services/discovery.MAX_CONTACT_HASHES): keep the
// payload bounded even for a huge address book.
const MAX_CONTACT_HASHES = 2000;

export interface MatchedCourse {
  course_id: string;
  code: string;
  name: string;
  member_count: number;
  signals: { resource_count: number };
}

export interface MatchedContact {
  id: string;
  full_name: string | null;
  avatar_url: string | null;
  same_school: boolean;
  courses: MatchedCourse[];
}

export type ContactsPermission = 'granted' | 'denied' | 'undetermined';

/** Map a permission response to the granted/denied/undetermined state the UI
 *  branches on (`granted` runs the match, `undetermined` can re-ask, `denied`
 *  is terminal until the user changes it in Settings). */
function toPermission(res: { granted: boolean; canAskAgain: boolean }): ContactsPermission {
  if (res.granted) return 'granted';
  return res.canAskAgain ? 'undetermined' : 'denied';
}

/** Current contacts-permission state without prompting. */
export async function getContactsPermission(): Promise<ContactsPermission> {
  return toPermission(await getPermissionsAsync());
}

/** Prompt for contacts permission (no-op re-grant if already granted). */
export async function requestContactsPermission(): Promise<ContactsPermission> {
  const current = await getPermissionsAsync();
  if (current.granted) return 'granted';
  return toPermission(await requestPermissionsAsync());
}

/** Read the address book, canonicalise every number, and return the deduped set
 *  of SHA-256 hashes — the only thing that leaves the device. Assumes permission
 *  is already granted. Uses the SDK 57 class-based API (`Contact.getAllDetails`). */
export async function collectContactHashes(): Promise<string[]> {
  const contacts = await Contact.getAllDetails([ContactField.PHONES] as const);

  // Dedupe on the canonical form first (a person is often saved under several
  // formats of the same number), so we only pay the async hash once each.
  const canonicals = new Set<string>();
  for (const contact of contacts) {
    for (const phone of contact.phones ?? []) {
      const raw = phone.number;
      if (!raw) continue;
      const canonical = canonicalPhone(raw);
      if (canonical) canonicals.add(canonical);
    }
  }

  const bounded = [...canonicals].slice(0, MAX_CONTACT_HASHES);
  const hashes = await Promise.all(bounded.map((c) => phoneHash(c)));
  return hashes.filter((h): h is string => h !== null);
}

/** Upload contact hashes and return matched contacts (with joinable courses). */
export async function matchContacts(hashes: string[]): Promise<MatchedContact[]> {
  if (!hashes.length) return [];
  const { data } = await api.post('/api/discovery/contacts', { phone_hashes: hashes });
  return (data.contacts ?? []) as MatchedContact[];
}
