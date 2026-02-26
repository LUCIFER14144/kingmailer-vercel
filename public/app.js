/* ── KINGMAILER Web – Frontend JS ────────────────────────────────────────── */
// ── Tab switching ─────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const panel = document.getElementById('tab-' + btn.dataset.tab);
    if (panel) panel.classList.add('active');
  });
});
// ── Helpers ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
function showStatus(elId, msg, type = 'ok') {
  const el = $(elId);
  if (!el) return;
  el.textContent = msg;
  el.className = 'status-msg ' + type;
  if (type === 'ok') setTimeout(() => { if (el.textContent === msg) el.textContent = ''; }, 5000);
}
async function api(endpoint, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(endpoint, opts);
  return res.json();
}
// ── Auth ──────────────────────────────────────────────────────────────────
async function logout() {
  await api('/api/logout', 'POST');
  window.location.href = '/';
}
// ── Send method → show/hide SMTP batch section ────────────────────────────
function syncBatchSection() {
  const method = $('sendMethod') ? $('sendMethod').value : '';
  const sec = $('smtpBatchSection');
  if (sec) sec.style.display = (method === 'smtp') ? '' : 'none';
}
document.addEventListener('DOMContentLoaded', () => {
  if ($('sendMethod')) {
    $('sendMethod').addEventListener('change', syncBatchSection);
    syncBatchSection();
  }
  // Update badge label when rotation select changes
  const rotSel = $('smtpRotation');
  if (rotSel) rotSel.addEventListener('change', () => {
    $('batchModeLabel').textContent = rotSel.value;
  });
});
// ── Compose: load HTML file ───────────────────────────────────────────────
function loadHtmlFile() {
  const file = $('htmlFile').files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  fetch('/api/upload-html', { method: 'POST', html: form })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        $('emailBody').value = d.html;
        showStatus('singleStatus', '✅ HTML loaded', 'ok');
      }
    });
}
// ── Compose: load recipients ──────────────────────────────────────────────
let recipients = [];
function loadRecipients() {
  const file = $('recipientFile').files[0];
  if (!file) return;
  form.append('file', file);
  fetch('/api/upload-recipients', { method: 'POST', html: form })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        recipients = d.emails;
        $('recipientCount').textContent = `✅ ${d.count} recipients loaded`;
      }
    });
}
// ── Compose: build send config ────────────────────────────────────────────
function getSendConfig() {
  return {
    from_name:   $('senderName').value.trim(),
    from_email:  $('senderEmail').value.trim(),
    subject:       $('emailSubject').value.trim(),
    html:          $('emailBody').value.trim(),
    method:        $('sendMethod').value,
    delay_min:     parseFloat($('delayMin').value) || 30,
    delay_max:     parseFloat($('delayMax').value) || 60,
    attach_as_pdf: $('attachAsPdf').checked,
    // SMTP batch options (used when method === 'smtp')
    batch_size:    parseInt($('batchSize').value) || 50,
    smtp_rotation: $('smtpRotation').value,
    smtp_config:   getSmtpConfig(),
    ses_config:    getSesConfig(),
    ec2_config:    {},
  };
}
// ── Single send ───────────────────────────────────────────────────────────
async function sendSingle() {
  const recipient = $('testRecipient').value.trim();
  if (!recipient) { showStatus('singleStatus', 'Enter a recipient email', 'err'); return; }
  showStatus('singleStatus', 'Sending…', 'info');
  const cfg = { ...getSendConfig(), to: recipient };
  const res = await api('/api/send', 'POST', cfg);
  if (res.success) {
    showStatus('singleStatus', `✅ Sent to ${recipient}`, 'ok');
  } else {
    showStatus('singleStatus', `❌ ${res.message}`, 'err');
  }
}
// ── Bulk send ─────────────────────────────────────────────────────────────
async function startBulk() {
  if (!recipients.length) { showStatus('singleStatus', 'Upload recipients first', 'err'); return; }
  const cfg = { ...getSendConfig(), recipients };
  const res = await api('/api/bulk-send', 'POST', cfg);
  if (res.success) {
    $('progressWrap').style.display = 'block';
    $('btnStart').disabled  = true;
    $('btnPause').disabled  = false;
    $('btnStop').disabled   = false;
    pollProgress();
  } else {
    showStatus('singleStatus', `❌ ${res.message}`, 'err');
  }
}
async function pauseSend() {
  await api('/api/bulk-send/pause', 'POST');
  $('btnPause').disabled  = true;
  $('btnResume').disabled = false;
}
async function resumeSend() {
  await api('/api/bulk-send/resume', 'POST');
  $('btnPause').disabled  = false;
  $('btnResume').disabled = true;
}
async function stopSend() {
  await api('/api/bulk-send/stop', 'POST');
  $('btnStart').disabled  = false;
  $('btnPause').disabled  = true;
  $('btnResume').disabled = true;
  $('btnStop').disabled   = true;
}
let pollTimer = null;
function pollProgress() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const d = await api('/api/progress');
    const pct = d.total > 0 ? Math.round((d.sent + d.failed) / d.total * 100) : 0;
    $('progressBar').style.width = pct + '%';
    $('progressText').textContent = `${d.sent + d.failed} / ${d.total}  (${pct}%)`;
    $('progressCurrent').textContent = d.current ? `→ ${d.current}` : '';
    if ($('progressBatch') && d.batch_info) {
      $('progressBatch').textContent = d.batch_info;
    }
    $('statSent').textContent   = d.sent;
    $('statFailed').textContent = d.failed;
    $('statTotal').textContent  = d.total;
    if (!d.sending) {
      clearInterval(pollTimer);
      $('btnStart').disabled  = false;
      $('btnPause').disabled  = true;
      $('btnResume').disabled = true;
      $('btnStop').disabled   = true;
    }
  }, 1500);
}
// ── SMTP ──────────────────────────────────────────────────────────────────
let smtpAccounts = [];
function getSmtpConfig() {
  return {
    server:   $('smtpServer').value.trim(),
    port:     parseInt($('smtpPort').value) || 587,
    username: $('smtpUser').value.trim(),
    password: $('smtpPass').value,
    use_tls:  $('smtpTls').checked,
  };
}
async function addSmtp() {
  const cfg = getSmtpConfig();
  if (!cfg.server || !cfg.username) { showStatus('smtpStatus', 'Fill in server and username', 'err'); return; }
  const res = await api('/api/smtp', 'POST', cfg);
  if (res.success) {
    showStatus('smtpStatus', '✅ Account added', 'ok');
    refreshSmtp();
    updateBadges();
  }
}
async function testSmtp() {
  showStatus('smtpStatus', 'Testing…', 'info');
  const res = await api('/api/smtp/test', 'POST', cfg);
  if (res.success) {
    showStatus('smtpStatus', res.message, 'ok');
  } else {
    showStatus('smtpStatus', `❌ ${res.message}`, 'err');
  }
}
async function deleteSmtp(id) {
  await api(`/api/smtp/${id}`, 'DELETE');
  refreshSmtp();
  updateBadges();
}
async function refreshSmtp() {
  const data = await api('/api/smtp');
  smtpAccounts = data;
  const tbody = $('smtpBody');
  tbody.innerHTML = '';
  data.forEach((a, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td>${a.server}</td>
      <td>${a.port}</td>
      <td>${a.username}</td>
      <td>${a.use_tls ? '✅' : '—'}</td>
      <td><button class="btn-sm" onclick="deleteSmtp('${a.id}')">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
}
// ── SES ───────────────────────────────────────────────────────────────────
function getSesConfig() {
  return {
    access_key: $('sesAccess').value.trim(),
    secret_key: $('sesSecret').value,
    region:     $('sesRegion').value,
  };
}
async function addSes() {
  const cfg = {
    name:       $('sesName').value.trim(),
    access_key: $('sesAccess').value.trim(),
    secret_key: $('sesSecret').value,
    region:     $('sesRegion').value,
  };
  if (!cfg.access_key) { showStatus('sesStatus', 'Enter Access Key', 'err'); return; }
  const res = await api('/api/ses', 'POST', cfg);
  if (res.success) { showStatus('sesStatus', '✅ SES account added', 'ok'); refreshSes(); updateBadges(); }
}
async function deleteSes(id) {
  await api(`/api/ses/${id}`, 'DELETE');
  refreshSes(); updateBadges();
}
async function refreshSes() {
  const data = await api('/api/ses');
  const tbody = $('sesBody');
  tbody.innerHTML = '';
  data.forEach(a => {
    tr.innerHTML = `
      <td>${a.name || '—'}</td>
      <td>${a.region}</td>
      <td>${a.access_key.slice(0,8)}…</td>
      <td><button class="btn-sm" onclick="deleteSes('${a.id}')">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
}
// ── EC2 ───────────────────────────────────────────────────────────────────
async function createEc2() {
    access_key:    $('ec2Access').value.trim(),
    secret_key:    $('ec2Secret').value,
    region:        $('ec2Region').value,
    ami:           $('ec2Ami').value.trim(),
    instance_type: $('ec2Type').value,
    keypair:       $('ec2Keypair').value.trim(),
    sg_id:         $('ec2Sg').value.trim(),
    ssh_key_path:  $('ec2SshKey').value.trim(),
    ssh_user:      $('ec2SshUser').value.trim() || 'ec2-user',
  };
  showStatus('ec2Status', '⚙️ Launching EC2 instance (this takes ~30 seconds)…', 'info');
  const res = await api('/api/ec2/create', 'POST', cfg);
  if (res.success) {
    showStatus('ec2Status', '✅ Launch initiated – refreshing in 5s...', 'ok');
    setTimeout(refreshEc2, 5000);
    setTimeout(refreshEc2, 15000);
    setTimeout(refreshEc2, 30000);
  } else {
    showStatus('ec2Status', `❌ ${res.message}`, 'err');
  }
}
async function terminateEc2(instanceId) {
  const access = $('ec2Access').value.trim();
  const secret = $('ec2Secret').value;
  await api(`/api/ec2/${instanceId}`, 'DELETE', { access_key: access, secret_key: secret });
  refreshEc2(); updateBadges();
}
async function refreshEc2() {
  const data = await api('/api/ec2');
  const tbody = $('ec2Body');
  tbody.innerHTML = '';
  data.forEach(i => {
    tr.innerHTML = `
      <td><code>${i.ip || '—'}</code></td>
      <td><small>${i.instance_id || '—'}</small></td>
      <td>${i.region || '—'}</td>
      <td><span class="badge">${i.status || 'UNKNOWN'}</span></td>
      <td><button class="btn-sm" onclick="terminateEc2('${i.instance_id}')">Terminate</button></td>
    `;
    tbody.appendChild(tr);
  });
  updateBadges();
}
// ── Logs ──────────────────────────────────────────────────────────────────
let logOffset = 0;
const logColors = {
  '✅': 'log-ok',
  '❌': 'log-err',
  '⏳': 'log-info',
  '⚙️': 'log-info',
  '🏁': 'ok',
  '🛑': 'log-warn',
  '📧': 'log-info',
};
function appendLogs(lines) {
  const box = $('logsBox');
  lines.forEach(line => {
    const div  = document.createElement('div');
    div.className = 'log-line';
    let cls = '';
    for (const [icon, c] of Object.entries(logColors)) {
      if (line.includes(icon)) { cls = c; break; }
    }
    if (cls) div.classList.add(cls);
    div.textContent = line;
    box.appendChild(div);
  });
  if ($('autoScroll').checked) box.scrollTop = box.scrollHeight;
}
async function pollLogs() {
  const d = await api(`/api/logs?since=${logOffset}`);
  if (d.logs && d.logs.length) {
    appendLogs(d.logs);
    logOffset = d.total;
  }
}
function clearLogs() {
  $('logsBox').innerHTML = '';
  logOffset = 0;
}
// ── Badges ────────────────────────────────────────────────────────────────
async function updateBadges() {
  const d = await api('/api/status');
  $('badge-smtp').textContent = `SMTP: ${d.smtp_count}`;
  $('badge-ses').textContent  = `SES: ${d.ses_count}`;
  $('badge-ec2').textContent  = `EC2: ${d.ec2_count}`;
}
// ── Gmail API ─────────────────────────────────────────────────────────────
async function setupGmailApi() {
  const clientId = $('gmailClientId').value.trim();
  const clientSecret = $('gmailClientSecret').value.trim();
  if (!clientId || !clientSecret) {
    showStatus('gmailSetupStatus', 'Enter Client ID and Client Secret', 'err');
    return;
  }
  showStatus('gmailSetupStatus', 'Generating authorization URL…', 'info');
  const res = await api('/api/gmail-api/setup', 'POST', {
    client_id: clientId,
    client_secret: clientSecret
  });
  if (res.success) {
    showStatus('gmailSetupStatus', '✅ Authorization URL generated! Click the link below.', 'ok');
    $('gmailAuthUrl').style.display = 'block';
    $('gmailAuthLink').href = res.auth_url;
    $('gmailAuthLink').textContent = '🔗 Click here to authorize Gmail access';
  } else {
    showStatus('gmailSetupStatus', `❌ ${res.message}`, 'err');
  }
}
async function authorizeGmailApi() {
  const code = $('gmailAuthCode').value.trim();
  if (!code) {
    showStatus('gmailAuthStatus', 'Paste the authorization code from Google', 'err');
    return;
  }
  showStatus('gmailAuthStatus', 'Authorizing…', 'info');
  const res = await api('/api/gmail-api/authorize', 'POST', { auth_code: code });
  if (res.success) {
    showStatus('gmailAuthStatus', res.message, 'ok');
    $('gmailApiActive').style.display = 'block';
  } else {
    showStatus('gmailAuthStatus', `❌ ${res.message}`, 'err');
  }
}
async function testGmailApi() {
  showStatus('gmailTestStatus', 'Testing Gmail API connection…', 'info');
  const res = await api('/api/gmail-api/test', 'POST', {});
  if (res.success) {
    showStatus('gmailTestStatus', res.message, 'ok');
    $('gmailApiActive').style.display = 'block';
  } else {
    showStatus('gmailTestStatus', `❌ ${res.message}`, 'err');
  }
}
async function checkGmailApiStatus() {
  const res = await api('/api/gmail-api/status');
  if (res.configured) {
    $('gmailApiActive').style.display = 'block';
  }
}
// ══════════════════════════════════════════════════════════════════════════
// ── SUBJECT & BODY LIBRARY (localStorage) ────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════
const LIBRARY_KEY = 'km_library_v1';
function loadLibrary() {
  try { return JSON.parse(localStorage.getItem(LIBRARY_KEY)) || { subjects: [], bodies: [] }; }
  catch { return { subjects: [], bodies: [] }; }
}
function saveLibrary(lib) {
  localStorage.setItem(LIBRARY_KEY, JSON.stringify(lib));
}
/** Save current subject to the library */
function saveSubject() {
  const text = $('emailSubject').value.trim();
  if (!text) { showStatus('singleStatus', 'Type a subject first', 'err'); return; }
  const lib = loadLibrary();
  if (lib.subjects.includes(text)) { showStatus('singleStatus', 'Already saved', 'info'); return; }
  lib.subjects.unshift(text);
  if (lib.subjects.length > 50) lib.subjects.pop();   // cap at 50
  saveLibrary(lib);
  renderSubjectList();
  showStatus('singleStatus', '✅ Subject saved', 'ok');
}
/** Save current body to the library */
function saveBody() {
  const text = $('emailBody').value.trim();
  if (!text) { showStatus('singleStatus', 'Type a body first', 'err'); return; }
  const key = text.slice(0, 120);
  if (lib.bodies.some(b => b.slice(0, 120) === key)) {
    showStatus('singleStatus', 'Already saved', 'info'); return;
  }
  lib.bodies.unshift(text);
  if (lib.bodies.length > 30) lib.bodies.pop();       // cap at 30
  saveLibrary(lib);
  renderBodyList();
  showStatus('singleStatus', '✅ Body saved', 'ok');
}
/** HTML-escape helper */
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
/** Render subject list */
function renderSubjectList() {
  const el = $('subjectList');
  if (!el) return;
  if (!lib.subjects.length) {
    el.innerHTML = '<div class="library-empty">No saved subjects — click "+ Save current" to add one</div>';
    return;
  }
  el.innerHTML = lib.subjects.map((s, i) => `
    <div class="library-item" onclick="loadSubject(${i})" title="${escHtml(s)}">
      <span class="library-item-text">${escHtml(s)}</span>
      <span class="library-item-del" onclick="deleteSubject(event,${i})" title="Remove">✕</span>
    </div>`).join('');
}
/** Render body list */
function renderBodyList() {
  const el = $('bodyList');
  if (!el) return;
  if (!lib.bodies.length) {
    el.innerHTML = '<div class="library-empty">No saved bodies — click "+ Save current" to add one</div>';
    return;
  }
  el.innerHTML = lib.bodies.map((b, i) => {
    const preview = b.replace(/<[^>]+>/g, '').slice(0, 80).trim();
    return `
    <div class="library-item" onclick="loadBody(${i})" title="${escHtml(preview)}">
      <span class="library-item-text">${escHtml(preview)}${b.length > 80 ? '…' : ''}</span>
      <span class="library-item-del" onclick="deleteBody(event,${i})" title="Remove">✕</span>
    </div>`;
  }).join('');
}
function loadSubject(i) {
  $('emailSubject').value = lib.subjects[i] || '';
  document.querySelectorAll('#subjectList .library-item').forEach((el, idx) => {
    el.classList.toggle('active', idx === i);
  });
}
function loadBody(i) {
  $('emailBody').value = lib.bodies[i] || '';
  document.querySelectorAll('#bodyList .library-item').forEach((el, idx) => {
    el.classList.toggle('active', idx === i);
  });
}
function deleteSubject(evt, i) {
  evt.stopPropagation();
  lib.subjects.splice(i, 1);
  saveLibrary(lib);
  renderSubjectList();
}
function deleteBody(evt, i) {
  evt.stopPropagation();
  lib.bodies.splice(i, 1);
  saveLibrary(lib);
  renderBodyList();
}
// ══════════════════════════════════════════════════════════════════════════
// ── SPINTAX PREVIEW ───────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════
/** Resolve {A|B|C} spintax client-side for preview */
function resolveSpintax(text) {
  let prev = '', maxIter = 30;
  while (text !== prev && maxIter-- > 0) {
    prev = text;
    text = text.replace(/\{([^{}]+)\}/g, (_, group) => {
      const opts = group.split('|');
      return opts[Math.floor(Math.random() * opts.length)];
    });
  }
  return text;
}
function previewSpintax(which) {
  if (which === 'subject') {
    const resolved = resolveSpintax($('emailSubject').value);
    const el = $('spintaxSubjectPreview');
    el.textContent = '👁 ' + resolved;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 7000);
  } else {
    const resolved = resolveSpintax($('emailBody').value);
    const plain = resolved.replace(/<[^>]+>/g, '').slice(0, 220);
    const el = $('spintaxBodyPreview');
    el.textContent = '👁 ' + plain + (plain.length >= 220 ? '…' : '');
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 7000);
  }
}
// ══════════════════════════════════════════════════════════════════════════
// ── HTML EXPORT / CONVERT ─────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════
async function exportContent(format) {
  const html = $('emailBody').value.trim();
  if (!html) {
    showStatus('exportStatus', 'No content to export — write or upload HTML first', 'err');
    return;
  }
  showStatus('exportStatus', `Converting to ${format.toUpperCase()}…`, 'info');
  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      html: JSON.stringify({ html, format }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      showStatus('exportStatus', `❌ ${j.message || res.statusText}`, 'err');
      return;
    }
    const blob = await res.blob();
    const ext = format;   // already correct extension
    const filename = `kingmailer_export.${ext}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
    showStatus('exportStatus', `✅ Downloaded as ${filename}`, 'ok');
  } catch (err) {
    showStatus('exportStatus', `❌ Export error: ${err.message}`, 'err');
  }
}
// ── Init ──────────────────────────────────────────────────────────────────
(async function init() {
  await Promise.all([refreshSmtp(), refreshSes(), refreshEc2(), updateBadges(), checkGmailApiStatus()]);
  renderSubjectList();
  renderBodyList();
  setInterval(pollLogs, 2000);
  setInterval(updateBadges, 10000);
  setInterval(refreshEc2, 30000);
})();
// ── Helpers ───────────────────────────────────────────────────────────────
  if (!el) return;
  el.textContent = msg;
  el.className = 'status-msg ' + type;
  if (type === 'ok') setTimeout(() => { if (el.textContent === msg) el.textContent = ''; }, 5000);
}
  if (body) opts.body = JSON.stringify(body);
  return res.json();
}
// ── Auth ──────────────────────────────────────────────────────────────────
  await api('/api/logout', 'POST');
  window.location.href = '/';
}
// ── Compose: load HTML file ───────────────────────────────────────────────
  if (!file) return;
  form.append('file', file);
  fetch('/api/upload-html', { method: 'POST', html: form })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        $('emailBody').value = d.html;
        showStatus('singleStatus', '✅ HTML loaded', 'ok');
      }
    });
}
// ── Compose: load recipients ──────────────────────────────────────────────
  if (!file) return;
  form.append('file', file);
  fetch('/api/upload-recipients', { method: 'POST', html: form })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        recipients = d.emails;
        $('recipientCount').textContent = `✅ ${d.count} recipients loaded`;
      }
    });
}
// ── Compose: build send config ────────────────────────────────────────────
  return {
    from_name:   $('senderName').value.trim(),
    from_email:  $('senderEmail').value.trim(),
    subject:       $('emailSubject').value.trim(),
    html:          $('emailBody').value.trim(),
    method:        $('sendMethod').value,
    delay_min:     parseFloat($('delayMin').value) || 30,
    delay_max:     parseFloat($('delayMax').value) || 60,
    attach_as_pdf: $('attachAsPdf').checked,
    smtp_config:   getSmtpConfig(),
    ses_config:    getSesConfig(),
    ec2_config:    {},
  };
}
// ── Single send ───────────────────────────────────────────────────────────
  if (!recipient) { showStatus('singleStatus', 'Enter a recipient email', 'err'); return; }
  showStatus('singleStatus', 'Sending…', 'info');
  if (res.success) {
    showStatus('singleStatus', `✅ Sent to ${recipient}`, 'ok');
  } else {
    showStatus('singleStatus', `❌ ${res.message}`, 'err');
  }
}
// ── Bulk send ─────────────────────────────────────────────────────────────
  if (!recipients.length) { showStatus('singleStatus', 'Upload recipients first', 'err'); return; }
  if (res.success) {
    $('progressWrap').style.display = 'block';
    $('btnStart').disabled  = true;
    $('btnPause').disabled  = false;
    $('btnStop').disabled   = false;
    pollProgress();
  } else {
    showStatus('singleStatus', `❌ ${res.message}`, 'err');
  }
}
  await api('/api/bulk-send/pause', 'POST');
  $('btnPause').disabled  = true;
  $('btnResume').disabled = false;
}
  await api('/api/bulk-send/resume', 'POST');
  $('btnPause').disabled  = false;
  $('btnResume').disabled = true;
}
  await api('/api/bulk-send/stop', 'POST');
  $('btnStart').disabled  = false;
  $('btnPause').disabled  = true;
  $('btnResume').disabled = true;
  $('btnStop').disabled   = true;
}
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    $('progressBar').style.width = pct + '%';
    $('progressText').textContent = `${d.sent + d.failed} / ${d.total}  (${pct}%)`;
    $('progressCurrent').textContent = d.current ? `→ ${d.current}` : '';
    $('statSent').textContent   = d.sent;
    $('statFailed').textContent = d.failed;
    $('statTotal').textContent  = d.total;
    if (!d.sending) {
      clearInterval(pollTimer);
      $('btnStart').disabled  = false;
      $('btnPause').disabled  = true;
      $('btnResume').disabled = true;
      $('btnStop').disabled   = true;
    }
  }, 1500);
}
// ── SMTP ──────────────────────────────────────────────────────────────────
  return {
    server:   $('smtpServer').value.trim(),
    port:     parseInt($('smtpPort').value) || 587,
    username: $('smtpUser').value.trim(),
    password: $('smtpPass').value,
    use_tls:  $('smtpTls').checked,
  };
}
  if (!cfg.server || !cfg.username) { showStatus('smtpStatus', 'Fill in server and username', 'err'); return; }
  if (res.success) {
    showStatus('smtpStatus', '✅ Account added', 'ok');
    refreshSmtp();
    updateBadges();
  }
}
  showStatus('smtpStatus', 'Testing…', 'info');
  if (res.success) {
    showStatus('smtpStatus', res.message, 'ok');
  } else {
    showStatus('smtpStatus', `❌ ${res.message}`, 'err');
  }
}
  await api(`/api/smtp/${id}`, 'DELETE');
  refreshSmtp();
  updateBadges();
}
  smtpAccounts = data;
  tbody.innerHTML = '';
  data.forEach(a => {
    tr.innerHTML = `
      <td>${a.server}</td>
      <td>${a.port}</td>
      <td>${a.username}</td>
      <td>${a.use_tls ? '✅' : '—'}</td>
      <td><button class="btn-sm" onclick="deleteSmtp('${a.id}')">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
}
// ── SES ───────────────────────────────────────────────────────────────────
  return {
    access_key: $('sesAccess').value.trim(),
    secret_key: $('sesSecret').value,
    region:     $('sesRegion').value,
  };
}
    name:       $('sesName').value.trim(),
    access_key: $('sesAccess').value.trim(),
    secret_key: $('sesSecret').value,
    region:     $('sesRegion').value,
  };
  if (!cfg.access_key) { showStatus('sesStatus', 'Enter Access Key', 'err'); return; }
  if (res.success) { showStatus('sesStatus', '✅ SES account added', 'ok'); refreshSes(); updateBadges(); }
}
  await api(`/api/ses/${id}`, 'DELETE');
  refreshSes(); updateBadges();
}
  tbody.innerHTML = '';
  data.forEach(a => {
    tr.innerHTML = `
      <td>${a.name || '—'}</td>
      <td>${a.region}</td>
      <td>${a.access_key.slice(0,8)}…</td>
      <td><button class="btn-sm" onclick="deleteSes('${a.id}')">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
}
// ── EC2 ───────────────────────────────────────────────────────────────────
    access_key:    $('ec2Access').value.trim(),
    secret_key:    $('ec2Secret').value,
    region:        $('ec2Region').value,
    ami:           $('ec2Ami').value.trim(),
    instance_type: $('ec2Type').value,
    keypair:       $('ec2Keypair').value.trim(),
    sg_id:         $('ec2Sg').value.trim(),
    ssh_key_path:  $('ec2SshKey').value.trim(),
    ssh_user:      $('ec2SshUser').value.trim() || 'ec2-user',
  };
  showStatus('ec2Status', '⚙️ Launching EC2 instance (this takes ~30 seconds)…', 'info');
  if (res.success) {
    showStatus('ec2Status', '✅ Launch initiated – refreshing in 5s...', 'ok');
    setTimeout(refreshEc2, 5000);
    setTimeout(refreshEc2, 15000);  // Poll again at 15s
    setTimeout(refreshEc2, 30000);  // Poll again at 30s
  } else {
    showStatus('ec2Status', `❌ ${res.message}`, 'err');
  }
}
  await api(`/api/ec2/${instanceId}`, 'DELETE', { access_key: access, secret_key: secret });
  refreshEc2(); updateBadges();
}
  tbody.innerHTML = '';
  data.forEach(i => {
    tr.innerHTML = `
      <td><code>${i.ip || '—'}</code></td>
      <td><small>${i.instance_id || '—'}</small></td>
      <td>${i.region || '—'}</td>
      <td><span class="badge">${i.status || 'UNKNOWN'}</span></td>
      <td><button class="btn-sm" onclick="terminateEc2('${i.instance_id}')">Terminate</button></td>
    `;
    tbody.appendChild(tr);
  });
  updateBadges();
}
// ── Logs ──────────────────────────────────────────────────────────────────
  '✅': 'log-ok',
  '❌': 'log-err',
  '⏳': 'log-info',
  '⚙️': 'log-info',
  '🏁': 'ok',
  '🛑': 'log-warn',
  '📧': 'log-info',
};
  lines.forEach(line => {
    div.className = 'log-line';
    for (const [icon, c] of Object.entries(logColors)) {
      if (line.includes(icon)) { cls = c; break; }
    }
    if (cls) div.classList.add(cls);
    div.textContent = line;
    box.appendChild(div);
  });
  if ($('autoScroll').checked) box.scrollTop = box.scrollHeight;
}
  if (d.logs && d.logs.length) {
    appendLogs(d.logs);
    logOffset = d.total;
  }
}
  $('logsBox').innerHTML = '';
  logOffset = 0;
}
// ── Badges ────────────────────────────────────────────────────────────────
  $('badge-smtp').textContent = `SMTP: ${d.smtp_count}`;
  $('badge-ses').textContent  = `SES: ${d.ses_count}`;
  $('badge-ec2').textContent  = `EC2: ${d.ec2_count}`;
}
// ── Gmail API ─────────────────────────────────────────────────────────────
  if (!clientId || !clientSecret) {
    showStatus('gmailSetupStatus', 'Enter Client ID and Client Secret', 'err');
    return;
  }
  showStatus('gmailSetupStatus', 'Generating authorization URL…', 'info');
    client_id: clientId,
    client_secret: clientSecret
  });
  if (res.success) {
    showStatus('gmailSetupStatus', '✅ Authorization URL generated! Click the link below.', 'ok');
    $('gmailAuthUrl').style.display = 'block';
    $('gmailAuthLink').href = res.auth_url;
    $('gmailAuthLink').textContent = '🔗 Click here to authorize Gmail access';
  } else {
    showStatus('gmailSetupStatus', `❌ ${res.message}`, 'err');
  }
}
  if (!code) {
    showStatus('gmailAuthStatus', 'Paste the authorization code from Google', 'err');
    return;
  }
  showStatus('gmailAuthStatus', 'Authorizing…', 'info');
  if (res.success) {
    showStatus('gmailAuthStatus', res.message, 'ok');
    $('gmailApiActive').style.display = 'block';
  } else {
    showStatus('gmailAuthStatus', `❌ ${res.message}`, 'err');
  }
}
  showStatus('gmailTestStatus', 'Testing Gmail API connection…', 'info');
  if (res.success) {
    showStatus('gmailTestStatus', res.message, 'ok');
    $('gmailApiActive').style.display = 'block';
  } else {
    showStatus('gmailTestStatus', `❌ ${res.message}`, 'err');
  }
}
  if (res.configured) {
    $('gmailApiActive').style.display = 'block';
  }
}
// ── Init ──────────────────────────────────────────────────────────────────
(async function init() {
  await Promise.all([refreshSmtp(), refreshSes(), refreshEc2(), updateBadges(), checkGmailApiStatus()]);
  setInterval(pollLogs, 2000);
  setInterval(updateBadges, 10000);
  setInterval(refreshEc2, 30000);
})();