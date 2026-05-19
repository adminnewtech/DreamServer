/* OpenClaw Dashboard - client logic */

(function() {
  // ── Tab switching ────────────────────
  const tabs = document.querySelectorAll('.tab');
  const navItems = document.querySelectorAll('.nav-item[data-tab]');
  let activeTab = 'overview';

  function showTab(name) {
    tabs.forEach(t => {
      if (t.dataset.tab === name) t.classList.remove('hidden');
      else t.classList.add('hidden');
    });
    navItems.forEach(n => {
      if (n.dataset.tab === name) n.classList.add('active');
      else n.classList.remove('active');
    });
    activeTab = name;
    onTabActivate(name);
    history.replaceState(null, '', '#' + name);
  }
  navItems.forEach(n => n.addEventListener('click', e => { e.preventDefault(); showTab(n.dataset.tab); }));

  // ── Loaders ──────────────────────────
  const seen = { overview: false, models: false, agents: false, channels: false, approvals: false, usage: false, logs: false };

  async function loadHealth() {
    try {
      const r = await fetch('/api/health'); const d = await r.json();
      setBig('kpi-gateway',  d.gateway.up ? 'UP' : 'DOWN', d.gateway.up);
      setBig('kpi-watchdog', d.systemd['openclaw-watchdog'] === 'active' ? 'UP' : 'DOWN', d.systemd['openclaw-watchdog'] === 'active');
      setBig('kpi-jwt',      d.jwt_secret_present ? 'OK' : 'MISSING', d.jwt_secret_present);
      document.getElementById('kpi-gateway-detail').textContent  = d.gateway.detail || '';
      document.getElementById('kpi-watchdog-detail').textContent = 'systemd: ' + d.systemd['openclaw-watchdog'];

      setFoot('foot-gateway',  d.gateway.up ? 'up' : 'down', d.gateway.up);
      setFoot('foot-watchdog', d.systemd['openclaw-watchdog'] === 'active' ? 'up' : 'down', d.systemd['openclaw-watchdog'] === 'active');
      setFoot('foot-jwt',      d.jwt_secret_present ? 'present' : 'missing', d.jwt_secret_present);
    } catch (e) { console.error(e); }
  }

  function setBig(id, text, isUp) {
    const el = document.getElementById(id); if (!el) return;
    el.textContent = text;
    el.className = 'big-status' + (isUp ? ' up' : ' down') + (text.length > 6 ? ' small' : '');
  }
  function setFoot(id, text, isUp) {
    const el = document.getElementById(id); if (!el) return;
    el.textContent = text;
    el.className = isUp ? 'up' : 'down';
  }

  async function loadInfo() {
    try {
      const r = await fetch('/api/info'); const d = await r.json();
      document.getElementById('kpi-version').textContent = (d.version || '').replace(/^OpenClaw\s*/, '');
      document.getElementById('info-status').textContent = d.status_raw || '(no status)';
    } catch (e) { console.error(e); }
  }

  async function loadCli(endpoint, targetId) {
    const el = document.getElementById(targetId); if (!el) return;
    el.textContent = 'Loading...';
    try {
      const r = await fetch('/api/' + endpoint); const d = await r.json();
      el.textContent = d.output || '(empty)';
    } catch (e) { el.textContent = 'Error: ' + e.message; }
  }

  function clearNode(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  async function loadUsage() {
    try {
      const r = await fetch('/api/usage'); const d = await r.json();
      document.getElementById('usage-lines').textContent = (d.today_lines || 0).toLocaleString();
      document.getElementById('usage-total').textContent = (d.total_size_kb || 0).toFixed(1) + ' KB';
      const tbody = document.querySelector('#usage-files tbody');
      clearNode(tbody);
      (d.log_files || []).forEach(f => {
        const tr = document.createElement('tr');
        const nameCell = document.createElement('td');
        const code = document.createElement('code');
        code.textContent = f.name;
        nameCell.appendChild(code);
        const sizeCell = document.createElement('td'); sizeCell.textContent = f.size_kb + ' KB';
        const modCell = document.createElement('td'); modCell.textContent = f.modified;
        tr.appendChild(nameCell); tr.appendChild(sizeCell); tr.appendChild(modCell);
        tbody.appendChild(tr);
      });
    } catch (e) { console.error(e); }
  }

  // ── Logs ─────────────────────────────
  const logOutput = document.getElementById('log-output');
  const logSrc = document.getElementById('log-src');
  const logRefresh = document.getElementById('log-refresh');
  const logStop = document.getElementById('log-stop');
  let logStream = null;

  function setLogText(txt) {
    clearNode(logOutput);
    logOutput.textContent = txt;
  }
  function appendLogLine(line) {
    const div = document.createElement('div');
    div.textContent = line;
    if (/error|fail|fatal/i.test(line)) div.style.color = '#fca5a5';
    else if (/warn/i.test(line)) div.style.color = '#fcd34d';
    logOutput.appendChild(div);
    while (logOutput.children.length > 1500) logOutput.removeChild(logOutput.firstChild);
    logOutput.scrollTop = logOutput.scrollHeight;
  }

  async function loadLogs() {
    stopStream();
    const src = logSrc.value;
    setLogText('Loading...');
    if (src === 'file') {
      const r = await fetch('/api/logs?lines=300'); setLogText(await r.text());
    } else if (src === 'journal') {
      const r = await fetch('/api/logs/journal?lines=300'); setLogText(await r.text());
    } else {
      setLogText('');
      logStream = new EventSource('/api/logs/stream');
      logStream.onmessage = e => appendLogLine(e.data);
      logStream.onerror = () => appendLogLine('--- stream error / reconnecting ---');
    }
  }
  function stopStream() {
    if (logStream) { logStream.close(); logStream = null; }
  }
  logRefresh.addEventListener('click', loadLogs);
  logStop.addEventListener('click', stopStream);

  // ── Refresh buttons ──────────────────
  document.querySelectorAll('[data-refresh]').forEach(b => {
    b.addEventListener('click', () => {
      const key = b.dataset.refresh;
      loadCli(key, 'out-' + key);
    });
  });

  // ── Playground ───────────────────────
  document.getElementById('pg-send').addEventListener('click', async () => {
    const btn = document.getElementById('pg-send');
    btn.disabled = true; btn.textContent = '…sending';
    const out = document.getElementById('pg-response');
    out.textContent = 'Sending…';
    try {
      const r = await fetch('/api/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: document.getElementById('pg-message').value,
          model: document.getElementById('pg-model').value,
          bearer: document.getElementById('pg-bearer').value || null,
        }),
      });
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
    } catch (e) {
      out.textContent = 'Error: ' + e.message;
    } finally {
      btn.disabled = false; btn.textContent = 'Send';
    }
  });
  document.getElementById('pg-clear').addEventListener('click', () => {
    document.getElementById('pg-message').value = '';
    document.getElementById('pg-response').textContent = 'Response will appear here.';
  });

  // ── Tab activation handlers ──────────
  function onTabActivate(name) {
    if (name === 'models' && !seen.models)       { seen.models = true;       loadCli('models',    'out-models'); }
    if (name === 'agents' && !seen.agents)       { seen.agents = true;       loadCli('agents',    'out-agents'); }
    if (name === 'channels' && !seen.channels)   { seen.channels = true;     loadCli('channels',  'out-channels'); }
    if (name === 'approvals' && !seen.approvals) { seen.approvals = true;    loadCli('approvals', 'out-approvals'); }
    if (name === 'usage' && !seen.usage)         { seen.usage = true;        loadUsage(); }
    if (name === 'logs' && !seen.logs)           { seen.logs = true;         loadLogs(); }
  }

  // ── Init ─────────────────────────────
  loadHealth(); loadInfo();
  setInterval(loadHealth, 10000);

  // Honour deep-link hash
  if (location.hash) {
    const tab = location.hash.slice(1);
    if (document.querySelector(`.nav-item[data-tab="${tab}"]`)) showTab(tab);
  }
})();
