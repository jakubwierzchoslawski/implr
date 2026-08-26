import { useEffect, useState } from 'react';
import * as api from './api';
import { checkHealth } from './health';
import type { HealthState } from './health';
import Palette from './panels/Palette';
import type { StepDef } from './types';

const POLL_MS = 5000;

export default function App() {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [steps, setSteps] = useState<StepDef[]>([]);
  const [phases, setPhases] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

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

  useEffect(() => {
    void (async () => {
      try {
        // One project in local mode, so no picker. A hosted tenant picks first.
        const { projects } = await api.getProjects();
        const project = projects[0];
        if (!project) throw new Error('the backend reported no projects');
        const registry = await api.getRegistry(project.id);
        setSteps(registry.steps);
        setPhases(registry.phases);
      } catch (e) {
        // Surfaced in the right rail: a broken registry must be visible, not an
        // empty palette that looks like nothing has loaded yet.
        setLoadError(e instanceof Error ? e.message : String(e));
      }
    })();
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

      <Palette steps={steps} phases={phases} />

      <div className="stage">
        <p className="placeholder">The canvas arrives in Phase 2.</p>
      </div>

      <aside className="aside">
        {loadError
          ? <p className="notice notice--bad">Could not load the step registry: {loadError}</p>
          : <p className="placeholder">Pipeline health arrives in Phase 3.</p>}
      </aside>
    </div>
  );
}
