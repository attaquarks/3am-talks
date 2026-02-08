/**
 * Validate sign-up and sign-in through the FRONTEND origin (Vite proxy -> backend).
 * Run: node frontend/scripts/validate-signin.mjs
 * Ensure frontend dev server is running (npm run dev) and backend on 5050.
 */

const PORTS = [5173, 5174];
const EMAIL = `validate-${Date.now()}@example.com`;
const PASSWORD = 'ValidateSignIn123!';
const NAME = 'Validation User';

function getCookie(headers) {
  const setCookie = headers.get('set-cookie');
  if (!setCookie) return null;
  const first = setCookie.split(',')[0].split(';')[0].trim();
  return first || null;
}

async function request(base, method, path, body = null, cookie = null) {
  const url = `${base}${path}`;
  const headers = { 'Content-Type': 'application/json' };
  if (cookie) headers['Cookie'] = cookie;
  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    redirect: 'manual',
  });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_) {}
  return { status: res.status, data, headers: res.headers, cookie: getCookie(res.headers) || cookie };
}

async function run(base) {
  console.log(`Validating via frontend at ${base}`);
  let cookie = null;

  // 1) Register
  console.log('1. POST /api/register ...');
  let r = await request(base, 'POST', '/api/register', { email: EMAIL, password: PASSWORD, name: NAME }, null);
  cookie = r.cookie || cookie;
  if (r.status !== 200) {
    console.log(`   FAIL: register returned ${r.status}:`, r.data);
    return 1;
  }
  console.log(`   OK: user id=${r.data?.id ?? '?'}`);

  // 2) GET /api/user
  console.log('2. GET /api/user (with session cookie) ...');
  r = await request(base, 'GET', '/api/user', null, cookie);
  cookie = r.cookie || cookie;
  if (r.status !== 200) {
    console.log(`   FAIL: /api/user after register returned ${r.status}:`, r.data);
    return 1;
  }
  console.log(`   OK: ${r.data?.email}`);

  // 3) Logout
  console.log('3. POST /api/logout ...');
  r = await request(base, 'POST', '/api/logout', null, cookie);
  cookie = r.cookie || cookie;
  console.log('   OK');

  // 4) Login
  console.log('4. POST /api/login ...');
  r = await request(base, 'POST', '/api/login', { email: EMAIL, password: PASSWORD }, cookie);
  cookie = r.cookie || cookie;
  if (r.status !== 200) {
    console.log(`   FAIL: login returned ${r.status}:`, r.data);
    return 1;
  }
  console.log(`   OK: user id=${r.data?.id}`);

  // 5) GET /api/user after login
  console.log('5. GET /api/user (after login) ...');
  r = await request(base, 'GET', '/api/user', null, cookie);
  if (r.status !== 200) {
    console.log(`   FAIL: /api/user after login returned ${r.status}:`, r.data);
    return 1;
  }
  console.log(`   OK: ${r.data?.email}`);

  console.log('\nAll checks passed. Frontend sign-up and sign-in are working.');
  return 0;
}

(async () => {
  for (const port of PORTS) {
    const base = `http://localhost:${port}`;
    try {
      const r = await fetch(`${base}/`, { method: 'HEAD', redirect: 'manual' });
      if (r.status === 200 || r.status === 304) {
        const code = await run(base);
        process.exit(code);
      }
    } catch (_) {}
  }
  console.error('Frontend not reachable on 5173 or 5174. Start it with: cd frontend && npm run dev');
  process.exit(1);
})();
