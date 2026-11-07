/**
 * screens/outbox/circular-modal.js — Compose General Notice / PTM Circular (Phase 5)
 */

import { apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc } from '../../core/dom.js';
import { icon } from '../../core/icons.js';
import { t } from '../../core/i18n.js';

export function openCircularModal(onSuccess) {
  const data = getBootstrap();
  const classes = data?.school?.standards || [];
  const classOpts = classes.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');

  const backdrop = document.getElementById('modal-backdrop');
  const titleEl  = document.getElementById('modal-title');
  const bodyEl   = document.getElementById('modal-body');
  const footEl   = document.getElementById('modal-footer');
  if (!backdrop || !bodyEl) return;

  titleEl.innerHTML = `${icon('mail', 18)} ${t('outbox_btn_circular')}`;
  bodyEl.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:12px;">
      <div class="form-group">
        <label class="form-label">Audience / Target</label>
        <select class="form-control" id="circ-target">
          <option value="all">Whole School (All Active Students)</option>
          <option value="class">Specific Class Section</option>
        </select>
      </div>

      <div class="form-group" id="circ-class-group" style="display:none;">
        <label class="form-label">Select Class</label>
        <select class="form-control" id="circ-class-id">
          ${classOpts}
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">Notice Title (e.g. Winter Break / PTM Notice)</label>
        <input type="text" class="form-control" id="circ-title" placeholder="Parent Teacher Meeting on Saturday" required />
      </div>

      <div class="form-group">
        <label class="form-label">Notice Message Details</label>
        <textarea class="form-control" id="circ-body" rows="4" placeholder="Dear Parents, you are requested to attend the PTM from 9:00 AM to 1:00 PM." required></textarea>
        <small style="color:var(--siyahi-soft); display:block; margin-top:4px;">
          Note: System will auto-insert student and school details for each guardian.
        </small>
      </div>
    </div>
  `;

  footEl.innerHTML = `
    <button type="button" class="btn btn-secondary" id="circ-btn-cancel">${t('common_cancel')}</button>
    <button type="button" class="btn btn-primary" id="circ-btn-submit">${icon('send', 14)} Queue for WhatsApp</button>
  `;

  backdrop.classList.add('open');

  const targetSel = document.getElementById('circ-target');
  targetSel?.addEventListener('change', e => {
    const classGrp = document.getElementById('circ-class-group');
    if (classGrp) classGrp.style.display = e.target.value === 'class' ? 'block' : 'none';
  });

  const close = () => backdrop.classList.remove('open');
  document.getElementById('circ-btn-cancel')?.addEventListener('click', close);
  document.getElementById('modal-close')?.addEventListener('click', close);

  document.getElementById('circ-btn-submit')?.addEventListener('click', async () => {
    const title = document.getElementById('circ-title')?.value.trim();
    const body = document.getElementById('circ-body')?.value.trim();
    const targetType = targetSel?.value || 'all';
    const classId = document.getElementById('circ-class-id')?.value;

    if (!title || !body) {
      alert('Please fill both Title and Message body.');
      return;
    }

    const btn = document.getElementById('circ-btn-submit');
    if (btn) btn.disabled = true;

    try {
      const res = await apiPost('/api/outbox/generate/circular', {
        title,
        body,
        target_type: targetType,
        class_id: targetType === 'class' && classId ? parseInt(classId, 10) : null,
      });

      if (res && res.ok) {
        close();
        if (onSuccess) onSuccess(res);
      } else {
        alert(res?.error || 'Failed to queue circular.');
      }
    } catch (err) {
      alert('Error creating circular: ' + err.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

