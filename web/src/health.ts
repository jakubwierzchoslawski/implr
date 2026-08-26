/** Backend liveness. Pure and never-throwing: a dead backend turns the dot red,
 *  it does not take the application down. */
export interface HealthState {
  up: boolean;
  workspace: string | null;
  version: string | null;
}

export const DOWN: HealthState = { up: false, workspace: null, version: null };

export async function checkHealth(): Promise<HealthState> {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) return DOWN;
    const body = await response.json();
    if (body?.status !== 'ok') return DOWN;
    return { up: true, workspace: body.workspace ?? null, version: body.version ?? null };
  } catch {
    return DOWN;
  }
}
