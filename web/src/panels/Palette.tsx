import { useMemo, useState } from 'react';
import type { StepDef } from '../types';

interface Props {
  steps: StepDef[];
  phases: string[];
}

/**
 * The step catalogue. Every step, phase, flag and tooltip arrives from
 * GET /api/projects/{pid}/registry - nothing here is hardcoded.
 *
 * Dragging arrives in Phase 2; `draggable` is deliberately absent so nothing
 * suggests an affordance that does not work yet.
 */
export default function Palette({ steps, phases }: Props) {
  const [query, setQuery] = useState('');

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return steps;
    return steps.filter((s) =>
      `${s.label} ${s.id} ${s.description}`.toLowerCase().includes(q));
  }, [steps, query]);

  const groups = phases
    .map((phase) => ({ phase, items: matches.filter((s) => s.phase === phase) }))
    .filter((g) => g.items.length > 0);

  return (
    <aside className="rail">
      <div className="rail__search">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search steps…"
          aria-label="Search steps"
        />
      </div>

      <div className="rail__list">
        {steps.length === 0 && <p className="rail__empty">Loading steps…</p>}

        {steps.length > 0 && groups.length === 0 && (
          <p className="rail__empty">No step matches “{query}”.</p>
        )}

        {groups.map(({ phase, items }) => (
          <section key={phase}>
            <h3 className="phase">{phase}</h3>
            {items.map((step) => (
              <div
                key={step.id}
                className={`chip-step${step.available ? '' : ' chip-step--off'}`}
                title={
                  step.available
                    ? step.description
                    : `${step.description} (not implemented yet - the skill does not exist)`
                }
              >
                <span>{step.label}</span>
                <span className="chip-step__meta">
                  {!step.available && <span className="tag tag--soon">soon</span>}
                  {step.available && step.interactive && <span className="tag tag--ask">asks</span>}
                </span>
              </div>
            ))}
          </section>
        ))}
      </div>
    </aside>
  );
}
