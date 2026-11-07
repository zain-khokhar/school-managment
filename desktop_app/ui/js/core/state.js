/**
 * state.js — Reactive Store for School ERP Desktop App (Phase 1 & Phase 2)
 */

const _state = {
  tab: 'dashboard',
  filter: '',
  bootstrapData: null,
  loadingBootstrap: false,
  user: null,
  role: 'admin',
  schoolName: 'School ERP',
  currentYear: null,
  currentSchool: null,
  bilingualMode: false,
  preferences: {
    bilingual_prints: false,
    enable_hostel: true,
    enable_transport: true,
    ramazan_mode: false,
  },
  backupHealth: null,
  selectedStudentId: null,
  selectedClassId: null,
};

const _listeners = new Map();

export function get(key) {
  return _state[key];
}

export function set(patch) {
  const changed = [];
  for (const [key, val] of Object.entries(patch)) {
    if (_state[key] !== val) {
      _state[key] = val;
      changed.push(key);
    }
  }
  for (const key of changed) {
    _listeners.get(key)?.forEach(fn => fn(_state[key]));
    _listeners.get('*')?.forEach(fn => fn(_state));
  }
}

export function subscribe(key, fn) {
  if (!_listeners.has(key)) _listeners.set(key, new Set());
  _listeners.get(key).add(fn);
  return () => _listeners.get(key)?.delete(fn);
}

export function setBootstrap(data) {
  const schools = data?.school?.schools || [];
  const years   = data?.school?.years   || [];
  const current = years.find(y => y.current) || years[0] || null;
  const prefs   = data?.preferences || _state.preferences;

  set({
    bootstrapData: data,
    loadingBootstrap: false,
    currentSchool: schools[0] || null,
    currentYear:   current,
    schoolName:    schools[0]?.name || 'School ERP',
    preferences:   prefs,
    bilingualMode: Boolean(prefs?.bilingual_prints),
    backupHealth:  data?.backup_health || _state.backupHealth,
  });
}

export function getBootstrap()  { return _state.bootstrapData; }
export function getTab()        { return _state.tab; }
export function setTab(tab)     { set({ tab }); }
export function getFilter()     { return _state.filter; }
export function setFilter(f)    { set({ filter: f }); }
export function isBilingual()   { return _state.bilingualMode; }
export function setBilingual(v) { set({ bilingualMode: Boolean(v) }); }
