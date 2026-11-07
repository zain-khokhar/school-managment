/**
 * api.js — Core API caller for School ERP Desktop App
 * Har request yahan se jaata hai. Error handling centralized.
 * No direct fetch() anywhere else in the codebase.
 */

/** @type {AbortController|null} */
let _activeController = null;

/**
 * Ek API call karo. Automatically JSON parse karta hai.
 * @param {string} url
 * @param {'GET'|'POST'|'PUT'|'DELETE'} [method='GET']
 * @param {object|null} [body=null]
 * @param {{signal?: AbortSignal, silent?: boolean}} [opts={}]
 * @returns {Promise<object>}
 */
export async function apiCall(url, method = 'GET', body = null, opts = {}) {
  const fetchOpts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    signal: opts.signal,
  };
  if (body !== null) fetchOpts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(url, fetchOpts);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    // Network error (Flask server down?)
    throw new Error('Server se connection nahi ho raha. App restart karein.');
  }

  let json;
  try {
    json = await res.json();
  } catch {
    throw new Error(`Server ne invalid response bheja (HTTP ${res.status})`);
  }

  if (!res.ok || json.ok === false) {
    // Log to console for debugging, but surface a clean message
    console.error('[API Error]', url, json);
    throw new Error(json.error || `Request fail ho gayi (HTTP ${res.status})`);
  }

  return json;
}

/**
 * GET helper — shorter syntax
 * @param {string} url
 * @param {Record<string,string|number>} [params={}]
 */
export async function apiGet(url, params = {}) {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  return apiCall(qs ? `${url}?${qs}` : url);
}

/**
 * POST helper
 * @param {string} url
 * @param {object} body
 */
export async function apiPost(url, body) {
  return apiCall(url, 'POST', body);
}

/**
 * Paginated GET — returns { items, total, page, pages }
 * @param {string} url
 * @param {number} page
 * @param {Record<string,any>} filters
 */
export async function apiPage(url, page = 1, filters = {}) {
  return apiGet(url, { page, ...filters });
}

