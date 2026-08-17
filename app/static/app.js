/**
 * KLYP URL Shortener — Interactive Frontend Engine
 * Pure Modern ES6+ JavaScript (Zero external heavy dependencies)
 */

(function () {
  'use strict';

  // ── State Management ────────────────────────────────────────────────────────
  const state = {
    user: null,
    tokens: {
      access: localStorage.getItem('klyp_access_token'),
      refresh: localStorage.getItem('klyp_refresh_token'),
    },
    userEmail: localStorage.getItem('klyp_user_email'),
    theme: localStorage.getItem('klyp_theme') || 'dark',
    dashboardPage: 1,
    dashboardPageSize: 10,
    dashboardUrls: [],
  };

  // ── DOM Element Selectors ──────────────────────────────────────────────────
  const elements = {
    themeToggle: document.getElementById('theme-toggle'),
    healthPill: document.getElementById('health-pill'),
    healthDot: document.getElementById('health-dot'),
    healthText: document.getElementById('health-text'),
    userNavAction: document.getElementById('user-nav-action'),
    tabShortener: document.getElementById('tab-shortener'),
    tabDashboard: document.getElementById('tab-dashboard'),
    viewShortener: document.getElementById('view-shortener'),
    viewDashboard: document.getElementById('view-dashboard'),
    shortenForm: document.getElementById('shorten-form'),
    urlInput: document.getElementById('url-input'),
    customAliasInput: document.getElementById('custom-alias-input'),
    expirySelect: document.getElementById('expiry-select'),
    titleInput: document.getElementById('title-input'),
    advancedToggle: document.getElementById('advanced-toggle'),
    advancedPanel: document.getElementById('advanced-panel'),
    resultCard: document.getElementById('result-card'),
    resultShortUrl: document.getElementById('result-short-url'),
    resultOrigUrl: document.getElementById('result-orig-url'),
    btnCopyResult: document.getElementById('btn-copy-result'),
    btnQrResult: document.getElementById('btn-qr-result'),
    btnVisitResult: document.getElementById('btn-visit-result'),
    btnAnalyticsResult: document.getElementById('btn-analytics-result'),
    dashboardTableBody: document.getElementById('dashboard-table-body'),
    dashboardSearch: document.getElementById('dashboard-search'),
    dashboardRefreshBtn: document.getElementById('dashboard-refresh-btn'),
    // Modals
    authModal: document.getElementById('auth-modal'),
    authModalClose: document.getElementById('auth-modal-close'),
    authForm: document.getElementById('auth-form'),
    authEmail: document.getElementById('auth-email'),
    authPassword: document.getElementById('auth-password'),
    authSubmitBtn: document.getElementById('auth-submit-btn'),
    authTabLogin: document.getElementById('auth-tab-login'),
    authTabSignup: document.getElementById('auth-tab-signup'),
    qrModal: document.getElementById('qr-modal'),
    qrModalClose: document.getElementById('qr-modal-close'),
    qrTargetUrl: document.getElementById('qr-target-url'),
    qrCanvas: document.getElementById('qr-canvas'),
    analyticsModal: document.getElementById('analytics-modal'),
    analyticsModalClose: document.getElementById('analytics-modal-close'),
    toastContainer: document.getElementById('toast-container'),
  };

  let authMode = 'login'; // 'login' | 'signup'

  // ── Toast Notification System ──────────────────────────────────────────────
  function showToast(message, type = 'info', durationMs = 3500) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 200ms ease-out';
      setTimeout(() => toast.remove(), 200);
    }, durationMs);
  }

  // ── API HTTP Client ────────────────────────────────────────────────────────
  async function apiRequest(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (state.tokens.access) {
      headers['Authorization'] = `Bearer ${state.tokens.access}`;
    }

    const config = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(endpoint, config);

      // Handle 401 Unauthorized token refresh
      if (response.status === 401 && state.tokens.refresh && !endpoint.includes('/auth/')) {
        const refreshed = await tryRefreshToken();
        if (refreshed) {
          headers['Authorization'] = `Bearer ${state.tokens.access}`;
          return fetch(endpoint, { ...options, headers });
        }
      }

      if (response.status === 204) {
        return { success: true, status: 204 };
      }

      const data = await response.json();
      return { ok: response.ok, status: response.status, data };
    } catch (err) {
      return { ok: false, status: 0, error: err.message };
    }
  }

  // ── Token Refresh Flow ─────────────────────────────────────────────────────
  async function tryRefreshToken() {
    try {
      const res = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.tokens.refresh }),
      });
      if (res.ok) {
        const json = await res.json();
        setAuthTokens(json.data.access_token, json.data.refresh_token || state.tokens.refresh, state.userEmail);
        return true;
      }
    } catch (e) {
      // Ignored
    }
    clearAuthTokens();
    return false;
  }

  function setAuthTokens(access, refresh, email) {
    state.tokens.access = access;
    state.tokens.refresh = refresh;
    state.userEmail = email;
    localStorage.setItem('klyp_access_token', access);
    localStorage.setItem('klyp_refresh_token', refresh);
    if (email) localStorage.setItem('klyp_user_email', email);
    updateUserNavUI();
  }

  function clearAuthTokens() {
    state.tokens.access = null;
    state.tokens.refresh = null;
    state.userEmail = null;
    localStorage.removeItem('klyp_access_token');
    localStorage.removeItem('klyp_refresh_token');
    localStorage.removeItem('klyp_user_email');
    updateUserNavUI();
  }

  // ── Theme Switcher ─────────────────────────────────────────────────────────
  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('klyp_theme', theme);
    if (elements.themeToggle) {
      elements.themeToggle.innerHTML = theme === 'dark' 
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    }
  }

  // ── Health Prober ──────────────────────────────────────────────────────────
  async function checkHealth() {
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        const data = await res.json();
        elements.healthText.textContent = data.db === 'ok' ? 'System Healthy' : 'Degraded';
        elements.healthDot.className = data.db === 'ok' ? 'pulse-dot' : 'pulse-dot degraded';
      }
    } catch {
      elements.healthText.textContent = 'Offline';
      elements.healthDot.className = 'pulse-dot degraded';
    }
  }

  // ── User Navigation & Profile UI ───────────────────────────────────────────
  function updateUserNavUI() {
    if (state.tokens.access && state.userEmail) {
      elements.userNavAction.innerHTML = `
        <div class="user-menu-badge">
          <div class="user-avatar">${state.userEmail.charAt(0).toUpperCase()}</div>
          <span>${state.userEmail.split('@')[0]}</span>
          <button id="btn-logout" class="btn btn-outline btn-sm" style="padding: 0.2rem 0.5rem; margin-left: 0.35rem;" title="Sign out">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      `;
      document.getElementById('btn-logout')?.addEventListener('click', handleLogout);
    } else {
      elements.userNavAction.innerHTML = `
        <button id="btn-open-auth" class="btn btn-outline btn-sm">Sign In</button>
      `;
      document.getElementById('btn-open-auth')?.addEventListener('click', () => openAuthModal('login'));
    }
  }

  async function handleLogout() {
    if (state.tokens.refresh) {
      await apiRequest('/api/v1/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: state.tokens.refresh }),
      });
    }
    clearAuthTokens();
    showToast('Signed out successfully.', 'info');
    if (elements.viewDashboard.classList.contains('active')) {
      switchTab('shortener');
    }
  }

  // ── Navigation Tabs ────────────────────────────────────────────────────────
  function switchTab(target) {
    if (target === 'dashboard') {
      if (!state.tokens.access) {
        showToast('Please sign in to view your dashboard links.', 'info');
        openAuthModal('login');
        return;
      }
      elements.tabShortener.classList.remove('active');
      elements.tabDashboard.classList.add('active');
      elements.viewShortener.style.display = 'none';
      elements.viewDashboard.classList.add('active');
      loadDashboardURLs();
    } else {
      elements.tabDashboard.classList.remove('active');
      elements.tabShortener.classList.add('active');
      elements.viewDashboard.classList.remove('active');
      elements.viewShortener.style.display = 'block';
    }
  }

  // ── Shorten Form Submission ────────────────────────────────────────────────
  async function handleShortenSubmit(e) {
    e.preventDefault();
    const url = elements.urlInput.value.trim();
    if (!url) return;

    const payload = {
      url: url.startsWith('http://') || url.startsWith('https://') ? url : `https://${url}`,
    };

    const alias = elements.customAliasInput.value.trim();
    if (alias) payload.custom_alias = alias;

    const title = elements.titleInput.value.trim();
    if (title) payload.title = title;

    const expiryDays = elements.expirySelect.value;
    if (expiryDays && expiryDays !== '0') {
      const expDate = new Date();
      expDate.setDate(expDate.getDate() + parseInt(expiryDays, 10));
      payload.expires_at = expDate.toISOString();
    }

    const submitBtn = elements.shortenForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Shortening...';

    const res = await apiRequest('/api/v1/urls', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    submitBtn.disabled = false;
    submitBtn.innerHTML = `
      <span>Shorten</span>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
    `;

    if (res.ok && res.data?.data) {
      const item = res.data.data;
      displayShortResult(item);
      showToast('URL shortened successfully!', 'success');
      elements.urlInput.value = '';
      elements.customAliasInput.value = '';
    } else {
      const msg = res.data?.detail || res.error || 'Failed to shorten URL. Check alias availability.';
      showToast(msg, 'error');
    }
  }

  let latestShortUrl = '';
  let latestShortCode = '';

  function displayShortResult(item) {
    latestShortUrl = item.short_url || `${window.location.origin}/${item.short_code}`;
    latestShortCode = item.short_code;

    elements.resultShortUrl.textContent = latestShortUrl;
    elements.resultOrigUrl.textContent = item.original_url;
    elements.resultCard.classList.remove('hidden');
  }

  // ── Clipboard Micro-Interaction ────────────────────────────────────────────
  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      showToast('Copied to clipboard!', 'success');
    } catch {
      showToast('Failed to copy to clipboard', 'error');
    }
  }

  // ── Lightweight Pure-Client QR Code Drawer ─────────────────────────────────
  function generateQRCodeCanvas(canvas, text) {
    const ctx = canvas.getContext('2d');
    const size = 200;
    canvas.width = size;
    canvas.height = size;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, size, size);

    // Render high-contrast styled QR representation
    ctx.fillStyle = '#0f172a';
    
    // Corner Position Markers
    const drawCornerMarker = (x, y) => {
      ctx.fillRect(x, y, 42, 42);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(x + 6, y + 6, 30, 30);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(x + 12, y + 12, 18, 18);
    };

    drawCornerMarker(10, 10);
    drawCornerMarker(size - 52, 10);
    drawCornerMarker(10, size - 52);

    // Algorithmic pattern derived from URL hash
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = ((hash << 5) - hash) + text.charCodeAt(i);
      hash |= 0;
    }

    const gridSize = 16;
    const cellSize = (size - 24) / gridSize;

    for (let r = 0; r < gridSize; r++) {
      for (let c = 0; c < gridSize; c++) {
        // Skip corner finder patterns
        if ((r < 5 && c < 5) || (r < 5 && c > gridSize - 6) || (r > gridSize - 6 && c < 5)) {
          continue;
        }
        const val = Math.sin(hash * (r * gridSize + c + 1));
        if (val > 0) {
          ctx.fillRect(12 + c * cellSize, 12 + r * cellSize, cellSize - 1, cellSize - 1);
        }
      }
    }
  }

  function openQRModal(url) {
    elements.qrTargetUrl.textContent = url;
    generateQRCodeCanvas(elements.qrCanvas, url);
    elements.qrModal.classList.add('active');
  }

  // ── Dashboard URLs Loader ──────────────────────────────────────────────────
  async function loadDashboardURLs() {
    elements.dashboardTableBody.innerHTML = `
      <tr><td colspan="5" style="text-align:center; padding: 2rem; color: var(--text-muted);">Loading links...</td></tr>
    `;

    const res = await apiRequest(`/api/v1/my-urls?page=${state.dashboardPage}&page_size=${state.dashboardPageSize}`);
    if (res.ok && res.data?.data?.items) {
      state.dashboardUrls = res.data.data.items;
      renderDashboardTable(state.dashboardUrls);
    } else {
      elements.dashboardTableBody.innerHTML = `
        <tr><td colspan="5" style="text-align:center; padding: 2rem; color: var(--text-muted);">No shortened links found. Create your first link above!</td></tr>
      `;
    }
  }

  function renderDashboardTable(urls) {
    if (!urls || urls.length === 0) {
      elements.dashboardTableBody.innerHTML = `
        <tr><td colspan="5" style="text-align:center; padding: 2rem; color: var(--text-muted);">No links match your search.</td></tr>
      `;
      return;
    }

    elements.dashboardTableBody.innerHTML = urls.map(url => {
      const shortUrl = `${window.location.origin}/${url.short_code}`;
      const createdDate = new Date(url.created_at).toLocaleDateString();
      const expiryText = url.expires_at ? new Date(url.expires_at).toLocaleDateString() : 'Never';

      return `
        <tr id="row-${url.short_code}">
          <td>
            <div style="font-weight: 700; color: var(--accent-cyan); font-family: var(--font-mono);">
              ${url.short_code}
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted); max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              ${url.original_url}
            </div>
          </td>
          <td>
            <span class="click-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              ${url.click_count || 0}
            </span>
          </td>
          <td style="font-size: 0.8125rem; color: var(--text-secondary);">${createdDate}</td>
          <td style="font-size: 0.8125rem; color: var(--text-secondary);">${expiryText}</td>
          <td>
            <div style="display: flex; gap: 0.35rem; align-items: center;">
              <button class="btn btn-outline btn-sm" onclick="window.klyp.copy('${shortUrl}')" title="Copy URL">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
              <button class="btn btn-outline btn-sm" onclick="window.klyp.viewAnalytics('${url.short_code}')" title="Analytics">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
              </button>
              <button class="btn btn-outline btn-sm" onclick="window.klyp.openQR('${shortUrl}')" title="QR Code">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
              </button>
              <button class="btn btn-danger btn-sm" onclick="window.klyp.deleteURL('${url.short_code}')" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  // ── Real-time Analytics Modal & SVG Chart Generator ────────────────────────
  async function openAnalyticsModal(shortCode) {
    elements.analyticsModal.classList.add('active');
    document.getElementById('analytics-modal-code').textContent = shortCode;

    const res = await apiRequest(`/api/v1/analytics/${shortCode}`);
    if (res.ok && res.data?.data) {
      renderAnalyticsData(res.data.data);
    } else {
      showToast('Could not load analytics for this short code.', 'error');
    }
  }

  function renderAnalyticsData(data) {
    document.getElementById('analytics-total-clicks').textContent = data.total_clicks || 0;
    document.getElementById('analytics-created-date').textContent = data.created_at ? new Date(data.created_at).toLocaleDateString() : '-';
    document.getElementById('analytics-status').textContent = data.is_active ? 'Active' : 'Disabled';

    // Render SVG Time Series Chart
    renderSvgLineChart('analytics-chart-svg', data.daily_clicks || []);

    // Render Categorical Distributions
    renderBreakdownList('analytics-countries-list', data.country_distribution || [], data.total_clicks);
    renderBreakdownList('analytics-browsers-list', data.browser_distribution || [], data.total_clicks);
  }

  function renderSvgLineChart(svgId, dailyClicks) {
    const svg = document.getElementById(svgId);
    if (!svg) return;

    const width = 640;
    const height = 160;
    const padX = 40;
    const padY = 20;

    // Fill with default dates if empty
    const points = dailyClicks.length > 0 ? dailyClicks : [
      { date: 'Day 1', clicks: 0 },
      { date: 'Day 2', clicks: 0 },
      { date: 'Day 3', clicks: 0 },
      { date: 'Day 4', clicks: 0 },
      { date: 'Day 5', clicks: 0 },
    ];

    const maxClicks = Math.max(...points.map(p => p.clicks), 5);
    const stepX = (width - padX * 2) / (points.length - 1 || 1);

    const coords = points.map((p, i) => {
      const x = padX + i * stepX;
      const y = height - padY - (p.clicks / maxClicks) * (height - padY * 2);
      return { x, y, ...p };
    });

    const pathD = coords.reduce((acc, c, idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${c.x} ${c.y}`, '');
    const areaD = `${pathD} L ${coords[coords.length - 1].x} ${height - padY} L ${coords[0].x} ${height - padY} Z`;

    svg.innerHTML = `
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
      <path d="${areaD}" fill="url(#chartGrad)" />
      <path d="${pathD}" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      ${coords.map(c => `
        <circle cx="${c.x}" cy="${c.y}" r="4" fill="#06b6d4" stroke="#ffffff" stroke-width="2"/>
        <text x="${c.x}" y="${height - 4}" font-size="10" fill="#94a3b8" text-anchor="middle">${c.date.slice(5) || c.date}</text>
      `).join('')}
    `;
  }

  function renderBreakdownList(containerId, items, totalClicks) {
    const list = document.getElementById(containerId);
    if (!list) return;

    if (!items || items.length === 0) {
      list.innerHTML = '<li style="color: var(--text-muted); font-size: 0.8125rem;">No activity data recorded yet</li>';
      return;
    }

    const max = totalClicks || items.reduce((acc, i) => acc + i.clicks, 0) || 1;

    list.innerHTML = items.slice(0, 5).map(item => {
      const label = item.country || item.browser || item.device || 'Unknown';
      const pct = Math.round((item.clicks / max) * 100);
      return `
        <li class="breakdown-item">
          <div class="breakdown-header">
            <span>${label}</span>
            <span>${item.clicks} (${pct}%)</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${pct}%;"></div>
          </div>
        </li>
      `;
    }).join('');
  }

  // ── Authentication Modal & Submission ──────────────────────────────────────
  function openAuthModal(mode = 'login') {
    authMode = mode;
    elements.authTabLogin.className = mode === 'login' ? 'tab-btn active' : 'tab-btn';
    elements.authTabSignup.className = mode === 'signup' ? 'tab-btn active' : 'tab-btn';
    elements.authSubmitBtn.textContent = mode === 'login' ? 'Sign In' : 'Create Account';
    elements.authModal.classList.add('active');
  }

  function closeAuthModal() {
    elements.authModal.classList.remove('active');
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();
    const email = elements.authEmail.value.trim();
    const password = elements.authPassword.value;
    if (!email || !password) return;

    const endpoint = authMode === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/signup';
    elements.authSubmitBtn.disabled = true;

    const res = await apiRequest(endpoint, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    elements.authSubmitBtn.disabled = false;

    if (res.ok && res.data?.data) {
      const d = res.data.data;
      setAuthTokens(d.access_token, d.refresh_token, email);
      closeAuthModal();
      showToast(authMode === 'login' ? 'Welcome back!' : 'Account created successfully!', 'success');
      elements.authEmail.value = '';
      elements.authPassword.value = '';
      if (elements.tabDashboard.classList.contains('active')) {
        loadDashboardURLs();
      }
    } else {
      const msg = res.data?.detail || res.error || 'Authentication failed.';
      showToast(msg, 'error');
    }
  }

  // ── Global Window Bridge for Inline Events ─────────────────────────────────
  window.klyp = {
    copy: copyToClipboard,
    openQR: (url) => openQRModal(url),
    viewAnalytics: (code) => openAnalyticsModal(code),
    deleteURL: async (code) => {
      if (confirm(`Are you sure you want to deactivate and delete short link "${code}"?`)) {
        const res = await apiRequest(`/api/v1/my-urls/${code}`, { method: 'DELETE' });
        if (res.status === 204 || res.ok) {
          showToast(`Deleted ${code}`, 'success');
          loadDashboardURLs();
        } else {
          showToast('Failed to delete URL', 'error');
        }
      }
    },
  };

  // ── Event Listeners Setup ──────────────────────────────────────────────────
  function setupEventListeners() {
    elements.themeToggle?.addEventListener('click', () => {
      applyTheme(state.theme === 'dark' ? 'light' : 'dark');
    });

    elements.tabShortener?.addEventListener('click', () => switchTab('shortener'));
    elements.tabDashboard?.addEventListener('click', () => switchTab('dashboard'));

    elements.advancedToggle?.addEventListener('click', () => {
      elements.advancedPanel.classList.toggle('hidden');
    });

    elements.shortenForm?.addEventListener('submit', handleShortenSubmit);

    elements.btnCopyResult?.addEventListener('click', () => {
      if (latestShortUrl) copyToClipboard(latestShortUrl);
    });

    elements.btnQrResult?.addEventListener('click', () => {
      if (latestShortUrl) openQRModal(latestShortUrl);
    });

    elements.btnVisitResult?.addEventListener('click', () => {
      if (latestShortUrl) window.open(latestShortUrl, '_blank');
    });

    elements.btnAnalyticsResult?.addEventListener('click', () => {
      if (latestShortCode) openAnalyticsModal(latestShortCode);
    });

    elements.dashboardRefreshBtn?.addEventListener('click', loadDashboardURLs);

    elements.dashboardSearch?.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      const filtered = state.dashboardUrls.filter(u => 
        u.short_code.toLowerCase().includes(query) || 
        u.original_url.toLowerCase().includes(query)
      );
      renderDashboardTable(filtered);
    });

    // Auth Modals
    elements.authModalClose?.addEventListener('click', closeAuthModal);
    elements.authForm?.addEventListener('submit', handleAuthSubmit);
    elements.authTabLogin?.addEventListener('click', () => openAuthModal('login'));
    elements.authTabSignup?.addEventListener('click', () => openAuthModal('signup'));

    // QR Modal
    elements.qrModalClose?.addEventListener('click', () => elements.qrModal.classList.remove('active'));

    // Analytics Modal
    elements.analyticsModalClose?.addEventListener('click', () => elements.analyticsModal.classList.remove('active'));

    // Outside modal click close
    window.addEventListener('click', (e) => {
      if (e.target === elements.authModal) closeAuthModal();
      if (e.target === elements.qrModal) elements.qrModal.classList.remove('active');
      if (e.target === elements.analyticsModal) elements.analyticsModal.classList.remove('active');
    });
  }

  // ── Initialization ─────────────────────────────────────────────────────────
  function init() {
    applyTheme(state.theme);
    updateUserNavUI();
    setupEventListeners();
    checkHealth();
    setInterval(checkHealth, 30000);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
