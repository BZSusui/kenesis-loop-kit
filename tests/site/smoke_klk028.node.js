/*
 * KLK-028 動的スモーク（Node.js）— SCR-001 の純ロジック（normalizeHex の #なし6桁受理）を
 * draft-gen/index.html から抽出して実挙動を検証する（smoke_klk006/024 と同型）。
 *
 * 対象: #なし6桁（Photoshopコピー値）の受理・既存ピンの維持（abc/#12/空/#12345/5桁/7桁→null）・
 *       validateRequired の充足・buildInstruction 出力が #つき小文字であること（後方互換）。
 *
 * Run: node tests/site/smoke_klk028.node.js
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

check('H1 #なし6桁の受理: 444850→#444850 / 大小文字 / 前後空白', function () {
  assert(normalizeHex('444850') === '#444850', '444850 不受理: ' + normalizeHex('444850'));
  assert(normalizeHex('44AB50') === '#44ab50', '大小文字の小文字化不一致: ' + normalizeHex('44AB50'));
  assert(normalizeHex('  444850  ') === '#444850', '前後空白trim不一致: ' + normalizeHex('  444850  '));
});

check('H2 既存ピン維持: #形式の受理と 不正入力の拒否（abc/#12/空/#12345/5桁/7桁→null）', function () {
  assert(normalizeHex('#ABC') === '#aabbcc', '#ABC 展開不一致');
  assert(normalizeHex('#2E7D6B') === '#2e7d6b', '#2E7D6B 小文字化不一致');
  assert(normalizeHex('abc') === null, 'abc(#なし3桁) が null でない');
  assert(normalizeHex('#12') === null, '#12 が null でない');
  assert(normalizeHex('') === null, '空文字が null でない');
  assert(normalizeHex('#12345') === null, '#12345 が null でない');
  assert(normalizeHex('12345') === null, '12345(5桁) が null でない');
  assert(normalizeHex('1234567') === null, '1234567(7桁) が null でない');
  assert(normalizeHex('44485g') === null, '44485g(16進外) が null でない');
});

check('H3 validateRequired: colors.main=444850（#なし）で「配色」が missing に入らない', function () {
  const v = validateRequired({ industryPreset: '士業', column: '1col', colors: { main: '444850' } });
  assert(v.ok === true, 'ok が true でない: ' + JSON.stringify(v));
  assert(v.missing.indexOf('配色') < 0, '配色が missing に入った: ' + JSON.stringify(v.missing));
});

check('H4 buildInstruction: colors.main=444850 → 出力は #444850（#つき小文字・後方互換）', function () {
  const out = buildInstruction({ column: '1col', colors: { main: '444850', sub: '44AB50' } });
  assert(out.colors.main === '#444850', 'main 正規化不一致: ' + out.colors.main);
  assert(out.colors.sub === '#44ab50', 'sub 正規化不一致: ' + out.colors.sub);
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
console.log('KLK-028 dynamic smoke checks (Node / draft-gen/index.html から純ロジック抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log('[' + st + '] ' + name);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(results.length + ' checks, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
