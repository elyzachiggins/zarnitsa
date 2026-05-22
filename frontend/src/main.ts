/**
 * ZARNITSA frontend — Vite + vanilla TS placeholder.
 *
 * Replaces the Colonel General single-file SPA with a proper Vite project.
 * The architectural model from v1 (transparent prompt viewer, live section toggles,
 * three-perspective educational overlay) is preserved here as the UX target.
 */

const app = document.getElementById("app");
if (app) {
  app.innerHTML = `
    <main style="font-family: system-ui, sans-serif; max-width: 60ch; margin: 4rem auto; padding: 0 1rem;">
      <h1 style="letter-spacing: 0.1em;">ZARNITSA</h1>
      <p style="color: #666;">Институциональный совет — frontend scaffold.</p>
      <p>
        Backend at <code>http://localhost:8000</code>. API docs at
        <a href="/docs">/docs</a>.
      </p>
      <ul>
        <li><a href="/v1/personas">List personas</a></li>
        <li><a href="/health">Health</a></li>
      </ul>
      <p style="color: #999; font-size: 0.9em;">
        UI implementation pending. See <code>docs/architecture.md</code>.
      </p>
    </main>
  `;
}
