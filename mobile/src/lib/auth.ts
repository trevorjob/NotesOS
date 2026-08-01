import { getStoredItem, setStoredItem, deleteStoredItem } from '@/lib/secureStorage';

const ACCESS_TOKEN_KEY = 'notesos.accessToken';
const REFRESH_TOKEN_KEY = 'notesos.refreshToken';

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export async function getAccessToken(): Promise<string | null> {
  return getStoredItem(ACCESS_TOKEN_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return getStoredItem(REFRESH_TOKEN_KEY);
}

export async function setTokens(tokens: AuthTokens): Promise<void> {
  await setStoredItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  await setStoredItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

export async function clearTokens(): Promise<void> {
  await deleteStoredItem(ACCESS_TOKEN_KEY);
  await deleteStoredItem(REFRESH_TOKEN_KEY);
}
