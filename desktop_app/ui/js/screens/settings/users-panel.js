/**
 * screens/settings/users-panel.js — Staff Accounts, Roles & PIN Management (Phase 2 — SET-6)
 *
 * Extracted from settings-screen.js so both modules stay <= 250 lines.
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal, confirm } from '../../core/dom.js';
import { formatDateTime } from '../../core/format.js';
import { icon } from '../../core/icons.js';

const ROLE_LABELS = {
  admin:         'Administrator',
  principal:     'Principal',
  teacher:       'Class / Subject Teacher',
  fee_clerk:     'Fee Clerk',
  front_desk:    'Front Desk / Admissions',
  exam_incharge: 'Exam In-Charge',
};

export async function loadAndRenderUsersPanel(containerId) {
  const wrap = document.getElementById(containerId);
  if (!wrap) return;

  try {
    const res = await apiGet('/api/auth/users');
    const users = res.users || [];
    wrap.innerHTML = _buildUsersTableHtml(users);
    _bindUserPanelEvents(wrap, containerId);
  } catch (err) {
    wrap.innerHTML = `<div class="panel-body" style="color:var(--siyahi-soft);">${esc(err.message)}</div>`;
  }
}

function _buildUsersTableHtml(users) {
  const rows = users.map(u => {
    const isLocked = u.locked_until && new Date(u.locked_until) > new Date();
    return `
      <tr>
        <td style="font-weight:600;">${esc(u.full_name)}</td>
        <td class="num">${esc(u.username)}</td>
        <td><span class="badge badge-info">${esc(ROLE_LABELS[u.role] || u.role)}</span></td>
        <td>
          ${!u.active
            ? '<span class="badge badge-neutral">Disabled</span>'
            : isLocked
              ? '<span class="badge badge-danger">Locked Out</span>'
              : '<span class="badge badge-neutral">Active</span>'}
        </td>
        <td style="font-size:12px; color:var(--siyahi-soft);">${esc(formatDateTime(u.last_login_at))}</td>
        <td>
          <div style="display:flex; gap:6px;">
            <button type="button" class="btn btn-xs btn-secondary" data-usr-reset="${esc(u.id)}" data-usr-name="${esc(u.username)}">Reset PIN</button>
            ${isLocked ? `<button type="button" class="btn btn-xs btn-primary" data-usr-act="unlock" data-usr-id="${esc(u.id)}">Unlock</button>` : ''}
            ${u.active
              ? `<button type="button" class="btn btn-xs btn-ghost" data-usr-act="disable" data-usr-id="${esc(u.id)}">Disable</button>`
              : `<button type="button" class="btn btn-xs btn-secondary" data-usr-act="enable" data-usr-id="${esc(u.id)}">Enable</button>`}
          </div>
        </td>
      </tr>`;
  }).join('');

  return `
    <div class="panel-header">
      <div>
        <div class="panel-title">Staff Accounts &amp; Role Access (SET-6)</div>
        <div class="panel-subtitle">Each staff member sees only their assigned operational workspace</div>
      </div>
      <button type="button" class="btn btn-primary btn-sm" id="btn-add-staff">${icon('plus', 14)} Add Staff Account</button>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Full Name</th><th>Username</th><th>Assigned Role</th><th>Status</th><th>Last Sign-In</th><th>Actions</th></tr>
        </thead>
        <tbody>${rows || `<tr><td colspan="6" style="padding:20px; text-align:center;">No staff accounts found.</td></tr>`}</tbody>
      </table>
    </div>`;
}

function _bindUserPanelEvents(wrap, containerId) {
  wrap.querySelector('#btn-add-staff')?.addEventListener('click', () => {
    _openCreateStaffModal(() => loadAndRenderUsersPanel(containerId));
  });

  wrap.querySelectorAll('[data-usr-reset]').forEach(btn => {
    btn.addEventListener('click', () => {
      const uid = parseInt(btn.getAttribute('data-usr-reset'), 10);
      const uname = btn.getAttribute('data-usr-name');
      openModal(`Reset PIN / Password — ${uname}`, `
        <div class="form-group">
          <label class="form-label required" for="rst-secret">New Password / PIN (min 6 chars)</label>
          <input class="form-control" id="rst-secret" type="password" minlength="6" required autofocus />
        </div>
      `, async () => {
        const new_secret = document.getElementById('rst-secret')?.value || '';
        await apiPost(`/api/auth/users/${uid}/action`, { action: 'reset_secret', new_secret });
        toast(`Credentials updated for ${uname}`, 'success');
        closeModal();
        loadAndRenderUsersPanel(containerId);
      }, { submitLabel: 'Update Credentials' });
    });
  });

  wrap.querySelectorAll('[data-usr-act]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const uid = parseInt(btn.getAttribute('data-usr-id'), 10);
      const act = btn.getAttribute('data-usr-act');
      if (act === 'disable') {
        const ok = await confirm('Disable Staff Account', 'Revoke active sessions and prevent sign-in for this user?');
        if (!ok) return;
      }
      try {
        await apiPost(`/api/auth/users/${uid}/action`, { action: act });
        toast(`Account action '${act}' applied`, 'success');
        loadAndRenderUsersPanel(containerId);
      } catch (err) {
        toast(err.message, 'error');
      }
    });
  });
}

function _openCreateStaffModal(onDone) {
  const teachers = getBootstrap()?.school?.teachers || [];
  const roleOpts = Object.entries(ROLE_LABELS)
    .map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join('');
  const teacherOpts = teachers
    .map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('');

  openModal('Create Staff Account', `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
      <div class="form-group">
        <label class="form-label required" for="stf-fullname">Full Name</label>
        <input class="form-control" id="stf-fullname" placeholder="e.g. Ayesha Siddiqui" required autofocus />
      </div>
      <div class="form-group">
        <label class="form-label required" for="stf-username">Username</label>
        <input class="form-control" id="stf-username" placeholder="e.g. ayesha" required />
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
      <div class="form-group">
        <label class="form-label required" for="stf-role">Operational Role</label>
        <select class="form-control" id="stf-role">${roleOpts}</select>
      </div>
      <div class="form-group">
        <label class="form-label" for="stf-teacher">Linked Faculty Profile (for Teachers)</label>
        <select class="form-control" id="stf-teacher">
          <option value="">— Optional —</option>${teacherOpts}
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label required" for="stf-secret">Initial Password or PIN (min 6 chars)</label>
      <input class="form-control" id="stf-secret" type="password" minlength="6" required />
    </div>
  `, async () => {
    const teacherVal = document.getElementById('stf-teacher')?.value;
    await apiPost('/api/auth/users', {
      full_name:  document.getElementById('stf-fullname')?.value.trim(),
      username:   document.getElementById('stf-username')?.value.trim(),
      role:       document.getElementById('stf-role')?.value,
      teacher_id: teacherVal ? parseInt(teacherVal, 10) : null,
      secret:     document.getElementById('stf-secret')?.value || '',
    });
    toast('Staff account created', 'success');
    closeModal();
    onDone();
  }, { submitLabel: 'Create Account' });
}
