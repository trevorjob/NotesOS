
import { router } from 'expo-router';
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '@/lib/auth';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

// Exported so the WebSocket client can derive ws(s)://…/ws/{course_id} from the same origin.
export const API_BASE_URL = BASE_URL;

// Auth endpoints own their own 401s (e.g. "wrong password") — the caller shows
// the message. Everywhere else, an unrecoverable 401 means the session is gone,
// so we bounce to login instead of letting the page render an error.
const AUTH_PATHS = ['/api/auth/login', '/api/auth/register', '/api/auth/refresh'];

function isAuthEndpoint(url?: string): boolean {
  return !!url && AUTH_PATHS.some((path) => url.includes(path));
}

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return null;

  try {
    const { data } = await axios.post(`${BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken });
    await setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token });
    return data.access_token as string;
  } catch {
    await clearTokens();
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined;
    if (error.response?.status !== 401 || !config || config._retried) {
      throw error;
    }
    config._retried = true;

    refreshPromise = refreshPromise ?? refreshAccessToken();
    const newToken = await refreshPromise;
    refreshPromise = null;

    if (!newToken) {
      // Session is unrecoverable. For non-auth requests, clear and bounce to
      // login so the user sees the login screen, not a page-level error.
      if (!isAuthEndpoint(config.url)) {
        await clearTokens();
        router.replace('/login');
      }
      throw error;
    }

    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${newToken}`;
    return api.request(config);
  }
);
