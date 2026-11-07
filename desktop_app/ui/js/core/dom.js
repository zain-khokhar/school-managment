/**
 * dom.js — Safe DOM helpers: escaping, toast, modal, confirm, event delegation
 * Uses geometric stroke SVG icons from icons.js (zero Unicode emojis).
 */

import { icon } from './icons.js';

export function esc(val) {
  if (val === null || val === undefined) return '';
  return String(val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const TOAST_ICON_NAMES = {
  success: 'check',
  error:   'x',
  warn:    'alert',
  info:    'info',
};

/** @type {Map<string, {el: HTMLElement, timer: number}>} */
const _toasts = new Map();

export function toast(msg, type = 'success', opts = {}) {
  const container = document.getElementById('toast-container');
  if (!container) return '';

  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const duration = opts.duration ?? 3800;

  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.id = id;
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');

  el.innerHTML = `
    <span class="toast-icon">${icon(TOAST_ICON_NAMES[type] || 'info', 16)}</span>
    <span class="toast-msg">${esc(msg)}</span>
    ${opts.undoFn
      ? `<button type="button" class="toast-undo" data-toast-undo="${esc(id)}">${esc(opts.undoLabel || 'Undo')}</button>`
      : ''}
  `;

  if (opts.undoFn) {
    el.querySelector('[data-toast-undo]')?.addEventListener('click', () => {
      opts.undoFn();
      dismissToast(id);
    });
  }

  container.appendChild(el);
  const timer = setTimeout(() => dismissToast(id), duration);
  _toasts.set(id, { el, timer });
  return id;
}

export function dismissToast(id) {
  const entry = _toasts.get(id);
  if (!entry) return;
  clearTimeout(entry.timer);
  entry.el.remove();
  _toasts.delete(id);
}

let _modalSubmitHandler = null;

function _ensureStandardFooter(submitLabel = 'Save') {
  const footer = document.getElementById('modal-footer');
  if (!footer) return;
  if (!document.getElementById('modal-submit') || !document.getElementById('modal-cancel')) {
    footer.innerHTML = `
      <button type="button" class="btn btn-secondary" id="modal-cancel">Cancel</button>
      <button type="submit" class="btn btn-primary" id="modal-submit">${esc(submitLabel)}</button>
    `;
    document.getElementById('modal-cancel')?.addEventListener('click', closeModal);
  } else {
    const submitEl = document.getElementById('modal-submit');
    if (submitEl) {
      submitEl.style.display = '';
      submitEl.textContent = submitLabel;
    }
  }
}

export function openModal(title, bodyHtml, onSubmit, opts = {}) {
  const backdrop = document.getElementById('modal-backdrop');
  const titleEl  = document.getElementById('modal-title');
  const bodyEl   = document.getElementById('modal-body');
  const cardEl   = backdrop?.querySelector('.modal-card');
  if (!backdrop || !titleEl || !bodyEl) return;

  _ensureStandardFooter(opts.submitLabel || 'Save');
  titleEl.textContent = title;
  bodyEl.innerHTML    = bodyHtml;
  _modalSubmitHandler = onSubmit;

  if (opts.wide) cardEl?.classList.add('modal-lg');
  else           cardEl?.classList.remove('modal-lg');

  backdrop.classList.add('open');
  setTimeout(() => {
    bodyEl.querySelector('input, select, textarea, button')?.focus();
  }, 40);
}

export function closeModal() {
  const backdrop = document.getElementById('modal-backdrop');
  backdrop?.classList.remove('open');
  _modalSubmitHandler = null;
  const bodyEl = document.getElementById('modal-body');
  if (bodyEl) bodyEl.innerHTML = '';
  _ensureStandardFooter('Save');
}

export function getModalSubmitHandler() {
  return _modalSubmitHandler;
}

export function confirm(title, desc, opts = {}) {
  return new Promise((resolve) => {
    const backdrop = document.getElementById('modal-backdrop');
    const footer   = document.getElementById('modal-footer');
    if (!backdrop || !footer) {
      resolve(window.confirm(`${title}\n\n${desc}`));
      return;
    }

    const confirmLabel = opts.confirmLabel || 'Confirm';
    const confirmClass = opts.confirmClass || 'btn-danger';

    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = `
      <div class="confirm-dialog-body">
        <div class="confirm-dialog-icon">${icon('alert', 28)}</div>
        <div class="confirm-dialog-title">${esc(title)}</div>
        <div class="confirm-dialog-desc">${esc(desc)}</div>
      </div>
    `;

    footer.innerHTML = `
      <button type="button" class="btn btn-secondary" id="_confirm-cancel">Cancel</button>
      <button type="button" class="btn ${esc(confirmClass)}" id="_confirm-ok">${esc(confirmLabel)}</button>
    `;
    document.getElementById('_confirm-cancel').onclick = () => { closeModal(); resolve(false); };
    document.getElementById('_confirm-ok').onclick     = () => { closeModal(); resolve(true); };
    backdrop.classList.add('open');
  });
}

export function delegate(parent, eventType, selector, handler) {
  if (!parent) return () => {};
  function listener(e) {
    const target = e.target.closest(selector);
    if (target && parent.contains(target)) handler(e, target);
  }
  parent.addEventListener(eventType, listener);
  return () => parent.removeEventListener(eventType, listener);
}

export function btnLoading(btn, loadingText = 'Saving...') {
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = loadingText;
  return () => {
    btn.disabled = false;
    btn.innerHTML = original;
  };
}
