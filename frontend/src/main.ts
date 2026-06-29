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
  main_intelligence_directorate: { abbr: 'GRU',    title: 'Main Intelligence Directorate' },
  minister_of_defense:           { abbr: 'MO',     title: 'Minister of Defense' },
  chief_of_general_staff:        { abbr: 'NGSh',   title: 'Chief of the General Staff' },
  security_council:              { abbr: 'Sovbez', title: 'Security Council' },
  commander_in_chief:            { abbr: 'VGK',    title: 'Commander-in-Chief', cinc: true },
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

const STAGE_STATUS: Record<number, string> = {
  1: 'MO · NGSh DELIBERATING IN PARALLEL <span class="cursor">█</span>',
  2: 'MO · NGSh DELIBERATING IN PARALLEL <span class="cursor">█</span>',
  3: 'SOVBEZ SYNTHESIZING <span class="cursor">█</span>',
  4: 'VGK RENDERING FINAL DECISION <span class="cursor">█</span>',
};

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

  const chatHistory = document.getElementById('chat-history') as HTMLElement;

  // Build the exchange container that grows as turns arrive
  const exchangeEl = document.createElement('div');
  exchangeEl.className = 'exchange exchange-loading';
  exchangeEl.innerHTML = `
    <div class="scenario-bubble">
      <span class="bubble-mode">${mode.toUpperCase()}</span>
      <span class="bubble-text">${esc(scenario)}</span>
    </div>
    <div class="loading-inline" id="stream-status">COUNCIL CONVENING <span class="cursor">█</span></div>
    <div class="council-turns" id="stream-turns"></div>`;
  chatHistory.appendChild(exchangeEl);
  scrollToBottom();

  const statusEl = exchangeEl.querySelector('#stream-status') as HTMLElement;
  const turnsEl = exchangeEl.querySelector('#stream-turns') as HTMLElement;

  const turns: PersonaTurn[] = [];

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

    const controller = new AbortController();
    const hardTimeout = setTimeout(() => controller.abort(), 600000);

    // Wake-up notice if backend is cold
    const wakeTimer = setTimeout(() => {
      if (turns.length === 0) statusEl.innerHTML = 'BACKEND WAKING UP — PLEASE WAIT <span class="cursor">█</span>';
    }, 8000);

    try {
      const res = await fetch(`${API_BASE}/v1/council/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      outer: while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by \n\n
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6)) as { type: string; turn?: PersonaTurn; message?: string };

          if (data.type === 'turn' && data.turn) {
            turns.push(data.turn);
            // Append card immediately — first card expanded, rest collapsed
            const cardHtml = renderPersonaCard(data.turn, turns.length > 1);
            const tmp = document.createElement('div');
            tmp.innerHTML = cardHtml.trim();
            const card = tmp.firstElementChild as HTMLElement;
            turnsEl.appendChild(card);
            attachCardToggles(card);
            // Update status to reflect next stage
            const nextStatus = STAGE_STATUS[turns.length];
            if (nextStatus) statusEl.innerHTML = nextStatus;
            scrollToBottom();
          } else if (data.type === 'done') {
            break outer;
          } else if (data.type === 'error') {
            throw new Error(data.message ?? 'Unknown server error');
          }
        }
      }
    } finally {
      clearTimeout(hardTimeout);
      clearTimeout(wakeTimer);
    }

    // Finalise — replace loading container with a clean exchange entry
    const exchange: Exchange = {
      scenario,
      mode,
      turns,
      summary: turns.find(t => t.persona === 'commander_in_chief')?.content?.slice(0, 300) ?? '',
    };
    session.push(exchange);
    exchangeEl.classList.remove('exchange-loading');
    statusEl.remove();

  } catch (err) {
    const isAbort = err instanceof DOMException && err.name === 'AbortError';
    statusEl.remove();
    const errBox = document.createElement('div');
    errBox.className = 'error-box';
    errBox.innerHTML = `${isAbort ? 'Request timed out — please try again.' : 'Council request failed — please try again.'}
      <br><span style="font-size:0.75em;opacity:0.7">${esc(String(err instanceof Error ? err.message : err))}</span>`;
    exchangeEl.appendChild(errBox);
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
