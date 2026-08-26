import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const ok = { status: 'ok', workspace: 'acme-platform', version: '0.1.0' };

describe('App shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(ok) }));
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('renders the product mark', async () => {
    render(<App />);

    expect(screen.getByText(/implr studio/i)).toBeInTheDocument();
  });

  it('shows the workspace name reported by the backend', async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText('acme-platform')).toBeInTheDocument());
  });

  it('shows a healthy indicator when the backend answers', async () => {
    const { container } = render(<App />);

    await waitFor(() => expect(container.querySelector('.dot--ok')).toBeTruthy());
  });

  it('shows a down indicator when the backend does not answer', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('refused'));

    const { container } = render(<App />);

    await waitFor(() => expect(container.querySelector('.dot--down')).toBeTruthy());
  });

  it('lays out three panes', () => {
    const { container } = render(<App />);

    expect(container.querySelector('.rail')).toBeTruthy();
    expect(container.querySelector('.stage')).toBeTruthy();
    expect(container.querySelector('.aside')).toBeTruthy();
  });
});
