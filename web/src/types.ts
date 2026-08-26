export type Tier = 'haiku' | 'sonnet' | 'opus';

export interface ArgSpec {
  flag: string;
  takes_value: boolean;
  value_pattern: string | null;
  note: string;
}

export interface AgentRef { name: string; fan_out: string }
export interface IOPath { path: string; note: string }

export type StepKind = 'skill' | 'agent';

/**
 * Phase 1 renders only label, phase, description, interactive and available.
 * The rest is typed now because the payload already carries it, and a partial
 * type would have to be widened four more times over phases 4-7.
 */
export interface StepDef {
  id: string;
  kind: StepKind;
  label: string;
  phase: string;
  skill: string;
  args_allowed: ArgSpec[];
  args_default: string[];
  interactive: boolean;
  agents: AgentRef[];
  consumes: IOPath[];
  produces: IOPath[];
  produces_artefact: string | null;
  description: string;
  available: boolean;
}

export interface Finding { code: string; message: string; node_id: string | null }
