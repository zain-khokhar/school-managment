/**
 * i18n.js — English UI Label Dictionary
 *
 * Centralizes common UI labels in standard English across all screens.
 */

import { isBilingual, setBilingual } from './state.js';
export { isBilingual, setBilingual };

export const STRINGS = {
  nav_dashboard:    'Overview',
  nav_students:     'Students',
  nav_attendance:   'Attendance',
  nav_fees:         'Fees & Billing',
  nav_exam:         'Exams & Results',
  nav_timetable:    'Timetable',
  nav_library:      'Library',
  nav_transport:    'Transport',
  nav_events:       'Events',

  att_title:        'Mark Attendance',
  att_present:      'Present',
  att_absent:       'Absent',
  att_on_leave:     'On Leave',
  att_submit:       'Submit Roll Call',
  att_total:        'Total',
  att_validate_ok:  'Attendance saved.',

  stu_gr_no:        'GR No.',
  stu_name:         'Name',
  stu_class:        'Class',
  stu_roll:         'Roll No.',
  stu_status:       'Status',
  stu_dob:          'Date of Birth',
  stu_gender:       'Gender',
  stu_mobile:       'Mobile',
  stu_father:       'Guardian',

  fee_voucher:      'Fee Voucher',
  fee_due:          'Balance Due',
  fee_paid:         'Paid',
  fee_total:        'Total',
  fee_month:        'Billing Month',
  fee_receive:      'Receive Payment',

  common_save:      'Save',
  common_cancel:    'Cancel',
  common_delete:    'Delete',
  common_search:    'Search',
  common_loading:   'Loading...',
  common_no_data:   'No records found.',
  common_actions:   'Actions',
  common_new:       'New',
  common_print:     'Print',
  common_export:    'Export',
  common_today:     'Today',
  common_yes:       'Confirm',
};

export function t(key) {
  return STRINGS[key] ?? key;
}

export function bilingualHtml(key) {
  return STRINGS[key] ?? key;
}

export function injectBilingualCSS() {
  // Retained as a no-op hook for module startup compatibility (English-only mode).
}
