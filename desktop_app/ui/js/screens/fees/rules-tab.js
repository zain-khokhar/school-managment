/**
 * screens/fees/rules-tab.js — School Fee Rules & Student Scholarships / Concessions (G5)
 *
 * Role-aware: Admin & Principal can configure rules and grant/deactivate scholarships;
 * Fee Clerks have full read visibility for counter transparency.
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap, get } from '../../core/state.js';
import { esc, toast, confirm, openModal, closeModal } from '../../core/dom.js';
import { formatPKR } from '../../core/format.js';
import { icon } from '../../core/icons.js';

function _openRuleModal(onSaved) {
  openModal('Add / Update School Fee Policy Rule', `
    <div style="display:grid; grid-template-columns:1.4fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="rl-name">Rule Name</label>
        <input class="form-control" id="rl-name" placeholder="e.g. Sibling Tuition Concession" required />
      </div>
      <div class="form-group">
        <label class="form-label required" for="rl-code">Unique Code</label>
        <input class="form-control" id="rl-code" placeholder="e.g. SIB-10" required />
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="rl-type">Rule Type</label>
        <select class="form-control" id="rl-type">
          <option value="sibling_discount">Sibling Discount</option>
          <option value="late_fee">After-Due Late Surcharge</option>
          <option value="vacation_discount">Summer / Vacation Discount</option>
          <option value="custom_discount">General Concession</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="rl-mode">Calculation</label>
        <select class="form-control" id="rl-mode">
          <option value="percent">Percentage (%)</option>
          <option value="fixed_paisa">Fixed Amount (PKR)</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="rl-val">Value (% or PKR)</label>
        <input class="form-control num" id="rl-val" type="number" step="0.01" min="0" value="10" required />
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label" for="rl-sib">Min Sibling Rank</label>
        <input class="form-control num" id="rl-sib" type="number" min="2" value="2" />
      </div>
      <div class="form-group">
        <label class="form-label" for="rl-grace">Grace Days</label>
        <input class="form-control num" id="rl-grace" type="number" min="0" value="5" />
      </div>
      <div class="form-group">
        <label class="form-label" for="rl-vac">Vacation Months (e.g. 6,7)</label>
        <input class="form-control" id="rl-vac" placeholder="6,7" />
      </div>
    </div>
  `, async () => {
    const calc_mode = document.getElementById('rl-mode')?.value || 'percent';
    const rawVal = parseFloat(document.getElementById('rl-val')?.value || '0');
    const payload = {
      name:             document.getElementById('rl-name')?.value?.trim(),
      code:             document.getElementById('rl-code')?.value?.trim(),
      rule_type:        document.getElementById('rl-type')?.value,
      calc_mode,
      min_sibling_rank: parseInt(document.getElementById('rl-sib')?.value || '2', 10),
      grace_days:       parseInt(document.getElementById('rl-grace')?.value || '0', 10),
      vacation_months:  document.getElementById('rl-vac')?.value?.trim() || '',
      active:           true,
    };
    if (calc_mode === 'percent') payload.value = Math.round(rawVal);
    else payload.value_rupees = rawVal;

    await apiPost('/api/fees/rules', payload);
    closeModal();
    toast('Fee policy rule saved.', 'success');
    onSaved?.();
  }, { submitLabel: 'Save Rule' });
}

function _openConcessionModal(onSaved) {
  const students = (getBootstrap()?.school?.students || []).filter(s => s.active !== 0);
  openModal('Grant Student Scholarship / Concession', `
    <div class="form-group">
      <label class="form-label required" for="cn-stu">Student</label>
      <select class="form-control" id="cn-stu" required>
        <option value="">— Select Student —</option>
        ${students.map(s => `<option value="${esc(s.id)}">${esc(s.student_name)} ${esc(s.last || '')} (${esc(s.pid || '')} • ${esc(s.class_name || '—')})</option>`).join('')}
      </select>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="cn-type">Category</label>
        <select class="form-control" id="cn-type">
          <option value="scholarship">Merit Scholarship</option>
          <option value="sibling">Sibling Concession</option>
          <option value="staff_child">Staff Child Ward</option>
          <option value="financial_aid">Need-Based Aid</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="cn-mode">Calculation</label>
        <select class="form-control" id="cn-mode">
          <option value="percent">Percentage (%)</option>
          <option value="fixed_paisa">Fixed Amount (PKR)</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="cn-val">Value (% or PKR)</label>
        <input class="form-control num" id="cn-val" type="number" step="0.01" min="1" value="25" required />
      </div>
    </div>
    <div class="form-group">
      <label class="form-label required" for="cn-reason">Approval Note / Citation</label>
      <input class="form-control" id="cn-reason" placeholder="e.g. Board Position Holder / Principal Approval" required />
    </div>
  `, async () => {
    const calc_mode = document.getElementById('cn-mode')?.value || 'percent';
    const rawVal = parseFloat(document.getElementById('cn-val')?.value || '0');
    const body = {
      student_id:      parseInt(document.getElementById('cn-stu')?.value || '0', 10),
      concession_type: document.getElementById('cn-type')?.value,
      calc_mode,
      reason:          document.getElementById('cn-reason')?.value?.trim(),
    };
    if (calc_mode === 'percent') body.value = Math.round(rawVal);
    else body.value_rupees = rawVal;

    await apiPost('/api/fees/concessions', body);
    closeModal();
    toast('Student scholarship/concession granted.', 'success');
    onSaved?.();
  }, { submitLabel: 'Grant Concession' });
}

export async function renderRulesSubTab(mountEl) {
  const canEdit = ['admin', 'principal'].includes(get('role') || 'admin');
  const [rulesRes, concRes] = await Promise.all([
    apiGet('/api/fees/rules'),
    apiGet('/api/fees/concessions'),
  ]);

  const rules = rulesRes.items || [];
  const concs = concRes.items || [];

  mountEl.innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1.15fr; gap:var(--sp-4); align-items:start;">
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">School-Wide Fee Policy Rules</div>
            <div class="panel-subtitle">Auto-applied during monthly bulk voucher generation</div>
          </div>
          ${canEdit ? `<button type="button" class="btn btn-primary btn-sm" id="rl-add-btn">${icon('plus', 14)} Add / Edit Rule</button>` : ''}
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Code</th><th>Rule</th><th>Type</th><th class="num">Value</th><th>Status</th></tr></thead>
            <tbody>
              ${rules.map(r => `
                <tr>
                  <td class="num" style="font-weight:600;">${esc(r.code)}</td>
                  <td>${esc(r.name)}</td>
                  <td><span class="badge badge-neutral">${esc(r.rule_type.replace('_', ' '))}</span></td>
                  <td class="num">${r.calc_mode === 'percent' ? `${esc(r.value)}%` : esc(formatPKR(r.value_rupees))}</td>
                  <td><span class="badge ${r.active ? 'badge-info' : 'badge-neutral'}">${r.active ? 'Active' : 'Inactive'}</span></td>
                </tr>`).join('') || `<tr><td colspan="5" style="text-align:center; padding:22px; color:var(--siyahi-soft);">No school-wide fee rules configured yet.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Student Scholarships &amp; Concessions</div>
            <div class="panel-subtitle">Individual tuition waivers &amp; merit scholarships</div>
          </div>
          ${canEdit ? `<button type="button" class="btn btn-primary btn-sm" id="cn-add-btn">${icon('plus', 14)} Grant Concession</button>` : ''}
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Student</th><th>Category</th><th class="num">Discount</th><th>Reason</th>${canEdit ? '<th>Action</th>' : ''}</tr></thead>
            <tbody>
              ${concs.map(c => `
                <tr>
                  <td>
                    <div style="font-weight:600;">${esc(c.student_name)} ${esc(c.last || '')}</div>
                    <div style="font-size:11.5px; color:var(--siyahi-soft);">${esc(c.pid || '')} • ${esc(c.class_name || '—')}</div>
                  </td>
                  <td><span class="badge badge-info">${esc(c.concession_type.replace('_', ' '))}</span></td>
                  <td class="num" style="font-weight:600;">${c.calc_mode === 'percent' ? `${esc(c.value)}%` : esc(formatPKR(c.value_rupees))}</td>
                  <td style="font-size:12px; color:var(--siyahi-soft);">${esc(c.reason || '—')}</td>
                  ${canEdit ? `<td><button type="button" class="btn btn-xs btn-secondary" data-cn-del="${esc(c.id)}">Remove</button></td>` : ''}
                </tr>`).join('') || `<tr><td colspan="${canEdit ? 5 : 4}" style="text-align:center; padding:22px; color:var(--siyahi-soft);">No active student concessions granted yet.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;

  const reload = () => renderRulesSubTab(mountEl);
  document.getElementById('rl-add-btn')?.addEventListener('click', () => _openRuleModal(reload));
  document.getElementById('cn-add-btn')?.addEventListener('click', () => _openConcessionModal(reload));
  mountEl.querySelectorAll('[data-cn-del]').forEach(btn => {
    btn.onclick = async () => {
      const cid = parseInt(btn.getAttribute('data-cn-del'), 10);
      const ok = await confirm('Deactivate Concession?', 'Future monthly vouchers for this student will no longer apply this concession.', {
        confirmLabel: 'Remove Concession',
        confirmClass: 'btn-danger',
      });
      if (!ok) return;
      await apiPost(`/api/fees/concessions/${cid}/delete`, {});
      toast('Concession deactivated.', 'info');
      reload();
    };
  });
}
