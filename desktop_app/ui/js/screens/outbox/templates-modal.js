/**
 * screens/outbox/templates-modal.js — Manage Message Templates (Phase 5)
 */

import { apiGet, apiPost } from '../../core/api.js';
import { esc } from '../../core/dom.js';
import { icon } from '../../core/icons.js';
import { t } from '../../core/i18n.js';

export async function openTemplatesModal(onSuccess) {
  const backdrop = document.getElementById('modal-backdrop');
  const titleEl  = document.getElementById('modal-title');
  const bodyEl   = document.getElementById('modal-body');
  const footEl   = document.getElementById('modal-footer');
  if (!backdrop || !bodyEl) return;

  titleEl.innerHTML = `${icon('folder', 18)} ${t('outbox_tab_templates')}`;
  bodyEl.innerHTML = '<div style="padding:24px; text-align:center;">Loading templates...</div>';
  footEl.innerHTML = `<button type="button" class="btn btn-secondary" id="tpl-modal-close">${t('common_cancel')}</button>`;

  backdrop.classList.add('open');

  const close = () => backdrop.classList.remove('open');
  document.getElementById('tpl-modal-close')?.addEventListener('click', close);
  document.getElementById('modal-close')?.addEventListener('click', close);

  try {
    const res = await apiGet('/api/outbox/templates');
    const templates = res?.templates || [];

    bodyEl.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:16px;">
        <p style="color:var(--siyahi-soft); margin:0; font-size:13px;">
          Edit the template text below. Supported variables: 
          <code>{student_name}</code>, <code>{guardian_name}</code>, <code>{class_name}</code>, 
          <code>{amount}</code>, <code>{due_date}</code>, <code>{percentage}</code>, <code>{grade}</code>, <code>{rank}</code>.
        </p>
        <div style="display:flex; flex-direction:column; gap:12px; max-height:420px; overflow-y:auto;">
          ${templates.map(tpl => `
            <div class="panel" style="padding:12px; border:1px solid var(--rule, #E3DAC9); border-radius:6px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <strong style="color:var(--chai);">${esc(tpl.title)}</strong>
                <span class="badge badge-info">${esc(tpl.code)}</span>
              </div>
              <input type="text" class="form-control form-control-sm" id="tpl-title-${tpl.id}" value="${esc(tpl.title)}" style="margin-bottom:6px;" />
              <textarea class="form-control form-control-sm" id="tpl-body-${tpl.id}" rows="3">${esc(tpl.body_template)}</textarea>
              <div style="text-align:right; margin-top:8px;">
                <button type="button" class="btn btn-secondary btn-xs" data-tpl-save="${tpl.id}">
                  ${icon('check', 12)} Save Template
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    bodyEl.querySelectorAll('[data-tpl-save]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-tpl-save');
        const title = document.getElementById(`tpl-title-${id}`)?.value.trim();
        const bodyTemplate = document.getElementById(`tpl-body-${id}`)?.value.trim();
        if (!title || !bodyTemplate) {
          alert('Title and body template cannot be empty.');
          return;
        }

        btn.disabled = true;
        btn.textContent = 'Saving...';
        try {
          const updateRes = await apiPost(`/api/outbox/templates/${id}`, {
            title,
            body_template: bodyTemplate,
          });
          if (updateRes && updateRes.ok) {
            btn.textContent = 'Saved!';
            setTimeout(() => {
              btn.disabled = false;
              btn.innerHTML = `${icon('check', 12)} Save Template`;
            }, 1500);
            if (onSuccess) onSuccess();
          } else {
            alert(updateRes?.error || 'Failed to update template.');
            btn.disabled = false;
          }
        } catch (err) {
          alert('Error: ' + err.message);
          btn.disabled = false;
        }
      });
    });
  } catch (err) {
    bodyEl.innerHTML = `<div style="color:var(--surkh); padding:16px;">Failed to load templates: ${esc(err.message)}</div>`;
  }
}

