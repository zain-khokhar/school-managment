/**
 * screens/settings/settings-screen.js — School Configuration, Backup/Restore & Audit (Phase 2 — G22)
 *
 * Implements SET-1..SET-6:
 *   - SET-1: 5-step First-Run Onboarding Checklist
 *   - SET-2: School Profile & Active Academic Year
 *   - SET-3/4: Bilingual Urdu Print toggle (D3) & Hostel/Transport module toggles
 *   - SET-5: SQLite WAL Backup, Integrity Check, Restore Drill & Recovery Code Rotation
 *   - SET-6: Staff Users & Role Matrix (via users-panel.js) + System Audit Trail
 */

import { apiGet, apiPost } from '../../core/api.js';
import { set, getBootstrap, setBilingual } from '../../core/state.js';
import { esc, toast, confirm, openModal, closeModal } from '../../core/dom.js';
import { formatDateTime } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { buildSidebar, navigateTo } from '../../core/router.js';
import { loadAndRenderUsersPanel } from './users-panel.js';

export async function renderSettingsScreen() {
  const [st, auditRes] = await Promise.all([
    apiGet('/api/settings'),
    apiGet('/api/audit/logs', { per_page: 25 }),
  ]);

  if (st.health) {
    set({ backupHealth: st.health });
    window.ERP?.refreshTopbarStatus?.();
  }

  const html = _buildSettingsHtml(st, auditRes.items || []);
  setTimeout(() => {
    _bindSettingsEvents(st);
    loadAndRenderUsersPanel('settings-users-panel');
  }, 20);
  return html;
}

function _buildSettingsHtml(st, logs) {
  const sch   = st.school || {};
  const prefs = st.preferences || {};
  const hlth  = st.health || {};
  const chk   = st.checklist || { steps: [], completed_count: 0, total_count: 5 };
  const years = st.years || [];
  const bks   = st.backups || [];

  const yearOpts = years.map(y =>
    `<option value="${esc(y.id)}" ${y.current ? 'selected' : ''}>${esc(y.name)}${y.current ? ' (Active)' : ''}</option>`
  ).join('');

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Settings, Backup &amp; Access Control</div>
        <div class="page-header-desc">Institution profile, module preferences, SQLite safety &amp; staff roles</div>
      </div>
    </div>

    <!-- SET-1: Onboarding Checklist -->
    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">First-Run Setup Progress (${chk.completed_count}/${chk.total_count})</div>
          <div class="panel-subtitle">Verify core institution setup steps</div>
        </div>
      </div>
      <div class="panel-body">
        <div class="checklist-strip">
          ${(chk.steps || []).map(s => `
            <button type="button" class="checklist-step ${s.done ? 'done' : ''}" data-set-goto="${esc(s.tab || 'settings')}">
              <span>${icon(s.done ? 'check' : 'arrow-right', 15)}</span>
              <span>${esc(s.label)}</span>
            </button>`).join('')}
        </div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:var(--sp-5); align-items:start;">
      <!-- SET-2: School Profile -->
      <div class="panel">
        <div class="panel-header"><div class="panel-title">Institution Profile &amp; Session (SET-2)</div></div>
        <form id="set-profile-form" class="panel-body">
          <div class="form-group">
            <label class="form-label required" for="sp-name">School Name</label>
            <input class="form-control" id="sp-name" value="${esc(sch.name || '')}" required />
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div class="form-group">
              <label class="form-label" for="sp-code">Institution Code</label>
              <input class="form-control" id="sp-code" value="${esc(sch.code || '')}" />
            </div>
            <div class="form-group">
              <label class="form-label" for="sp-year">Active Academic Year</label>
              <select class="form-control" id="sp-year">${yearOpts}</select>
            </div>
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div class="form-group">
              <label class="form-label" for="sp-phone">Office Phone</label>
              <input class="form-control" id="sp-phone" value="${esc(sch.phone || '')}" />
            </div>
            <div class="form-group">
              <label class="form-label" for="sp-city">City / Campus</label>
              <input class="form-control" id="sp-city" value="${esc(sch.city || '')}" />
            </div>
          </div>
          <button type="submit" class="btn btn-primary">Save Institution Profile</button>
        </form>
      </div>

      <!-- SET-3 & SET-4: Preferences & Module Visibility -->
      <div class="panel">
        <div class="panel-header"><div class="panel-title">Print &amp; Campus Module Preferences (SET-3 / SET-4)</div></div>
        <div class="panel-body">
          <div class="setting-toggle-row">
            <div>
              <div style="font-weight:600;">Bilingual English + Urdu Prints (D3)</div>
              <div style="font-size:12px; color:var(--siyahi-soft);">Show Urdu labels alongside English on parent-facing profiles &amp; slips</div>
            </div>
            <input type="checkbox" id="pref-bilingual" ${prefs.bilingual_prints ? 'checked' : ''} style="width:18px; height:18px;" />
          </div>
          <div class="setting-toggle-row">
            <div>
              <div style="font-weight:600;">Enable Boarding / Hostel Module</div>
              <div style="font-size:12px; color:var(--siyahi-soft);">Hide Hostel from sidebar for day-scholar-only schools</div>
            </div>
            <input type="checkbox" id="pref-hostel" ${prefs.enable_hostel !== false ? 'checked' : ''} style="width:18px; height:18px;" />
          </div>
          <div class="setting-toggle-row">
            <div>
              <div style="font-weight:600;">Enable Fleet / Transport Module</div>
              <div style="font-size:12px; color:var(--siyahi-soft);">Show school van/bus routes &amp; fee registrations</div>
            </div>
            <input type="checkbox" id="pref-transport" ${prefs.enable_transport !== false ? 'checked' : ''} style="width:18px; height:18px;" />
          </div>
          <div class="setting-toggle-row">
            <div>
              <div style="font-weight:600;">Ramazan / Winter Short-Period Timings</div>
              <div style="font-size:12px; color:var(--siyahi-soft);">Flag shorter bell schedule across timetable views</div>
            </div>
            <input type="checkbox" id="pref-ramazan" ${prefs.ramazan_mode ? 'checked' : ''} style="width:18px; height:18px;" />
          </div>
          <div style="margin-top:14px;">
            <button type="button" class="btn btn-primary" id="btn-save-prefs">Save Preferences</button>
          </div>
        </div>
      </div>
    </div>

    <!-- SET-5: Backup, Integrity Check & Emergency Recovery Key -->
    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">Database Safety, WAL Backups &amp; Recovery Key (SET-5)</div>
          <div class="panel-subtitle">
            SQLite Integrity: <strong>${hlth.integrity_ok ? 'Healthy (OK)' : 'Check Required'}</strong> •
            Size: <strong class="num">${esc(hlth.db_size_kb || 0)} KB</strong> •
            Last Backup: <strong>${hlth.last_backup_at ? esc(formatDateTime(hlth.last_backup_at)) : 'Never'}</strong>
          </div>
        </div>
        <div class="panel-toolbar">
          <button type="button" class="btn btn-secondary btn-sm" id="btn-rotate-rk">${icon('key', 14)} Rotate Recovery Key</button>
          <button type="button" class="btn btn-primary btn-sm" id="btn-create-backup">${icon('database', 14)} Create Safe Backup Now</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Backup File</th><th>Created At</th><th class="num">Size (KB)</th><th>Action</th></tr></thead>
          <tbody>
            ${bks.slice(0, 8).map(b => `
              <tr>
                <td class="num" style="font-weight:500;">${esc(b.filename)}</td>
                <td>${esc(formatDateTime(b.created_at))}</td>
                <td class="num">${esc(b.size_kb)} KB</td>
                <td><button type="button" class="btn btn-xs btn-secondary" data-restore-file="${esc(b.filename)}">Restore Snapshot</button></td>
              </tr>`).join('') || `<tr><td colspan="4" style="padding:18px; text-align:center; color:var(--siyahi-soft);">No snapshots created yet — click "Create Safe Backup Now".</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>

    <!-- SET-6: Staff Users & Roles -->
    <div class="panel" id="settings-users-panel"></div>

    <!-- System Audit Log -->
    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">System Audit Log</div>
          <div class="panel-subtitle">Every mutating operation is recorded with staff username, role &amp; timestamp</div>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Timestamp</th><th>Staff</th><th>Role</th><th>Action</th><th>Summary</th></tr></thead>
          <tbody>
            ${logs.map(l => `
              <tr>
                <td class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(formatDateTime(l.created_at))}</td>
                <td style="font-weight:600;">${esc(l.username)}</td>
                <td><span class="badge badge-neutral">${esc(l.role)}</span></td>
                <td class="num" style="font-size:12px;">${esc(l.action)}</td>
                <td>${esc(l.summary)}</td>
              </tr>`).join('') || `<tr><td colspan="5" style="padding:18px; text-align:center;">No audit entries recorded yet.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>`;
}

function _bindSettingsEvents() {
  document.querySelectorAll('[data-set-goto]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-set-goto');
      if (target && target !== 'settings') navigateTo(target);
    });
  });

  document.getElementById('set-profile-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const name = document.getElementById('sp-name').value.trim();
    await apiPost('/api/settings/profile', {
      name,
      code:             document.getElementById('sp-code').value.trim(),
      phone:            document.getElementById('sp-phone').value.trim(),
      city:             document.getElementById('sp-city').value.trim(),
      academic_year_id: parseInt(document.getElementById('sp-year').value, 10) || null,
    });
    set({ schoolName: name });
    const brand = document.getElementById('brand-school-name');
    if (brand) brand.textContent = name;
    toast('Institution profile updated', 'success');
    navigateTo('settings');
  });

  document.getElementById('btn-save-prefs')?.addEventListener('click', async () => {
    const prefs = {
      bilingual_prints: document.getElementById('pref-bilingual').checked,
      enable_hostel:    document.getElementById('pref-hostel').checked,
      enable_transport: document.getElementById('pref-transport').checked,
      ramazan_mode:     document.getElementById('pref-ramazan').checked,
    };
    await apiPost('/api/settings/preferences', prefs);
    set({ preferences: prefs });
    setBilingual(prefs.bilingual_prints);
    buildSidebar(getBootstrap());
    toast('Preferences saved and navigation updated', 'success');
  });

  document.getElementById('btn-create-backup')?.addEventListener('click', async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const res = await apiPost('/api/settings/backup', { note: 'Manual backup from Settings' });
      toast(`Backup saved: ${res.backup.filename}`, 'success');
      navigateTo('settings');
    } catch (err) {
      toast(err.message, 'error');
      btn.disabled = false;
    }
  });

  document.querySelectorAll('[data-restore-file]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const fn = btn.getAttribute('data-restore-file');
      const ok = await confirm(
        'Restore Database Snapshot?',
        `This will create an automatic safety snapshot of current data and restore '${fn}'. Continue?`,
        { confirmLabel: 'Restore Database', confirmClass: 'btn-danger' }
      );
      if (!ok) return;
      await apiPost('/api/settings/restore', { filename: fn });
      toast('Database restored successfully. Reloading workspace...', 'success');
      setTimeout(() => window.location.reload(), 700);
    });
  });

  document.getElementById('btn-rotate-rk')?.addEventListener('click', () => {
    openModal('Rotate Emergency Recovery Key', `
      <p style="font-size:13px; color:var(--siyahi-soft); margin-bottom:12px;">
        Confirm your current Administrator password/PIN to generate a fresh emergency recovery code. Any previous code will stop working immediately.
      </p>
      <div class="form-group">
        <label class="form-label required" for="rk-cur-secret">Current Password / PIN</label>
        <input class="form-control" id="rk-cur-secret" type="password" required autofocus />
      </div>
    `, async () => {
      const current_secret = document.getElementById('rk-cur-secret')?.value || '';
      const res = await apiPost('/api/settings/recovery-code', { current_secret });
      openModal('New Emergency Recovery Key', `
        <div class="recovery-box">
          <div style="font-size:11px; color:var(--siyahi-soft); text-transform:uppercase;">Write Down or Print Immediately</div>
          <div class="recovery-code-display">${esc(res.recovery_code)}</div>
        </div>
      `, async () => closeModal(), { submitLabel: 'Done' });
    }, { submitLabel: 'Generate New Key' });
  });
}
