// Tilt AI Trading Agents — frontend
// Single file vanilla JS. SSE consumer + minimal DOM glue.

const els = {
  capUsed: document.getElementById('cap-used'),
  capLimit: document.getElementById('cap-limit'),
  activePath: document.getElementById('active-path'),
  btnMock: document.getElementById('btn-mock'),
  btnReal: document.getElementById('btn-real'),
  btnStop: document.getElementById('btn-stop'),
  runStatus: document.getElementById('run-status'),
  agentOutputs: document.getElementById('agent-outputs'),
  finalPanel: document.getElementById('final-panel'),
  cardProposal: document.querySelector('#card-proposal pre'),
  cardRisk: document.querySelector('#card-risk pre'),
  cardFm: document.querySelector('#card-fm pre'),
  cardExec: document.querySelector('#card-exec pre'),
  sampleSelect: document.getElementById('sample-select'),
  sampleLoad: document.getElementById('sample-load'),
  sampleView: document.getElementById('sample-view'),
  archTbody: document.getElementById('arch-tbody'),
};

const PIPELINE_NODES = [
  'fundamentals', 'technical', 'news', 'sentiment',
  'bull', 'bear', 'trader', 'risk', 'fund_manager',
];

const ROLE_LABELS = {
  fundamentals: 'Fundamentals',
  technical: 'Technical',
  news: 'News',
  sentiment: 'Sentiment',
  bull: 'Bull',
  bear: 'Bear',
  trader: 'Trader',
  risk: 'Risk Manager',
  fund_manager: 'Fund Manager',
  reflection: 'Reflection (post-close)',
};

let activeStream = null;

// ---- Tabs ---------------------------------------------------------------
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab').forEach((s) => s.classList.toggle('active', s.id === `tab-${tab}`));
  });
});

// ---- Boot ---------------------------------------------------------------
async function refreshCap() {
  try {
    const r = await fetch('/api/cap');
    const d = await r.json();
    els.capUsed.textContent = d.used;
    els.capLimit.textContent = d.limit;
    els.btnReal.disabled = d.used >= d.limit;
    if (d.used >= d.limit) {
      els.btnReal.title = `Cap reached for ${d.date}. Resets at UTC midnight.`;
    }
  } catch (err) {
    els.capUsed.textContent = '?';
    els.capLimit.textContent = '?';
  }
}

async function loadArchitecture() {
  const r = await fetch('/api/architecture');
  const d = await r.json();
  els.activePath.textContent = `path: ${d.active_path}`;

  // Per-role model labels in the pipeline diagram
  Object.entries(d.openrouter_role_map).forEach(([role, modelId]) => {
    document.querySelectorAll(`.model[data-role="${role}"]`).forEach((el) => {
      el.textContent = modelId;
    });
  });

  // Fill architecture table
  const order = [
    'fundamentals', 'technical', 'news', 'sentiment',
    'bull', 'bear', 'trader', 'risk', 'fund_manager', 'reflection',
  ];
  els.archTbody.innerHTML = '';
  for (const role of order) {
    const tr = document.createElement('tr');
    const tdRole = document.createElement('td');
    tdRole.textContent = ROLE_LABELS[role] || role;
    const tdOR = document.createElement('td');
    const orModel = d.openrouter_role_map[role];
    tdOR.innerHTML = orModel ? `<code>${orModel}</code>` : '–';
    const tdAnth = document.createElement('td');
    const anthModel = d.anthropic_fallback_role_map[role];
    tdAnth.innerHTML = anthModel ? `<code>${anthModel}</code>` : '–';
    tr.append(tdRole, tdOR, tdAnth);
    els.archTbody.appendChild(tr);
  }
}

async function loadSamples() {
  const r = await fetch('/api/samples');
  const d = await r.json();
  els.sampleSelect.innerHTML = '';
  for (const name of d.files) {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    els.sampleSelect.appendChild(opt);
  }
  if (d.files.includes('summary.json')) els.sampleSelect.value = 'summary.json';
}

els.sampleLoad.addEventListener('click', async () => {
  const name = els.sampleSelect.value;
  if (!name) return;
  els.sampleView.textContent = 'loading…';
  try {
    const r = await fetch(`/api/samples/${encodeURIComponent(name)}`);
    const d = await r.json();
    els.sampleView.textContent = JSON.stringify(d, null, 2);
  } catch (err) {
    els.sampleView.textContent = `error: ${err}`;
  }
});

// ---- Run flow -----------------------------------------------------------
function resetPipelineUI() {
  for (const node of PIPELINE_NODES) {
    const el = document.querySelector(`.stage[data-node="${node}"]`);
    if (el) {
      el.classList.remove('running', 'done');
    }
  }
  els.agentOutputs.innerHTML = '';
  els.finalPanel.hidden = true;
  for (const pre of [els.cardProposal, els.cardRisk, els.cardFm, els.cardExec]) {
    pre.textContent = '';
  }
  els.runStatus.classList.remove('error');
}

function appendAgentOutput(node, diff, elapsed) {
  const wrap = document.createElement('div');
  wrap.className = 'agent-output';
  const h = document.createElement('h4');
  const label = ROLE_LABELS[node] || node;
  h.innerHTML = `<span>${label}</span><span class="meta">+${elapsed}s</span>`;
  const pre = document.createElement('pre');
  let body = '';
  if (diff.fundamentals_report) body = diff.fundamentals_report;
  else if (diff.technical_report) body = diff.technical_report;
  else if (diff.news_report) body = diff.news_report;
  else if (diff.sentiment_report) body = diff.sentiment_report;
  else if (diff.bull_argument) body = diff.bull_argument;
  else if (diff.bear_argument) body = diff.bear_argument;
  else if (diff.trade_proposal) body = JSON.stringify(diff.trade_proposal, null, 2);
  else if (diff.risk_decision) body = `decision: ${diff.risk_decision}\n\n${diff.risk_reasoning || ''}`;
  else if (diff.fund_manager_decision) body = `decision: ${diff.fund_manager_decision}` + (diff.execution_result ? `\n\nexecution: ${JSON.stringify(diff.execution_result, null, 2)}` : '');
  else body = JSON.stringify(diff, null, 2);
  pre.textContent = body;
  wrap.append(h, pre);
  els.agentOutputs.appendChild(wrap);
}

function setStageRunning(node) {
  document.querySelector(`.stage[data-node="${node}"]`)?.classList.add('running');
}
function setStageDone(node) {
  const el = document.querySelector(`.stage[data-node="${node}"]`);
  if (el) { el.classList.remove('running'); el.classList.add('done'); }
}

function startRun(mode) {
  if (activeStream) return;
  resetPipelineUI();
  els.btnMock.disabled = true;
  els.btnReal.disabled = true;
  els.btnStop.disabled = false;
  els.runStatus.textContent = `connecting (${mode})…`;

  // For mock mode every node fires basically instantly, so light all up
  // optimistically. For real mode we mark each node as it returns.
  const es = new EventSource(`/api/run/${mode}`);
  activeStream = es;

  let receivedAny = false;
  es.addEventListener('queued', (e) => {
    const d = JSON.parse(e.data);
    els.runStatus.textContent = d.message;
  });
  es.addEventListener('start', (e) => {
    const d = JSON.parse(e.data);
    els.runStatus.textContent = `running ${d.ticker} on ${d.cycle_date} via ${d.active_path}…`;
    // Mark the parallel analysts running together — graph fires them concurrently.
    for (const n of ['fundamentals', 'technical', 'news', 'sentiment']) setStageRunning(n);
  });
  es.addEventListener('node', (e) => {
    receivedAny = true;
    const d = JSON.parse(e.data);
    setStageDone(d.node);
    appendAgentOutput(d.node, d.diff, d.elapsed);
    // Mark next stage running
    const idx = PIPELINE_NODES.indexOf(d.node);
    const next = PIPELINE_NODES[idx + 1];
    if (next && !document.querySelector(`.stage[data-node="${next}"]`).classList.contains('done')) {
      setStageRunning(next);
    }
    els.runStatus.textContent = `${d.node} done (+${d.elapsed}s)`;
  });
  es.addEventListener('complete', (e) => {
    const d = JSON.parse(e.data);
    const s = d.final_state;
    if (s.trade_proposal) els.cardProposal.textContent = JSON.stringify(s.trade_proposal, null, 2);
    if (s.risk_decision) els.cardRisk.textContent = `${s.risk_decision.toUpperCase()}\n\n${s.risk_reasoning || ''}`;
    if (s.fund_manager_decision) els.cardFm.textContent = s.fund_manager_decision.toUpperCase();
    if (s.execution_result) els.cardExec.textContent = JSON.stringify(s.execution_result, null, 2);
    els.finalPanel.hidden = false;
    els.runStatus.textContent = `complete in ${d.elapsed}s`;
    cleanup();
    refreshCap();
  });
  es.addEventListener('error', (e) => {
    let body = 'stream error';
    try { body = JSON.parse(e.data).message || body; } catch { /* ignore */ }
    els.runStatus.textContent = `error: ${body}`;
    els.runStatus.classList.add('error');
    cleanup();
    refreshCap();
  });
  // Default error handler — fires on connection close
  es.onerror = () => {
    if (!receivedAny) {
      els.runStatus.textContent = 'connection failed or closed';
      els.runStatus.classList.add('error');
    }
    cleanup();
  };

  function cleanup() {
    if (activeStream) { activeStream.close(); activeStream = null; }
    els.btnMock.disabled = false;
    els.btnStop.disabled = true;
    refreshCap();
  }
}

els.btnMock.addEventListener('click', () => startRun('mock'));
els.btnReal.addEventListener('click', () => {
  if (!confirm('This will spend ~$0.05 of the project OpenRouter budget. Proceed?')) return;
  startRun('real');
});
els.btnStop.addEventListener('click', () => {
  if (activeStream) { activeStream.close(); activeStream = null; }
  els.btnMock.disabled = false;
  els.btnReal.disabled = false;
  els.btnStop.disabled = true;
  els.runStatus.textContent = 'disconnected by user';
});

// ---- Boot
refreshCap();
loadArchitecture();
loadSamples();
setInterval(refreshCap, 30000);
