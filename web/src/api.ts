/**
 * Typed fetch wrappers. Paths are relative so the dev proxy (and the built
 * bundle served by the backend) resolve them - never hardcode a host or port.
 */
import type { Finding, StepDef, Tier } from './types';

export class ValidationError extends Error {
  findings: Finding[];
  constructor(findings: Finding[]) {
    super(findings.map((f) => f.message).join('; ') || 'pipeline is invalid');
    this.name = 'ValidationError';
    this.findings = findings;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 422 && Array.isArray((body as { findings?: Finding[] }).findings)) {
      throw new ValidationError((body as { findings: Finding[] }).findings);
    }
    const detail = (body as { detail?: unknown }).detail;
    throw new Error(typeof detail === 'string' ? detail : `request failed: ${response.status}`);
  }
  return body as T;
}

export interface RegistryResponse {
  steps: StepDef[];
  phases: string[];
  tiers: Tier[];
}

export interface ProjectDTO { id: string; slug: string; name: string }

// Every project resource is addressed under its project. `projectId` comes from
// getProjects, which returns exactly one entry in local mode.
export const getRegistry = (projectId: string) =>
  request<RegistryResponse>(`/projects/${projectId}/registry`);

export const getProjects = () => request<{ projects: ProjectDTO[] }>('/projects');
