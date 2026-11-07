/**
 * screens/fees/fees-workspace.js — Phase 3 Fees, Family Ledger & Print Workspace
 *
 * Replaces the legacy Fees tab with an exact-paisa enterprise billing console:
 *   1. Vouchers & Counter (`vouchers-tab.js`)
 *   2. Family Ledger (`family-tab.js`)
 *   3. Daily Cash Tally (`tally-defaulters-tab.js`)
 *   4. Overdue & Defaulters (`tally-defaulters-tab.js`)
 *   5. Rules & Scholarships (`rules-tab.js`)
 */

import { apiGet } from '../../core/api.js';
import { get, set, getBootstrap } from '../../core/state.js';
import { esc, openModal, closeModal } from '../../core/dom.js';
import { formatPaisa } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { openBulkGenerateModal, renderVouchersSubTab, setVouchersMonthFilter } from './vouchers-tab.js';
import { renderFamilySubTab } from './family-tab.js';
import { renderTallySubTab, renderDefaultersSubTab } from './tally-defaulters-tab.js';
import { renderRulesSubTab } from './rules-tab.js';
import { openVoucherPrintPreview } from '../../print/voucher-print.js';

let _activeTab = 'vouchers';

function _openBatchPrintModal() {
  const classes = getBootstrap()?.school?.standards || [];
  const nowMonth = new Date().toISOString().slice(0, 7);

  openModal('Batch Print 3-Part Bank Fee Vouchers', `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label" for="bp-month">Billing Month</label>
        <input class="form-control" id="bp-month" type="month" value="${esc(nowMonth)}" />
        <div class="form-hint">Leave blank to include all active billing months</div>
      </div>
      <div class="form-group">
        <label class="form-label" for="bp-class">Class</label>
        <select class="form-control" id="bp-class">
          <option value="">All Classes</option>
          ${classes.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}
        </select>
      </div>
    </div>
  `, async () => {
    const billingMonth = document.getElementById('bp-month')?.value?.trim() || '';
    const classId = document.getElementById('bp-class')?.value || '';
    closeModal();
    await openVoucherPrintPreview({ billingMonth, classId });
  }, { submitLabel: 'Preview Vouchers' });
}

async function _refreshKpiStrip() {
  try {
    const [tally, defs, defs30] = await Promise.all([
      apiGet('/api/fees/tally'),
      apiGet('/api/fees/defaulters'),
      apiGet('/api/fees/defaulters', { min_days_overdue: 30 }),
    ]);

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };
    setTxt('fees-kpi-today', formatPaisa(tally.net_collected_paisa || 0));
    setTxt('fees-kpi-today-sub', `${tally.active_receipts_count || 0} active receipts today`);
    setTxt('fees-kpi-due', formatPaisa(defs.total_due_paisa || 0));
    setTxt('fees-kpi-due-sub', `${defs.total || 0} open vouchers`);
    setTxt('fees-kpi-30d', String(defs30.total || 0));
    setTxt('fees-kpi-30d-sub', formatPaisa(defs30.total_due_paisa || 0));
    setTxt('fees-kpi-cash', formatPaisa(tally.by_mode_paisa?.cash || 0));
    setTxt('fees-kpi-cash-sub', `Bank/Online: ${formatPaisa((tally.by_mode_paisa?.bank || 0) + (tally.by_mode_paisa?.online || 0))}`);
  } catch {
    /* non-blocking */
  }
}

async function _mountActiveSubTab() {
  const mount = document.getElementById('fees-subtab-mount');
  if (!mount) return;

  document.querySelectorAll('[data-fees-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-fees-tab') === _activeTab);
  });

  if (_activeTab === 'family')     await renderFamilySubTab(mount, _refreshKpiStrip);
  else if (_activeTab === 'tally') await renderTallySubTab(mount, _refreshKpiStrip);
  else if (_activeTab === 'overdue') await renderDefaultersSubTab(mount, _refreshKpiStrip);
  else if (_activeTab === 'rules') await renderRulesSubTab(mount);
  else                             await renderVouchersSubTab(mount, _refreshKpiStrip);
}

export async function renderFeesScreen() {
  const requested = get('feesSubTab');
  if (requested) {
    _activeTab = requested;
    set({ feesSubTab: '' });
  }

  const html = `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Fees, Family Ledger &amp; Billing</div>
        <div class="page-header-desc">Exact paisa accounting, consolidated sibling accounts, daily cash tally &amp; 3-part bank vouchers</div>
      </div>
      <div class="page-header-actions">
        <button type="button" class="btn btn-secondary" id="fees-btn-batch-print">${icon('printer', 15)} Print Class Vouchers</button>
        <button type="button" class="btn btn-primary" id="fees-btn-bulk-gen">${icon('plus', 15)} Bulk Generate Vouchers</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Collected Today</div>
        <div class="kpi-value num" id="fees-kpi-today">Rs. 0</div>
        <div class="kpi-sub" id="fees-kpi-today-sub">Loading daily tally...</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Cash In Drawer Today</div>
        <div class="kpi-value num" id="fees-kpi-cash">Rs. 0</div>
        <div class="kpi-sub" id="fees-kpi-cash-sub">Bank/Online: Rs. 0</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Outstanding Dues</div>
        <div class="kpi-value num" id="fees-kpi-due">Rs. 0</div>
        <div class="kpi-sub" id="fees-kpi-due-sub">0 open vouchers</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">30+ Days Overdue Vouchers</div>
        <div class="kpi-value num" id="fees-kpi-30d">0</div>
        <div class="kpi-sub" id="fees-kpi-30d-sub">Rs. 0</div>
      </div>
    </div>

    <div class="panel" style="margin-bottom:var(--sp-4);">
      <div class="tab-bar" role="tablist" style="border-bottom:none;">
        <button type="button" class="tab-btn ${_activeTab === 'vouchers' ? 'active' : ''}" data-fees-tab="vouchers">Vouchers &amp; Counter</button>
        <button type="button" class="tab-btn ${_activeTab === 'family' ? 'active' : ''}" data-fees-tab="family">Family Ledger</button>
        <button type="button" class="tab-btn ${_activeTab === 'tally' ? 'active' : ''}" data-fees-tab="tally">Daily Cash Tally</button>
        <button type="button" class="tab-btn ${_activeTab === 'overdue' ? 'active' : ''}" data-fees-tab="overdue">Overdue &amp; Defaulters</button>
        <button type="button" class="tab-btn ${_activeTab === 'rules' ? 'active' : ''}" data-fees-tab="rules">Rules &amp; Scholarships</button>
      </div>
    </div>

    <div id="fees-subtab-mount"></div>
  `;

  setTimeout(() => {
    document.getElementById('fees-btn-batch-print')?.addEventListener('click', _openBatchPrintModal);
    document.getElementById('fees-btn-bulk-gen')?.addEventListener('click', () => {
      openBulkGenerateModal(async bm => {
        setVouchersMonthFilter(bm);
        _activeTab = 'vouchers';
        await _mountActiveSubTab();
        await _refreshKpiStrip();
      });
    });
    document.querySelectorAll('[data-fees-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        _activeTab = btn.getAttribute('data-fees-tab') || 'vouchers';
        _mountActiveSubTab();
      });
    });
    _refreshKpiStrip();
    _mountActiveSubTab();
  }, 20);

  return html;
}
