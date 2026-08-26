import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (f: string) => readFileSync(join(__dirname, f), 'utf8');

/** These files document the rules they follow, so a comment naming a banned
 *  construct would fail a raw substring check. Assert against the CSS only. */
const rules = (f: string) => read(f).replace(/\/\*[\s\S]*?\*\//g, '');

/** Any hex colour with real saturation. Greys are allowed anywhere. */
function saturatedHexes(css: string): string[] {
  const found: string[] = [];
  for (const match of css.matchAll(/#([0-9a-fA-F]{6})\b/g)) {
    const hex = match[1];
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    if (Math.max(r, g, b) - Math.min(r, g, b) > 24) found.push('#' + hex);
  }
  return found;
}

describe('tokens.css is the only source of colour', () => {
  it('defines the reserved semantic groups', () => {
    const css = read('tokens.css');

    for (const state of [
      'running', 'succeeded', 'failed', 'blocked',
      'input', 'approval', 'skipped', 'pending', 'review',
    ]) {
      expect(css).toContain(`--st-${state}:`);
    }
    for (const tier of ['haiku', 'sonnet', 'opus']) {
      expect(css).toContain(`--tier-${tier}:`);
    }
    expect(css).toContain('--gate:');
    expect(css).toContain('--bone:');
    expect(css).toContain('--cyan:');
  });

  it('defines every run-state token in both themes', () => {
    // A state token present only in :root renders as the dark value on a light
    // theme, which is the one bug this palette cannot show in a screenshot.
    const css = read('tokens.css');
    const light = css.slice(css.indexOf('[data-theme="light"]'));

    for (const state of [
      'running', 'succeeded', 'failed', 'blocked',
      'input', 'approval', 'skipped', 'pending', 'review',
    ]) {
      expect(light).toContain(`--st-${state}:`);
    }
  });

  it('is dark by default with no prefers-color-scheme query', () => {
    // Dark is the commitment: a light OS must not flip the console.
    expect(rules('tokens.css')).not.toContain('prefers-color-scheme');
    expect(read('tokens.css')).toContain('[data-theme="light"]');
  });

  it('paints the body background from a token', () => {
    // A transparent body silently borrows the host page's ground.
    expect(read('tokens.css')).toMatch(/body\s*\{[^}]*background:\s*var\(--ground\)/);
  });

  it('component styles introduce no saturated colour of their own', () => {
    // THE design rule. Every hue in the app is a reserved token, so a brand
    // colour can never compete with the run-state palette the operator reads.
    expect(saturatedHexes(rules('app.css'))).toEqual([]);
  });

  it('every font-family declares a fallback stack', () => {
    const css = read('tokens.css');
    const families = [...css.matchAll(/--(?:sans|display|mono):([^;]+);/g)].map((m) => m[1]);

    expect(families.length).toBeGreaterThanOrEqual(3);
    for (const stack of families) {
      expect(stack.split(',').length).toBeGreaterThan(1);
    }
  });

  it('respects prefers-reduced-motion', () => {
    expect(read('tokens.css')).toContain('prefers-reduced-motion');
  });
});
