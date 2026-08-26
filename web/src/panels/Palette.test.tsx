import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Palette from './Palette';
import type { StepDef } from '../types';

const base = {
  kind: 'skill' as const,
  args_allowed: [], args_default: [], interactive: false,
  agents: [], consumes: [], produces: [], produces_artefact: null,
};

const steps: StepDef[] = [
  { ...base, id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery',
    skill: 'doc-ingest', description: 'Indexes the knowledge base.', available: true },
  { ...base, id: 'arch-gen', label: 'Architecture Brief', phase: 'design',
    skill: 'arch-gen', description: 'Writes ARCHITECTURE.md.', available: true,
    interactive: true },
  { ...base, id: 'sec-review', label: 'Security Checks', phase: 'verify',
    skill: 'sec-review', description: 'Security review.', available: false },
];

const phases = ['discovery', 'design', 'verify'];

describe('Palette', () => {
  it('groups steps under their phase heading', () => {
    render(<Palette steps={steps} phases={phases} />);

    expect(screen.getByText('discovery')).toBeInTheDocument();
    expect(screen.getByText('verify')).toBeInTheDocument();
  });

  it('omits a phase heading with no steps', () => {
    render(<Palette steps={steps} phases={[...phases, 'build']} />);

    expect(screen.queryByText('build')).not.toBeInTheDocument();
  });

  it('renders phases in the order given, not alphabetically', () => {
    const { container } = render(<Palette steps={steps} phases={phases} />);

    const headings = [...container.querySelectorAll('.phase')].map((h) => h.textContent);
    expect(headings).toEqual(['discovery', 'design', 'verify']);
  });

  it('marks an unimplemented step and explains why', () => {
    render(<Palette steps={steps} phases={phases} />);

    const planned = screen.getByText('Security Checks').closest('.chip-step')!;
    expect(planned.className).toContain('chip-step--off');
    expect(planned).toHaveAttribute('title', expect.stringMatching(/not implemented/i));
  });

  it('describes an available step in its tooltip', () => {
    render(<Palette steps={steps} phases={phases} />);

    expect(screen.getByText('Document Ingestion').closest('.chip-step'))
      .toHaveAttribute('title', 'Indexes the knowledge base.');
  });

  it('badges an interactive step', () => {
    render(<Palette steps={steps} phases={phases} />);

    expect(screen.getByText('asks')).toBeInTheDocument();
  });

  it('filters by label', async () => {
    render(<Palette steps={steps} phases={phases} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'architecture');

    expect(screen.getByText('Architecture Brief')).toBeInTheDocument();
    expect(screen.queryByText('Document Ingestion')).not.toBeInTheDocument();
  });

  it('filters by description too, not only label', async () => {
    render(<Palette steps={steps} phases={phases} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'knowledge');

    expect(screen.getByText('Document Ingestion')).toBeInTheDocument();
    expect(screen.queryByText('Security Checks')).not.toBeInTheDocument();
  });

  it('says so when nothing matches', async () => {
    render(<Palette steps={steps} phases={phases} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'zzzz');

    expect(screen.getByText(/no step matches/i)).toBeInTheDocument();
  });

  it('restores every step when the query is cleared', async () => {
    render(<Palette steps={steps} phases={phases} />);
    const box = screen.getByLabelText(/search steps/i);

    await userEvent.type(box, 'zzzz');
    await userEvent.clear(box);

    expect(screen.getByText('Document Ingestion')).toBeInTheDocument();
    expect(screen.getByText('Security Checks')).toBeInTheDocument();
  });

  it('renders an empty state before the registry arrives', () => {
    render(<Palette steps={[]} phases={phases} />);

    expect(screen.getByText(/loading steps/i)).toBeInTheDocument();
  });

  it('offers no drag affordance yet', () => {
    // Dragging is Phase 2. Nothing may suggest an affordance that does not work.
    const { container } = render(<Palette steps={steps} phases={phases} />);

    expect(container.querySelector('[draggable="true"]')).toBeNull();
  });
});
