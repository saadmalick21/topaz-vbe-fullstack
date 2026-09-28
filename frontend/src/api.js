/* API layer for the Topaz-VBE replica.
   Base '/api' (proxied to the backend by vite in dev, nginx in prod).
   Set VITE_API_URL at build time to point at a remote backend
   (e.g. https://topaz-vbe-api.onrender.com/api). Falls back to '/api'.
   JWT is attached from localStorage ('topaz_token' for teams,
   'topaz_admin_token' for admins). JSON in/out.
   Throws { status, body } on HTTP error. */

const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

export function getToken() {
  return localStorage.getItem('topaz_token');
}

export function getAdminToken() {
  return localStorage.getItem('topaz_admin_token');
}

export async function apiFetch(path, opts = {}) {
  const { method = 'GET', body, admin = false } = opts;
  const token = admin ? getAdminToken() : getToken();
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = 'Bearer ' + token;

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (e) {
    data = null;
  }

  if (!res.ok) {
    // Session died (or token revoked): drop credentials and go home.
    // Not applied to login calls (they carry no token; 401 there is expected).
    if (res.status === 401 && token) {
      localStorage.removeItem('topaz_token');
      localStorage.removeItem('topaz_admin_token');
      localStorage.removeItem('topaz_auth');
      if (window.location.hash !== '#/') window.location.hash = '#/';
    }
    throw { status: res.status, body: data };
  }
  return data;
}

/* ---------- team auth ---------- */

export async function loginTeam(creds) {
  const res = await apiFetch('/auth/login', { method: 'POST', body: creds });
  localStorage.setItem('topaz_token', res.token);
  return res; // { token, role, team, industry }
}

export async function loginAdmin(creds) {
  const res = await apiFetch('/auth/admin-login', { method: 'POST', body: creds });
  localStorage.setItem('topaz_admin_token', res.token);
  return res; // { token, role }
}

export function logoutTeam() {
  localStorage.removeItem('topaz_token');
  localStorage.removeItem('topaz_auth');
}

export function logoutAdmin() {
  localStorage.removeItem('topaz_admin_token');
  localStorage.removeItem('topaz_admin_auth');
}

/* ---------- team endpoints ---------- */

export const me = () => apiFetch('/me');
export const quarters = () => apiFetch('/quarters');

export const getDecisions = () => apiFetch('/decisions/current');
export const saveDecisions = (data) =>
  apiFetch('/decisions/current', { method: 'PUT', body: { data } });
export const resetDecisions = () =>
  apiFetch('/decisions/current/reset', { method: 'POST' });
export const submitDecisions = () =>
  apiFetch('/decisions/current/submit', { method: 'POST' });

export const getReport = (year, quarter) =>
  apiFetch(`/reports?year=${encodeURIComponent(year)}&quarter=${encodeURIComponent(quarter)}`);

export const getTables = () => apiFetch('/tables');

/* ---------- admin endpoints ---------- */

const adminFetch = (path, opts = {}) => apiFetch(path, { ...opts, admin: true });

export const adminIndustries = () => adminFetch('/admin/industries');
export const adminCreateIndustry = (payload) =>
  adminFetch('/admin/industries', { method: 'POST', body: payload });
export const adminIndustryDetail = (id) => adminFetch(`/admin/industries/${id}`);
export const adminCreateTeam = (id, payload) =>
  adminFetch(`/admin/industries/${id}/teams`, { method: 'POST', body: payload });
export const adminOpenQuarter = (id, payload) =>
  adminFetch(`/admin/industries/${id}/quarters`, { method: 'POST', body: payload });
export const adminSetShock = (id, payload) =>
  adminFetch(`/admin/industries/${id}/shocks`, { method: 'POST', body: payload });
export const adminRollStatus = (id) =>
  adminFetch(`/admin/industries/${id}/roll-status`);
export const adminRollQuarter = (id, force) =>
  adminFetch(`/admin/industries/${id}/roll-quarter`, {
    method: 'POST',
    body: { force: !!force },
  });
export const adminAuditLog = () => adminFetch('/admin/audit');
