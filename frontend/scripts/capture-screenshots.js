/**
 * Capture current NotesOS UI screenshots for Stitch redesign mode.
 *
 * Outputs into: <repoRoot>/design/current-screens/{desktop|mobile}
 *
 * Assumptions:
 * - Frontend is running at http://localhost:3000
 * - Backend is running at http://localhost:8000
 * - We can register a throwaway user via /api/auth/register
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { chromium, devices } from 'playwright';

const WEB_BASE = process.env.NOTESOS_WEB_BASE || 'http://localhost:3000';
const API_BASE = process.env.NOTESOS_API_BASE || 'http://localhost:8000';

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

  const { user, access_token, refresh_token } = register;

  // Seed minimal content so dynamic routes render.
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
  if (!courseId) throw new Error(`Could not read courseId from response: ${JSON.stringify(course).slice(0, 500)}`);

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
  if (!topicId) throw new Error(`Could not read topicId from response: ${JSON.stringify(topic).slice(0, 500)}`);

  await apiFetch(`/api/topics/${topicId}/resources/text`, {
    method: 'POST',
    token: access_token,
    json: {
      topic_id: topicId,
      title: 'Seed Note',
      content:
        'These are seeded notes used to capture UI screenshots for Stitch.\\n\\n- Minimal layout\\n- Clear hierarchy\\n- Intentional spacing\\n',
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
    console.warn(`[seed] Could not create invite (continuing)`);
  }

  return { user, access_token, refresh_token, courseId, topicId, email, password };
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function sanitize(name) {
  return name.replace(/[^a-z0-9-_]+/gi, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '');
}

async function captureForProfile(profile, ctxConfig, shots, seedData) {
  const outRoot = path.resolve(import.meta.dirname, '..', '..', 'design', 'current-screens', profile);
  ensureDir(outRoot);

  const browser = await chromium.launch({ headless: true });
  const loggedOutContext = await browser.newContext(ctxConfig);
  const loggedInContext = await browser.newContext(ctxConfig);

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

  // Stabilize animations/transitions as much as we can.
  await loggedOutContext.addInitScript(stabilizationScript);
  await loggedInContext.addInitScript(stabilizationScript);

  // Auth storage for protected routes (logged-in context only)
  await loggedInContext.addInitScript(({ authPersistValue, accessToken, refreshToken }) => {
    localStorage.setItem('notesos_access_token', accessToken);
    localStorage.setItem('notesos_refresh_token', refreshToken);
    localStorage.setItem('notesos-auth', authPersistValue);
  }, {
    authPersistValue: JSON.stringify({ state: { user: seedData.user, isAuthenticated: true }, version: 0 }),
    accessToken: seedData.access_token,
    refreshToken: seedData.refresh_token,
  });

  const loggedOutPage = await loggedOutContext.newPage();
  const loggedInPage = await loggedInContext.newPage();
  loggedOutPage.setDefaultNavigationTimeout(120000);
  loggedInPage.setDefaultNavigationTimeout(120000);
  loggedOutPage.setDefaultTimeout(60000);
  loggedInPage.setDefaultTimeout(60000);

  for (const shot of shots) {
    const filename = `${String(shot.order).padStart(2, '0')}_${sanitize(shot.name)}.png`;
    const outPath = path.join(outRoot, filename);

    const page = shot.auth === 'logged_out' ? loggedOutPage : loggedInPage;

    const url = `${WEB_BASE}${shot.path}`;
    console.log(`[${profile}] ${shot.name} -> ${url}`);

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
    // Let client components hydrate and fetch.
    await sleep(1500);

    // Wait for a stable element when provided (reduces flakiness on cold compile).
    if (shot.waitFor) {
      try {
        await page.waitForSelector(shot.waitFor, { timeout: 90000 });
      } catch {
        console.warn(`[${profile}] waitFor selector timed out for ${shot.name}: ${shot.waitFor}`);
      }
    }

    // Some pages have sticky headers; scroll a tiny bit to trigger layout settle.
    try {
      await page.evaluate(() => window.scrollTo(0, 0));
    } catch { }
    await sleep(300);

    await page.screenshot({ path: outPath, fullPage: true });
  }

  await loggedOutContext.close();
  await loggedInContext.close();
  await browser.close();
}

async function main() {
  console.log('[seed] Creating demo user/course/topic/resource...');
  const seedData = await seed();
  console.log(`[seed] Created user ${seedData.email}, courseId=${seedData.courseId}, topicId=${seedData.topicId}`);

  const fakeTestId = crypto.randomUUID();
  const fakeAttemptId = crypto.randomUUID();

  const shots = [
    { order: 1, name: 'Root', path: '/' },
    { order: 2, name: 'Login', path: '/login', auth: 'logged_out' },
    { order: 3, name: 'Register', path: '/register', auth: 'logged_out' },

    { order: 10, name: 'Courses_List', path: '/courses' },
    { order: 11, name: 'Courses_New', path: '/courses/new' },
    { order: 12, name: 'Courses_Join', path: '/courses/join' },
    { order: 13, name: 'Course_Home', path: `/courses/${seedData.courseId}` },
    { order: 14, name: 'Topic_Study', path: `/courses/${seedData.courseId}/topics/${seedData.topicId}` },

    { order: 20, name: 'Tests_List', path: `/courses/${seedData.courseId}/tests` },
    { order: 21, name: 'Tests_Take_NotFound', path: `/courses/${seedData.courseId}/tests/${fakeTestId}` },
    { order: 22, name: 'Tests_Results_NotFound', path: `/courses/${seedData.courseId}/tests/${fakeTestId}/results?attemptId=${fakeAttemptId}` },

    { order: 30, name: 'Progress', path: `/courses/${seedData.courseId}/progress` },
    { order: 40, name: 'Invites', path: '/invites' },
    { order: 50, name: 'Profile', path: '/profile' },
  ];

  // Desktop
  await captureForProfile(
    'desktop',
    {
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    },
    shots,
    seedData
  );

  // Mobile (iPhone 14-ish)
  const iPhone = devices['iPhone 14'];
  await captureForProfile(
    'mobile',
    {
      ...iPhone,
      locale: 'en-US',
    },
    shots,
    seedData
  );

  console.log('Done. Screenshots saved to design/current-screens/{desktop|mobile}');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

