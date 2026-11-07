/**
 * state.js — Reactive state store (no framework, no deps)
 * Bootstrap data ek baar load hota hai. Targeted refresh ke liye
 * specific API calls karo — poora bootstrap repeat nahi hoga.
 */

/** @type {AppState} */
const _state = {
  tab: 'dashboard',
  filter: '',
  bootstrapData: null,       // full bootstrap snapshot (loaded once)
  loadingBootstrap: false,
  role: 'admin',             // Phase 2 mein auth se aayega
  schoolName: '',
  currentYear: null,
  currentSchool: null,
  bilingualMode: false,      // D3: Urdu toggle
};

/** @type {Map<string, Set<Function>>} */
const _listeners = new Map();

/**
 * State ka current value lo
 * @param {keyof AppState} key
 */
export function get(key) {
  return _state[key];
}

/**
 * State update karo aur listeners ko notify karo
 * @param {Partial<AppState>} patch
 */
export function set(patch) {
  const changed = [];
  for (const [key, val] of Object.entries(patch)) {
    if (_state[key] !== val) {
      _state[key] = val;
      changed.push(key);
    }
  }
  for (const key of changed) {
    const fns = _listeners.get(key);
    if (fns) fns.forEach(fn => fn(_state[key]));
    // '*' = koi bhi change pe fire karo
    const all = _listeners.get('*');
    if (all) all.forEach(fn => fn(_state));
  }
}

/**
 * State key ki change sun-o
 * @param {string} key - state key ya '*' for any
 * @param {Function} fn - callback(newValue)
 * @returns {Function} unsubscribe function
 */
export function subscribe(key, fn) {
  if (!_listeners.has(key)) _listeners.set(key, new Set());
  _listeners.get(key).add(fn);
  return () => _listeners.get(key)?.delete(fn);
}

/**
 * Bootstrap data set karo aur common derived values extract karo
 * @param {object} data
 */
export function setBootstrap(data) {
  const schools = data?.school?.schools || [];
  const years   = data?.school?.years   || [];
  const current = years.find(y => y.current) || years[0] || null;

  set({
    bootstrapData: data,
    loadingBootstrap: false,
    currentSchool: schools[0] || null,
    currentYear:   current,
    schoolName:    schools[0]?.name || 'School ERP',
  });
}

/**
 * Bootstrap data padhna — null agar load nahi hua
 * @returns {object|null}
 */
export function getBootstrap() {
  return _state.bootstrapData;
}

/** Active tab get/set shortcuts */
export function getTab()      { return _state.tab; }
export function setTab(tab)   { set({ tab }); }
export function getFilter()   { return _state.filter; }
export function setFilter(f)  { set({ filter: f }); }
export function isBilingual() { return _state.bilingualMode; }
export function setBilingual(v) { set({ bilingualMode: v }); }

/**
 * @typedef {Object} AppState
 * @property {string} tab
 * @property {string} filter
 * @property {object|null} bootstrapData
 * @property {boolean} loadingBootstrap
 * @property {string} role
 * @property {string} schoolName
 * @property {object|null} currentYear
 * @property {object|null} currentSchool
 * @property {boolean} bilingualMode
 */

