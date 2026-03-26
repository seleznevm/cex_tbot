const STORAGE_KEYS = {
  apiKey: 'cex_tbot_api_key',
  rememberApiKey: 'cex_tbot_remember_api_key',
  reportMode: 'cex_tbot_report_mode',
};

const state = {
  activeView: 'dashboard',
  proposals: [],
  selectedProposalId: null,
  selectedProposalDetail: null,
  dashboard: null,
  noTrades: [],
  refreshTimer: null,
  loading: false,
  reportMode: localStorage.getItem(STORAGE_KEYS.reportMode) || 'text',
};

const els = {
  apiKey: document.getElementById('api-key'),
  rememberApiKey: document.getElementById('remember-api-key'),
  refreshInterval: document.getElementById('refresh-interval'),
  refreshNow: document.getElementById('refresh-now'),
  statusLine: document.getElementById('status-line'),
  viewTitle: document.getElementById('view-title'),
  dashboardView: document.getElementById('dashboard-view'),
  proposalsView: document.getElementById('proposals-view'),
  noTradesView: document.getElementById('no-trades-view'),
  proposalList: document.getElementById('proposal-list'),
  proposalDetail: document.getElementById('proposal-detail'),
  proposalFilter: document.getElementById('proposal-filter'),
  proposalStatusFilter: document.getElementById('proposal-status-filter'),
  proposalSort: document.getElementById('proposal-sort'),
  proposalDescending: document.getElementById('proposal-descending'),
  proposalSubmit: document.getElementById('proposal-submit'),
  navButtons: [...document.querySelectorAll('.nav-btn')],
};

function loadPreferences() {
  const remember = localStorage.getItem(STORAGE_KEYS.rememberApiKey) === 'true';
  els.rememberApiKey.checked = remember;
  if (remember) els.apiKey.value = localStorage.getItem(STORAGE_KEYS.apiKey) || '';
}

function persistApiKeyPreference() {
  localStorage.setItem(STORAGE_KEYS.rememberApiKey, String(els.rememberApiKey.checked));
  if (els.rememberApiKey.checked) {
    localStorage.setItem(STORAGE_KEYS.apiKey, els.apiKey.value.trim());
  } else {
    localStorage.removeItem(STORAGE_KEYS.apiKey);
  }
}

function apiHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (els.apiKey.value.trim()) headers['X-API-Key'] = els.apiKey.value.trim();
  return headers;
}

async function apiFetch(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { ...apiHeaders(), ...(options.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail?.error?.message || body?.detail || response.statusText;
    throw new Error(String(detail));
  }
  return body;
}

function setStatus(text) { els.statusLine.textContent = text; }
function setLoading(isLoading, text = 'Working…') {
  state.loading = isLoading;
  els.refreshNow.disabled = isLoading;
  if (isLoading) setStatus(text);
}
function toast(text, isError = false) {
  const node = document.createElement('div');
  node.className = `toast ${isError ? 'error' : ''}`;
  node.textContent = text;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 3500);
}

function badgeClass(status) {
  if (String(status).includes('EXECUT')) return 'success';
  if (String(status).includes('REJECT') || String(status).includes('INVALID')) return 'danger';
  if (String(status).includes('APPROV')) return 'accent';
  return 'neutral';
}

function switchView(view) {
  state.activeView = view;
  for (const button of els.navButtons) button.classList.toggle('active', button.dataset.view === view);
  for (const section of document.querySelectorAll('.view')) section.classList.remove('active');
  document.getElementById(`${view}-view`).classList.add('active');
  els.viewTitle.textContent = view === 'no-trades' ? 'No-trades' : view[0].toUpperCase() + view.slice(1);
}

function populateStatusFilter() {
  const current = els.proposalStatusFilter.value;
  const statuses = [...new Set(state.proposals.map(item => item.status))].sort();
  els.proposalStatusFilter.innerHTML = `<option value="">All statuses</option>${statuses.map(s => `<option value="${s}">${s}</option>`).join('')}`;
  els.proposalStatusFilter.value = statuses.includes(current) ? current : '';
}

function renderProposalSubmitForm() {
  const defaultProposal = {
    agent_name: 'Luma', strategy_id: 'breakout_reclaim', strategy_version: 'v3', market_context_id: `ctx_${Date.now()}`,
    symbol: 'BTC_USDT', timeframe: '15m', direction: 'LONG', entry_zone_min: 100, entry_zone_max: 101,
    entry_split: [{ leg_number: 1, planned_entry_price: 101, allocation_pct: 100, size_fraction: 1, valid_until: new Date(Date.now() + 15 * 60 * 1000).toISOString() }],
    stop_loss: 99, take_profit_1: 103, take_profit_2: 105, risk_percent: 0.5, risk_usd: 5, position_size: 10,
    confidence_score: 0.8, thesis: 'structure intact', invalidity_condition: 'reclaim fails', liquidity_check: 'ok', data_freshness_ms: 1000,
    created_at: new Date().toISOString(), expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(), status: 'PENDING_APPROVAL',
  };
  els.proposalSubmit.innerHTML = `
    <details class="nested-panel" ${state.proposals.length === 0 ? 'open' : ''}>
      <summary>Submit proposal</summary>
      <label class="field"><span>Proposal JSON</span><textarea id="proposal-submit-json" rows="18">${JSON.stringify(defaultProposal, null, 2)}</textarea></label>
      <div class="actions"><button id="submit-proposal-btn" class="primary">Submit proposal</button></div>
    </details>
  `;
  document.getElementById('submit-proposal-btn')?.addEventListener('click', submitProposalForm);
}

function renderDashboard() {
  if (!state.dashboard) {
    els.dashboardView.innerHTML = '<p class="muted">No dashboard data yet.</p>';
    return;
  }
  const d = state.dashboard;
  els.dashboardView.innerHTML = `
    <div class="cards">
      <div class="card"><h3>Proposals</h3><div class="metric">${d.kpis.total_proposals}</div></div>
      <div class="card"><h3>Executed</h3><div class="metric">${d.kpis.executed_proposals}</div></div>
      <div class="card"><h3>Rejected</h3><div class="metric">${d.kpis.rejected_proposals}</div></div>
      <div class="card"><h3>No-trades</h3><div class="metric">${d.kpis.total_no_trade_decisions}</div></div>
      <div class="card"><h3>Commands</h3><div class="metric">${d.kpis.operator_commands}</div></div>
      <div class="card"><h3>Halt</h3><div class="metric ${d.risk.emergency_halt_active ? 'danger-text' : 'success-text'}">${d.risk.emergency_halt_active ? 'ON' : 'OFF'}</div></div>
    </div>
    <div class="panel nested-panel">
      <div class="detail-header"><div><h3>System controls</h3><p class="muted">Emergency halt for operator flows.</p></div></div>
      <label class="field"><span>Halt reason</span><input id="halt-reason" type="text" placeholder="manual-safety-stop" value="manual-safety-stop" /></label>
      <div class="actions wrap"><button id="halt-btn" class="danger">Halt</button><button id="unhalt-btn">Unhalt</button>${d.risk.halt_reason ? `<span class="muted">Current reason: ${d.risk.halt_reason}</span>` : ''}</div>
    </div>
    <div class="panel nested-panel">
      <h3>Latest trades</h3>
      ${d.latest_trades.length ? d.latest_trades.map(item => `
        <div class="proposal-item quick-open" data-proposal-id="${item.proposal_id}"><strong>${item.proposal_id}</strong><br><span class="muted">${item.symbol} ${item.direction} · ${item.timeframe}</span><br><span class="badge ${badgeClass(item.status)}">${item.status}</span></div>
      `).join('') : '<p class="muted">No trades yet.</p>'}
    </div>
  `;
  document.getElementById('halt-btn')?.addEventListener('click', haltSystem);
  document.getElementById('unhalt-btn')?.addEventListener('click', unhaltSystem);
  els.dashboardView.querySelectorAll('.quick-open').forEach(node => {
    node.addEventListener('click', async () => {
      switchView('proposals');
      state.selectedProposalId = node.dataset.proposalId;
      renderProposalList();
      await loadProposalDetail(state.selectedProposalId);
    });
  });
}

function filteredProposals() {
  const q = els.proposalFilter.value.trim().toLowerCase();
  const statusFilter = els.proposalStatusFilter.value;
  let items = state.proposals.filter(item => !statusFilter || item.status === statusFilter);
  if (q) items = items.filter(item => [item.proposal_id, item.symbol, item.status].some(v => String(v).toLowerCase().includes(q)));
  const sortKey = els.proposalSort.value || 'proposal_id';
  items = [...items].sort((a, b) => String(a[sortKey]).localeCompare(String(b[sortKey])));
  if (els.proposalDescending.checked) items.reverse();
  return items;
}

function renderProposalList() {
  const items = filteredProposals();
  els.proposalList.innerHTML = items.length ? items.map(item => `
    <div class="proposal-item ${item.proposal_id === state.selectedProposalId ? 'active' : ''}" data-proposal-id="${item.proposal_id}">
      <div><strong>${item.proposal_id}</strong></div>
      <div class="muted">${item.symbol} ${item.direction} · ${item.timeframe}</div>
      <div class="meta-row"><span class="badge ${badgeClass(item.status)}">${item.status}</span><span class="muted">conf=${Number(item.confidence_score).toFixed(2)}</span></div>
    </div>
  `).join('') : '<p class="muted">No proposals found.</p>';
  els.proposalList.querySelectorAll('[data-proposal-id]').forEach(node => {
    node.addEventListener('click', async () => {
      state.selectedProposalId = node.dataset.proposalId;
      renderProposalList();
      await loadProposalDetail(state.selectedProposalId);
    });
  });
}

function buildReplacementPayload(detail) {
  return {
    proposal_id: `${detail.proposal_id}_mod`, proposal_version: detail.proposal_version + 1, agent_name: detail.agent_name,
    strategy_id: detail.strategy_id, strategy_version: detail.strategy_version, market_context_id: detail.market_context_id,
    symbol: detail.symbol, timeframe: detail.timeframe, direction: detail.direction, entry_zone_min: detail.entry_zone_min,
    entry_zone_max: detail.entry_zone_max, entry_split: [{ leg_number: 1, planned_entry_price: Number(detail.entry_zone_max), allocation_pct: 100.0, size_fraction: 1.0, valid_until: detail.expires_at }],
    stop_loss: detail.stop_loss, take_profit_1: detail.take_profit_1, take_profit_2: detail.take_profit_2, risk_percent: detail.risk_percent,
    risk_usd: detail.risk_usd, position_size: detail.position_size, confidence_score: detail.confidence_score,
    thesis: detail.thesis, invalidity_condition: detail.invalidity_condition, liquidity_check: detail.liquidity_check,
    data_freshness_ms: detail.data_freshness_ms, created_at: detail.created_at, expires_at: detail.expires_at, status: 'PENDING_APPROVAL',
  };
}

function renderModifyPanel(detail) {
  const replacement = buildReplacementPayload(detail);
  return `
    <details class="panel nested-panel">
      <summary>Modify proposal</summary>
      <label class="field"><span>Change summary</span><textarea id="modify-changes" rows="3" placeholder="Example: tighten stop, reduce size, raise TP1"></textarea></label>
      <label class="field"><span>Replacement payload (editable JSON)</span><textarea id="modify-payload" rows="18">${JSON.stringify(replacement, null, 2)}</textarea></label>
      <div class="actions"><button data-action="modify" class="primary">Submit modify</button></div>
    </details>
  `;
}

function reportTextForMode(report) {
  if (state.reportMode === 'operator') return report.operator_text;
  if (state.reportMode === 'telegram') return report.telegram_text;
  if (state.reportMode === 'compact') return report.compact_text;
  return report.text;
}

async function loadProposalDetail(proposalId) {
  try {
    setLoading(true, `Loading ${proposalId}…`);
    const [detail, report] = await Promise.all([apiFetch(`/proposals/${proposalId}`), apiFetch(`/trades/${proposalId}/report`)]);
    state.selectedProposalDetail = detail;
    const latestEvents = (detail.timeline?.events || []).slice(-6).map(event => `• ${event.kind}: ${event.message}`).join('\n') || 'No timeline events yet.';
    const renderedReport = reportTextForMode(report);
    els.proposalDetail.innerHTML = `
      <div class="detail-header"><div><h3>${detail.proposal_id}</h3><div class="meta-row"><span class="badge ${badgeClass(detail.status)}">${detail.status}</span><span class="muted">${detail.symbol} ${detail.direction} · ${detail.timeframe}</span></div></div></div>
      <div class="detail-grid">
        <div><span class="muted">Confidence</span><div>${Number(detail.confidence_score).toFixed(2)}</div></div>
        <div><span class="muted">Risk</span><div>${detail.risk_percent}% / $${detail.risk_usd}</div></div>
        <div><span class="muted">Entry zone</span><div>${detail.entry_zone_min} → ${detail.entry_zone_max}</div></div>
        <div><span class="muted">Position size</span><div>${detail.position_size}</div></div>
        <div><span class="muted">Stop / TP1 / TP2</span><div>${detail.stop_loss} / ${detail.take_profit_1} / ${detail.take_profit_2}</div></div>
        <div><span class="muted">Approvals / commands</span><div>${detail.approval_decision_count} / ${detail.operator_command_count}</div></div>
      </div>
      <div class="panel nested-panel"><h4>Thesis</h4><p>${detail.thesis}</p><p class="muted">Invalidation: ${detail.invalidity_condition}</p></div>
      <div class="actions wrap"><button class="primary" data-action="approve">Approve</button><button class="danger" data-action="reject">Reject</button><button data-action="execute">Execute</button></div>
      ${renderModifyPanel(detail)}
      <div class="panel nested-panel"><h4>Timeline</h4><pre>${latestEvents}</pre></div>
      <div class="panel nested-panel"><div class="detail-header"><h4>Report</h4><select id="report-mode"><option value="text">text</option><option value="operator">operator</option><option value="telegram">telegram</option><option value="compact">compact</option></select></div><pre id="report-output">${renderedReport}</pre></div>
    `;
    els.proposalDetail.querySelectorAll('[data-action="approve"],[data-action="reject"],[data-action="execute"]').forEach(btn => btn.addEventListener('click', () => runAction(proposalId, btn.dataset.action)));
    els.proposalDetail.querySelector('[data-action="modify"]')?.addEventListener('click', () => runModify(proposalId));
    const reportMode = document.getElementById('report-mode');
    reportMode.value = state.reportMode;
    reportMode.addEventListener('change', () => {
      state.reportMode = reportMode.value;
      localStorage.setItem(STORAGE_KEYS.reportMode, state.reportMode);
      document.getElementById('report-output').textContent = reportTextForMode(report);
    });
    setStatus(`Loaded ${proposalId}`);
  } catch (error) {
    toast(error.message, true);
    setStatus('Detail load failed');
  } finally {
    setLoading(false);
  }
}

function renderNoTrades() {
  els.noTradesView.innerHTML = state.noTrades.length ? state.noTrades.map(item => `
    <div class="panel" style="margin-bottom:12px;"><div class="meta-row"><strong>${item.symbol}</strong><span class="badge warning">${item.reason_code}</span></div><div class="muted">conf=${Number(item.confidence_score).toFixed(2)}</div><div>${item.reason_text}</div></div>
  `).join('') : '<p class="muted">No no-trade decisions yet.</p>';
}

async function runAction(proposalId, action) {
  try {
    setLoading(true, `${action} ${proposalId}…`);
    const path = action === 'execute' ? `/trades/${proposalId}/execute` : `/proposals/${proposalId}/${action}`;
    const payload = { actor: 'Mike', portfolio_equity: 1000, execute_on_approve: false };
    const result = await apiFetch(path, { method: 'POST', body: JSON.stringify(payload) });
    toast(result.text || `${action} done`);
    await refreshAll(false);
    if (state.selectedProposalId) await loadProposalDetail(state.selectedProposalId);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function runModify(proposalId) {
  try {
    const changes = document.getElementById('modify-changes')?.value?.trim();
    const rawPayload = document.getElementById('modify-payload')?.value?.trim();
    if (!changes) throw new Error('Add a short change summary first.');
    if (!rawPayload) throw new Error('Replacement payload is empty.');
    const replacement = JSON.parse(rawPayload);
    setLoading(true, `modify ${proposalId}…`);
    const result = await apiFetch(`/proposals/${proposalId}/modify`, { method: 'POST', body: JSON.stringify({ actor: 'Mike', portfolio_equity: 1000, changes, replacement }) });
    toast(result.text || 'modify done');
    await refreshAll(false);
    state.selectedProposalId = replacement.proposal_id;
    renderProposalList();
    await loadProposalDetail(state.selectedProposalId);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function submitProposalForm() {
  try {
    const raw = document.getElementById('proposal-submit-json')?.value?.trim();
    if (!raw) throw new Error('Proposal JSON is empty.');
    const payload = JSON.parse(raw);
    setLoading(true, 'Submitting proposal…');
    const result = await apiFetch('/proposals', { method: 'POST', body: JSON.stringify(payload) });
    toast(`Proposal stored: ${result.proposal_id}`);
    await refreshAll(false);
    state.selectedProposalId = result.proposal_id;
    renderProposalList();
    await loadProposalDetail(state.selectedProposalId);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function haltSystem() {
  try {
    const reason = document.getElementById('halt-reason')?.value?.trim() || 'manual-safety-stop';
    setLoading(true, 'Halting system…');
    await apiFetch('/system/halt', { method: 'POST', body: JSON.stringify({ reason }) });
    toast('Emergency halt activated');
    await refreshAll(false);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function unhaltSystem() {
  try {
    setLoading(true, 'Clearing halt…');
    await apiFetch('/system/unhalt', { method: 'POST', body: JSON.stringify({}) });
    toast('Emergency halt cleared');
    await refreshAll(false);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function refreshAll(showLoading = true) {
  if (showLoading) setLoading(true, 'Refreshing…');
  try {
    const [dashboard, proposals, noTrades] = await Promise.all([apiFetch('/dashboard'), apiFetch('/proposals'), apiFetch('/no-trades')]);
    state.dashboard = dashboard;
    state.proposals = proposals;
    state.noTrades = noTrades;
    populateStatusFilter();
    renderProposalSubmitForm();
    renderDashboard();
    renderProposalList();
    renderNoTrades();
    setStatus(`Updated at ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    setStatus('Refresh failed');
    toast(error.message, true);
  } finally {
    if (showLoading) setLoading(false);
  }
}

function setupRefreshTimer() {
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  const ms = Number(els.refreshInterval.value);
  if (ms > 0) state.refreshTimer = setInterval(() => refreshAll(false), ms);
}

els.navButtons.forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
els.refreshNow.addEventListener('click', () => refreshAll(true));
els.refreshInterval.addEventListener('change', setupRefreshTimer);
els.proposalFilter.addEventListener('input', renderProposalList);
els.proposalStatusFilter.addEventListener('change', renderProposalList);
els.proposalSort.addEventListener('change', renderProposalList);
els.proposalDescending.addEventListener('change', renderProposalList);
els.apiKey.addEventListener('input', persistApiKeyPreference);
els.apiKey.addEventListener('change', () => refreshAll(true));
els.rememberApiKey.addEventListener('change', persistApiKeyPreference);

loadPreferences();
setupRefreshTimer();
refreshAll(true);
