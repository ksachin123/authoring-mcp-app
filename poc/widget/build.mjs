import { build } from 'esbuild';
import { writeFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist', { recursive: true });

await build({
  entryPoints: ['src/entry.tsx'],
  bundle: true,
  outfile: 'dist/bundle.js',
  format: 'esm',
  jsx: 'automatic'
});

writeFileSync(
  'dist/index.html',
  `<!doctype html><html><head><meta charset="utf-8"><title>Research Authoring Workspace</title></head><body><div id="root"></div><script type="module" src="./bundle.js"></script></body></html>`
);

console.log('Widget bundle built at dist/bundle.js');
