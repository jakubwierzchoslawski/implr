import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { checkHealth } from './health';

describe('checkHealth', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('uses a relative /api path so no host is hardcoded', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, json: () => Promise.resolve({ status: 'ok', workspace: 'w', version: '0.1.0' }),
    });

    await checkHealth();

    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toBe('/api/health');
  });

  it('reports the workspace name on success', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok', workspace: 'acme', version: '0.1.0' }),
    });

    await expect(checkHealth()).resolves.toEqual({
      up: true, workspace: 'acme', version: '0.1.0',
    });
  });

  it('reports down rather than throwing when the backend is unreachable', async () => {
    // The dot must go red, not blow up the app.
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(checkHealth()).resolves.toEqual({ up: false, workspace: null, version: null });
  });

  it('reports down on a non-ok response', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });

    await expect(checkHealth()).resolves.toMatchObject({ up: false });
  });
});
