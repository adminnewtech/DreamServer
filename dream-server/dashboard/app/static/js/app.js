/* Dream Dashboard - shared client logic
   - Theme toggle (dream / lemonade / light) persisted in localStorage
   - Service worker registration for PWA
   - Quick action buttons (restart/stop/start) on service cards
*/

(function() {
  // ── Theme toggle ─────────────────────────────────────
  const THEMES = ['dream', 'lemonade', 'light'];
  const toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dream';
      const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('dream-theme', next);
    });
  }

  // ── PWA ──────────────────────────────────────────────
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  // ── Quick action buttons (HTMX-swapped grid) ─────────
  document.body.addEventListener('click', async (e) => {
    const btn = e.target.closest('.svc-action');
    if (!btn) return;
    e.preventDefault();
    const kind = btn.dataset.kind;
    const target = btn.dataset.target;
    const action = btn.dataset.action;
    if (!confirm(`${action} ${target}?`)) return;
    btn.disabled = true;
    const originalLabel = btn.textContent;
    btn.textContent = '⏳';
    try {
      const r = await fetch(`/actions/${kind}/${encodeURIComponent(target)}/${action}`, {
        method: 'POST',
      });
      if (r.status === 401) {
        alert('Login required for write actions.');
        window.location = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
        return;
      }
      const data = await r.json();
      if (!r.ok || !data.ok) {
        alert(`Failed: ${data.output || 'HTTP ' + r.status}`);
      } else {
        btn.textContent = '✓';
        setTimeout(() => { btn.textContent = originalLabel; btn.disabled = false; }, 1500);
        return;
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
    btn.textContent = originalLabel;
    btn.disabled = false;
  });

  // ── Keyboard shortcuts (global) ──────────────────────
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 'g') {
      // Vim-style: g then o/s/l/m/d/t/a goes to overview/services/logs/...
      const second = (e2) => {
        e2.preventDefault();
        document.removeEventListener('keydown', second);
        const map = { o: '/overview', s: '/', l: '/logs', m: '/metrics', d: '/databases', t: '/topology', x: '/security', a: '/assistant' };
        if (map[e2.key]) window.location = map[e2.key];
      };
      document.addEventListener('keydown', second, { once: true });
    }
    if (e.key === 'r' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      window.location.reload();
    }
  });
})();
