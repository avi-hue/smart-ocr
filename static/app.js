/**
 * app.js – Smart-OCR Web UI Client Logic
 * Handles: navigation, file upload, SSE streaming, results rendering,
 * history, settings, drawer, toasts, and all UI micro-interactions.
 */

'use strict';

// ══════════════════════════════════════════════════════════ STATE
let currentJobId = null;
let currentResultsJobId = null;
let allResults = [];
let filteredResults = [];
let currentResultsTab = 'summary';
let uploadedFiles = [];
let eventSource = null;

// ══════════════════════════════════════════════════════════ NAVIGATION
const PAGE_TITLES = {
  dashboard: 'Dashboard',
  upload:    'Upload & Process',
  results:   'Extraction Results',
};

function navigate(page) {
  // Deactivate all
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Activate selected
  const pageEl = document.getElementById(`page-${page}`);
  const navEl  = document.querySelector(`[data-page="${page}"]`);
  if (pageEl) pageEl.classList.add('active');
  if (navEl)  navEl.classList.add('active');

  document.getElementById('page-title').textContent = PAGE_TITLES[page] || page;

  // Load page data
  if (page === 'dashboard') loadDashboard();
}

function toggleMobileMenu() {
  const sidebar = document.querySelector('aside');
  sidebar.classList.toggle('hidden');
}

// ══════════════════════════════════════════════════════════ TOAST
function showToast(title, message, type = 'info') {
  // Luxury editorial toast — charcoal/gold left accent border, alabaster card
  const borderColors = {
    success: 'border-l-primary',
    warn:    'border-l-secondary',
    error:   'border-l-error',
    info:    'border-l-primary',
  };
  const labelColors = {
    success: 'text-primary',
    warn:    'text-secondary',
    error:   'text-error',
    info:    'text-primary',
  };
  const themeBorder = borderColors[type] || borderColors.info;
  const themeText = labelColors[type] || labelColors.info;

  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast pointer-events-auto bg-surface-container border border-outline-variant ${themeBorder} border-l-[3px] shadow-lg px-5 py-4 relative overflow-hidden`;
  toast.innerHTML = `
    <div class="flex items-start gap-3">
      <div class="w-0.5 self-stretch bg-primary/25 shrink-0"></div>
      <div>
        <div class="text-[9px] font-medium tracking-[0.25em] uppercase ${themeText}">${title}</div>
        <div class="text-xs text-on-surface-variant mt-1.5 leading-relaxed">${message}</div>
      </div>
    </div>
    <div class="absolute bottom-0 left-0 right-0 h-px bg-outline-variant/10">
      <div class="toast-drain h-full bg-primary/30 w-full" style="animation:drain 4s linear forwards;"></div>
    </div>
  `;
  if (!document.getElementById('drain-style')) {
    const s = document.createElement('style');
    s.id = 'drain-style';
    s.textContent = '@keyframes drain{from{width:100%}to{width:0%}}';
    document.head.appendChild(s);
  }
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = 'all 0.4s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 450);
  }, 4000);
}

// ══════════════════════════════════════════════════════════ DASHBOARD
async function loadDashboard() {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    const { jobs, stats } = data;

    // Stat counters
    animateCount('stat-processed', stats.total_processed);
    animateCount('stat-accuracy', stats.total_extracted);
    animateCount('stat-jobs', stats.total_jobs);
    const totalErrors = jobs.reduce((s, j) => s + (j.errors || 0), 0);
    animateCount('stat-errors', totalErrors);

    // Render jobs table
    const tbody = document.getElementById('dashboard-jobs-body');
    const emptyEl = document.getElementById('dashboard-empty');

    if (!jobs.length) {
      tbody.innerHTML = '';
      emptyEl.classList.remove('hidden');
      return;
    }
    emptyEl.classList.add('hidden');

    tbody.innerHTML = jobs.slice(0, 50).map(j => `
      <tr onclick="loadResultsForJob('${j.job_id}')" class="cursor-pointer group">
        <td class="px-6 py-4 font-mono text-xs text-primary">#${j.job_id}</td>
        <td class="px-6 py-4">
          <span class="badge ${j.extractor_mode === 'hybrid' ? 'badge-info' : j.extractor_mode === 'llm' ? 'badge-warn' : 'badge-success'}">${j.extractor_mode}</span>
        </td>
        <td class="px-6 py-4 text-sm">${j.total}</td>
        <td class="px-6 py-4 text-sm text-tertiary font-bold">${j.extracted}</td>
        <td class="px-6 py-4">
          <span class="badge ${j.status === 'running' ? 'badge-run' : j.errors > 0 ? 'badge-warn' : 'badge-success'}">
            ${j.status === 'running' ? '⟳ Running' : j.errors > 0 ? '⚠ Partial' : '✓ Done'}
          </span>
        </td>
        <td class="px-6 py-4">
          <div class="flex gap-2">
            <button onclick="event.stopPropagation();loadResultsForJob('${j.job_id}')" class="text-[10px] text-primary hover:underline font-mono uppercase">View</button>
            ${j.excel_available ? `<button onclick="event.stopPropagation();downloadExcelJob('${j.job_id}')" class="text-[10px] text-tertiary hover:underline font-mono uppercase">Excel</button>` : ''}
          </div>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
}

function animateCount(id, end, duration = 1200) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = 0;
  const startTime = performance.now();
  function update(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.floor(ease * (end - start) + start);
    if (progress < 1) requestAnimationFrame(update);
    else el.textContent = end;
  }
  requestAnimationFrame(update);
}

// ══════════════════════════════════════════════════════════ FILE UPLOAD
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.add('drag-over');
}
function handleDragLeave(e) {
  document.getElementById('drop-zone').classList.remove('drag-over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  addFiles(Array.from(e.dataTransfer.files));
}
function handleFileSelect(e) {
  addFiles(Array.from(e.target.files));
  e.target.value = '';
}

function addFiles(newFiles) {
  const allowed = ['.pdf', '.png', '.jpg', '.jpeg'];
  newFiles.forEach(f => {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) { showToast('Unsupported', `${f.name} is not a supported type.`, 'warn'); return; }
    if (!uploadedFiles.find(u => u.name === f.name)) uploadedFiles.push(f);
  });
  renderFileList();
}

function renderFileList() {
  const section  = document.getElementById('file-queue-section');
  const list     = document.getElementById('file-list');
  const label    = document.getElementById('queue-label');
  const btn      = document.getElementById('start-btn');
  const btnMob   = document.getElementById('start-btn-mobile');

  if (!uploadedFiles.length) {
    section.classList.add('hidden');
    if (btn)    btn.disabled = true;
    if (btnMob) btnMob.disabled = true;
    return;
  }

  section.classList.remove('hidden');
  label.textContent = `Queue · ${uploadedFiles.length} file${uploadedFiles.length !== 1 ? 's' : ''}`;
  if (btn)    btn.disabled = false;
  if (btnMob) btnMob.disabled = false;

  list.innerHTML = uploadedFiles.map((f, i) => {
    const isPdf = f.name.toLowerCase().endsWith('.pdf');
    const size  = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + ' MB' : Math.round(f.size / 1024) + ' KB';
    const typeLabel = isPdf ? 'PDF' : 'IMG';
    return `
      <div class="file-entry flex items-center gap-4 py-3.5 border-b border-outline-variant">
        <div class="text-[8px] tracking-[0.2em] uppercase text-on-surface-variant font-medium w-8 shrink-0">${typeLabel}</div>
        <div class="flex-1 min-w-0">
          <div class="text-sm text-on-background font-medium truncate">${f.name}</div>
          <div class="text-[11px] text-on-surface-variant">${size}</div>
        </div>
        <button onclick="removeFile(${i})" class="text-on-surface-variant hover:text-on-background transition-colors duration-300 shrink-0">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="square" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>`;
  }).join('');
}

function removeFile(index) {
  uploadedFiles.splice(index, 1);
  renderFileList();
}

function clearQueue() {
  uploadedFiles = [];
  renderFileList();
  document.getElementById('result-shortcut').classList.add('hidden');
}

function toggleParallel(cb) {
  document.getElementById('workers-section').classList.toggle('hidden', !cb.checked);
}

// ══════════════════════════════════════════════════════════ PROCESSING
async function startProcessing() {
  if (!uploadedFiles.length) return;

  const engine   = document.querySelector('input[name="engine"]:checked')?.value || 'hybrid';
  const parallel = document.getElementById('parallel-toggle').checked;
  const workers  = document.getElementById('workers-slider').value;

  // Build FormData
  const fd = new FormData();
  uploadedFiles.forEach(f => fd.append('files', f));
  fd.append('extractor_mode', engine);
  fd.append('parallel', parallel);
  fd.append('workers', workers);

  // Show processing panel, hide shortcut
  const panel   = document.getElementById('processing-panel');
  const logEl   = document.getElementById('log-console');
  const progBar = document.getElementById('progress-bar');
  const progLbl = document.getElementById('progress-label');
  const startBtn    = document.getElementById('start-btn');
  const startBtnMob = document.getElementById('start-btn-mobile');
  const shortcut    = document.getElementById('result-shortcut');

  panel.classList.remove('hidden');
  shortcut.classList.add('hidden');
  logEl.innerHTML = '';
  progBar.style.width = '0%';
  progBar.className = 'h-full bar-flow';
  progLbl.textContent = `0 / ${uploadedFiles.length}`;
  if (startBtn)    { startBtn.disabled = true; }
  if (startBtnMob) { startBtnMob.disabled = true; }

  try {
    const res = await fetch('/api/process', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    currentJobId = data.job_id;
    openEventStream(data.job_id, data.total);
  } catch (e) {
    appendLog(`ERROR: ${e.message}`, 'error');
    resetStartButton();
  }
}

function openEventStream(jobId, total) {
  if (eventSource) eventSource.close();

  const logEl   = document.getElementById('log-console');
  const progBar = document.getElementById('progress-bar');
  const progLbl = document.getElementById('progress-label');

  eventSource = new EventSource(`/api/stream/${jobId}`);

  eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data);

    if (event.type === 'log') {
      appendLog(event.text, event.level);
    } else if (event.type === 'progress') {
      const pct = event.pct;
      progBar.style.width = pct + '%';
      progLbl.textContent = `${event.current} / ${total}`;
      if (event.filename) appendLog(`→ Processing: ${event.filename}`, 'info');
    } else if (event.type === 'done') {
      progBar.style.width = '100%';
      progBar.className = 'h-full rounded-full progress-bar-fill';
      progLbl.textContent = `${total} / ${total}`;
      eventSource.close();
      onJobComplete(jobId, event.extracted, event.errors);
    } else if (event.type === 'heartbeat') {
      // keep-alive, ignore
    }
  };

  eventSource.onerror = () => {
    appendLog('Stream disconnected — check server.', 'warn');
    eventSource.close();
    resetStartButton();
  };
}

function appendLog(text, level = 'info') {
  const logEl = document.getElementById('log-console');
  const span  = document.createElement('span');
  span.className = `log-line log-${level}`;
  const ts = new Date().toLocaleTimeString([], {hour12: false});
  // Strip emoji characters from log text
  const clean = text.replace(/[\u{1F300}-\u{1FFFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F000}-\u{1F02F}\u{1F0A0}-\u{1F0FF}\u{1F100}-\u{1F1FF}\u{1F200}-\u{1F2FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}]/gu, '').trim();
  span.textContent = `[${ts}] ${clean}`;
  logEl.appendChild(span);
  logEl.scrollTop = logEl.scrollHeight;
}

function onJobComplete(jobId, extracted, errors) {
  resetStartButton();
  const shortcut = document.getElementById('result-shortcut');
  const summary  = document.getElementById('result-summary');
  shortcut.classList.remove('hidden');
  summary.textContent = `${extracted} invoice${extracted !== 1 ? 's' : ''} extracted${errors ? `, ${errors} error${errors !== 1 ? 's' : ''}` : ''}`;

  showToast(
    errors === 0 ? 'Complete!' : 'Done with warnings',
    `${extracted} invoice(s) extracted from ${uploadedFiles.length} file(s).`,
    errors === 0 ? 'success' : 'warn'
  );

  // Pre-load results
  loadResultsForJob(jobId);
}

function resetStartButton() {
  const btn    = document.getElementById('start-btn');
  const btnMob = document.getElementById('start-btn-mobile');
  const empty  = uploadedFiles.length === 0;
  // Restore gold-slide button structure
  const inner  = `<span class="gold-overlay"></span><span class="btn-content gap-3">Start Extraction</span>`;
  if (btn)    { btn.disabled = empty; btn.innerHTML = inner; }
  if (btnMob) { btnMob.disabled = empty; btnMob.innerHTML = inner; }
}

// ══════════════════════════════════════════════════════════ RESULTS
async function loadResultsForJob(jobId) {
  try {
    const res  = await fetch(`/api/results/${jobId}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    currentResultsJobId = jobId;
    allResults = data.results || [];
    filteredResults = [...allResults];

    document.getElementById('results-subtitle').textContent =
      `Job #${jobId} · ${data.extracted} extracted · ${data.errors} errors`;

    const dlBtn = document.getElementById('download-btn');
    if (data.excel_available) dlBtn.classList.remove('hidden');
    else dlBtn.classList.add('hidden');

    document.getElementById('results-count').textContent = `${allResults.length} results`;
    renderSummaryTable(filteredResults);
    renderLineItemsTable(allResults);
    navigate('results');
  } catch (e) {
    showToast('Error', `Could not load results: ${e.message}`, 'error');
  }
}

function filterResults() {
  const q   = (document.getElementById('results-search').value || '').toLowerCase();
  const st  = document.getElementById('results-status-filter').value;

  filteredResults = allResults.filter(r => {
    const haystack = [r.vendor_name, r.invoice_number, r.source_file, r.buyer_name].join(' ').toLowerCase();
    const matchQ   = !q || haystack.includes(q);
    const conf     = parseFloat((r.ocr_confidence || '').replace('%', '')) || 100;
    const matchSt  = !st || (st === 'ok' ? conf >= 80 : conf < 80);
    return matchQ && matchSt;
  });

  document.getElementById('results-count').textContent = `${filteredResults.length} results`;
  renderSummaryTable(filteredResults);
}

function renderSummaryTable(rows) {
  const tbody = document.getElementById('summary-table-body');
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-on-surface-variant font-light">No results match your filter.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((r, i) => {
    const confNum   = parseFloat((r.ocr_confidence || '').replace('%', '')) || null;
    const confPct   = confNum !== null ? confNum : 100;
    // Luxury confidence bar: primary (good), on-surface-variant (ok), error (low)
    const confFill  = confPct >= 80 ? 'rgb(var(--color-primary))' : confPct >= 60 ? 'rgb(var(--color-on-surface-variant))' : 'rgb(var(--color-error))';
    const confTxt   = confPct >= 80 ? 'rgb(var(--color-primary))' : confPct >= 60 ? 'rgb(var(--color-on-surface-variant))' : 'rgb(var(--color-error))';
    const badgeType = confPct >= 80 ? 'badge-success' : confPct >= 60 ? 'badge-warn' : 'badge-error';
    const badgeText = confPct >= 80 ? 'Extracted' : confPct >= 60 ? 'Review' : 'Flagged';
    const initials  = (r.vendor_name || '??').substring(0,2).toUpperCase();
    return `
      <tr onclick="openDrawer(${i})">
        <td class="py-5 pr-10">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 bg-surface-container flex items-center justify-center text-[11px] font-medium text-on-surface tracking-wide shrink-0">${initials}</div>
            <div>
              <div class="font-headline text-base font-light text-on-background">${r.vendor_name || '<span class="text-on-surface-variant">Unknown</span>'}</div>
              <div class="text-[11px] text-on-surface-variant truncate max-w-[140px] font-mono">${r.source_file || ''}</div>
            </div>
          </div>
        </td>
        <td class="py-5 pr-10 font-mono text-xs text-on-surface-variant">${r.invoice_number || '—'}</td>
        <td class="py-5 pr-10 text-xs text-on-surface-variant">${r.invoice_date || '—'}</td>
        <td class="py-5 pr-10 font-mono text-sm font-medium text-on-background">${r.total_amount || '—'}</td>
        <td class="py-5 pr-10">
          <div class="flex items-center gap-2.5">
            <div class="conf-bar w-16"><div class="conf-bar-fill" style="width:${confPct}%; background:${confFill};"></div></div>
            <span class="text-[11px] font-medium" style="color:${confTxt}">${r.ocr_confidence || 'N/A'}</span>
          </div>
        </td>
        <td class="py-5 pr-10"><span class="badge ${badgeType}">${badgeText}</span></td>
        <td class="py-5 text-on-surface-variant">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="square" d="M9 18l6-6-6-6"/></svg>
        </td>
      </tr>`;
  }).join('');
}

function renderLineItemsTable(results) {
  const tbody = document.getElementById('items-table-body');
  const rows  = [];
  results.forEach(r => {
    (r.line_items || []).forEach(item => {
      rows.push({ ...item, _source: r.source_file, _inv: r.invoice_number });
    });
  });
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-on-surface-variant font-light">No line items extracted.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(item => `
    <tr>
      <td class="py-4 pr-8 text-[11px] font-mono text-on-surface-variant truncate max-w-[100px]">${item._source || ''}</td>
      <td class="py-4 pr-8 text-[11px] font-mono text-on-surface-variant">${item._inv || '—'}</td>
      <td class="py-4 pr-8 text-sm text-on-background">${item.Description || item.description || '—'}</td>
      <td class="py-4 pr-8 text-xs font-mono text-on-surface-variant">${item.Qty || item.quantity || '—'}</td>
      <td class="py-4 pr-8 text-xs font-mono text-on-background">${item['Unit Price'] || item.unit_price || '—'}</td>
      <td class="py-4 pr-8 text-xs font-mono text-on-surface-variant">${item['Tax Rate'] || item.tax_rate || '—'}</td>
      <td class="py-4 text-xs font-mono font-medium text-on-background">${item['Line Total'] || item.line_total || '—'}</td>
    </tr>`
  ).join('');
}

function switchResultsTab(tab) {
  currentResultsTab = tab;
  const summaryBtn = document.getElementById('tab-summary-btn');
  const itemsBtn   = document.getElementById('tab-items-btn');
  const indicator  = document.getElementById('tab-indicator');
  const summaryEl  = document.getElementById('content-summary');
  const itemsEl    = document.getElementById('content-items');

  if (tab === 'summary') {
    summaryBtn.classList.add('text-primary'); summaryBtn.classList.remove('text-on-surface-variant');
    itemsBtn.classList.remove('text-primary'); itemsBtn.classList.add('text-on-surface-variant');
    summaryEl.classList.remove('hidden'); itemsEl.classList.add('hidden');
    indicator.style.width = '150px'; indicator.style.transform = 'translateX(0)';
  } else {
    itemsBtn.classList.add('text-primary'); itemsBtn.classList.remove('text-on-surface-variant');
    summaryBtn.classList.remove('text-primary'); summaryBtn.classList.add('text-on-surface-variant');
    itemsEl.classList.remove('hidden'); summaryEl.classList.add('hidden');
    indicator.style.width = '90px'; indicator.style.transform = 'translateX(180px)';
  }
}

// ══════════════════════════════════════════════════════════ DRAWER
function openDrawer(index) {
  const r = filteredResults[index];
  if (!r) return;

  document.getElementById('drawer-title').textContent = r.vendor_name || 'Invoice Details';
  document.getElementById('drawer-subtitle').textContent = `#${r.invoice_number || 'N/A'} · ${r.source_file}`;

  const fields = [
    ['Vendor',        r.vendor_name],
    ['Buyer',         r.buyer_name],
    ['Invoice #',     r.invoice_number],
    ['Invoice Date',  r.invoice_date],
    ['Due Date',      r.due_date],
    ['PO Number',     r.purchase_order],
    ['GSTIN',         r.vendor_gstin],
    ['PAN',           r.vendor_pan],
    ['Subtotal',      r.subtotal],
    ['Tax Amount',    r.tax_amount],
    ['Grand Total',   r.total_amount],
    ['Currency',      r.currency],
    ['OCR Confidence',r.ocr_confidence],
  ].filter(([, v]) => v);

  const lineItems = r.line_items || [];

  document.getElementById('drawer-content').innerHTML = `
    <!-- Key-value grid with horizontal separators — editorial layout -->
    <div class="space-y-0 mb-8">
      ${fields.map(([k, v]) => `
        <div class="flex items-baseline justify-between py-3.5 border-b border-outline-variant">
          <div class="text-[9px] tracking-[0.25em] uppercase text-on-surface-variant font-medium shrink-0 mr-4">${k}</div>
          <div class="text-sm text-on-background font-light text-right">${v}</div>
        </div>`).join('')}
    </div>

    ${lineItems.length ? `
    <div class="mb-8">
      <div class="text-[9px] tracking-[0.3em] uppercase text-primary font-medium mb-4">Line Items · ${lineItems.length}</div>
      <!-- Luxury editorial line-items block: warm bg, thin borders -->
      <div class="bg-surface-container border-t border-outline-variant overflow-hidden">
        <table class="w-full">
          <thead>
            <tr class="border-b border-outline-variant">
              <th class="px-4 py-2.5 text-left text-[8px] tracking-[0.2em] uppercase text-on-surface-variant font-medium">Description</th>
              <th class="px-4 py-2.5 text-right text-[8px] tracking-[0.2em] uppercase text-on-surface-variant font-medium">Qty</th>
              <th class="px-4 py-2.5 text-right text-[8px] tracking-[0.2em] uppercase text-on-surface-variant font-medium">Total</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant">
            ${lineItems.map(item => `
              <tr>
                <td class="px-4 py-3 text-xs text-on-background">${item.Description || item.description || '—'}</td>
                <td class="px-4 py-3 text-right font-mono text-xs text-on-surface-variant">${item.Qty || item.quantity || '—'}</td>
                <td class="px-4 py-3 text-right font-mono text-xs font-medium text-on-background">${item['Line Total'] || item.line_total || '—'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>` : ''}

    <div class="border-t border-outline-variant pt-6">
      <button class="btn-secondary w-full h-10 text-center"
              onclick="downloadExcelJob('${currentResultsJobId}')">
        Export Excel
      </button>
    </div>
  `;

  const drawer = document.getElementById('side-drawer');
  const overlay = document.getElementById('drawer-overlay');
  drawer.classList.remove('translate-x-full');
  drawer.classList.add('drawer-open');
  overlay.classList.remove('hidden');
}

function closeDrawer() {
  const drawer = document.getElementById('side-drawer');
  const overlay = document.getElementById('drawer-overlay');
  drawer.classList.add('translate-x-full');
  drawer.classList.remove('drawer-open');
  overlay.classList.add('hidden');
}

// ══════════════════════════════════════════════════════════ DOWNLOAD
function downloadExcel() {
  if (!currentResultsJobId) return;
  downloadExcelJob(currentResultsJobId);
}
function downloadExcelJob(jobId) {
  if (!jobId) return;
  const a = document.createElement('a');
  a.href = `/api/download/${jobId}`;
  a.download = 'invoices.xlsx';
  a.click();
}

// ══════════════════════════════════════════════════════════ SETTINGS
function updateSidebarEngineStatus(mode) {
  const text = mode === 'llm' ? 'gemini ai only' : mode === 'local' ? 'local only' : 'hybrid';
  const el = document.getElementById('sidebar-engine-status');
  if (el) el.textContent = `${text} mode active`;
}

async function loadSettings() {
  try {
    const res  = await fetch('/api/settings');
    const data = await res.json();
    const mode = data.extractor_mode || 'hybrid';
    updateSidebarEngineStatus(mode);
    const radio = document.querySelector(`input[name="engine"][value="${mode}"]`);
    if (radio) radio.checked = true;
  } catch (e) {
    console.error('Settings load failed:', e);
  }
}

// ════════════════════════════════════════════════════════ DARK MODE
function toggleDarkMode() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark');
  localStorage.setItem('darkMode', isDark ? 'enabled' : 'disabled');
  // Brief transition class for smooth simultaneous color change
  document.body.classList.add('theme-transitioning');
  setTimeout(function() { document.body.classList.remove('theme-transitioning'); }, 400);
  updateDarkModeUI(isDark);
}

function updateDarkModeUI(isDark) {
  const moonIcon = document.getElementById('moon-icon');
  const sunIcon = document.getElementById('sun-icon');
  if (!moonIcon || !sunIcon) return;
  if (isDark) {
    moonIcon.classList.add('hidden');
    sunIcon.classList.remove('hidden');
  } else {
    sunIcon.classList.add('hidden');
    moonIcon.classList.remove('hidden');
  }
}

function initDarkMode() {
  const stored = localStorage.getItem('darkMode');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = stored === 'enabled' || (stored === null && prefersDark);
  // Apply to <html> element — matches html.dark CSS selector
  if (isDark) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  updateDarkModeUI(isDark);
}

// ══════════════════════════════════════════════════════════ INIT
document.addEventListener('DOMContentLoaded', () => {
  initDarkMode();
  loadDashboard();
  loadSettings();

  // Listen to engine radio options selection
  document.querySelectorAll('input[name="engine"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      if (e.target.checked) {
        updateSidebarEngineStatus(e.target.value);
      }
    });
  });

  // Sync sidebar engine status with the initially-checked radio
  const checkedEngine = document.querySelector('input[name="engine"]:checked');
  if (checkedEngine) updateSidebarEngineStatus(checkedEngine.value);

  // Auto-refresh dashboard every 10s if on it
  setInterval(() => {
    if (document.querySelector('[data-page="dashboard"].active')) loadDashboard();
  }, 10000);
});
