/*
 * KLK-024 動的スモーク（Node.js）— SCR-001 の純ロジック（sanitizeCopy / buildInstruction の条件付き copy）を
 * draft-gen/index.html から抽出して実挙動を検証する（smoke_klk006/022 と同型）。
 *
 * 対象: 指定コピー（copy.mvCatch/mvLead）の後方互換（無指定→キーなし）・整形（\r\n→\n・改行以外の制御文字除去・
 *       trim・上限切詰め）・片方のみ指定・入力非破壊。
 *
 * Run: node tests/site/smoke_klk024.node.js
 * exit 0 = all pass / 1 = fail / 2 = harness error。ネットワーク非使用・Node標準のみ。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(path.dirname(__dirname));
const src = fs.readFileSync(path.join(ROOT, 'draft-gen', 'index.html'), 'utf8');
const START = 'const COLUMN_KEYS';
const END = '\nfunction render() {';
const iStart = src.indexOf(START);
const iEnd = src.indexOf(END);
if (iStart < 0 || iEnd < 0 || iEnd <= iStart) {
  console.error('[HARNESS ERROR] 純ロジック領域の抽出に失敗（マーカー不一致）');
  process.exit(2);
}
const slice = src.slice(iStart, iEnd);

const testBody = `
const results = [];
function check(name, fn) {
  try { fn(); results.push(['PASS', name, '']); }
  catch (e) { results.push(['FAIL', name, e && e.message || String(e)]); }
}
function assert(c, m) { if (!c) throw new Error(m); }
const BASE = { column: '1col', colors: { main: '#123456' } };

check('C1 後方互換: 無指定/空白のみ → copy キー自体を出さない', function () {
  const a = buildInstruction(Object.assign({}, BASE));
  assert(!('copy' in a), '無指定で copy が出た: ' + JSON.stringify(a.copy));
  const b = buildInstruction(Object.assign({}, BASE, { mvCatch: '   ', mvLead: '\\n\\n' }));
  assert(!('copy' in b), '空白のみで copy が出た: ' + JSON.stringify(b.copy));
});

check('C2 片方のみ指定 → そのキーだけ出る', function () {
  const a = buildInstruction(Object.assign({}, BASE, { mvCatch: 'CATCH' }));
  assert(a.copy && a.copy.mvCatch === 'CATCH' && !('mvLead' in a.copy), 'catchのみ不一致: ' + JSON.stringify(a.copy));
  const b = buildInstruction(Object.assign({}, BASE, { mvLead: 'LEAD' }));
  assert(b.copy && b.copy.mvLead === 'LEAD' && !('mvCatch' in b.copy), 'leadのみ不一致: ' + JSON.stringify(b.copy));
});

check('C3 整形: CRLF正規化・改行以外の制御文字除去・trim', function () {
  const a = buildInstruction(Object.assign({}, BASE, { mvCatch: '  L1\\r\\nL2  ' }));
  assert(a.copy.mvCatch === 'L1\\nL2', 'CRLF正規化/trim 不一致: ' + JSON.stringify(a.copy.mvCatch));
  const b = buildInstruction(Object.assign({}, BASE, { mvCatch: 'A\\u0001B\\tC' }));
  assert(b.copy.mvCatch === 'ABC', '制御文字除去不一致: ' + JSON.stringify(b.copy.mvCatch));
});

check('C4 上限切詰め: mvCatch 60字 / mvLead 200字', function () {
  const a = buildInstruction(Object.assign({}, BASE, { mvCatch: 'x'.repeat(100), mvLead: 'y'.repeat(300) }));
  assert(a.copy.mvCatch.length === 60, 'mvCatch 上限不一致: ' + a.copy.mvCatch.length);
  assert(a.copy.mvLead.length === 200, 'mvLead 上限不一致: ' + a.copy.mvLead.length);
});

check('C5 sanitizeCopy 純関数: 非文字列→空・改行は保持', function () {
  assert(sanitizeCopy(undefined, 60) === '', 'undefined が空でない');
  assert(sanitizeCopy(123, 60) === '', '数値が空でない');
  assert(sanitizeCopy('A\\nB', 60) === 'A\\nB', '改行が保持されない');
});

check('C6 入力非破壊（buildInstruction が input を変更しない）', function () {
  const inp = Object.assign({}, BASE, { mvCatch: 'A\\nB', mvLead: 'L' });
  const snap = JSON.stringify(inp);
  buildInstruction(inp);
  assert(JSON.stringify(inp) === snap, 'buildInstruction が入力を破壊的変更した');
});

return results;
`;

let results;
try {
  results = new Function(slice + '\n' + testBody)();
} catch (e) {
  console.error('[HARNESS ERROR] スライス実行に失敗:', (e && e.stack) || e);
  process.exit(2);
}

console.log('='.repeat(78));
console.log('KLK-024 dynamic smoke checks (Node / draft-gen/index.html から純ロジック抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log('[' + st + '] ' + name);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(results.length + ' checks, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
