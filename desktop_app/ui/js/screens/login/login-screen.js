/**
 * screens/login/login-screen.js — First-Run Setup, Staff Sign-In & PIN Recovery (Phase 2 — G3)
 *
 * Enforces:
 *   - First-run Admin/Principal setup when 0 accounts exist
 *   - Mandatory printable/copyable Recovery Code confirmation gate (anti-lockout)
 *   - Staff username + PIN/Password sign-in with lockout error messaging
 *   - Offline one-time Recovery Code password reset flow
 */

import { apiCall, apiPost, setSessionToken } from '../../core/api.js';
import { esc, toast } from '../../core/dom.js';
import { icon } from '../../core/icons.js';

let _mode = 'login'; // 'setup' | 'recovery_confirm' | 'login' | 'recover'
let _pendingRecoveryCode = '';
let _pendingUser = null;
let _onAuthenticated = null;

export async function checkAuthAndGate(onAuthenticated) {
  _onAuthenticated = onAuthenticated;
  const status = await apiCall('/api/auth/status', 'GET', null, { skipAuthGate: true });

  if (status.authenticated && status.user) {
    _hideOverlay();
    return status.user;
  }

  if (status.auth_enforced === false && !status.setup_required) {
    _hideOverlay();
    return { id: 0, username: 'admin', full_name: 'Administrator', role: 'admin' };
  }

  _mode = status.setup_required ? 'setup' : 'login';
  _renderOverlay();
  return null;
}

export function showLoginGate(onAuthenticated) {
  if (onAuthenticated) _onAuthenticated = onAuthenticated;
  _mode = 'login';
  _renderOverlay();
}

function _hideOverlay() {
  const el = document.getElementById('auth-overlay');
  if (el) {
    el.classList.remove('open');
    el.innerHTML = '';
  }
}

function _renderOverlay() {
  let overlay = document.getElementById('auth-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'auth-overlay';
    overlay.className = 'auth-overlay';
    document.body.appendChild(overlay);
  }
  overlay.classList.add('open');

  if (_mode === 'setup') {
    overlay.innerHTML = _buildSetupHtml();
    _bindSetupEvents(overlay);
  } else if (_mode === 'recovery_confirm') {
    overlay.innerHTML = _buildRecoveryConfirmHtml();
    _bindRecoveryConfirmEvents(overlay);
  } else if (_mode === 'recover') {
    overlay.innerHTML = _buildRecoverHtml();
    _bindRecoverEvents(overlay);
  } else {
    overlay.innerHTML = _buildLoginHtml();
    _bindLoginEvents(overlay);
  }
}

function _brandHeader(subtitle) {
  return `
    <div class="auth-brand">
      <div class="auth-brand-mark">${icon('shield', 18)}</div>
      <div>
        <div style="font-size:15px; font-weight:700; color:var(--siyahi);">School Management ERP</div>
        <div style="font-size:12px; color:var(--siyahi-soft);">${esc(subtitle)}</div>
      </div>
    </div>`;
}

function _buildSetupHtml() {
  return `
    <div class="auth-card">
      ${_brandHeader('First-Run Principal / Administrator Setup')}
      <p style="font-size:13px; color:var(--siyahi-soft); margin-bottom:16px;">
        Create your primary Administrator account. An offline Emergency Recovery Code will be generated on the next step.
      </p>
      <form id="auth-setup-form">
        <div class="form-group">
          <label class="form-label required" for="su-fullname">Full Name</label>
          <input class="form-control" id="su-fullname" placeholder="e.g. Principal Tariq Mahmood" required autofocus />
        </div>
        <div class="form-group">
          <label class="form-label required" for="su-username">Username</label>
          <input class="form-control" id="su-username" value="admin" required autocomplete="username" />
        </div>
        <div class="form-group">
          <label class="form-label required" for="su-secret">Password or Staff PIN (min 6 chars)</label>
          <input class="form-control" id="su-secret" type="password" minlength="6" required autocomplete="new-password" />
        </div>
        <div id="auth-err" class="form-error" style="display:none; margin-bottom:12px;"></div>
        <button type="submit" class="btn btn-primary btn-block" id="su-submit">
          Create Administrator Account
        </button>
      </form>
    </div>`;
}

function _buildRecoveryConfirmHtml() {
  return `
    <div class="auth-card">
      ${_brandHeader('Save Offline Emergency Recovery Code')}
      <p style="font-size:13px; color:var(--siyahi-soft);">
        Write down or print this one-time code and keep it in the Principal's office register. If you ever forget your password, this is the only way to unlock the offline database.
      </p>
      <div class="recovery-box">
        <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:var(--siyahi-soft);">
          Emergency Recovery Key
        </div>
        <div class="recovery-code-display" id="rk-code-val">${esc(_pendingRecoveryCode)}</div>
        <div style="display:flex; justify-content:center; gap:8px; margin-top:8px;">
          <button type="button" class="btn btn-secondary btn-sm" id="rk-copy-btn">${icon('key', 14)} Copy Code</button>
          <button type="button" class="btn btn-secondary btn-sm" id="rk-print-btn">${icon('printer', 14)} Print Slip</button>
        </div>
      </div>
      <label style="display:flex; align-items:center; gap:8px; font-size:13px; margin:14px 0; cursor:pointer;">
        <input type="checkbox" id="rk-ack-chk" />
        <span>I have written down or printed this Recovery Code safely.</span>
      </label>
      <button type="button" class="btn btn-primary btn-block" id="rk-continue-btn" disabled>
        Enter School ERP
      </button>
    </div>`;
}

function _buildLoginHtml() {
  return `
    <div class="auth-card">
      ${_brandHeader('Staff Sign In • Offline Desktop Edition')}
      <form id="auth-login-form">
        <div class="form-group">
          <label class="form-label required" for="li-username">Username</label>
          <input class="form-control" id="li-username" placeholder="e.g. admin, feeclerk, teacher" required autofocus autocomplete="username" />
        </div>
        <div class="form-group">
          <label class="form-label required" for="li-secret">Password / PIN</label>
          <input class="form-control" id="li-secret" type="password" required autocomplete="current-password" />
        </div>
        <div id="auth-err" class="form-error" style="display:none; margin-bottom:12px;"></div>
        <button type="submit" class="btn btn-primary btn-block" id="li-submit">
          ${icon('lock', 15)} Sign In
        </button>
      </form>
      <div style="margin-top:16px; text-align:center;">
        <button type="button" class="btn btn-ghost btn-sm" id="li-goto-recover">
          Forgot Admin Password? Use Recovery Code
        </button>
      </div>
    </div>`;
}

function _buildRecoverHtml() {
  return `
    <div class="auth-card">
      ${_brandHeader('Emergency Administrator Password Reset')}
      <form id="auth-recover-form">
        <div class="form-group">
          <label class="form-label required" for="rc-username">Admin Username</label>
          <input class="form-control" id="rc-username" value="admin" required />
        </div>
        <div class="form-group">
          <label class="form-label required" for="rc-code">Emergency Recovery Code</label>
          <input class="form-control" id="rc-code" placeholder="RK-XXXX-XXXX-XXXX" required autofocus />
        </div>
        <div class="form-group">
          <label class="form-label required" for="rc-secret">New Password / PIN (min 6 chars)</label>
          <input class="form-control" id="rc-secret" type="password" minlength="6" required />
        </div>
        <div id="auth-err" class="form-error" style="display:none; margin-bottom:12px;"></div>
        <button type="submit" class="btn btn-primary btn-block">Reset Password &amp; Rotate Key</button>
      </form>
      <div style="margin-top:12px; text-align:center;">
        <button type="button" class="btn btn-ghost btn-sm" id="rc-back-login">Back to Sign In</button>
      </div>
    </div>`;
}

function _showErr(overlay, msg) {
  const el = overlay.querySelector('#auth-err');
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}

function _bindSetupEvents(overlay) {
  overlay.querySelector('#auth-setup-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      const res = await apiPost('/api/auth/setup', {
        full_name: overlay.querySelector('#su-fullname').value.trim(),
        username:  overlay.querySelector('#su-username').value.trim(),
        secret:    overlay.querySelector('#su-secret').value,
      }, { skipAuthGate: true });
      setSessionToken(res.token);
      _pendingUser = res.user;
      _pendingRecoveryCode = res.recovery_code;
      _mode = 'recovery_confirm';
      _renderOverlay();
    } catch (err) {
      _showErr(overlay, err.message);
    }
  });
}

function _bindRecoveryConfirmEvents(overlay) {
  const chk = overlay.querySelector('#rk-ack-chk');
  const btn = overlay.querySelector('#rk-continue-btn');
  chk?.addEventListener('change', () => { btn.disabled = !chk.checked; });
  overlay.querySelector('#rk-copy-btn')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(_pendingRecoveryCode);
    toast('Recovery code copied to clipboard', 'info');
  });
  overlay.querySelector('#rk-print-btn')?.addEventListener('click', () => window.print());
  btn?.addEventListener('click', () => {
    _hideOverlay();
    if (_onAuthenticated && _pendingUser) _onAuthenticated(_pendingUser);
  });
}

function _bindLoginEvents(overlay) {
  overlay.querySelector('#li-goto-recover')?.addEventListener('click', () => {
    _mode = 'recover'; _renderOverlay();
  });
  overlay.querySelector('#auth-login-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      const res = await apiPost('/api/auth/login', {
        username: overlay.querySelector('#li-username').value.trim(),
        secret:   overlay.querySelector('#li-secret').value,
      }, { skipAuthGate: true });
      setSessionToken(res.token);
      _hideOverlay();
      if (_onAuthenticated) _onAuthenticated(res.user);
    } catch (err) {
      _showErr(overlay, err.message);
    }
  });
}

function _bindRecoverEvents(overlay) {
  overlay.querySelector('#rc-back-login')?.addEventListener('click', () => {
    _mode = 'login'; _renderOverlay();
  });
  overlay.querySelector('#auth-recover-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      const res = await apiPost('/api/auth/recover', {
        username:      overlay.querySelector('#rc-username').value.trim(),
        recovery_code: overlay.querySelector('#rc-code').value.trim(),
        new_secret:    overlay.querySelector('#rc-secret').value,
      }, { skipAuthGate: true });
      _pendingRecoveryCode = res.new_recovery_code;
      _pendingUser = null;
      toast('Password reset complete. Save your new rotated recovery code.', 'success');
      const loginRes = await apiPost('/api/auth/login', {
        username: overlay.querySelector('#rc-username').value.trim(),
        secret:   overlay.querySelector('#rc-secret').value,
      }, { skipAuthGate: true });
      setSessionToken(loginRes.token);
      _pendingUser = loginRes.user;
      _mode = 'recovery_confirm';
      _renderOverlay();
    } catch (err) {
      _showErr(overlay, err.message);
    }
  });
}

