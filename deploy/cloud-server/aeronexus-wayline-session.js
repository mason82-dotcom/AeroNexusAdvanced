// Reuse the existing Cloud UI session. Never collect or submit passwords.
(() => {
  'use strict';
  if (location.protocol !== 'http:' || location.port !== '8085' ||
      !/^192\.168\.178\.\d{1,3}$/.test(location.hostname)) return;
  const url = `https://${location.hostname}:8000/api/v1/local-cloud/session`;
  let busy = false;
  async function shareSession() {
    if (busy || document.visibilityState === 'hidden') return;
    let token, workspace;
    try {
      token = localStorage.getItem('x-auth-token');
      workspace = localStorage.getItem('workspace_id');
    } catch { return; }
    if (!token || !workspace) return;
    busy = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      await fetch(url, {
        method: 'POST', credentials: 'omit', redirect: 'error',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({access_token: token, workspace_id: workspace}),
        signal: controller.signal
      });
    } catch { /* An unavailable Advanced service must not interrupt Pilot 2. */ }
    finally { clearTimeout(timer); busy = false; }
  }
  window.addEventListener('storage', shareSession);
  document.addEventListener('visibilitychange', shareSession);
  setInterval(shareSession, 30000);
  shareSession();
})();
