// Backend base URL:
// 1) If window.STEM_API_BASE is set, use it.
// 2) If served from backend/reverse proxy (:5000, :443, :80), use relative /api.
// 3) Otherwise (Live Server, file://), use this device hostname on port 5000.
let API_BASE = '/api';
const ADMIN_TOKEN_KEY = "stem_admin_token";
const USER_TOKEN_KEY = "stem_user_token";
try {
  const override = window.STEM_API_BASE;
  if (override) {
    API_BASE = String(override).replace(/\/+$/, '');
  }
  const origin = window.location && window.location.origin ? window.location.origin : '';
  const hostname = window.location && window.location.hostname ? window.location.hostname : '';
  const protocol = window.location && window.location.protocol ? window.location.protocol : 'http:';
  const port = window.location && window.location.port ? window.location.port : '';
  const likelySameOriginBackend = protocol !== 'file:' && (port === '' || port === '5000' || port === '443' || port === '80');
  if (!override && !likelySameOriginBackend) {
    const fallbackProtocol = protocol === 'https:' ? 'https:' : 'http:';
    API_BASE = hostname ? `${fallbackProtocol}//${hostname}:5000/api` : 'http://localhost:5000/api';
  }
} catch (e) {
  API_BASE = 'http://localhost:5000/api';
}

function getAdminToken() {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY) || "";
  } catch (e) {
    return "";
  }
}

function getUserToken() {
  try {
    return localStorage.getItem(USER_TOKEN_KEY) || "";
  } catch (e) {
    return "";
  }
}

function setAdminToken(token) {
  try {
    if (token) {
      localStorage.setItem(ADMIN_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(ADMIN_TOKEN_KEY);
    }
  } catch (e) {
    // ignore storage errors
  }
}

function setUserToken(token) {
  try {
    if (token) {
      localStorage.setItem(USER_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(USER_TOKEN_KEY);
    }
  } catch (e) {
    // ignore storage errors
  }
}

function buildAuthHeaders(headers) {
  const token = getAdminToken();
  if (!token) return headers || {};
  return Object.assign({}, headers || {}, { Authorization: `Bearer ${token}` });
}

function buildUserHeaders(headers) {
  const token = getUserToken();
  if (!token) return headers || {};
  return Object.assign({}, headers || {}, { Authorization: `Bearer ${token}` });
}

function buildAnyAuthHeaders(headers) {
  const userToken = getUserToken();
  if (userToken) {
    return Object.assign({}, headers || {}, { Authorization: `Bearer ${userToken}` });
  }
  return buildAuthHeaders(headers);
}

async function uploadImage(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API_BASE}/images`, {
    method: 'POST',
    headers: buildUserHeaders(),
    body: fd
  });
  if (res.status === 401 || res.status === 403) throw new Error('Please sign in');
  if (!res.ok) throw new Error('Upload failed');
  return res.json(); // { image_id, image_url }
}

async function createJob(imageId) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: buildUserHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ image_id: imageId })
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error('Please sign in');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to create job');
  }
  return res.json(); // { job_id }
}

async function listJobs() {
  const res = await fetch(`${API_BASE}/jobs`, { headers: buildUserHeaders() });
  if (res.status === 401 || res.status === 403) {
    throw new Error('Please sign in');
  }
  if (!res.ok) return [];
  return res.json();
}

async function getJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`, {
    headers: buildUserHeaders(),
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error('Please sign in');
  }
  if (!res.ok) return null;
  return res.json();
}

async function clearAllHistory() {
  const res = await fetch(`${API_BASE}/admin/clear-history`, {
    method: 'DELETE',
    headers: buildAuthHeaders(),
  });
  if (!res.ok) throw new Error(res.status === 401 ? 'Unauthorized' : 'Failed to clear history');
  return res.json();
}

async function getAdminStats() {
  const res = await fetch(`${API_BASE}/admin/stats`, { headers: buildAuthHeaders() });
  if (!res.ok) throw new Error(res.status === 401 ? 'Unauthorized' : 'Failed to load stats');
  return res.json();
}

async function adminListUsers() {
  const res = await fetch(`${API_BASE}/admin/users`, { headers: buildAuthHeaders() });
  if (!res.ok) throw new Error(res.status === 401 ? 'Unauthorized' : 'Failed to load users');
  return res.json();
}

async function adminRegisterUser(username, password, isAdmin) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ username, password, is_admin: !!isAdmin }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    if (res.status === 409) throw new Error('Username already exists');
    throw new Error('Failed to create user');
  }
  return res.json();
}

async function adminDeleteUser(userId) {
  const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
    headers: buildAuthHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    if (res.status === 409) throw new Error('Cannot delete admin users');
    throw new Error('Failed to delete user');
  }
  return res.json();
}

async function adminLogin(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Invalid credentials');
    throw new Error('Login request failed');
  }
  const data = await res.json();
  setAdminToken(data.access_token || '');
  return data;
}

function adminLogout() {
  setAdminToken('');
}

async function userLogin(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Invalid credentials');
    throw new Error('Login request failed');
  }
  const data = await res.json();
  setUserToken(data.access_token || '');
  return data;
}

function userLogout() {
  setUserToken('');
}

async function deleteJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
    headers: buildUserHeaders(),
  });
  if (!res.ok) throw new Error(res.status === 401 ? 'Please sign in' : 'Failed to delete job');
  return res.json();
}
