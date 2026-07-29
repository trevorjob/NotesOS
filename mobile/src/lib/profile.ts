import { api } from '@/lib/api';

// Current-user profile client — the settings screen. Maps to the /api/auth/me family.
// Phone is the primary identity and is intentionally not editable here (see ProfileUpdate
// on the backend). study_personality is a free-form dict; the three keys below are the
// ones the tutor reads.

export interface StudyPersonality {
  tone?: string;
  emoji_usage?: string;
  explanation_style?: string;
}

export interface Me {
  id: string;
  phone: string;
  email: string | null;
  full_name: string;
  avatar_url: string | null;
  study_personality: StudyPersonality | null;
  university: string | null;
  program: string | null;
  entry_year: number | null;
}

export async function fetchMe(): Promise<Me> {
  const { data } = await api.get('/api/auth/me');
  return data;
}

/** Partial update of the tutor personality (tone / emoji_usage / explanation_style). */
export async function updatePersonality(patch: Partial<StudyPersonality>): Promise<void> {
  await api.patch('/api/auth/me/personality', patch);
}

/** Partial profile update. Phone is not accepted server-side by design. */
export async function updateProfile(patch: {
  full_name?: string;
  school_name?: string;
  program?: string;
  entry_year?: number;
}): Promise<void> {
  await api.patch('/api/auth/me', patch);
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.post('/api/auth/me/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

/**
 * Soft-delete the account: the server anonymises PII, frees the phone, deactivates, and
 * revokes sessions (contributions to shared notes are kept as "Former member"). Password
 * accounts must reauth. The caller should clear local tokens and route to /login after.
 */
export async function deleteAccount(password: string): Promise<void> {
  await api.post('/api/auth/me/delete', { password });
}
