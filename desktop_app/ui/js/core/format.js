/**
 * format.js — Display Formatting Utilities
 *
 * Standardized currency (PKR), dates, percentages, student names, and calm status badges.
 */

/**
 * Format PKR amount — e.g. "Rs. 1,500" or "Rs. 1,500.50".
 * @param {number|string|null} val
 * @param {boolean} [showDecimals=false]
 * @returns {string}
 */
export function formatPKR(val, showDecimals = false) {
  const n = parseFloat(String(val || 0));
  if (isNaN(n)) return 'Rs. 0';
  const opts = {
    minimumFractionDigits: showDecimals ? 2 : 0,
    maximumFractionDigits: showDecimals ? 2 : 0,
  };
  return 'Rs.\u00A0' + n.toLocaleString('en-PK', opts);
}

/**
 * Format exact integer paisa as PKR ("Rs. 1,500" when whole rupees, "Rs. 1,500.55" when fractional).
 * @param {number|null|undefined} paisa
 * @returns {string}
 */
export function formatPaisa(paisa) {
  const p = Number(paisa || 0);
  if (!Number.isFinite(p)) return 'Rs.\u00A00';
  const hasCents = Math.abs(Math.trunc(p)) % 100 !== 0;
  return formatPKR(p / 100, hasCents);
}

/**
 * Compact PKR amount — "Rs. 45K", "Rs. 1.2M".
 * @param {number|string|null} val
 * @returns {string}
 */
export function formatPKRCompact(val) {
  const n = parseFloat(String(val || 0));
  if (isNaN(n) || n === 0) return 'Rs.\u00A0—';
  if (n >= 1_000_000) return `Rs.\u00A0${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `Rs.\u00A0${(n / 1_000).toFixed(0)}K`;
  return formatPKR(n);
}

const MONTHS_EN = [
  'Jan','Feb','Mar','Apr','May','Jun',
  'Jul','Aug','Sep','Oct','Nov','Dec'
];

function parseDate(val) {
  if (!val) return null;
  if (val instanceof Date) return isNaN(val) ? null : val;
  const m = String(val).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3]);
}

/**
 * Short date — "6 Nov 2026".
 * @param {string|Date|null} val
 * @returns {string}
 */
export function formatDate(val) {
  const d = parseDate(val);
  if (!d) return '—';
  return `${d.getDate()} ${MONTHS_EN[d.getMonth()]} ${d.getFullYear()}`;
}

/**
 * Relative day label in English — "Today", "Tomorrow", "Yesterday", "3 days ago".
 * @param {string|Date|null} val
 * @returns {string}
 */
export function formatRelative(val) {
  const d = parseDate(val);
  if (!d) return '—';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((d - today) / 86_400_000);
  if (diff === 0)  return 'Today';
  if (diff === 1)  return 'Tomorrow';
  if (diff === -1) return 'Yesterday';
  if (diff > 1)    return `In ${diff} days`;
  return `${Math.abs(diff)} days ago`;
}

/**
 * ISO timestamp to short time — "8:30 AM".
 * @param {string|null} iso
 * @returns {string}
 */
export function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return '—';
  let h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, '0');
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${h}:${m} ${ampm}`;
}

/**
 * ISO timestamp to compact date + time — "6 Nov 2026, 2:10 PM".
 * @param {string|null} iso
 * @returns {string}
 */
export function formatDateTime(iso) {
  if (!iso) return '—';
  const normalized = String(iso).includes('T') ? iso : String(iso).replace(' ', 'T') + 'Z';
  const d = new Date(normalized);
  if (isNaN(d)) return formatDate(iso);
  return `${d.getDate()} ${MONTHS_EN[d.getMonth()]} ${d.getFullYear()}, ${formatTime(d.toISOString())}`;
}

/**
 * Percentage format — "87%".
 * @param {number|string|null} val
 * @param {number} [decimals=0]
 * @returns {string}
 */
export function formatPct(val, decimals = 0) {
  const n = parseFloat(String(val || 0));
  if (isNaN(n)) return '—';
  return `${n.toFixed(decimals)}%`;
}

/**
 * Concatenate student full name cleanly.
 * @param {object} student
 * @returns {string}
 */
export function fullName(student) {
  return [student.student_name, student.middle, student.last]
    .filter(Boolean)
    .join(' ')
    .trim() || '—';
}

const STATE_LABELS = {
  draft:          'Draft',
  done:           'Enrolled',
  fees_received:  'Enrolled',
  alumni:         'Alumni',
  terminate:      'Terminated',
  cancel:         'Cancelled',
  cancelled:      'Cancelled',
  paid:           'Paid',
  confirm:        'Issued',
  pending:        'Partial / Due',
  rolled_over:    'Carried Forward',
  reversed:       'Reversed',
  validate:       'Validated',
  approve:        'Approved',
  toapprove:      'Pending Approval',
  reject:         'Rejected',
  running:        'Active',
  open:           'Open',
  close:          'Closed',
  active:         'Active',
  inactive:       'Inactive',
  available:      'Available',
  notavailable:   'Checked Out',
  pass:           'Pass',
  fail:           'Fail',
  fine:           'Overdue Fine',
  issue:          'Issued',
  return:         'Returned',
  expire:         'Expired',
  're-evaluation':'Re-Eval',
};

export function stateLabel(state) {
  return STATE_LABELS[String(state || '').toLowerCase()] || state;
}

/**
 * Calm Enterprise Badge Mapping (Section 9.2):
 *   - badge-success: strictly financial settlement / approval / pass
 *   - badge-info:    routine active operational states
 *   - badge-warn:    action-required / partial due queues
 *   - badge-danger:  true exceptions / reversals / rejections / fines
 *   - badge-neutral: quiet draft / archival / carried-forward states
 * @param {string} state
 * @returns {'badge-success'|'badge-warn'|'badge-danger'|'badge-info'|'badge-neutral'}
 */
export function stateBadgeClass(state) {
  const s = String(state || '').toLowerCase();
  if (['paid', 'approve', 'pass'].includes(s)) {
    return 'badge-success';
  }
  if (['done', 'fees_received', 'confirm', 'validate', 'running', 'open', 'active', 'available'].includes(s)) {
    return 'badge-info';
  }
  if (['pending', 'toapprove', 'issue', 're-evaluation', 're-evaluation_confirm', 'expire'].includes(s)) {
    return 'badge-warn';
  }
  if (['cancel', 'cancelled', 'terminate', 'reject', 'fail', 'fine', 'lost', 'reversed'].includes(s)) {
    return 'badge-danger';
  }
  return 'badge-neutral';
}
