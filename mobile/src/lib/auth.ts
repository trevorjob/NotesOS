import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const ACCESS_TOKEN_KEY = 'notesos.accessToken';
const REFRESH_TOKEN_KEY = 'notesos.refreshToken';

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

// expo-secure-store has no web implementation, so the native module methods are
// undefined under react-native-web. Fall back to localStorage on web.
const isWeb = Platform.OS === 'web';

async function getItem(key: string): Promise<string | null> {
  if (isWeb) {
    return globalThis.localStorage?.getItem(key) ?? null;
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key: string, value: string): Promise<void> {
  if (isWeb) {
    globalThis.localStorage?.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteItem(key: string): Promise<void> {
  if (isWeb) {
    globalThis.localStorage?.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export async function getAccessToken(): Promise<string | null> {
  return getItem(ACCESS_TOKEN_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return getItem(REFRESH_TOKEN_KEY);
}

export async function setTokens(tokens: AuthTokens): Promise<void> {
  await setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  await setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

export async function clearTokens(): Promise<void> {
  await deleteItem(ACCESS_TOKEN_KEY);
  await deleteItem(REFRESH_TOKEN_KEY);
}
