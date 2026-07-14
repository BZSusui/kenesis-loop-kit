/*
 * KLK-022 動的スモーク（Node.js）— SCR-001 の純ロジック（buildInstruction / normalizeSections）を
 * draft-gen/index.html から抽出して実挙動を検証する（smoke_klk006 と同型）。
 *
 * 対象: セクション選択（sections）・ヘッダー位置（layout.navPosition）・CTA誘導先（sectionOptions.CTA）の
 *       後方互換つき整形。純ロジック領域（const COLUMN_KEYS 〜 function render() 直前）を slice し、
 *       new Function(slice + testBody)() で同一スコープに束ねて実行する。
 *
 * Run: node tests/site/smoke_klk022.node.js
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

check('K1 後方互換: sections/navPosition 無指定 → 既定(top / ABOUT,MENU,GALLERY / {})', function () {
  const a = buildInstruction({ column: '1col', colors: { main: '#123456' } });
  assert(a.layout.navPosition === 'top', 'navPosition 既定が top でない: ' + a.layout.navPosition);
  assert(JSON.stringify(a.sections) === JSON.stringify(['ABOUT', 'MENU', 'GALLERY']), 'sections 既定不一致: ' + JSON.stringify(a.sections));
  assert(JSON.stringify(a.sectionOptions) === '{}', 'sectionOptions 既定が空でない: ' + JSON.stringify(a.sectionOptions));
});

check('K2 canonical整形: 順不同+重複+未知 → canonical順・重複無・未知除去', function () {
  const b = buildInstruction({ column: '1col', colors: { main: '#123456' }, sections: ['CTA', 'ABOUT', 'ABOUT', 'ZZZ', 'GALLERY'] });
  assert(JSON.stringify(b.sections) === JSON.stringify(['ABOUT', 'GALLERY', 'CTA']), 'canonical整形不一致: ' + JSON.stringify(b.sections));
});

check('K3 空/無効セクション → 後方互換の既定(ABOUT/MENU/GALLERY)', function () {
  const empty = buildInstruction({ column: '1col', colors: { main: '#123456' }, sections: [] });
  const bad = buildInstruction({ column: '1col', colors: { main: '#123456' }, sections: ['NOPE', 'XXX'] });
  assert(JSON.stringify(empty.sections) === JSON.stringify(['ABOUT', 'MENU', 'GALLERY']), '空→既定 不一致: ' + JSON.stringify(empty.sections));
  assert(JSON.stringify(bad.sections) === JSON.stringify(['ABOUT', 'MENU', 'GALLERY']), '無効のみ→既定 不一致: ' + JSON.stringify(bad.sections));
});

check('K4 navPosition enum: below-hero は透過・enum外は top へ丸め', function () {
  const below = buildInstruction({ column: '1col', colors: { main: '#123456' }, navPosition: 'below-hero' });
  const bad = buildInstruction({ column: '1col', colors: { main: '#123456' }, navPosition: 'sideways' });
  assert(below.layout.navPosition === 'below-hero', 'below-hero 透過不備: ' + below.layout.navPosition);
  assert(bad.layout.navPosition === 'top', 'enum外の丸め不備: ' + bad.layout.navPosition);
});

check('K5 CTA目的プリセット → 既定ボタン文言（purpose/label 出力）', function () {
  const d = buildInstruction({ column: '1col', colors: { main: '#123456' }, sections: ['CTA'], ctaPurpose: 'order' });
  assert(d.sectionOptions.CTA && d.sectionOptions.CTA.purpose === 'order', 'CTA purpose 不一致: ' + JSON.stringify(d.sectionOptions));
  assert(typeof d.sectionOptions.CTA.label === 'string' && d.sectionOptions.CTA.label.length > 0, 'CTA 既定ラベル欠落: ' + JSON.stringify(d.sectionOptions));
});

check('K6 CTA自由入力(custom)を採用・CTA未選択なら sectionOptions 空', function () {
  const custom = buildInstruction({ column: '1col', colors: { main: '#123456' }, sections: ['CTA'], ctaPurpose: 'custom', ctaLabel: 'FREE_TEXT' });
  assert(custom.sectionOptions.CTA.purpose === 'custom' && custom.sectionOptions.CTA.label === 'FREE_TEXT', 'custom ラベル不採用: ' + JSON.stringify(custom.sectionOptions));
  const noCta = buildInstruction({ column: '1col', colors: { main: '#123456' }, sections: ['ABOUT'], ctaPurpose: 'order' });
  assert(JSON.stringify(noCta.sectionOptions) === '{}', 'CTA未選択で options 非空: ' + JSON.stringify(noCta.sectionOptions));
});

check('K7 入力非破壊（buildInstruction が input を変更しない）', function () {
  const inp = { column: '1col', colors: { main: '#123456' }, sections: ['CTA', 'ABOUT'] };
  const snap = JSON.stringify(inp);
  buildInstruction(inp);
  assert(JSON.stringify(inp) === snap, 'buildInstruction が入力を破壊的変更した');
});

check('K8 純ロジック定数: SECTION_KEYS(14)/NAV_POSITIONS(2)/CTA_PURPOSES(6)', function () {
  assert(Array.isArray(SECTION_KEYS) && SECTION_KEYS.length === 14, 'SECTION_KEYS が14でない');
  assert(Array.isArray(NAV_POSITIONS) && NAV_POSITIONS.length === 2, 'NAV_POSITIONS が2でない');
  assert(Array.isArray(CTA_PURPOSES) && CTA_PURPOSES.length === 6, 'CTA_PURPOSES が6でない');
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
console.log('KLK-022 dynamic smoke checks (Node / draft-gen/index.html から純ロジック抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log('[' + st + '] ' + name);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(results.length + ' checks, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
