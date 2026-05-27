import './style.css';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

interface Citation {
  entry_id: string;
  tier: string;
  snippet: string;
}

interface PersonaTurn {
  persona: string;
  content: string;
  citations: Citation[];
  confidence: number | null;
}

interface CouncilResponse {
  recommendation: string;
  courses_of_action: string[];
  dissents: string[];
  turns: PersonaTurn[];
  knowledge_horizon: string | null;
}

const PERSONAS: Record<string, { abbr: string; title: string; cinc?: true }> = {
  commander_in_chief:            { abbr: 'ВГК',  title: 'Commander-in-Chief', cinc: true },
  chief_of_general_staff:        { abbr: 'НГШ',  title: 'Chief of the General Staff' },
  main_operations_directorate:   { abbr: 'НГОУ', title: 'Main Operations Directorate' },
  main_org_mob_directorate:      { abbr: 'НГОМУ',title: 'Main Org-Mobilization Directorate' },
  center_military_strategic:     { abbr: 'ЦВСИ', title: 'Center for Military-Strategic Studies' },
  main_intelligence_directorate: { abbr: 'ГРУ',  title: 'Military Intelligence Directorate' },
  unmanned_systems_forces:       { abbr: 'ВБпС', title: 'Unmanned Systems Forces' },
  minister_of_defense:           { abbr: 'МО',   title: 'Minister of Defense' },
  sino_russian_liaison:          { abbr: '中俄',  title: 'Sino-Russian Strategic Liaison' },
  economic_advisor:              { abbr: 'ЭС',   title: 'Economic Advisor' },
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

function renderPersonaCard(turn: PersonaTurn): string {
  const meta = PERSONAS[turn.persona] ?? { abbr: turn.persona.slice(0, 6).toUpperCase(), title: turn.persona };
  const citations = turn.citations.length
    ? `<div class="citations">${turn.citations.map(c =>
        `<span class="citation-tag">${esc(c.entry_id)} · ${esc(c.tier)}</span>`
      ).join('')}</div>`
    : '';
  return `
    <div class="persona-card${meta.cinc ? ' is-cinc' : ''}">
      <div class="persona-header">
        <span class="persona-abbr">${meta.abbr}</span>
        <span class="persona-title">${esc(meta.title)}</span>
        <span class="persona-toggle">▲</span>
      </div>
      <div class="persona-body">${esc(turn.content)}</div>
      ${citations}
    </div>`;
}

function renderSummary(data: CouncilResponse, mode: string): string {
  if (!data.recommendation && !data.courses_of_action.length && !data.dissents.length) return '';
  const coas = data.courses_of_action.length
    ? `<div class="list-label">COURSES OF ACTION</div>
       <ul class="item-list">${data.courses_of_action.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`
    : '';
  const dissents = data.dissents.length
    ? `<div class="list-label">DISSENTS</div>
       <ul class="item-list dissent">${data.dissents.map(d => `<li>${esc(d)}</li>`).join('')}</ul>`
    : '';
  return `
    <div class="council-summary">
      <h2>COUNCIL OUTPUT · ${mode.toUpperCase()}</h2>
      ${data.recommendation ? `<p>${esc(data.recommendation)}</p>` : ''}
      ${coas}${dissents}
    </div>`;
}

async function handleSubmit(): Promise<void> {
  const scenario = (document.getElementById('scenario') as HTMLTextAreaElement).value.trim();
  const cincIntent = (document.getElementById('cinc-intent') as HTMLInputElement).value.trim();
  const mode = (document.getElementById('mode') as HTMLSelectElement).value;
  const panel = document.getElementById('response-panel') as HTMLElement;
  const btn = document.getElementById('submit') as HTMLButtonElement;

  if (!scenario) {
    panel.innerHTML = `<div class="error-box">Scenario text is required.</div>`;
    return;
  }

  btn.disabled = true;

  const updateStatus = (msg: string) => {
    panel.innerHTML = `
      <div class="loading">
        <div>${msg} <span class="cursor">█</span></div>
        <div class="loading-scenario">${esc(scenario.slice(0, 140))}${scenario.length > 140 ? '…' : ''}</div>
      </div>`;
  };

  updateStatus('COUNCIL IN DELIBERATION');

  try {
    const body: Record<string, unknown> = { scenario, wargame_mode: mode };
    if (cincIntent) body.cinc_intent = cincIntent;

    // Wake the backend first — if it's cold-starting this can take ~30s
    let wakeTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      updateStatus('BACKEND WAKING UP — PLEASE WAIT');
    }, 8000);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);

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
      if (wakeTimer) clearTimeout(wakeTimer);
      wakeTimer = null;
    }

    if (!res.ok) {
      throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
    }

    const data: CouncilResponse = await res.json();
    panel.innerHTML =
      renderSummary(data, mode) +
      (data.turns.length
        ? `<div class="council-turns">${data.turns.map(renderPersonaCard).join('')}</div>`
        : '<div class="loading">No persona responses returned.</div>');

    panel.querySelectorAll<HTMLElement>('.persona-header').forEach(header => {
      header.addEventListener('click', () => {
        const body = header.nextElementSibling as HTMLElement;
        const toggle = header.querySelector('.persona-toggle') as HTMLElement;
        const collapsed = body.classList.toggle('collapsed');
        toggle.textContent = collapsed ? '▼' : '▲';
      });
    });

  } catch (err) {
    const isTimeout = err instanceof DOMException && err.name === 'AbortError';
    panel.innerHTML = `
      <div class="error-box">
        ${isTimeout
          ? 'Request timed out (120s). The backend may be under heavy load — please try again.'
          : 'Council request failed. Please try again in a moment.'}
        <br><span style="font-size:0.78em;opacity:0.8">${esc(err instanceof Error ? err.message : String(err))}</span>
      </div>`;
  } finally {
    btn.disabled = false;
  }
}

function init(): void {
  const app = document.getElementById('app');
  if (!app) return;

  app.innerHTML = `
    <div class="banner">UNCLASSIFIED // EDUCATIONAL USE ONLY // ADVERSARY MODELING SYSTEM</div>

    <header>
      <div>
        <div class="logo">ЗАРНИЦА · ZARNITSA</div>
        <div class="logo-sub">Russian Red Team Agent · Research Prototype · v0.1</div>
      </div>
    </header>

    <main>
      <section class="input-panel">
        <div class="form-group">
          <label>SCENARIO</label>
          <textarea id="scenario" placeholder="Describe the operational or strategic scenario for council deliberation..."></textarea>
        </div>
        <div class="form-group">
          <label>CINC INTENT <span style="opacity:0.5">(optional)</span></label>
          <input id="cinc-intent" type="text" placeholder="Commander's stated intent or political objective...">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>WARGAME MODE</label>
            <select id="mode">
              <option value="strategic">STRATEGIC</option>
              <option value="analytic">ANALYTIC</option>
              <option value="freeplay">FREEPLAY — MODE 1</option>
              <option value="predetermined">PREDETERMINED — MODE 2</option>
            </select>
            <div class="mode-hint" id="mode-hint">${MODE_HINTS['strategic']}</div>
          </div>
          <button id="submit">CONVENE COUNCIL</button>
        </div>
      </section>

      <div id="response-panel"></div>
    </main>

    <footer>ZARNITSA · Unclassified · For Professional Military Education and Research Use Only</footer>`;

  const modeSelect = document.getElementById('mode') as HTMLSelectElement;
  const modeHint = document.getElementById('mode-hint') as HTMLElement;
  modeSelect.addEventListener('change', () => {
    modeHint.textContent = MODE_HINTS[modeSelect.value] ?? '';
  });

  document.getElementById('submit')!.addEventListener('click', () => { void handleSubmit(); });
}

init();
