import './style.css';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

interface Citation { entry_id: string; tier: string; snippet: string; }
interface PersonaTurn { persona: string; content: string; citations: Citation[]; }
interface CouncilResponse {
  recommendation: string;
  courses_of_action: string[];
  dissents: string[];
  turns: PersonaTurn[];
}
interface Exchange {
  scenario: string;
  mode: string;
  turns: PersonaTurn[];
  summary: string;
}

const PERSONAS: Record<string, { abbr: string; title: string; cinc?: true }> = {
  main_intelligence_directorate: { abbr: 'ГРУ',    title: 'Main Intelligence Directorate' },
  minister_of_defense:           { abbr: 'МО',     title: 'Minister of Defense' },
  chief_of_general_staff:        { abbr: 'НГШ',    title: 'Chief of the General Staff' },
  security_council:              { abbr: 'СовБез', title: 'Security Council' },
  commander_in_chief:            { abbr: 'ВГК',    title: 'Commander-in-Chief', cinc: true },
};

const MODE_HINTS: Record<string, string> = {
  strategic:     'Default advisory mode — strategic analysis and recommendations',
  analytic:      'Commentary — range of options, doctrinal analysis, anti-mirror-imaging',
  freeplay:      'MODE 1 — council determines action from the scenario',
  predetermined: 'MODE 2 — action assigned; council adjudicates rationale and execution',
};

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Session state
const session: Exchange[] = [];

function renderPersonaCard(turn: PersonaTurn, defaultCollapsed = false): string {
  const meta = PERSONAS[turn.persona] ?? { abbr: turn.persona.slice(0, 6).toUpperCase(), title: turn.persona };
  const citations = turn.citations?.length
    ? `<div class="citations">${turn.citations.map(c =>
        `<span class="citation-tag">${esc(c.entry_id)} · ${esc(c.tier)}</span>`
      ).join('')}</div>`
    : '';
  return `
    <div class="persona-card${meta.cinc ? ' is-cinc' : ''}">
      <div class="persona-header">
        <span class="persona-abbr">${meta.abbr}</span>
        <span class="persona-title">${esc(meta.title)}</span>
        <span class="persona-toggle">${defaultCollapsed ? '▼' : '▲'}</span>
      </div>
      <div class="persona-body${defaultCollapsed ? ' collapsed' : ''}">${esc(turn.content)}</div>
      ${citations}
    </div>`;
}

function renderExchange(ex: Exchange, index: number): string {
  const modeLabel = ex.mode.toUpperCase();
  const bubbleClass = 'scenario-bubble';
  const cards = ex.turns.map((t, i) => renderPersonaCard(t, i > 0)).join('');
  return `
    <div class="exchange" data-index="${index}">
      <div class="${bubbleClass}">
        <span class="bubble-mode">${modeLabel}</span>
        <span class="bubble-text">${esc(ex.scenario)}</span>
      </div>
      <div class="council-turns">${cards}</div>
    </div>`;
}

function scrollToBottom(): void {
  const history = document.getElementById('chat-history');
  if (history) history.scrollTop = history.scrollHeight;
}

function attachCardToggles(container: HTMLElement): void {
  container.querySelectorAll<HTMLElement>('.persona-header').forEach(header => {
    header.addEventListener('click', () => {
      const body = header.nextElementSibling as HTMLElement;
      const toggle = header.querySelector('.persona-toggle') as HTMLElement;
      const collapsed = body.classList.toggle('collapsed');
      toggle.textContent = collapsed ? '▼' : '▲';
    });
  });
}

function renderHistory(): void {
  const history = document.getElementById('chat-history') as HTMLElement;
  if (session.length === 0) {
    history.innerHTML = `
      <div class="empty-state">
        <div>COUNCIL STANDING BY</div>
        <div style="font-size:0.72rem;margin-top:0.5rem;color:var(--text-dim)">Enter a scenario below to convene deliberation</div>
      </div>`;
    return;
  }
  history.innerHTML = session.map(renderExchange).join('');
  attachCardToggles(history);
  scrollToBottom();
}

async function submitScenario(): Promise<void> {
  const input = document.getElementById('chat-input') as HTMLTextAreaElement;
  const modeSelect = document.getElementById('mode') as HTMLSelectElement;
  const cincInput = document.getElementById('cinc-intent') as HTMLInputElement;
  const sendBtn = document.getElementById('send-btn') as HTMLButtonElement;

  const scenario = input.value.trim();
  if (!scenario) return;

  const mode = modeSelect.value;

  sendBtn.disabled = true;
  input.value = '';

  const history = document.getElementById('chat-history') as HTMLElement;
  const loadingEl = document.createElement('div');
  loadingEl.className = 'exchange-loading';
  loadingEl.innerHTML = `
    <div class="scenario-bubble">
      <span class="bubble-mode">${mode.toUpperCase()}</span>
      <span class="bubble-text">${esc(scenario)}</span>
    </div>
    <div class="loading-inline">COUNCIL DELIBERATING <span class="cursor">█</span></div>`;
  history.appendChild(loadingEl);
  scrollToBottom();

  try {
    const priorExchanges = session.slice(-3).map(ex => ({
      scenario: ex.scenario,
      summary: ex.summary,
    }));

    const body: Record<string, unknown> = {
      scenario,
      wargame_mode: mode,
      prior_exchanges: priorExchanges,
    };
    const cinc = cincInput.value.trim();
    if (cinc) body.cinc_intent = cinc;

    let wakeTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      const li = loadingEl.querySelector('.loading-inline');
      if (li) li.innerHTML = 'BACKEND WAKING UP — PLEASE WAIT <span class="cursor">█</span>';
    }, 8000);

    const deliberationTimer = setTimeout(() => {
      const li = loadingEl.querySelector('.loading-inline');
      if (li) li.innerHTML = 'COUNCIL DELIBERATING — 5–7 MINUTES FOR FULL OUTPUT <span class="cursor">█</span>';
    }, 20000);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 600000);

    let res: Response;
    try {
      res = await fetch(`${API_BASE}/v1/council`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
      clearTimeout(deliberationTimer);
      if (wakeTimer) clearTimeout(wakeTimer);
      wakeTimer = null;
    }

    if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);

    const data: CouncilResponse = await res.json();
    const exchange: Exchange = {
      scenario,
      mode,
      turns: data.turns,
      summary: data.recommendation?.slice(0, 300) ?? '',
    };
    session.push(exchange);
    loadingEl.remove();
    renderHistory();

  } catch (err) {
    const isTimeout = err instanceof DOMException && err.name === 'AbortError';
    loadingEl.innerHTML = `
      <div class="scenario-bubble">
        <span class="bubble-mode">${mode.toUpperCase()}</span>
        <span class="bubble-text">${esc(scenario)}</span>
      </div>
      <div class="error-box">
        ${isTimeout ? 'Request timed out — please try again.' : 'Council request failed — please try again.'}
        <br><span style="font-size:0.75em;opacity:0.7">${esc(String(err instanceof Error ? err.message : err))}</span>
      </div>`;
    scrollToBottom();
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function init(): void {
  const app = document.getElementById('app');
  if (!app) return;

  app.innerHTML = `
    <div class="banner">UNCLASSIFIED // EDUCATIONAL USE ONLY // ADVERSARY MODELING SYSTEM</div>

    <header>
      <div class="header-left">
        <div class="logo">ЗАРНИЦА · ZARNITSA</div>
        <div class="logo-sub">Russian Red Team Agent · Research Prototype · v0.1</div>
      </div>
      <div class="header-controls">
        <button id="clear-btn" class="ctrl-btn">CLEAR SESSION</button>
      </div>
    </header>

    <div class="chat-layout">
      <div class="sidebar">
        <label>MODE</label>
        <select id="mode">
          <option value="strategic">STRATEGIC</option>
          <option value="analytic">ANALYTIC</option>
          <option value="freeplay">FREEPLAY — MODE 1</option>
          <option value="predetermined">PREDETERMINED — MODE 2</option>
        </select>
        <div class="mode-hint" id="mode-hint">${MODE_HINTS['strategic']}</div>

        <label style="margin-top:1.25rem">CINC INTENT <span style="opacity:0.4">(optional)</span></label>
        <input id="cinc-intent" type="text" placeholder="Commander's stated intent...">
      </div>

      <div class="chat-main">
        <div id="chat-history" class="chat-history"></div>

        <div class="chat-input-area">
          <textarea id="chat-input" placeholder="Enter scenario or follow-up question..." rows="3"></textarea>
          <button id="send-btn">SEND</button>
        </div>
      </div>
    </div>

    <footer>ZARNITSA · Unclassified · For Professional Military Education and Research Use Only</footer>`;

  // Mode hint
  const modeSelect = document.getElementById('mode') as HTMLSelectElement;
  const modeHint = document.getElementById('mode-hint') as HTMLElement;
  modeSelect.addEventListener('change', () => {
    modeHint.textContent = MODE_HINTS[modeSelect.value] ?? '';
  });

  // Clear session
  document.getElementById('clear-btn')!.addEventListener('click', () => {
    session.length = 0;
    renderHistory();
  });

  // Send
  document.getElementById('send-btn')!.addEventListener('click', () => { void submitScenario(); });

  // Enter to send (Shift+Enter for newline)
  const chatInput = document.getElementById('chat-input') as HTMLTextAreaElement;
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void submitScenario();
    }
  });

  renderHistory();
}

init();
