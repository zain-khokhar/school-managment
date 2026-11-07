/**
 * screens/outbox/outbox-workspace.js — Outbox, WhatsApp & Parent Rabta Workspace (Phase 5)
 */

import { apiGet, apiPost } from '../../core/api.js';
import { esc, delegate } from '../../core/dom.js';
import { icon } from '../../core/icons.js';
import { t } from '../../core/i18n.js';
import { openCircularModal } from './circular-modal.js';
import { openTemplatesModal } from './templates-modal.js';
import { openCircularSlipsPreview } from '../../print/circular-slips.js';

let _outboxState = { page: 1, perPage: 20, status: 'all', category: 'all', q: '' };
let _searchTimer = null;

export async function renderOutboxScreen() {
  const container = document.getElementById('main-view');
  if (!container) return;

  container.innerHTML = `
    <div class="page-header">
      <div class="page-header-info">
        <h2 class="page-header-title">${icon('mail', 20)} ${t('outbox_title')}</h2>
        <div class="page-header-desc">${t('outbox_desc')}</div>
      </div>
      <div class="page-header-actions">
        <button type="button" class="btn btn-secondary btn-sm" id="outbox-btn-templates">${icon('folder', 14)} Templates</button>
        <button type="button" class="btn btn-secondary btn-sm" id="outbox-btn-slips">${icon('printer', 14)} ${t('outbox_fallback_print')}</button>
        <button type="button" class="btn btn-secondary btn-sm" id="outbox-btn-absent">${icon('alert', 14)} ${t('outbox_btn_absent')}</button>
        <button type="button" class="btn btn-secondary btn-sm" id="outbox-btn-fees">${icon('fees', 14)} ${t('outbox_btn_fees')}</button>
        <button type="button" class="btn btn-primary btn-sm" id="outbox-btn-circular">${icon('send', 14)} ${t('outbox_btn_circular')}</button>
      </div>
    </div>

    <!-- Status KPI Pills -->
    <div class="outbox-status-bar" id="outbox-kpi-bar">
      <div class="outbox-kpi-pill">Total: <strong id="kpi-total">0</strong></div>
      <div class="outbox-kpi-pill" style="border-color:#25D366;">Ready to Send: <strong id="kpi-ready" style="color:#1EBE5D;">0</strong></div>
      <div class="outbox-kpi-pill">Sent: <strong id="kpi-sent" style="color:var(--neel);">0</strong></div>
      <div class="outbox-kpi-pill">Absent Alerts Pending: <strong id="kpi-absent" style="color:var(--surkh);">0</strong></div>
    </div>

    <!-- Filters & Search -->
    <div class="filter-bar" style="margin-bottom:12px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <input type="search" class="form-control form-control-sm" id="outbox-search" placeholder="Search parent, phone, message..." style="width:260px;" />
      
      <select class="form-control form-control-sm" id="outbox-status-filter" style="width:140px;">
        <option value="all">All Statuses</option>
        <option value="ready" selected>Ready to Send</option>
        <option value="sent">Sent</option>
        <option value="queued">Queued</option>
        <option value="cancelled">Cancelled</option>
      </select>

      <select class="form-control form-control-sm" id="outbox-category-filter" style="width:150px;">
        <option value="all">All Categories</option>
        <option value="attendance">Attendance</option>
        <option value="fee_due">Fee Dues</option>
        <option value="result">Exam Result</option>
        <option value="circular">Circular</option>
      </select>

      <button type="button" class="btn btn-secondary btn-sm" id="outbox-refresh-btn">${icon('refresh', 13)} Refresh</button>
    </div>

    <!-- Message Queue Table -->
    <div class="panel">
      <div class="panel-body" style="padding:0;">
        <div class="table-responsive" id="outbox-table-wrap">
          <div style="padding:24px; text-align:center;">Loading Outbox records...</div>
        </div>
      </div>
      <div class="panel-footer" id="outbox-pagination" style="display:flex; justify-content:space-between; align-items:center; padding:10px 16px;"></div>
    </div>
  `;

  _bindEvents();
  _loadMessages();
}

function _bindEvents() {
  document.getElementById('outbox-btn-templates')?.addEventListener('click', () => openTemplatesModal(() => _loadMessages()));
  document.getElementById('outbox-btn-circular')?.addEventListener('click', () => openCircularModal(() => _loadMessages()));
  document.getElementById('outbox-btn-slips')?.addEventListener('click', () => openCircularSlipsPreview());

  document.getElementById('outbox-btn-absent')?.addEventListener('click', async () => {
    const btn = document.getElementById('outbox-btn-absent');
    if (btn) btn.disabled = true;
    try {
      const res = await apiPost('/api/outbox/generate/absent', {});
      alert(`Generated ${res?.enqueued || 0} absent alerts for today.`);
      _loadMessages();
    } catch (err) {
      alert('Error generating absent alerts: ' + err.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  document.getElementById('outbox-btn-fees')?.addEventListener('click', async () => {
    const btn = document.getElementById('outbox-btn-fees');
    if (btn) btn.disabled = true;
    try {
      const res = await apiPost('/api/outbox/generate/fee-reminders', { min_balance: 1 });
      alert(`Generated ${res?.enqueued || 0} fee reminders.`);
      _loadMessages();
    } catch (err) {
      alert('Error generating fee reminders: ' + err.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  document.getElementById('outbox-status-filter')?.addEventListener('change', e => {
    _outboxState.status = e.target.value;
    _outboxState.page = 1;
    _loadMessages();
  });

  document.getElementById('outbox-category-filter')?.addEventListener('change', e => {
    _outboxState.category = e.target.value;
    _outboxState.page = 1;
    _loadMessages();
  });

  document.getElementById('outbox-refresh-btn')?.addEventListener('click', () => _loadMessages());

  document.getElementById('outbox-search')?.addEventListener('input', e => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
      _outboxState.q = e.target.value.trim();
      _outboxState.page = 1;
      _loadMessages();
    }, 250);
  });

  const wrap = document.getElementById('outbox-table-wrap');
  delegate(wrap, 'click', '[data-outbox-action]', async (e, btn) => {
    const action = btn.getAttribute('data-outbox-action');
    const id = btn.getAttribute('data-msg-id');
    if (!id || !action) return;

    if (action === 'delete' && !confirm('Are you sure you want to delete this message?')) return;

    try {
      await apiPost(`/api/outbox/messages/${id}/action`, { action });
      _loadMessages();
    } catch (err) {
      alert('Action error: ' + err.message);
    }
  });
}

async function _loadMessages() {
  const wrap = document.getElementById('outbox-table-wrap');
  if (!wrap) return;

  const url = `/api/outbox/messages?status=${_outboxState.status}&category=${_outboxState.category}&page=${_outboxState.page}&per_page=${_outboxState.perPage}&q=${encodeURIComponent(_outboxState.q)}`;

  try {
    const res = await apiGet(url);
    const items = res?.items || [];
    const stats = res?.stats || {};

    // Update KPI pills
    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt('kpi-total', stats.total || 0);
    setTxt('kpi-ready', stats.ready || 0);
    setTxt('kpi-sent', stats.sent || 0);
    setTxt('kpi-absent', stats.absent_today_ready || 0);

    if (items.length === 0) {
      wrap.innerHTML = `<div style="padding:32px; text-align:center; color:var(--siyahi-soft);">${t('common_no_data')}</div>`;
      return;
    }

    wrap.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th style="width:130px;">Date & Recipient</th>
            <th style="width:120px;">Contact</th>
            <th style="width:100px;">Category</th>
            <th>Message Body Preview</th>
            <th style="width:90px;">Status</th>
            <th style="width:230px; text-align:right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(m => `
            <tr>
              <td>
                <div style="font-weight:600;">${esc(m.to_name)}</div>
                <small style="color:var(--siyahi-soft);">${esc(m.class_name || 'Class')}</small>
              </td>
              <td>
                <span class="phone-display">${esc(m.to_phone || 'No phone')}</span>
              </td>
              <td>
                <span class="badge badge-info">${esc(m.category)}</span>
              </td>
              <td>
                <div style="max-height:48px; overflow:hidden; text-overflow:ellipsis; font-size:12px; line-height:1.4;">
                  ${esc(m.body_text)}
                </div>
              </td>
              <td>
                <span class="badge badge-${m.status === 'sent' ? 'success' : m.status === 'ready' ? 'warning' : 'secondary'}">
                  ${esc(m.status)}
                </span>
              </td>
              <td style="text-align:right;">
                ${m.whatsapp_link && m.status === 'ready' ? `
                  <a href="${esc(m.whatsapp_link)}" target="_blank" class="btn btn-xs wa-btn" style="text-decoration:none;">
                    ${icon('whatsapp', 12)} ${t('outbox_open_wa')}
                  </a>
                ` : ''}
                ${m.status === 'ready' ? `
                  <button type="button" class="btn btn-secondary btn-xs" data-outbox-action="mark_sent" data-msg-id="${m.id}" title="Mark Delivered">
                    ${icon('check', 11)} Sent
                  </button>
                  <button type="button" class="btn btn-ghost btn-xs" data-outbox-action="cancel" data-msg-id="${m.id}" title="Cancel">
                    ${icon('x', 11)}
                  </button>
                ` : `
                  <button type="button" class="btn btn-ghost btn-xs" data-outbox-action="delete" data-msg-id="${m.id}" title="Delete">
                    ${icon('x', 11)}
                  </button>
                `}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;

    _renderPagination(res.page || 1, res.pages || 1, res.total || 0);
  } catch (err) {
    wrap.innerHTML = `<div style="padding:24px; color:var(--surkh);">Failed to load messages: ${esc(err.message)}</div>`;
  }
}

function _renderPagination(page, pages, total) {
  const foot = document.getElementById('outbox-pagination');
  if (!foot) return;
  foot.innerHTML = `
    <span style="font-size:12px; color:var(--siyahi-soft);">Showing page ${page} of ${pages} (${total} total messages)</span>
    <div style="display:flex; gap:6px;">
      <button type="button" class="btn btn-secondary btn-xs" id="outbox-prev-page" ${page <= 1 ? 'disabled' : ''}>Previous</button>
      <button type="button" class="btn btn-secondary btn-xs" id="outbox-next-page" ${page >= pages ? 'disabled' : ''}>Next</button>
    </div>
  `;

  document.getElementById('outbox-prev-page')?.addEventListener('click', () => {
    if (_outboxState.page > 1) {
      _outboxState.page--;
      _loadMessages();
    }
  });

  document.getElementById('outbox-next-page')?.addEventListener('click', () => {
    if (_outboxState.page < pages) {
      _outboxState.page++;
      _loadMessages();
    }
  });
}

