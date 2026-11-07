/**
 * i18n.js — Bilingual toggle support (D3 decision)
 * English full UI; settings toggle enable karne pe
 * parents-facing screens mein Urdu below/English above.
 * Koi external library nahi — simple key lookup.
 */

import { isBilingual, setBilingual } from './state.js';
export { isBilingual, setBilingual };

/**
 * UI strings — English (default) + Urdu (bilingual mode)
 * Format: { key: { en: '...', ur: '...' } }
 * Urdu sirf parents-facing cards/prints mein dikhega.
 */
export const STRINGS = {
  // ── Navigation ────────────────────────────────────────────
  nav_dashboard:    { en: 'Dashboard',       ur: 'مرکزی صفحہ'       },
  nav_students:     { en: 'Students',        ur: 'طلبہ'             },
  nav_attendance:   { en: 'Attendance',      ur: 'حاضری'            },
  nav_fees:         { en: 'Fee Management',  ur: 'فیس'              },
  nav_exam:         { en: 'Exams & Results', ur: 'امتحانات'         },
  nav_timetable:    { en: 'Timetable',       ur: 'نظام الاوقات'     },
  nav_library:      { en: 'Library',         ur: 'کتب خانہ'         },
  nav_transport:    { en: 'Transport',       ur: 'نقل و حمل'        },
  nav_events:       { en: 'Events',          ur: 'تقریبات'          },

  // ── Attendance Screen ──────────────────────────────────────
  att_title:        { en: 'Mark Attendance',   ur: 'حاضری لگائیں'  },
  att_present:      { en: 'Present',           ur: 'حاضر'           },
  att_absent:       { en: 'Absent',            ur: 'غیر حاضر'      },
  att_on_leave:     { en: 'On Leave',          ur: 'چھٹی'           },
  att_submit:       { en: 'Submit Attendance', ur: 'حاضری جمع کریں' },
  att_total:        { en: 'Total',             ur: 'کل'             },
  att_validate_ok:  { en: 'Attendance saved!', ur: 'حاضری محفوظ!'   },

  // ── Students ───────────────────────────────────────────────
  stu_gr_no:        { en: 'GR No.',     ur: 'جی آر نمبر'     },
  stu_name:         { en: 'Name',       ur: 'نام'             },
  stu_class:        { en: 'Class',      ur: 'جماعت'           },
  stu_roll:         { en: 'Roll No.',   ur: 'رول نمبر'        },
  stu_status:       { en: 'Status',     ur: 'حیثیت'           },
  stu_dob:          { en: 'Date of Birth', ur: 'تاریخ پیدائش'  },
  stu_gender:       { en: 'Gender',     ur: 'جنس'             },
  stu_mobile:       { en: 'Mobile',     ur: 'موبائل'          },
  stu_father:       { en: 'Father',     ur: 'والد'            },

  // ── Fees ───────────────────────────────────────────────────
  fee_voucher:      { en: 'Fee Voucher',   ur: 'فیس وصولی'     },
  fee_due:          { en: 'Due Amount',    ur: 'باقی رقم'      },
  fee_paid:         { en: 'Paid',         ur: 'ادا شدہ'        },
  fee_total:        { en: 'Total',         ur: 'کل رقم'        },
  fee_month:        { en: 'Month',         ur: 'مہینہ'         },
  fee_receive:      { en: 'Receive Fee',   ur: 'فیس وصول کریں' },

  // ── Common ─────────────────────────────────────────────────
  common_save:      { en: 'Save',          ur: 'محفوظ کریں'   },
  common_cancel:    { en: 'Cancel',        ur: 'منسوخ'         },
  common_delete:    { en: 'Delete',        ur: 'حذف'          },
  common_search:    { en: 'Search',        ur: 'تلاش'          },
  common_loading:   { en: 'Loading...',    ur: 'لوڈ ہو رہا ہے' },
  common_no_data:   { en: 'No records found.', ur: 'کوئی ریکارڈ نہیں' },
  common_actions:   { en: 'Actions',       ur: 'اقدامات'       },
  common_new:       { en: '+ New',         ur: '+ نیا'         },
  common_print:     { en: 'Print',         ur: 'پرنٹ'          },
  common_export:    { en: 'Export',        ur: 'برآمد'         },
  common_today:     { en: 'Today',         ur: 'آج'            },
  common_yes:       { en: 'Yes, Proceed',  ur: 'ہاں، جاری رکھیں' },
};

/**
 * Key se string lo.
 * @param {string} key - STRINGS object ka key
 * @param {'en'|'ur'} [lang] - override language (optional)
 * @returns {string}
 */
export function t(key, lang) {
  const entry = STRINGS[key];
  if (!entry) {
    console.warn(`[i18n] Missing string: "${key}"`);
    return key;
  }
  const useLang = lang ?? 'en';
  return entry[useLang] ?? entry.en ?? key;
}

/**
 * Bilingual HTML banao — English bold upar, Urdu muted neeche.
 * Sirf parents-facing areas mein use karo jab bilingualMode ON ho.
 * @param {string} key
 * @returns {string} HTML string (safe — sirf STRINGS se aata hai)
 */
export function bilingualHtml(key) {
  const entry = STRINGS[key];
  if (!entry) return t(key);

  if (!isBilingual()) return entry.en;

  return `<span class="bilingual-wrap">
    <span class="bilingual-en">${entry.en}</span>
    <span class="bilingual-ur urdu">${entry.ur}</span>
  </span>`;
}

/**
 * Bilingual CSS — index.html mein ya main.js se inject karo
 * Ek baar call karo app startup pe
 */
export function injectBilingualCSS() {
  if (document.getElementById('bilingual-css')) return;
  const style = document.createElement('style');
  style.id = 'bilingual-css';
  style.textContent = `
    .bilingual-wrap { display: flex; flex-direction: column; gap: 1px; }
    .bilingual-en   { font-size: 13.5px; color: var(--siyahi); font-weight: 500; }
    .bilingual-ur   { font-size: 12px;   color: var(--siyahi-soft); direction: rtl; text-align: right; }
  `;
  document.head.appendChild(style);
}

