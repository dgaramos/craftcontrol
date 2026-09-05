import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, '../static/app.css'), 'utf8');

describe('Mobile shell CSS tokens (Phase 1)', () => {
  test('--color-active-nav is defined as gold #f4c95d', () => {
    expect(css).toMatch(/--color-active-nav\s*:\s*#f4c95d\s*;/);
  });

  test('--color-inactive-nav is defined as faint #46534a', () => {
    expect(css).toMatch(/--color-inactive-nav\s*:\s*#46534a\s*;/);
  });

  test('--tap-target-min is defined as 58px', () => {
    expect(css).toMatch(/--tap-target-min\s*:\s*58px\s*;/);
  });

  test('--game-mode-btn-min-height is defined as 36px', () => {
    expect(css).toMatch(/--game-mode-btn-min-height\s*:\s*36px\s*;/);
  });

  test('--color-active-nav and --color-inactive-nav are distinct values', () => {
    const activeMatch = css.match(/--color-active-nav\s*:\s*(#[0-9a-f]+)\s*;/i);
    const inactiveMatch = css.match(/--color-inactive-nav\s*:\s*(#[0-9a-f]+)\s*;/i);
    expect(activeMatch).not.toBeNull();
    expect(inactiveMatch).not.toBeNull();
    expect(activeMatch[1]).not.toBe(inactiveMatch[1]);
  });
});
