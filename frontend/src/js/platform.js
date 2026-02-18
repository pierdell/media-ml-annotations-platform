// ═══════════════════════════════════════════════════════════
// Index Factory - Platform Dashboard (SPA)
// ═══════════════════════════════════════════════════════════

import * as api from './api.js';

const $ = (s, p = document) => p.querySelector(s);
const $$ = (s, p = document) => [...p.querySelectorAll(s)];
const app = () => $('#app');

let currentUser = null;
let currentProject = null;

// ═══════════════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════════════
const routes = {
  '/login': renderLogin,
  '/register': renderRegister,
  '/projects': renderProjects,
  '/projects/:id': renderProjectDashboard,
  '/projects/:id/media': renderMediaLibrary,
  '/projects/:id/datasets': renderDatasets,
  '/projects/:id/datasets/:did': renderDatasetDetail,
  '/projects/:id/search': renderSearch,
  '/projects/:id/settings': renderProjectSettings,
};

function navigate(hash) {
  window.location.hash = hash;
}

function matchRoute(hash) {
  const path = hash.replace('#', '') || '/projects';
  for (const [pattern, handler] of Object.entries(routes)) {
    const regex = new RegExp('^' + pattern.replace(/:(\w+)/g, '([^/]+)') + '$');
    const match = path.match(regex);
    if (match) return { handler, params: match.slice(1) };
  }
  return { handler: renderProjects, params: [] };
}

async function handleRoute() {
  if (!api.isAuthenticated() && !window.location.hash.match(/#\/(login|register)/)) {
    navigate('/login');
    return;
  }

  if (api.isAuthenticated() && !currentUser) {
    try {
      currentUser = await api.auth.me();
    } catch {
      api.setToken(null);
      navigate('/login');
      return;
    }
  }

  const { handler, params } = matchRoute(window.location.hash);
  try {
    await handler(...params);
  } catch (err) {
    console.error('Route error:', err);
    toast(err.message, 'error');
  }
}

window.addEventListener('hashchange', handleRoute);
window.addEventListener('DOMContentLoaded', () => {
  if (!window.location.hash) window.location.hash = '#/projects';
  handleRoute();
});

// ═══════════════════════════════════════════════════════════
// Icons (inline SVG)
// ═══════════════════════════════════════════════════════════
const icons = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
  database: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
  brain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2z"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>',
  music: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  fileText: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
  logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
};

const typeIcon = (type) => ({ image: icons.image, video: icons.video, audio: icons.music, text: icons.fileText }[type] || icons.fileText);

// ═══════════════════════════════════════════════════════════
// Shell Layout
// ═══════════════════════════════════════════════════════════
function shell(projectId, activeNav, content) {
  const navItems = [
    { id: 'dashboard', icon: icons.home, label: 'Dashboard', href: `#/projects/${projectId}` },
    { id: 'media', icon: icons.image, label: 'Media Library', href: `#/projects/${projectId}/media` },
    { id: 'datasets', icon: icons.database, label: 'Datasets', href: `#/projects/${projectId}/datasets` },
    { id: 'search', icon: icons.search, label: 'Search', href: `#/projects/${projectId}/search` },
    { id: 'settings', icon: icons.settings, label: 'Settings', href: `#/projects/${projectId}/settings` },
  ];

  const initial = currentUser ? currentUser.full_name.charAt(0).toUpperCase() : '?';

  return `
    <div class="shell">
      <aside class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-logo"><span>Index</span>Factory</div>
        </div>
        <nav class="sidebar-nav">
          <div class="nav-section-label">Project</div>
          ${navItems.map(n => `
            <a class="nav-item ${activeNav === n.id ? 'active' : ''}" href="${n.href}">
              ${n.icon} ${n.label}
            </a>
          `).join('')}
          <div class="nav-section-label">Tools</div>
          <a class="nav-item" href="/annotator/" target="_blank">
            ${icons.edit} Annotation Tool
          </a>
          <a class="nav-item" href="#/projects">
            ${icons.folder} All Projects
          </a>
        </nav>
        <div class="sidebar-footer">
          <div class="user-info" onclick="document.dispatchEvent(new Event('logout'))">
            <div class="user-avatar">${initial}</div>
            <div>
              <div class="user-name">${currentUser?.full_name || 'User'}</div>
              <div class="user-email">${currentUser?.email || ''}</div>
            </div>
          </div>
        </div>
      </aside>
      <div class="main-content">${content}</div>
    </div>
  `;
}

document.addEventListener('logout', () => {
  api.setToken(null);
  currentUser = null;
  navigate('/login');
});

// ═══════════════════════════════════════════════════════════
// Pages
// ═══════════════════════════════════════════════════════════

// ── Login ─────────────────────────────────────────────────
async function renderLogin() {
  app().innerHTML = `
    <div class="login-page">
      <div class="login-card">
        <div class="login-title"><span style="color:var(--accent-light)">Index</span>Factory</div>
        <div class="login-subtitle">ML Dataset Creation Platform</div>
        <form id="loginForm">
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-input" type="email" id="loginEmail" required placeholder="admin@indexfactory.local" value="admin@indexfactory.local">
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input class="form-input" type="password" id="loginPassword" required placeholder="Password">
          </div>
          <button class="btn btn-primary" style="width:100%;justify-content:center;margin-top:8px" type="submit">Sign In</button>
          <p style="text-align:center;margin-top:16px;font-size:12px;color:var(--text-2)">
            Don't have an account? <a href="#/register">Register</a>
          </p>
        </form>
      </div>
    </div>
  `;

  $('#loginForm').onsubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await api.auth.login({
        email: $('#loginEmail').value,
        password: $('#loginPassword').value,
      });
      api.setToken(res.access_token);
      currentUser = res.user;
      navigate('/projects');
    } catch (err) {
      toast(err.message, 'error');
    }
  };
}

// ── Register ──────────────────────────────────────────────
async function renderRegister() {
  app().innerHTML = `
    <div class="login-page">
      <div class="login-card">
        <div class="login-title">Create Account</div>
        <div class="login-subtitle">Join the ML Dataset Creation Platform</div>
        <form id="regForm">
          <div class="form-group">
            <label class="form-label">Full Name</label>
            <input class="form-input" id="regName" required placeholder="Your name">
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-input" type="email" id="regEmail" required placeholder="you@company.com">
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input class="form-input" type="password" id="regPassword" required minlength="8" placeholder="Min 8 characters">
          </div>
          <button class="btn btn-primary" style="width:100%;justify-content:center;margin-top:8px" type="submit">Create Account</button>
          <p style="text-align:center;margin-top:16px;font-size:12px;color:var(--text-2)">
            Already have an account? <a href="#/login">Sign in</a>
          </p>
        </form>
      </div>
    </div>
  `;

  $('#regForm').onsubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await api.auth.register({
        full_name: $('#regName').value,
        email: $('#regEmail').value,
        password: $('#regPassword').value,
      });
      api.setToken(res.access_token);
      currentUser = res.user;
      navigate('/projects');
    } catch (err) {
      toast(err.message, 'error');
    }
  };
}

// ── Projects List ─────────────────────────────────────────
async function renderProjects() {
  app().innerHTML = `<div class="main-content" style="max-width:1000px;margin:0 auto;padding:40px 24px">
    <div class="section-header">
      <div><div class="page-title">Projects</div><div style="color:var(--text-2);font-size:13px;margin-top:4px">Your ML dataset workspaces</div></div>
      <button class="btn btn-primary" id="btnNewProject">${icons.plus} New Project</button>
    </div>
    <div id="projectsList" style="margin-top:20px">Loading...</div>
  </div>`;

  const projectsList = await api.projects.list();
  const container = $('#projectsList');

  if (projectsList.length === 0) {
    container.innerHTML = `<div class="empty-state">${icons.folder}<h3>No projects yet</h3><p>Create your first project to start building ML datasets.</p></div>`;
  } else {
    container.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px">
      ${projectsList.map(p => `
        <div class="card" style="cursor:pointer" onclick="location.hash='#/projects/${p.id}'">
          <div class="card-body">
            <div style="font-size:16px;font-weight:600;color:var(--text-0)">${esc(p.name)}</div>
            <div style="font-size:12px;color:var(--text-2);margin-top:4px">${esc(p.description || 'No description')}</div>
            <div style="display:flex;gap:16px;margin-top:16px">
              <div><span style="font-weight:700;color:var(--text-0)">${p.media_count}</span> <span style="font-size:11px;color:var(--text-2)">media</span></div>
              <div><span style="font-weight:700;color:var(--text-0)">${p.dataset_count}</span> <span style="font-size:11px;color:var(--text-2)">datasets</span></div>
              <div><span style="font-weight:700;color:var(--text-0)">${p.member_count}</span> <span style="font-size:11px;color:var(--text-2)">members</span></div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>`;
  }

  $('#btnNewProject').onclick = () => showCreateProjectModal();
}

// ── Project Dashboard ─────────────────────────────────────
async function renderProjectDashboard(projectId) {
  const project = await api.projects.get(projectId);
  currentProject = project;

  let indexingStats = { total_media: 0, indexed: 0, pending: 0, processing: 0, failed: 0 };
  try { indexingStats = await api.indexing.status(projectId); } catch {}

  const pct = indexingStats.total_media > 0 ? Math.round((indexingStats.indexed / indexingStats.total_media) * 100) : 0;

  app().innerHTML = shell(projectId, 'dashboard', `
    <div class="topbar">
      <div class="topbar-left"><div class="page-title">${esc(project.name)}</div></div>
      <div class="topbar-right">
        <button class="btn btn-sm" onclick="location.hash='#/projects/${projectId}/media'">${icons.upload} Upload Media</button>
      </div>
    </div>
    <div class="page-content">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--accent-bg);color:var(--accent-light)">${icons.image}</div>
          <div class="stat-label">Total Media</div>
          <div class="stat-value">${indexingStats.total_media}</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--green-bg);color:var(--green)">${icons.brain}</div>
          <div class="stat-label">Indexed</div>
          <div class="stat-value">${indexingStats.indexed}</div>
          <div class="stat-sub">${pct}% complete</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--yellow-bg);color:var(--yellow)">${icons.database}</div>
          <div class="stat-label">Datasets</div>
          <div class="stat-value">${project.dataset_count}</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--blue-bg);color:var(--blue)">${icons.folder}</div>
          <div class="stat-label">Pending / Failed</div>
          <div class="stat-value">${indexingStats.pending + indexingStats.failed}</div>
          ${indexingStats.processing > 0 ? `<div class="stat-sub"><span class="indexing-dot processing"></span> ${indexingStats.processing} processing</div>` : ''}
        </div>
      </div>

      <div style="margin-top:24px">
        <div class="section-header">
          <div class="section-title">Indexing Progress</div>
          ${indexingStats.pending > 0 ? `<button class="btn btn-sm btn-primary" id="btnRunIndex">${icons.play} Run Indexing</button>` : ''}
        </div>
        <div class="progress-bar" style="margin-top:8px">
          <div class="progress-bar-fill" style="width:${pct}%;background:var(--green)"></div>
        </div>
        <div style="display:flex;gap:16px;margin-top:8px;font-size:12px;color:var(--text-2)">
          <span><span class="indexing-dot completed"></span> Completed: ${indexingStats.indexed}</span>
          <span><span class="indexing-dot pending"></span> Pending: ${indexingStats.pending}</span>
          <span><span class="indexing-dot processing"></span> Processing: ${indexingStats.processing}</span>
          <span><span class="indexing-dot failed"></span> Failed: ${indexingStats.failed}</span>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px">
        <div class="card" style="cursor:pointer" onclick="location.hash='#/projects/${projectId}/media'">
          <div class="card-body" style="text-align:center;padding:32px">
            <div style="color:var(--accent-light);margin-bottom:12px">${icons.image}</div>
            <div style="font-size:15px;font-weight:600;color:var(--text-0)">Media Library</div>
            <div style="font-size:12px;color:var(--text-2);margin-top:4px">Upload, browse, and manage media</div>
          </div>
        </div>
        <div class="card" style="cursor:pointer" onclick="location.hash='#/projects/${projectId}/search'">
          <div class="card-body" style="text-align:center;padding:32px">
            <div style="color:var(--accent-light);margin-bottom:12px">${icons.search}</div>
            <div style="font-size:15px;font-weight:600;color:var(--text-0)">Semantic Search</div>
            <div style="font-size:12px;color:var(--text-2);margin-top:4px">CLIP + text hybrid search</div>
          </div>
        </div>
      </div>
    </div>
  `);

  const runBtn = $('#btnRunIndex');
  if (runBtn) {
    runBtn.onclick = async () => {
      try {
        await api.indexing.run(projectId, { pipelines: ['clip', 'dino', 'vlm', 'text'] });
        toast('Indexing started', 'success');
        setTimeout(() => renderProjectDashboard(projectId), 2000);
      } catch (err) { toast(err.message, 'error'); }
    };
  }
}

// ── Media Library ─────────────────────────────────────────
async function renderMediaLibrary(projectId) {
  const project = await api.projects.get(projectId);
  currentProject = project;

  app().innerHTML = shell(projectId, 'media', `
    <div class="topbar">
      <div class="topbar-left"><div class="page-title">Media Library</div></div>
      <div class="topbar-right">
        <div class="search-bar" style="width:250px">
          ${icons.search}
          <input id="mediaSearch" placeholder="Search media...">
        </div>
        <button class="btn btn-primary" id="btnUpload">${icons.upload} Upload</button>
      </div>
    </div>
    <div class="tabs">
      <div class="tab active" data-filter="">All</div>
      <div class="tab" data-filter="image">Images</div>
      <div class="tab" data-filter="video">Videos</div>
      <div class="tab" data-filter="audio">Audio</div>
      <div class="tab" data-filter="text">Text</div>
    </div>
    <div id="mediaContent">
      <div class="media-grid" id="mediaGrid">Loading...</div>
    </div>
    <input type="file" id="fileInput" multiple accept="image/*,video/*,audio/*" style="display:none">
  `);

  let currentFilter = '';
  async function loadMedia(filter = '', search = '') {
    const params = new URLSearchParams();
    if (filter) params.set('media_type', filter);
    if (search) params.set('search', search);
    params.set('per_page', '100');

    const data = await api.media.list(projectId, params.toString());
    const grid = $('#mediaGrid');

    if (data.items.length === 0) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        ${icons.image}<h3>No media found</h3><p>Upload images, videos, or audio files to get started.</p>
      </div>`;
      return;
    }

    grid.innerHTML = data.items.map(m => `
      <div class="media-card" data-id="${m.id}">
        <div class="media-thumb">
          ${m.thumbnail_url ? `<img src="${m.thumbnail_url}" alt="" loading="lazy">` : typeIcon(m.media_type)}
        </div>
        <div class="media-card-info">
          <div class="media-card-name">${esc(m.original_filename)}</div>
          <div class="media-card-meta">
            <span>${m.media_type}</span>
            <span>${m.width && m.height ? `${m.width}x${m.height}` : formatSize(m.file_size)}</span>
          </div>
        </div>
        <div class="media-card-badge">
          <span class="indexing-dot ${m.indexing_status}" title="${m.indexing_status}"></span>
        </div>
      </div>
    `).join('');
  }

  await loadMedia();

  // Tab filtering
  $$('.tab').forEach(tab => {
    tab.onclick = () => {
      $$('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentFilter = tab.dataset.filter;
      loadMedia(currentFilter, $('#mediaSearch').value);
    };
  });

  // Search
  let searchTimeout;
  $('#mediaSearch').oninput = (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadMedia(currentFilter, e.target.value), 300);
  };

  // Upload
  const fileInput = $('#fileInput');
  $('#btnUpload').onclick = () => fileInput.click();
  fileInput.onchange = async (e) => {
    if (e.target.files.length === 0) return;
    try {
      toast('Uploading...', 'success');
      await api.media.upload(projectId, e.target.files);
      toast(`Uploaded ${e.target.files.length} file(s)`, 'success');
      e.target.value = '';
      await loadMedia(currentFilter);
    } catch (err) {
      toast(err.message, 'error');
    }
  };
}

// ── Datasets ──────────────────────────────────────────────
async function renderDatasets(projectId) {
  const project = await api.projects.get(projectId);
  currentProject = project;
  const datasetsList = await api.datasets.list(projectId);

  const typeLabels = {
    image_classification: 'Image Classification',
    object_detection: 'Object Detection',
    instance_segmentation: 'Instance Segmentation',
    semantic_segmentation: 'Semantic Segmentation',
    image_captioning: 'Image Captioning',
    video_classification: 'Video Classification',
    video_object_tracking: 'Video Object Tracking',
    audio_classification: 'Audio Classification',
    speech_recognition: 'Speech Recognition',
    text_classification: 'Text Classification',
    ner: 'NER',
    custom: 'Custom',
  };

  app().innerHTML = shell(projectId, 'datasets', `
    <div class="topbar">
      <div class="topbar-left"><div class="page-title">Datasets</div></div>
      <div class="topbar-right">
        <button class="btn btn-primary" id="btnNewDataset">${icons.plus} New Dataset</button>
      </div>
    </div>
    <div class="page-content">
      ${datasetsList.length === 0 ? `
        <div class="empty-state">${icons.database}<h3>No datasets yet</h3><p>Create a dataset to start annotating and building training data.</p></div>
      ` : `
        <div class="table-container">
          <table>
            <thead><tr>
              <th>Name</th><th>Type</th><th>Status</th><th>Items</th><th>Annotated</th><th>Created</th>
            </tr></thead>
            <tbody>
              ${datasetsList.map(d => `
                <tr style="cursor:pointer" onclick="location.hash='#/projects/${projectId}/datasets/${d.id}'">
                  <td><strong style="color:var(--text-0)">${esc(d.name)}</strong></td>
                  <td>${typeLabels[d.dataset_type] || d.dataset_type}</td>
                  <td><span class="badge badge-${d.status === 'active' ? 'green' : d.status === 'frozen' ? 'blue' : 'gray'}">${d.status}</span></td>
                  <td>${d.item_count}</td>
                  <td>${d.annotated_count} <span style="color:var(--text-2)">(${d.item_count > 0 ? Math.round(d.annotated_count / d.item_count * 100) : 0}%)</span></td>
                  <td style="color:var(--text-2);font-size:12px">${new Date(d.created_at).toLocaleDateString()}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `);

  $('#btnNewDataset').onclick = () => showCreateDatasetModal(projectId);
}

// ── Dataset Detail ────────────────────────────────────────
async function renderDatasetDetail(projectId, datasetId) {
  const [dataset, items, versions] = await Promise.all([
    api.datasets.get(projectId, datasetId),
    api.datasets.listItems(projectId, datasetId),
    api.datasets.listVersions(projectId, datasetId),
  ]);
  currentProject = await api.projects.get(projectId);

  const pct = dataset.item_count > 0 ? Math.round(dataset.annotated_count / dataset.item_count * 100) : 0;

  app().innerHTML = shell(projectId, 'datasets', `
    <div class="topbar">
      <div class="topbar-left">
        <div class="breadcrumb"><a href="#/projects/${projectId}/datasets">Datasets</a> <span>/</span></div>
        <div class="page-title">${esc(dataset.name)}</div>
      </div>
      <div class="topbar-right">
        <button class="btn btn-sm" id="btnAddItems">${icons.plus} Add Media</button>
        <button class="btn btn-sm btn-primary" id="btnCreateVersion">${icons.database} Create Version</button>
      </div>
    </div>
    <div class="page-content">
      <div class="stats-grid" style="margin-bottom:24px">
        <div class="stat-card"><div class="stat-label">Items</div><div class="stat-value">${dataset.item_count}</div></div>
        <div class="stat-card"><div class="stat-label">Annotated</div><div class="stat-value">${dataset.annotated_count}</div><div class="stat-sub">${pct}% complete</div></div>
        <div class="stat-card"><div class="stat-label">Versions</div><div class="stat-value">${versions.length}</div></div>
        <div class="stat-card"><div class="stat-label">Type</div><div class="stat-value" style="font-size:16px">${dataset.dataset_type.replace(/_/g, ' ')}</div></div>
      </div>

      ${items.items?.length > 0 ? `
        <div class="card" style="margin-bottom:24px">
          <div class="card-header"><div class="card-title">Dataset Items</div></div>
          <div class="table-container">
            <table>
              <thead><tr><th>Media</th><th>Split</th><th>Annotated</th></tr></thead>
              <tbody>
                ${items.items.map(i => `
                  <tr>
                    <td style="font-size:12px;font-family:var(--mono)">${i.media_id.slice(0, 8)}...</td>
                    <td><span class="badge badge-${i.split === 'train' ? 'green' : i.split === 'val' ? 'yellow' : 'blue'}">${i.split}</span></td>
                    <td>${i.is_annotated ? '<span class="badge badge-green">Yes</span>' : '<span class="badge badge-gray">No</span>'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      ` : `<div class="empty-state">${icons.image}<h3>No items in this dataset</h3><p>Add media from your library to start building this dataset.</p></div>`}

      ${versions.length > 0 ? `
        <div class="card">
          <div class="card-header"><div class="card-title">Versions</div></div>
          <div class="table-container">
            <table>
              <thead><tr><th>Tag</th><th>Items</th><th>Format</th><th>Created</th></tr></thead>
              <tbody>
                ${versions.map(v => `
                  <tr>
                    <td><strong style="color:var(--text-0)">${esc(v.version_tag)}</strong></td>
                    <td>${v.item_count}</td>
                    <td>${v.export_format || '-'}</td>
                    <td style="color:var(--text-2);font-size:12px">${new Date(v.created_at).toLocaleDateString()}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      ` : ''}
    </div>
  `);

  $('#btnCreateVersion').onclick = () => {
    const tag = prompt('Version tag (e.g. v1.0):');
    if (!tag) return;
    api.datasets.createVersion(projectId, datasetId, { version_tag: tag, export_format: 'coco' })
      .then(() => { toast('Version created', 'success'); renderDatasetDetail(projectId, datasetId); })
      .catch(err => toast(err.message, 'error'));
  };
}

// ── Search ────────────────────────────────────────────────
async function renderSearch(projectId) {
  currentProject = await api.projects.get(projectId);

  app().innerHTML = shell(projectId, 'search', `
    <div class="topbar">
      <div class="topbar-left"><div class="page-title">Semantic Search</div></div>
    </div>
    <div class="page-content">
      <div class="card">
        <div class="card-body">
          <div style="display:flex;gap:12px;align-items:end">
            <div class="form-group" style="flex:1;margin-bottom:0">
              <label class="form-label">Search Query</label>
              <div class="search-bar">
                ${icons.search}
                <input id="searchQuery" placeholder="Describe what you're looking for... (e.g., 'dogs playing in park')">
              </div>
            </div>
            <button class="btn btn-primary" id="btnSearch">${icons.search} Search</button>
          </div>
          <div style="display:flex;gap:16px;margin-top:12px">
            <label style="font-size:12px;color:var(--text-2);display:flex;align-items:center;gap:4px">
              <input type="checkbox" id="useClip" checked> CLIP
            </label>
            <label style="font-size:12px;color:var(--text-2);display:flex;align-items:center;gap:4px">
              <input type="checkbox" id="useText" checked> Text
            </label>
          </div>
        </div>
      </div>
      <div id="searchResults" style="margin-top:20px"></div>
    </div>
  `);

  async function doSearch() {
    const query = $('#searchQuery').value.trim();
    if (!query) return;

    const resultsEl = $('#searchResults');
    resultsEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-2)">Searching...</div>';

    try {
      const res = await api.search.query(projectId, {
        query,
        use_clip: $('#useClip').checked,
        use_text: $('#useText').checked,
        limit: 30,
      });

      if (res.results.length === 0) {
        resultsEl.innerHTML = `<div class="empty-state">${icons.search}<h3>No results</h3><p>Try a different query or upload more media.</p></div>`;
        return;
      }

      resultsEl.innerHTML = `
        <div style="font-size:12px;color:var(--text-2);margin-bottom:12px">${res.total} results in ${res.took_ms}ms</div>
        <div class="media-grid">
          ${res.results.map(r => `
            <div class="media-card">
              <div class="media-thumb">
                ${r.thumbnail_url ? `<img src="${r.thumbnail_url}" alt="">` : typeIcon(r.media_type)}
              </div>
              <div class="media-card-info">
                <div class="media-card-name">${esc(r.filename)}</div>
                <div class="media-card-meta">
                  <span class="badge badge-${r.match_source === 'hybrid' ? 'green' : 'blue'}" style="font-size:10px">${r.match_source}</span>
                  <span>${(r.score * 100).toFixed(1)}%</span>
                </div>
                ${r.auto_caption ? `<div style="font-size:11px;color:var(--text-2);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.auto_caption)}</div>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } catch (err) {
      resultsEl.innerHTML = `<div style="text-align:center;padding:20px;color:var(--red)">${err.message}</div>`;
    }
  }

  $('#btnSearch').onclick = doSearch;
  $('#searchQuery').onkeydown = (e) => { if (e.key === 'Enter') doSearch(); };
}

// ── Project Settings ──────────────────────────────────────
async function renderProjectSettings(projectId) {
  const [project, members] = await Promise.all([
    api.projects.get(projectId),
    api.projects.members(projectId),
  ]);
  currentProject = project;

  app().innerHTML = shell(projectId, 'settings', `
    <div class="topbar">
      <div class="topbar-left"><div class="page-title">Project Settings</div></div>
    </div>
    <div class="page-content" style="max-width:700px">
      <div class="card" style="margin-bottom:20px">
        <div class="card-header"><div class="card-title">General</div></div>
        <div class="card-body">
          <div class="form-group">
            <label class="form-label">Project Name</label>
            <input class="form-input" id="projName" value="${esc(project.name)}">
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <textarea class="form-textarea" id="projDesc">${esc(project.description || '')}</textarea>
          </div>
          <button class="btn btn-primary" id="btnSaveProject">Save Changes</button>
        </div>
      </div>

      <div class="card" style="margin-bottom:20px">
        <div class="card-header">
          <div class="card-title">Members (${members.length})</div>
          <button class="btn btn-sm" id="btnInvite">${icons.plus} Invite</button>
        </div>
        <div class="table-container">
          <table>
            <thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead>
            <tbody>
              ${members.map(m => `
                <tr>
                  <td style="color:var(--text-0)">${esc(m.user_name)}</td>
                  <td>${esc(m.user_email)}</td>
                  <td><span class="badge badge-${m.role === 'owner' ? 'green' : m.role === 'admin' ? 'blue' : 'gray'}">${m.role}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card" style="border-color:var(--red)">
        <div class="card-header"><div class="card-title" style="color:var(--red)">Danger Zone</div></div>
        <div class="card-body">
          <button class="btn btn-danger" id="btnDeleteProject">Delete Project</button>
        </div>
      </div>
    </div>
  `);

  $('#btnSaveProject').onclick = async () => {
    try {
      await api.projects.update(projectId, {
        name: $('#projName').value,
        description: $('#projDesc').value,
      });
      toast('Project updated', 'success');
    } catch (err) { toast(err.message, 'error'); }
  };

  $('#btnDeleteProject').onclick = async () => {
    if (!confirm('Are you sure you want to delete this project? This cannot be undone.')) return;
    try {
      await api.projects.delete(projectId);
      toast('Project deleted', 'success');
      navigate('/projects');
    } catch (err) { toast(err.message, 'error'); }
  };
}

// ═══════════════════════════════════════════════════════════
// Modals
// ═══════════════════════════════════════════════════════════
function showCreateProjectModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-title">Create New Project</div>
      <div class="form-group">
        <label class="form-label">Project Name</label>
        <input class="form-input" id="newProjName" placeholder="My ML Project" autofocus>
      </div>
      <div class="form-group">
        <label class="form-label">Description</label>
        <textarea class="form-textarea" id="newProjDesc" placeholder="What are you building?"></textarea>
      </div>
      <div class="modal-actions">
        <button class="btn" id="cancelProj">Cancel</button>
        <button class="btn btn-primary" id="confirmProj">Create</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  overlay.querySelector('#cancelProj').onclick = close;
  overlay.onclick = (e) => { if (e.target === overlay) close(); };
  overlay.querySelector('#confirmProj').onclick = async () => {
    const name = overlay.querySelector('#newProjName').value.trim();
    if (!name) return;
    try {
      const proj = await api.projects.create({
        name,
        description: overlay.querySelector('#newProjDesc').value,
      });
      close();
      toast('Project created', 'success');
      navigate(`/projects/${proj.id}`);
    } catch (err) { toast(err.message, 'error'); }
  };
}

function showCreateDatasetModal(projectId) {
  const types = [
    'image_classification', 'object_detection', 'instance_segmentation',
    'semantic_segmentation', 'image_captioning', 'video_classification',
    'video_object_tracking', 'audio_classification', 'speech_recognition',
    'text_classification', 'ner', 'custom',
  ];

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-title">Create New Dataset</div>
      <div class="form-group">
        <label class="form-label">Dataset Name</label>
        <input class="form-input" id="newDsName" placeholder="Training Data v1" autofocus>
      </div>
      <div class="form-group">
        <label class="form-label">Type</label>
        <select class="form-select" id="newDsType">
          ${types.map(t => `<option value="${t}">${t.replace(/_/g, ' ')}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Description</label>
        <textarea class="form-textarea" id="newDsDesc" placeholder="Dataset description..."></textarea>
      </div>
      <div class="modal-actions">
        <button class="btn" id="cancelDs">Cancel</button>
        <button class="btn btn-primary" id="confirmDs">Create</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  overlay.querySelector('#cancelDs').onclick = close;
  overlay.onclick = (e) => { if (e.target === overlay) close(); };
  overlay.querySelector('#confirmDs').onclick = async () => {
    const name = overlay.querySelector('#newDsName').value.trim();
    if (!name) return;
    try {
      const ds = await api.datasets.create(projectId, {
        name,
        dataset_type: overlay.querySelector('#newDsType').value,
        description: overlay.querySelector('#newDsDesc').value,
      });
      close();
      toast('Dataset created', 'success');
      navigate(`/projects/${projectId}/datasets/${ds.id}`);
    } catch (err) { toast(err.message, 'error'); }
  };
}

// ═══════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function toast(msg, type = 'info') {
  const container = $('#toastContainer');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
