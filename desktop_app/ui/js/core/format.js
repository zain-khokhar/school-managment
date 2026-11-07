/**
 * format.js — Display formatting utilities
 * Currency (PKR), dates (Urdu/English), percentages, durations.
 * Koi hard-coded string nahi — sab yahan se aaye.
 */

// ─── Currency ─────────────────────────────────────────────────────────────────

/**
 * PKR amount format karo — Rs. 1,500 or Rs. 1,500.50
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
 * Compact amount — Rs. 1.2K, Rs. 45K, Rs. 1.2M
 * KPI cards ke liye jab space kam ho
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

// ─── Dates ────────────────────────────────────────────────────────────────────

const MONTHS_EN = [
  'Jan','Feb','Mar','Apr','May','Jun',
  'Jul','Aug','Sep','Oct','Nov','Dec'
];

/**
 * Date string parse karo — 'YYYY-MM-DD' ya JS Date se
 * @param {string|Date|null} val
 * @returns {Date|null}
 */
function parseDate(val) {
  if (!val) return null;
  if (val instanceof Date) return isNaN(val) ? null : val;
  // 'YYYY-MM-DD' — parse as local (not UTC) to avoid timezone shift
  const m = String(val).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3]);
}

/**
 * Short date — "6 Nov 2026"
 * @param {string|Date|null} val
 * @returns {string}
 */
export function formatDate(val) {
  const d = parseDate(val);
  if (!d) return '—';
  return `${d.getDate()} ${MONTHS_EN[d.getMonth()]} ${d.getFullYear()}`;
}

/**
 * Relative date — "aaj", "kal", "3 din pehle"
 * @param {string|Date|null} val
 * @returns {string}
 */
export function formatRelative(val) {
  const d = parseDate(val);
  if (!d) return '—';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((d - today) / 86_400_000);
  if (diff === 0)   return 'Aaj';
  if (diff === 1)   return 'Kal';
  if (diff === -1)  return 'Kal (guzra)';
  if (diff > 1)     return `${diff} din baad`;
  return `${Math.abs(diff)} din pehle`;
}

/**
 * ISO timestamp to short time — "8:30 AM"
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

// ─── Percentage ───────────────────────────────────────────────────────────────

/**
 * Percentage format — "87%"
 * @param {number|string|null} val
 * @param {number} [decimals=0]
 * @returns {string}
 */
export function formatPct(val, decimals = 0) {
  const n = parseFloat(String(val || 0));
  if (isNaN(n)) return '—';
  return `${n.toFixed(decimals)}%`;
}

// ─── Name ─────────────────────────────────────────────────────────────────────

/**
 * Full naam banao — first + middle + last (empty parts skip karo)
 * @param {object} student
 * @returns {string}
 */
export function fullName(student) {
  return [student.student_name, student.middle, student.last]
    .filter(Boolean)
    .join(' ')
    .trim() || '—';
}

// ─── Status → badge text mapping ──────────────────────────────────────────────

/** Backend state values ko human-readable English mein convert karo */
const STATE_LABELS = {
  draft:        'Draft',
  done:         'Enrolled',
  alumni:       'Alumni',
  terminate:    'Terminated',
  cancel:       'Cancelled',
  paid:         'Paid',
  confirm:      'Confirmed',
  validate:     'Validated',
  approve:      'Approved',
  toapprove:    'Pending Approval',
  reject:       'Rejected',
  running:      'Active',
  open:         'Open',
  close:        'Closed',
  active:       'Active',
  inactive:     'Inactive',
  available:    'Available',
  notavailable: 'Not Available',
  pass:         'Pass',
  fail:         'Fail',
  fine:         'Overdue Fine',
  issue:        'Issued',
  return:       'Returned',
  expire:       'Expired',
};

/**
 * State string ko label mein convert karo
 * @param {string} state
 * @returns {string}
 */
export function stateLabel(state) {
  return STATE_LABELS[String(state || '').toLowerCase()] || state;
}

/**
 * State string ko badge class mein convert karo
 * @param {string} state
 * @returns {'badge-success'|'badge-warn'|'badge-danger'|'badge-info'|'badge-neutral'}
 */
export function stateBadgeClass(state) {
  const s = String(state || '').toLowerCase();
  if (['done', 'paid', 'confirm', 'validate', 'approve', 'running',
       'available', 'pass', 'open', 'active', 'return'].includes(s)) {
    return 'badge-success';
  }
  if (['draft', 'pending', 'toapprove', 'issue'].includes(s)) {
    return 'badge-warn';
  }
  if (['cancel', 'terminate', 'reject', 'fail', 'fine',
       'notavailable', 'expire', 'close', 'alumni'].includes(s)) {
    return 'badge-danger';
  }
  return 'badge-neutral';
}

