import { useEffect, useState } from 'react';
import { checkHealth } from './health';
import type { HealthState } from './health';

const POLL_MS = 5000;

export default function App() {
  const [health, setHealth] = useState<HealthState | null>(null);

  useEffect(() => {
    let live = true;
    const tick = async () => {
      const next = await checkHealth();
      if (live) setHealth(next);
    };
    void tick();
    const timer = setInterval(tick, POLL_MS);
    return () => { live = false; clearInterval(timer); };
  }, []);

  const state = health ?? null;
  const dot = state === null ? 'dot--wait' : state.up ? 'dot--ok' : 'dot--down';
  const label = state === null ? 'connecting…' : state.up ? 'connected' : 'backend unreachable';

  return (
    <div className="layout">
      <header className="appbar">
        <div className="mark"><i>iS</i> implr Studio</div>
        <div className="ws">
          <span className={`dot ${dot}`} role="img" aria-label={label} title={label} />
          <span>{state?.workspace ?? (state === null ? 'connecting…' : 'no backend')}</span>
        </div>
        <div className="spacer" />
        {state?.version && <span className="placeholder">v{state.version}</span>}
      </header>

      <aside className="rail">
        <p className="placeholder">Steps arrive in Phase 1.</p>
      </aside>

      <div className="stage">
        <p className="placeholder">The canvas arrives in Phase 2.</p>
      </div>

      <aside className="aside">
        <p className="placeholder">Pipeline health arrives in Phase 3.</p>
      </aside>
    </div>
  );
}
