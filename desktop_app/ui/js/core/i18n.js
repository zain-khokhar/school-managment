/**
 * core/i18n.js — Bilingual English/Urdu System & RTL Controller (Phase 5)
 */

import { EN } from '../i18n/en.js';
import { UR } from '../i18n/ur.js';
import { isBilingual, setBilingual } from './state.js';

export { isBilingual, setBilingual };

let _currentLang = localStorage.getItem('erp_lang') || 'en';

export function getLang() {
  return _currentLang;
}

export function setLang(lang) {
  _currentLang = lang === 'ur' ? 'ur' : 'en';
  localStorage.setItem('erp_lang', _currentLang);
  const isRtl = _currentLang === 'ur';

  document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr');
  document.documentElement.setAttribute('lang', _currentLang);
  document.body?.classList.toggle('rtl-mode', isRtl);

  window.dispatchEvent(new CustomEvent('erp:lang-change', { detail: { lang: _currentLang } }));
}

export function toggleLang() {
  const next = _currentLang === 'en' ? 'ur' : 'en';
  setLang(next);
  return next;
}

export function t(key) {
  const dict = _currentLang === 'ur' ? UR : EN;
  return dict[key] || EN[key] || key;
}

export function bilingualHtml(key) {
  const enText = EN[key] || key;
  const urText = UR[key];
  if (!urText || urText === enText) return enText;
  return `<span class="bilingual-wrap"><span class="bilingual-en">${enText}</span><span class="bilingual-ur">${urText}</span></span>`;
}

export function initI18n() {
  setLang(_currentLang);
}

export function injectBilingualCSS() {
  // Retained for backward compatibility
}
