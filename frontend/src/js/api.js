// ═══════════════════════════════════════════════════════════
// API Client
// ═══════════════════════════════════════════════════════════

const BASE = '/api/v1';

let _token = localStorage.getItem('token');

export function setToken(token) {
  _token = token;
  if (token) localStorage.setItem('token', token);
  else localStorage.removeItem('token');
}

export function getToken() { return _token; }

export function isAuthenticated() { return !!_token; }

async function request(method, path, body = null, isFormData = false) {
  const headers = {};
  if (_token) headers['Authorization'] = `Bearer ${_token}`;
  if (body && !isFormData) headers['Content-Type'] = 'application/json';

  const opts = { method, headers };
  if (body) opts.body = isFormData ? body : JSON.stringify(body);

  const res = await fetch(`${BASE}${path}`, opts);

  if (res.status === 401) {
    setToken(null);
    window.location.hash = '#/login';
    throw new Error('Unauthorized');
  }

  if (res.status === 204) return null;

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// Auth
export const auth = {
  register: (body) => request('POST', '/auth/register', body),
  login: (body) => request('POST', '/auth/login', body),
  me: () => request('GET', '/auth/me'),
};

// Projects
export const projects = {
  list: () => request('GET', '/projects'),
  get: (id) => request('GET', `/projects/${id}`),
  create: (body) => request('POST', '/projects', body),
  update: (id, body) => request('PATCH', `/projects/${id}`, body),
  delete: (id) => request('DELETE', `/projects/${id}`),
  members: (id) => request('GET', `/projects/${id}/members`),
  addMember: (id, body) => request('POST', `/projects/${id}/members`, body),
  prompts: (id) => request('GET', `/projects/${id}/prompts`),
  createPrompt: (id, body) => request('POST', `/projects/${id}/prompts`, body),
};

// Media
export const media = {
  list: (pid, params = '') => request('GET', `/projects/${pid}/media${params ? '?' + params : ''}`),
  get: (pid, mid) => request('GET', `/projects/${pid}/media/${mid}`),
  getUrl: (pid, mid) => request('GET', `/projects/${pid}/media/${mid}/url`),
  update: (pid, mid, body) => request('PATCH', `/projects/${pid}/media/${mid}`, body),
  delete: (pid, mid) => request('DELETE', `/projects/${pid}/media/${mid}`),
  upload: (pid, files) => {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    return request('POST', `/projects/${pid}/media/upload`, fd, true);
  },
  bulk: (pid, body) => request('POST', `/projects/${pid}/media/bulk`, body),
  addSource: (pid, mid, body) => request('POST', `/projects/${pid}/media/${mid}/sources`, body),
  sources: (pid, mid) => request('GET', `/projects/${pid}/media/${mid}/sources`),
};

// Datasets
export const datasets = {
  list: (pid) => request('GET', `/projects/${pid}/datasets`),
  get: (pid, did) => request('GET', `/projects/${pid}/datasets/${did}`),
  create: (pid, body) => request('POST', `/projects/${pid}/datasets`, body),
  update: (pid, did, body) => request('PATCH', `/projects/${pid}/datasets/${did}`, body),
  delete: (pid, did) => request('DELETE', `/projects/${pid}/datasets/${did}`),
  addItems: (pid, did, body) => request('POST', `/projects/${pid}/datasets/${did}/items`, body),
  listItems: (pid, did, params = '') => request('GET', `/projects/${pid}/datasets/${did}/items${params ? '?' + params : ''}`),
  createAnnotation: (pid, did, iid, body) => request('POST', `/projects/${pid}/datasets/${did}/items/${iid}/annotations`, body),
  listAnnotations: (pid, did, iid) => request('GET', `/projects/${pid}/datasets/${did}/items/${iid}/annotations`),
  createVersion: (pid, did, body) => request('POST', `/projects/${pid}/datasets/${did}/versions`, body),
  listVersions: (pid, did) => request('GET', `/projects/${pid}/datasets/${did}/versions`),
};

// Search
export const search = {
  query: (pid, body) => request('POST', `/projects/${pid}/search`, body),
  similar: (pid, body) => request('POST', `/projects/${pid}/search/similar`, body),
};

// Indexing
export const indexing = {
  run: (pid, body) => request('POST', `/projects/${pid}/indexing/run`, body),
  status: (pid) => request('GET', `/projects/${pid}/indexing/status`),
};
