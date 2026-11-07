/**
 * dom.js — Safe DOM helpers: escaping, toast, modal, event delegation
 * Koi innerHTML raw string nahi — sirf esc() se guzra hua content.
 */

// ─── XSS-safe escaping ───────────────────────────────────────────────────────

/**
 * HTML-escape karo (XSS prevention). Hamesha use karo template literals mein.
 * @param {any} val
 * @returns {string}
 */
export function esc(val) {
  if (val === null || val === undefined) return '';
  return String(val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ─── Toast System ─────────────────────────────────────────────────────────────

const TOAST_ICONS = {
  success: '✓',
  error:   '✕',
  warn:    '⚠',
  info:    'ℹ',
};

/** @type {Map<string, {el: HTMLElement, timer: number}>} */
const _toasts = new Map();

/**
 * Toast dikhao.
 * @param {string} msg
 * @param {'success'|'error'|'warn'|'info'} [type='success']
 * @param {{duration?: number, undoFn?: Function, undoLabel?: string}} [opts={}]
 * @returns {string} toast id (dismiss karne ke liye)
 */
export function toast(msg, type = 'success', opts = {}) {
  const container = document.getElementById('toast-container');
  if (!container) { console.warn('[toast] #toast-container not found'); return ''; }

  const id = `toast-${Date.now()}`;
  const duration = opts.duration ?? 3800;

  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.id = id;
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');

  el.innerHTML = `
    <span class="toast-icon">${TOAST_ICONS[type] || '•'}</span>
    <span class="toast-msg">${esc(msg)}</span>
    ${opts.undoFn
      ? `<button class="toast-undo" data-toast-undo="${esc(id)}">${esc(opts.undoLabel || 'Undo')}</button>`
      : ''}
  `;

  if (opts.undoFn) {
    el.querySelector('[data-toast-undo]').addEventListener('click', () => {
      opts.undoFn();
      dismissToast(id);
    });
  }

  container.appendChild(el);

  const timer = setTimeout(() => dismissToast(id), duration);
  _toasts.set(id, { el, timer });
  return id;
}

/**
 * Toast dismiss karo
 * @param {string} id
 */
export function dismissToast(id) {
  const entry = _toasts.get(id);
  if (!entry) return;
  clearTimeout(entry.timer);
  entry.el.remove();
  _toasts.delete(id);
}

// ─── Modal ───────────────────────────────────────────────────────────────────

/** @type {Function|null} */
let _modalSubmitHandler = null;

/**
 * Modal kholaو
 * @param {string} title
 * @param {string} bodyHtml - esc() se safe kiya hua HTML
 * @param {Function} onSubmit - async (formData) => void
 * @param {{submitLabel?: string, wide?: boolean}} [opts={}]
 */
export function openModal(title, bodyHtml, onSubmit, opts = {}) {
  const backdrop = document.getElementById('modal-backdrop');
  const titleEl  = document.getElementById('modal-title');
  const bodyEl   = document.getElementById('modal-body');
  const submitEl = document.getElementById('modal-submit');
  const cardEl   = backdrop?.querySelector('.modal-card');

  if (!backdrop || !titleEl || !bodyEl) return;

  titleEl.textContent    = title;
  bodyEl.innerHTML       = bodyHtml;
  submitEl.textContent   = opts.submitLabel || 'Save';
  _modalSubmitHandler    = onSubmit;

  if (opts.wide) cardEl?.classList.add('modal-lg');
  else           cardEl?.classList.remove('modal-lg');

  backdrop.classList.add('open');

  // First focusable element ko focus karo
  setTimeout(() => {
    const first = bodyEl.querySelector('input, select, textarea, button');
    first?.focus();
  }, 50);
}

/** Modal band karo */
export function closeModal() {
  const backdrop = document.getElementById('modal-backdrop');
  backdrop?.classList.remove('open');
  _modalSubmitHandler = null;
  const bodyEl = document.getElementById('modal-body');
  if (bodyEl) bodyEl.innerHTML = '';
}

/** Modal form submit handler — api.js calls this */
export function getModalSubmitHandler() {
  return _modalSubmitHandler;
}

// ─── Confirm Dialog ──────────────────────────────────────────────────────────

/**
 * Confirm dialog — returns Promise<boolean>
 * Default button: Cancel (safe — user must actively choose)
 * @param {string} title
 * @param {string} desc
 * @param {{confirmLabel?: string, confirmClass?: string}} [opts={}]
 * @returns {Promise<boolean>}
 */
export function confirm(title, desc, opts = {}) {
  return new Promise((resolve) => {
    const backdrop = document.getElementById('modal-backdrop');
    if (!backdrop) { resolve(false); return; }

    const confirmLabel = opts.confirmLabel || 'Confirm';
    const confirmClass = opts.confirmClass || 'btn-danger';

    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = `
      <div class="confirm-dialog-body">
        <div class="confirm-dialog-icon">⚠️</div>
        <div class="confirm-dialog-title">${esc(title)}</div>
        <div class="confirm-dialog-desc">${esc(desc)}</div>
      </div>
    `;

    // Override footer buttons
    const footer = document.getElementById('modal-footer');
    if (footer) {
      footer.innerHTML = `
        <button class="btn btn-secondary" id="_confirm-cancel">Cancel</button>
        <button class="btn ${esc(confirmClass)}" id="_confirm-ok">${esc(confirmLabel)}</button>
      `;
      document.getElementById('_confirm-cancel').onclick = () => { closeModal(); resolve(false); };
      document.getElementById('_confirm-ok').onclick    = () => { closeModal(); resolve(true);  };
    } else {
      // Fallback: use native confirm
      closeModal();
      resolve(window.confirm(`${title}\n\n${desc}`));
      return;
    }

    // Hide default submit button
    const submit = document.getElementById('modal-submit');
    if (submit) submit.style.display = 'none';

    backdrop.classList.add('open');
  });
}

// ─── Event Delegation ────────────────────────────────────────────────────────

/**
 * Event delegation — parent pe listener, selector pe match karo.
 * Avoid karo har row pe individual listeners.
 * @param {HTMLElement} parent
 * @param {string} eventType
 * @param {string} selector
 * @param {Function} handler - (event, matchedEl) => void
 * @returns {Function} cleanup function
 */
export function delegate(parent, eventType, selector, handler) {
  function listener(e) {
    const target = e.target.closest(selector);
    if (target && parent.contains(target)) {
      handler(e, target);
    }
  }
  parent.addEventListener(eventType, listener);
  return () => parent.removeEventListener(eventType, listener);
}

// ─── Loading State ───────────────────────────────────────────────────────────

/**
 * Button ko loading state mein daalo
 * @param {HTMLButtonElement} btn
 * @param {string} [loadingText='...']
 * @returns {Function} restore function
 */
export function btnLoading(btn, loadingText = '...') {
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = loadingText;
  return () => {
    btn.disabled = false;
    btn.textContent = original;
  };
}

