const state = {
  activeView: 'dashboard',
  proposals: [],
  selectedProposalId: null,
  dashboard: null,
  noTrades: [],
  refreshTimer: null,
};

const els = {
  apiKey: document.getElementById('api-key'),
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
  navButtons: [...document.querySelectorAll('.nav-btn')],
};

function apiHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (els.apiKey.value.trim()) headers['X-API-Key'] = els.apiKey.value.trim();
  return headers;
}

async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...apiHeaders(), ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail?.error?.message || body?.detail || response.statusText;
    throw new Error(String(detail));
  }
  return body;
}

function setStatus(text) { els.statusLine.textContent = text; }
function toast(text, isError = false) {
  const node = document.createElement('div');
  node.className = `toast ${isError ? 'error' : ''}`;
  node.textContent = text;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 3200);
}

function switchView(view) {
  state.activeView = view;
  for (const button of els.navButtons) button.classList.toggle('active', button.dataset.view === view);
  for (const section of document.querySelectorAll('.view')) section.classList.remove('active');
  document.getElementById(`${view}-view`).classList.add('active');
  els.viewTitle.textContent = view === 'no-trades' ? 'No-trades' : view[0].toUpperCase() + view.slice(1);
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
      <div class="card"><h3>Halt</h3><div class="metric">${d.risk.emergency_halt_active ? 'ON' : 'OFF'}</div></div>
    </div>
    <div class="panel" style="margin-top:16px;">
      <h3>Latest trades</h3>
      ${d.latest_trades.length ? d.latest_trades.map(item => `<div class="proposal-item"><strong>${item.proposal_id}</strong><br><span class="muted">${item.symbol} ${item.direction} · ${item.status}</span></div>`).join('') : '<p class="muted">No trades yet.</p>'}
    </div>
  `;
}

function filteredProposals() {
  const q = els.proposalFilter.value.trim().toLowerCase();
  if (!q) return state.proposals;
  return state.proposals.filter(item => [item.proposal_id, item.symbol, item.status].some(v => String(v).toLowerCase().includes(q)));
}

function renderProposalList() {
  const items = filteredProposals();
  els.proposalList.innerHTML = items.length ? items.map(item => `
    <div class="proposal-item ${item.proposal_id === state.selectedProposalId ? 'active' : ''}" data-proposal-id="${item.proposal_id}">
      <div><strong>${item.proposal_id}</strong></div>
      <div class="muted">${item.symbol} ${item.direction} · ${item.timeframe}</div>
      <div style="margin-top:8px;"><span class="badge">${item.status}</span></div>
    </div>
  `).join('') : '<p class="muted">No proposals found.</p>';

  els.proposalList.querySelectorAll('[data-proposal-id]').forEach(node => {
    node.addEventListener('click', () => {
      state.selectedProposalId = node.dataset.proposalId;
      renderProposalList();
      loadProposalDetail(state.selectedProposalId);
    });
  });
}

async function loadProposalDetail(proposalId) {
  try {
    const detail = await apiFetch(`/proposals/${proposalId}`);
    const report = await apiFetch(`/trades/${proposalId}/report`);
    els.proposalDetail.innerHTML = `
      <h3>${detail.proposal_id}</h3>
      <div class="detail-grid">
        <div><span class="muted">Symbol</span><div>${detail.symbol}</div></div>
        <div><span class="muted">Status</span><div>${detail.status}</div></div>
        <div><span class="muted">Direction</span><div>${detail.direction}</div></div>
        <div><span class="muted">Confidence</span><div>${detail.confidence_score}</div></div>
        <div><span class="muted">Entry zone</span><div>${detail.entry_zone_min} → ${detail.entry_zone_max}</div></div>
        <div><span class="muted">Stop / TP</span><div>${detail.stop_loss} / ${detail.take_profit_1} / ${detail.take_profit_2}</div></div>
      </div>
      <div class="actions">
        <button class="primary" data-action="approve">Approve</button>
        <button class="danger" data-action="reject">Reject</button>
        <button data-action="execute">Execute</button>
      </div>
      <h4>Report</h4>
      <pre>${report.text}</pre>
    `;
    els.proposalDetail.querySelectorAll('[data-action]').forEach(btn => btn.addEventListener('click', () => runAction(proposalId, btn.dataset.action)));
  } catch (error) {
    toast(error.message, true);
  }
}

function renderNoTrades() {
  els.noTradesView.innerHTML = state.noTrades.length ? state.noTrades.map(item => `
    <div class="panel" style="margin-bottom:12px;">
      <strong>${item.symbol}</strong>
      <div class="muted">${item.reason_code} · conf=${item.confidence_score}</div>
      <div>${item.reason_text}</div>
    </div>
  `).join('') : '<p class="muted">No no-trade decisions yet.</p>';
}

async function runAction(proposalId, action) {
  try {
    const path = action === 'execute' ? `/trades/${proposalId}/execute` : `/proposals/${proposalId}/${action}`;
    const payload = { actor: 'Mike', portfolio_equity: 1000, execute_on_approve: false };
    const result = await apiFetch(path, { method: 'POST', body: JSON.stringify(payload) });
    toast(result.text || `${action} done`);
    await refreshAll();
    if (state.selectedProposalId) await loadProposalDetail(state.selectedProposalId);
  } catch (error) {
    toast(error.message, true);
  }
}

async function refreshAll() {
  setStatus('Refreshing…');
  try {
    const [dashboard, proposals, noTrades] = await Promise.all([
      apiFetch('/dashboard'),
      apiFetch('/proposals'),
      apiFetch('/no-trades'),
    ]);
    state.dashboard = dashboard;
    state.proposals = proposals;
    state.noTrades = noTrades;
    renderDashboard();
    renderProposalList();
    renderNoTrades();
    setStatus(`Updated at ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    setStatus('Refresh failed');
    toast(error.message, true);
  }
}

function setupRefreshTimer() {
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  const ms = Number(els.refreshInterval.value);
  if (ms > 0) state.refreshTimer = setInterval(refreshAll, ms);
}

els.navButtons.forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
els.refreshNow.addEventListener('click', refreshAll);
els.refreshInterval.addEventListener('change', setupRefreshTimer);
els.proposalFilter.addEventListener('input', renderProposalList);
els.apiKey.addEventListener('change', refreshAll);

setupRefreshTimer();
refreshAll();
