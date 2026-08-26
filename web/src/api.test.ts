import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from './api';

const okJson = (body: unknown) =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);

describe('api client', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('uses relative /api paths so no host is hardcoded', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      okJson({ steps: [], phases: [], tiers: [] }));

    await api.getRegistry('local');

    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toBe('/api/projects/local/registry');
    expect(url).not.toContain('http');
  });

  it('addresses projects under their own path', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(okJson({ projects: [] }));

    await api.getProjects();

    expect((fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('/api/projects');
  });

  it('throws a plain error with the backend detail on failure', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: false, status: 500, json: () => Promise.resolve({ detail: 'registry unreadable' }),
      } as Response));

    await expect(api.getRegistry('local')).rejects.toThrowError(/registry unreadable/);
  });

  it('raises ValidationError with findings on a 422', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: false,
        status: 422,
        json: () => Promise.resolve({
          findings: [{ code: 'cycle', message: 'graph has a cycle', node_id: null }],
        }),
      } as Response));

    await expect(api.getRegistry('local')).rejects.toBeInstanceOf(api.ValidationError);
  });
});
