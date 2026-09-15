import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'migration/project-import.json')));
for (const source of [manifest.platform, manifest.python]) {
  git('merge-base', '--is-ancestor', source.revision, 'HEAD');
  assert.equal(git('rev-parse', `${source.revision}^{tree}`), source.tree);
}
assert.equal(git('rev-parse', `${manifest.import_commit}^1`), manifest.platform.revision);
assert.equal(git('rev-parse', `${manifest.import_commit}^2`), manifest.python.revision);
assert.equal(git('rev-parse', `${manifest.import_commit}:python`), manifest.python.tree);
console.log('Original Platform and STPD histories and exact Python import verified');
