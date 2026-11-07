/**
 * tests/js/format_and_icons.test.mjs — Built-in `node --test` Suite (ADVANCEMENT_PLAN.md 10.6)
 *
 * Verifies:
 *   1. PKR currency & date formatting
 *   2. Calm enterprise status badge restraint (routine states != bright green/red)
 *   3. Geometric stroke SVG icon generator (zero Unicode emojis)
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { formatPKR, formatPaisa, formatRelative, fullName, stateLabel, stateBadgeClass } from '../../desktop_app/ui/js/core/format.js';
import { icon } from '../../desktop_app/ui/js/core/icons.js';

test('formatPKR and formatPaisa format integer and fractional paisa cleanly', () => {
  assert.match(formatPKR(4500), /Rs\.\s*4,500/);
  assert.equal(formatPKR(null), 'Rs.\u00A00');
  assert.match(formatPaisa(450000), /Rs\.\s*4,500$/);
  assert.match(formatPaisa(123455), /Rs\.\s*1,234\.55$/);
  assert.equal(formatPaisa(0), 'Rs.\u00A00');
});

test('fullName concatenates student name parts without extra spaces', () => {
  assert.equal(fullName({ student_name: 'Hamza', middle: '', last: 'Khan' }), 'Hamza Khan');
  assert.equal(fullName({}), '—');
});

test('stateBadgeClass enforces calm enterprise color restraint', () => {
  // Routine states must NOT be painted green (badge-success) or red (badge-danger)
  assert.equal(stateBadgeClass('done'), 'badge-info');
  assert.equal(stateBadgeClass('confirm'), 'badge-info');
  assert.equal(stateBadgeClass('validate'), 'badge-info');
  assert.equal(stateBadgeClass('alumni'), 'badge-neutral');
  assert.equal(stateBadgeClass('draft'), 'badge-neutral');
  assert.equal(stateBadgeClass('close'), 'badge-neutral');

  // Settled completion -> badge-success
  assert.equal(stateBadgeClass('paid'), 'badge-success');
  assert.equal(stateBadgeClass('approve'), 'badge-success');
  assert.equal(stateBadgeClass('pass'), 'badge-success');

  // True exceptions -> badge-danger
  assert.equal(stateBadgeClass('reject'), 'badge-danger');
  assert.equal(stateBadgeClass('fail'), 'badge-danger');
  assert.equal(stateBadgeClass('fine'), 'badge-danger');
  assert.equal(stateBadgeClass('reversed'), 'badge-danger');
  assert.equal(stateBadgeClass('rolled_over'), 'badge-neutral');
  assert.equal(stateLabel('done'), 'Enrolled');
  assert.equal(stateLabel('rolled_over'), 'Carried Forward');
  assert.equal(formatRelative(new Date().toISOString()), 'Today');
});

test('icon() renders valid inline 24x24 stroke SVG without emojis', () => {
  const svg = icon('dashboard', 18);
  assert.match(svg, /^<svg class="ui-icon" width="18" height="18" viewBox="0 0 24 24"/);
  assert.doesNotMatch(svg, /[\u{1F300}-\u{1FAFF}\u2600-\u27BF]/u);
});

