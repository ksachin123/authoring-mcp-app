import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist', { recursive: true });

await build({
  entryPoints: ['src/entry.tsx'],
  bundle: true,
  outfile: 'dist/bundle.js',
  format: 'esm',
  jsx: 'automatic'
});

// Previously duplicated index.html's markup as a hardcoded string here,
// which silently drifted out of sync with the real index.html (a CSS-reset
// fix landed in index.html and had zero effect on the built widget because
// of this). Read the actual file instead so there's one source of truth.
writeFileSync('dist/index.html', readFileSync('index.html', 'utf8'));

console.log('Widget bundle built at dist/bundle.js');
