/**
 * Capture current NotesOS UI screenshots for Stitch redesign mode.
 *
 * Key properties:
 * - Logs in via the UI (reliable) instead of trying to fake zustand/localStorage.
 * - Uses route-specific "ready" checks and long timeouts.
 * - Saves into: <repoRoot>/design/current-screens/{desktop|mobile}
 *
 * Usage:
 * - Ensure backend is running at http://localhost:8000
 * - Ensure frontend is running (dev or start) at http://localhost:3000 (or set NOTESOS_WEB_BASE)
 * - Run: npm run capture:screens
 */

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { chromium, devices } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const WEB_BASE = process.env.NOTESOS_WEB_BASE || 'http://localhost:3000';
const API_BASE = process.env.NOTESOS_API_BASE || 'http://localhost:8000';

const OUT_ROOT =
  process.env.NOTESOS_SCREENSHOT_DIR
    ? path.resolve(process.env.NOTESOS_SCREENSHOT_DIR)
    : path.resolve(__dirname, '..', '..', 'design', 'current-screens');

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function sanitize(name) {
  return name.replace(/[^a-z0-9-_]+/gi, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '');
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function apiFetch(endpoint, { method = 'GET', token, json } = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: json ? JSON.stringify(json) : undefined,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg = typeof data === 'string' ? data : JSON.stringify(data);
    throw new Error(`API ${method} ${endpoint} failed (${res.status}): ${msg}`);
  }
  return data;
}

async function seed() {
  const nonce = `${Date.now()}-${crypto.randomBytes(3).toString('hex')}`;
  const email = `stitchbot+${nonce}@example.com`;
  const password = 'Password123!';
  const full_name = 'Stitch Bot';

  const register = await apiFetch('/api/auth/register', {
    method: 'POST',
    json: { email, password, full_name },
  });

  const { access_token } = register;

  const course = await apiFetch('/api/courses', {
    method: 'POST',
    token: access_token,
    json: {
      code: 'DEMO-101',
      name: 'Demo Course',
      description: 'Seeded course for UI screenshots.',
      semester: 'Spring 2026',
      is_public: false,
    },
  });

  const courseId = course?.course?.id || course?.id || course?.course_id;
  if (!courseId) {
    throw new Error(`Could not read courseId from response: ${JSON.stringify(course).slice(0, 500)}`);
  }

  const topic = await apiFetch(`/api/courses/${courseId}/topics`, {
    method: 'POST',
    token: access_token,
    json: {
      course_id: courseId,
      title: 'Week 1 — Foundations',
      description: 'Seeded topic for UI screenshots.',
      week_number: 1,
      order_index: 1,
    },
  });

  const topicId = topic?.id || topic?.topic?.id || topic?.topic_id;
  if (!topicId) {
    throw new Error(`Could not read topicId from response: ${JSON.stringify(topic).slice(0, 500)}`);
  }

  await apiFetch(`/api/topics/${topicId}/resources/text`, {
    method: 'POST',
    token: access_token,
    json: {
      topic_id: topicId,
      title: 'Seed Note',
      content:
        'These are seeded notes used to capture UI screenshots for Stitch.\n\n- Minimal layout\n- Clear hierarchy\n- Intentional spacing\n',
    },
  });

  // Optional: create an invite so /invites has content.
  try {
    await apiFetch('/api/invites/global', {
      method: 'POST',
      token: access_token,
      json: { name: 'Demo Class' },
    });
  } catch {
    // Not critical for capture.
  }

  return { email, password, courseId, topicId };
}

async function waitForAnySelector(page, selectors, timeoutMs) {
  if (!selectors || selectors.length === 0) return;
  const attempts = selectors.map(async (sel) => {
    if (typeof sel === 'string' && sel.startsWith('text=')) {
      const text = sel.slice('text='.length);
      await page.getByText(text, { exact: false }).first().waitFor({ state: 'visible', timeout: timeoutMs });
      return;
    }
    await page.waitForSelector(sel, { timeout: timeoutMs, state: 'visible' });
  });
  await Promise.race(attempts);
}

async function waitForTextExists(page, text, timeoutMs) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: 'attached', timeout: timeoutMs });
}

async function assertNoNextNotFound(page, name) {
  const notFound = page.getByText('This page could not be found.');
  if (await notFound.count()) {
    throw new Error(`[capture] ${name}: reached Next.js not-found page`);
  }
}

async function waitForAppReady(page, name, timeoutMs) {
  // Wait until we're no longer on the full-screen AuthGuard loader.
  // This loader includes the text "Loading..." centered on screen.
  try {
    await page.waitForSelector('text=Loading...', { state: 'detached', timeout: timeoutMs });
  } catch {
    // If it never detaches, keep going; the page-specific ready selectors will be the real gate.
  }

  // Same for AuthRedirect "Redirecting..."
  try {
    await page.waitForSelector('text=Redirecting...', { state: 'detached', timeout: timeoutMs });
  } catch {
    // ignore
  }

  // If we somehow ended up back at /login while trying to capture a logged-in page, fail loudly.
  const url = page.url();
  if (!name.toLowerCase().includes('login') && !name.toLowerCase().includes('register') && url.includes('/login')) {
    throw new Error(`[capture] ${name}: got redirected to /login (auth not established)`);
  }
}

async function loginViaUI(page, email, password) {
  await page.goto(`${WEB_BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 180000 });
  await page.waitForSelector('text=Welcome back', { timeout: 180000 });

  await page.getByPlaceholder('you@university.edu').fill(email);
  await page.getByPlaceholder('••••••••').fill(password);

  // Wait for the actual login API request/response so we can fail fast with signal.
  const loginResponsePromise = page.waitForResponse(
    (resp) =>
      resp.request().method() === 'POST' &&
      resp.url().includes('/api/auth/login'),
    { timeout: 180000 }
  );

  await page.getByRole('button', { name: 'Sign in' }).click();

  let loginResp;
  try {
    loginResp = await loginResponsePromise;
  } catch {
    // If the request never fired, capture the DOM state via URL check below.
    loginResp = null;
  }

  if (loginResp) {
    const status = loginResp.status();
    if (status < 200 || status >= 300) {
      let body = '';
      try {
        body = await loginResp.text();
      } catch {
        body = '<no-body>';
      }
      throw new Error(`[loginViaUI] /api/auth/login failed (${status}): ${body}`);
    }
  }

  // Consider login successful when courses UI appears.
  await Promise.race([
    page.waitForSelector('text=Your Courses', { timeout: 180000 }).catch(() => {}),
    page.waitForURL('**/courses', { timeout: 180000 }).catch(() => {}),
  ]);

  const url = page.url();
  if (url.includes('/login')) {
    // Surface any visible error content to help debug.
    const errorText = await page.locator('[class*="error"], text=Login failed, text=Incorrect email or password').first().innerText().catch(() => '');
    throw new Error(`[loginViaUI] Login did not navigate away from /login. VisibleError="${errorText}"`);
  }
}

async function loginByApiAndSetStorage(context, page, email, password) {
  // Log in via backend, then seed the exact localStorage keys this app reads:
  // - notesos_access_token / notesos_refresh_token (used by axios interceptor)
  // - persist store key: notesos-auth (used by zustand/persist)
  const data = await apiFetch('/api/auth/login', {
    method: 'POST',
    json: { email, password },
  });

  const accessToken = data?.access_token;
  const refreshToken = data?.refresh_token;
  const user = data?.user;
  if (!accessToken || !refreshToken || !user) {
    throw new Error(
      `[loginByApiAndSetStorage] Missing fields from login response: ${JSON.stringify(data).slice(0, 500)}`
    );
  }

  const persistKey = 'notesos-auth';
  const persistValue = JSON.stringify({
    state: { user, isAuthenticated: true },
    version: 0,
  });

  await context.addInitScript(({ accessToken, refreshToken, persistKey, persistValue }) => {
    localStorage.setItem('notesos_access_token', accessToken);
    localStorage.setItem('notesos_refresh_token', refreshToken);
    localStorage.setItem(persistKey, persistValue);
  }, { accessToken, refreshToken, persistKey, persistValue });

  // Load a protected route to force AuthGuard validation.
  await page.goto(`${WEB_BASE}/courses`, { waitUntil: 'domcontentloaded', timeout: 180000 });
  await page.waitForLoadState('networkidle', { timeout: 180000 }).catch(() => {});
  await page.waitForSelector('text=Your Courses', { timeout: 180000 });
}

async function captureProfile(profile, ctxConfig, seedData) {
  const outDir = path.join(OUT_ROOT, profile);
  ensureDir(outDir);

  const browser = await chromium.launch({ headless: true });
  const loggedOutContext = await browser.newContext(ctxConfig);
  const loggedInContext = await browser.newContext(ctxConfig);

  const loggedOutPage = await loggedOutContext.newPage();
  const loggedInPage = await loggedInContext.newPage();

  loggedOutPage.setDefaultNavigationTimeout(180000);
  loggedInPage.setDefaultNavigationTimeout(180000);
  loggedOutPage.setDefaultTimeout(180000);
  loggedInPage.setDefaultTimeout(180000);

  // Disable transitions/animations to reduce flakiness
  const stabilizationScript = () => {
    const style = document.createElement('style');
    style.innerHTML = `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        scroll-behavior: auto !important;
      }
    `;
    document.head.appendChild(style);
  };
  await loggedOutContext.addInitScript(stabilizationScript);
  await loggedInContext.addInitScript(stabilizationScript);

  // Log in once for the logged-in context.
  // UI login has been flaky under headless for this codebase; we prefer API + localStorage seeding.
  await loginByApiAndSetStorage(loggedInContext, loggedInPage, seedData.email, seedData.password);

  const fakeTestId = crypto.randomUUID();
  const fakeAttemptId = crypto.randomUUID();

  const shots = [
    // Auth screens (logged out)
    {
      order: 1,
      name: 'Login',
      path: '/login',
      auth: 'out',
      waitAny: ['text=Welcome back', 'text=Sign in'],
    },
    {
      order: 2,
      name: 'Register',
      path: '/register',
      auth: 'out',
      waitAny: ['text=Create your account', 'text=Create account'],
    },

    // Courses
    {
      order: 10,
      name: 'Courses_List',
      path: '/courses',
      auth: 'in',
      waitAny: ['text=Your Courses', 'text=Create Course'],
    },
    {
      order: 11,
      name: 'Courses_New',
      path: '/courses/new',
      auth: 'in',
      waitAny: ['text=Create a Course', 'text=Single course', 'text=Course Code'],
    },
    {
      order: 12,
      name: 'Courses_Join',
      path: '/courses/join',
      auth: 'in',
      waitAny: ['text=Join a Course', 'text=Course Code'],
    },
    {
      order: 13,
      name: 'Course_Home',
      path: `/courses/${seedData.courseId}`,
      auth: 'in',
      waitAny: ['text=Demo Course', 'text=Progress', 'text=Practice Test'],
    },

    // Topic
    {
      order: 14,
      name: 'Topic_Study',
      path: `/courses/${seedData.courseId}/topics/${seedData.topicId}`,
      auth: 'in',
      waitAny: ['text=Study Resources', 'text=Pre-class Research', 'text=Loading topic...', 'text=Upload Files'],
    },

    // Tests (list should work; take/results may be a not-found state inside the page)
    {
      order: 20,
      name: 'Tests_List',
      path: `/courses/${seedData.courseId}/tests`,
      auth: 'in',
      waitAny: ['text=Practice Test', 'h1:has-text("Practice Test")', 'text=Generate test', 'text=Generate'],
    },
    // NOTE: Tests_Take / Tests_Results require a real test + attempt; in dev they can hang on loaders.
    // For design capture, the list page is sufficient for Stitch prompts.

    // Progress / Invites / Profile
    {
      order: 30,
      name: 'Progress',
      path: `/courses/${seedData.courseId}/progress`,
      auth: 'in',
      waitAny: ['text=Your Progress', 'text=Topic progress', 'text=Recommendations'],
    },
    {
      order: 40,
      name: 'Invites',
      path: '/invites',
      auth: 'in',
      waitAny: ['text=Class Invites', 'h1:has-text(\"Class Invites\")', 'text=Loading invites...', 'text=Create Invite'],
    },
    {
      order: 50,
      name: 'Profile',
      path: '/profile',
      auth: 'in',
      waitAny: ['text=Profile', 'text=Account'],
    },
  ];

  for (const shot of shots) {
    const page = shot.auth === 'out' ? loggedOutPage : loggedInPage;
    const url = `${WEB_BASE}${shot.path}`;
    const filename = `${String(shot.order).padStart(2, '0')}_${sanitize(shot.name)}.png`;
    const outPath = path.join(outDir, filename);

    process.stdout.write(`[${profile}] ${shot.name} -> ${url}\n`);

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 180000 });
    await page.waitForLoadState('networkidle', { timeout: 180000 }).catch(() => {});
    await waitForAppReady(page, shot.name, 180000);
    // Some pages render critical headers offscreen due to layout; attached is good enough for capture.
    if (shot.name === 'Topic_Study') {
      await waitForTextExists(page, 'Study Resources', 180000);
    } else {
      await waitForAnySelector(page, shot.waitAny, 180000);
    }
    await assertNoNextNotFound(page, shot.name);
    await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
    await sleep(300);
    await page.screenshot({ path: outPath, fullPage: true });
  }

  await loggedOutContext.close();
  await loggedInContext.close();
  await browser.close();
}

async function main() {
  ensureDir(OUT_ROOT);

  process.stdout.write(`[seed] Creating demo user/course/topic/resource via ${API_BASE}...\n`);
  const seedData = await seed();
  process.stdout.write(`[seed] Created ${seedData.email}, courseId=${seedData.courseId}, topicId=${seedData.topicId}\n`);

  // Desktop
  await captureProfile('desktop', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 }, seedData);

  // Mobile
  const iPhone = devices['iPhone 14'];
  await captureProfile('mobile', { ...iPhone, locale: 'en-US' }, seedData);

  process.stdout.write(`Done. Screenshots saved to ${OUT_ROOT}/{desktop|mobile}\n`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

