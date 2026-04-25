// Tilt AI Trading Agents — frontend.
// Vanilla JS, no framework. SSE consumer + DOM glue + light micro-animations.

const els = {
  capUsed: document.getElementById('cap-used'),
  capLimit: document.getElementById('cap-limit'),
  capPill: document.getElementById('cap-pill'),
  activePath: document.getElementById('active-path'),
  btnMock: document.getElementById('btn-mock'),
  btnReal: document.getElementById('btn-real'),
  btnStop: document.getElementById('btn-stop'),
  runStatus: document.getElementById('run-status'),
  runTimer: document.getElementById('run-timer'),
  agentOutputs: document.getElementById('agent-outputs'),
  streamCounter: document.getElementById('stream-counter'),
  finalPanel: document.getElementById('final-panel'),
  finalElapsed: document.getElementById('final-elapsed'),
  rpDir: document.getElementById('rp-dir'),
  rpSize: document.getElementById('rp-size'),
  rpEntry: document.getElementById('rp-entry'),
  rpTgt: document.getElementById('rp-tgt'),
  rpThesis: document.getElementById('rp-thesis'),
  rdVerdict: document.getElementById('rd-verdict'),
  rdReason: document.getElementById('rd-reason'),
  fmVerdict: document.getElementById('fm-verdict'),
  exStatus: document.getElementById('ex-status'),
  exChain: document.getElementById('ex-chain'),
  exBlock: document.getElementById('ex-block'),
  exTx: document.getElementById('ex-tx'),
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
  bull: 'Bull researcher',
  bear: 'Bear researcher',
  trader: 'Trader',
  risk: 'Risk Manager',
  fund_manager: 'Fund Manager',
  reflection: 'Reflection (post-close)',
};

let activeStream = null;
let timerInterval = null;
let runStartedAt = 0;
let eventCount = 0;

// ---- Tabs ---------------------------------------------------------------
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab').forEach((s) => s.classList.toggle('active', s.id === `tab-${tab}`));
  });
});

// ---- Data loaders -------------------------------------------------------
async function refreshCap() {
  try {
    const r = await fetch('/api/cap');
    const d = await r.json();
    els.capUsed.textContent = d.used;
    els.capLimit.textContent = d.limit;
    const maxed = d.used >= d.limit;
    els.capPill.classList.toggle('maxed', maxed);
    if (els.btnReal) {
      els.btnReal.disabled = maxed && !activeStream;
      els.btnReal.title = maxed ? `Cap reached for ${d.date}. Resets at UTC midnight.` : '';
    }
  } catch {
    els.capUsed.textContent = '?';
    els.capLimit.textContent = '?';
  }
}

async function loadArchitecture() {
  const r = await fetch('/api/architecture');
  const d = await r.json();
  els.activePath.textContent = d.active_path;

  Object.entries(d.openrouter_role_map).forEach(([role, modelId]) => {
    document.querySelectorAll(`.node-model[data-role="${role}"]`).forEach((el) => {
      el.textContent = modelId;
    });
  });

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
    tdOR.innerHTML = orModel ? `<code>${orModel}</code>` : '<span class="dim">–</span>';
    const tdAnth = document.createElement('td');
    const anthModel = d.anthropic_fallback_role_map[role];
    tdAnth.innerHTML = anthModel ? `<code>${anthModel}</code>` : '<span class="dim">–</span>';
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
    const el = document.querySelector(`.node[data-node="${node}"]`);
    if (el) el.classList.remove('running', 'done');
    const tickEl = el?.querySelector('.node-tick .t');
    if (tickEl) tickEl.textContent = '0';
  }
  els.agentOutputs.innerHTML = '<div class="stream-empty">Streaming…</div>';
  els.streamCounter.textContent = '0 events';
  els.finalPanel.hidden = true;
  // Clear final cards
  els.rpDir.textContent = '–'; els.rpDir.className = 'big';
  els.rpSize.textContent = '–';
  els.rpEntry.textContent = '–';
  els.rpTgt.textContent = '–';
  els.rpThesis.textContent = '';
  els.rdVerdict.textContent = '–'; els.rdVerdict.className = 'verdict';
  els.rdReason.textContent = '';
  els.fmVerdict.textContent = '–'; els.fmVerdict.className = 'verdict';
  els.exStatus.textContent = '–';
  els.exChain.textContent = '–';
  els.exBlock.textContent = '–';
  els.exTx.textContent = '–';
  els.runStatus.classList.remove('error', 'success');
  els.runTimer.textContent = '0.0s';
  eventCount = 0;
}

function startTimer() {
  runStartedAt = performance.now();
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const dt = (performance.now() - runStartedAt) / 1000;
    els.runTimer.textContent = `${dt.toFixed(1)}s`;
  }, 100);
}
function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;
}

function diffToText(diff) {
  if (diff.fundamentals_report) return diff.fundamentals_report;
  if (diff.technical_report) return diff.technical_report;
  if (diff.news_report) return diff.news_report;
  if (diff.sentiment_report) return diff.sentiment_report;
  if (diff.bull_argument) return diff.bull_argument;
  if (diff.bear_argument) return diff.bear_argument;
  if (diff.trade_proposal) return JSON.stringify(diff.trade_proposal, null, 2);
  if (diff.risk_decision) return `decision: ${diff.risk_decision}\n\n${diff.risk_reasoning || ''}`;
  if (diff.fund_manager_decision) {
    let body = `decision: ${diff.fund_manager_decision}`;
    if (diff.execution_result) body += `\n\nexecution: ${JSON.stringify(diff.execution_result, null, 2)}`;
    return body;
  }
  return JSON.stringify(diff, null, 2);
}

function appendEvent(node, diff, elapsed) {
  if (eventCount === 0) els.agentOutputs.innerHTML = '';
  eventCount += 1;
  els.streamCounter.textContent = `${eventCount} event${eventCount === 1 ? '' : 's'}`;

  const event = document.createElement('div');
  event.className = 'event';

  const head = document.createElement('header');
  const role = document.createElement('span');
  role.className = 'role';
  role.textContent = ROLE_LABELS[node] || node;
  const meta = document.createElement('span');
  meta.className = 'meta';
  meta.innerHTML = `<span>+${elapsed.toFixed(1)}s</span>`;
  head.append(role, meta);

  const pre = document.createElement('pre');
  pre.textContent = diffToText(diff);

  event.append(head, pre);
  els.agentOutputs.appendChild(event);
  els.agentOutputs.scrollTop = els.agentOutputs.scrollHeight;
}

function setStageRunning(node) {
  document.querySelector(`.node[data-node="${node}"]`)?.classList.add('running');
}
function setStageDone(node, elapsed) {
  const el = document.querySelector(`.node[data-node="${node}"]`);
  if (el) {
    el.classList.remove('running');
    el.classList.add('done');
    const t = el.querySelector('.node-tick .t');
    if (t) t.textContent = elapsed.toFixed(1);
  }
}

function applyFinalState(s) {
  if (s.trade_proposal) {
    const p = s.trade_proposal;
    if (p.direction) {
      els.rpDir.textContent = p.direction.toUpperCase();
      els.rpDir.className = `big ${String(p.direction).toLowerCase()}`;
    }
    if (typeof p.size_pct === 'number') {
      els.rpSize.textContent = `${(p.size_pct * 100).toFixed(2)}% NAV`;
    }
    if (Array.isArray(p.entry_band) && p.entry_band.length === 2) {
      els.rpEntry.textContent = `$${p.entry_band[0]}–$${p.entry_band[1]}`;
    }
    const t = p.target, st = p.stop;
    if (t != null && st != null) els.rpTgt.textContent = `$${t} / $${st}`;
    if (p.thesis) els.rpThesis.textContent = p.thesis;
  }
  if (s.risk_decision) {
    els.rdVerdict.textContent = s.risk_decision.toUpperCase();
    els.rdVerdict.className = `verdict ${s.risk_decision.toLowerCase()}`;
    els.rdReason.textContent = s.risk_reasoning || '';
  }
  if (s.fund_manager_decision) {
    els.fmVerdict.textContent = s.fund_manager_decision.toUpperCase();
    els.fmVerdict.className = `verdict ${s.fund_manager_decision.toLowerCase()}`;
  }
  if (s.execution_result) {
    const ex = s.execution_result;
    els.exStatus.textContent = ex.status || '–';
    els.exChain.textContent = ex.chain_id ?? '–';
    els.exBlock.textContent = ex.block_number ?? '–';
    els.exTx.textContent = ex.tx_hash ? `${ex.tx_hash.slice(0, 12)}…${ex.tx_hash.slice(-8)}` : '–';
    if (ex.tx_hash) els.exTx.title = ex.tx_hash;
  }
  els.finalPanel.hidden = false;
}

function startRun(mode) {
  if (activeStream) return;
  resetPipelineUI();
  els.btnMock.disabled = true;
  els.btnReal.disabled = true;
  els.btnStop.disabled = false;
  els.runStatus.textContent = `connecting (${mode})…`;
  startTimer();

  const es = new EventSource(`/api/run/${mode}`);
  activeStream = es;

  let receivedAny = false;

  es.addEventListener('queued', (e) => {
    const d = JSON.parse(e.data);
    els.runStatus.textContent = d.message;
  });
  es.addEventListener('start', (e) => {
    const d = JSON.parse(e.data);
    els.runStatus.textContent = `running ${d.ticker} on ${d.cycle_date} via ${d.active_path}`;
    for (const n of ['fundamentals', 'technical', 'news', 'sentiment']) setStageRunning(n);
  });
  es.addEventListener('node', (e) => {
    receivedAny = true;
    const d = JSON.parse(e.data);
    setStageDone(d.node, d.elapsed);
    appendEvent(d.node, d.diff, d.elapsed);
    const idx = PIPELINE_NODES.indexOf(d.node);
    const next = PIPELINE_NODES[idx + 1];
    if (next) {
      const nextEl = document.querySelector(`.node[data-node="${next}"]`);
      if (nextEl && !nextEl.classList.contains('done')) setStageRunning(next);
    }
    els.runStatus.textContent = `${ROLE_LABELS[d.node] || d.node} done (+${d.elapsed.toFixed(1)}s)`;
  });
  es.addEventListener('complete', (e) => {
    const d = JSON.parse(e.data);
    applyFinalState(d.final_state);
    els.runStatus.textContent = `complete in ${d.elapsed.toFixed(1)}s`;
    els.runStatus.classList.add('success');
    els.finalElapsed.textContent = `${d.elapsed.toFixed(1)}s · ${eventCount} events`;
    cleanup();
  });
  es.addEventListener('error', (e) => {
    let body = 'stream error';
    try { body = JSON.parse(e.data).message || body; } catch {}
    els.runStatus.textContent = `error: ${body}`;
    els.runStatus.classList.add('error');
    cleanup();
  });
  es.onerror = () => {
    if (!receivedAny) {
      els.runStatus.textContent = 'connection failed or closed';
      els.runStatus.classList.add('error');
    }
    cleanup();
  };

  function cleanup() {
    if (activeStream) { activeStream.close(); activeStream = null; }
    stopTimer();
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
  stopTimer();
  els.btnMock.disabled = false;
  els.btnReal.disabled = false;
  els.btnStop.disabled = true;
  els.runStatus.textContent = 'disconnected';
});

// ---- Boot
refreshCap();
loadArchitecture();
loadSamples();
setInterval(refreshCap, 30000);
