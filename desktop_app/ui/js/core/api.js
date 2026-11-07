/**
 * api.js — Centralized HTTP Client with Session Token & 401 Auth Gate Hook
 */

let _sessionToken = '';
let _unauthorizedHandler = null;

export function setSessionToken(token) {
  _sessionToken = token || '';
  window.ERP_SESSION_TOKEN = _sessionToken;
}

export function getSessionToken() {
  return _sessionToken;
}

export function onUnauthorized(handler) {
  _unauthorizedHandler = handler;
}

/**
 * Execute JSON API request with cookie + optional X-Session-Token header.
 * @param {string} url
 * @param {'GET'|'POST'|'PUT'|'DELETE'} [method='GET']
 * @param {object|null} [body=null]
 * @param {{signal?: AbortSignal, skipAuthGate?: boolean}} [opts={}]
 * @returns {Promise<object>}
 */
export async function apiCall(url, method = 'GET', body = null, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (_sessionToken) headers['X-Session-Token'] = _sessionToken;

  const fetchOpts = {
    method,
    headers,
    credentials: 'same-origin',
    signal: opts.signal,
  };
  if (body !== null) fetchOpts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(url, fetchOpts);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new Error('Local server unreachable. Please restart the desktop application.');
  }

  let json;
  try {
    json = await res.json();
  } catch {
    throw new Error(`Unexpected server response (HTTP ${res.status})`);
  }

  if (res.status === 401 && !opts.skipAuthGate && !url.startsWith('/api/auth/')) {
    if (typeof _unauthorizedHandler === 'function') {
      _unauthorizedHandler();
    }
  }

  if (!res.ok || json.ok === false) {
    const err = new Error(json.error || `Request failed (HTTP ${res.status})`);
    err.status = res.status;
    err.code = json.code || '';
    throw err;
  }

  return json;
}

export async function apiGet(url, params = {}) {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  return apiCall(qs ? `${url}?${qs}` : url);
}

export async function apiPost(url, body, opts = {}) {
  return apiCall(url, 'POST', body, opts);
}

export async function apiPage(url, page = 1, filters = {}) {
  return apiGet(url, { page, ...filters });
}
