/*
 * KLK-027 動的スモーク（Node.js）— SCR-001 の純ロジック（buildInstruction の sectionTexts 反映）を
 * draft-gen/index.html から抽出して実挙動を検証する（smoke_klk024 と同型）。
 *
 * 対象: sectionOptions.{KEY}.heading/.lead の後方互換（無指定→従来形）・選択セクション限定・
 *       整形（heading 1行化/40字・lead 改行保持/200字）・CTA purpose/label との併用・入力非破壊。
 *
 * Run: node tests/site/smoke_klk027.node.js
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

check('T1 後方互換: sectionTexts 無指定 → sectionOptions は従来形（CTA選択時は purpose/label のみ）', function () {
  const a = buildInstruction(Object.assign({}, BASE, { sections: ['ABOUT', 'CTA'], ctaPurpose: 'order' }));
  assert(!('ABOUT' in a.sectionOptions), 'ABOUT が出た: ' + JSON.stringify(a.sectionOptions));
  const cta = a.sectionOptions.CTA;
  assert(cta && cta.purpose === 'order' && !('heading' in cta) && !('lead' in cta), 'CTA形不一致: ' + JSON.stringify(cta));
});

check('T2 選択セクションのみ反映（非選択 KEY の sectionTexts は無視）', function () {
  const b = buildInstruction(Object.assign({}, BASE, {
    sections: ['ABOUT', 'MENU'],
    sectionTexts: { ABOUT: { heading: 'H_A', lead: 'L_A' }, GALLERY: { heading: 'IGNORED' } },
  }));
  assert(b.sectionOptions.ABOUT && b.sectionOptions.ABOUT.heading === 'H_A' && b.sectionOptions.ABOUT.lead === 'L_A',
    'ABOUT 不一致: ' + JSON.stringify(b.sectionOptions));
  assert(!('GALLERY' in b.sectionOptions), '非選択 GALLERY が出た');
  assert(!('MENU' in b.sectionOptions), '未入力 MENU が出た');
});

check('T3 整形: heading は改行→スペースで1行化・40字切詰め / lead は改行保持・200字切詰め', function () {
  const c = buildInstruction(Object.assign({}, BASE, {
    sections: ['ABOUT'],
    sectionTexts: { ABOUT: { heading: 'AA\\nBB', lead: 'X\\nY' } },
  }));
  assert(c.sectionOptions.ABOUT.heading === 'AA BB', 'heading 1行化不一致: ' + JSON.stringify(c.sectionOptions.ABOUT.heading));
  assert(c.sectionOptions.ABOUT.lead === 'X\\nY', 'lead 改行保持不一致: ' + JSON.stringify(c.sectionOptions.ABOUT.lead));
  const caps = buildInstruction(Object.assign({}, BASE, {
    sections: ['ABOUT'],
    sectionTexts: { ABOUT: { heading: 'h'.repeat(80), lead: 'l'.repeat(300) } },
  }));
  assert(caps.sectionOptions.ABOUT.heading.length === 40, 'heading 上限不一致: ' + caps.sectionOptions.ABOUT.heading.length);
  assert(caps.sectionOptions.ABOUT.lead.length === 200, 'lead 上限不一致: ' + caps.sectionOptions.ABOUT.lead.length);
});

check('T4 CTA と併用（purpose/label に heading/lead が同一オブジェクトへマージ）', function () {
  const d = buildInstruction(Object.assign({}, BASE, {
    sections: ['CTA'], ctaPurpose: 'reserve',
    sectionTexts: { CTA: { heading: 'CTA_H', lead: 'CTA_L' } },
  }));
  const cta = d.sectionOptions.CTA;
  assert(cta.purpose === 'reserve' && typeof cta.label === 'string' && cta.label.length > 0,
    'purpose/label 消失: ' + JSON.stringify(cta));
  assert(cta.heading === 'CTA_H' && cta.lead === 'CTA_L', 'heading/lead マージ不一致: ' + JSON.stringify(cta));
});

check('T5 空文字のみ→キー出力なし・入力非破壊', function () {
  const e = buildInstruction(Object.assign({}, BASE, {
    sections: ['ABOUT'], sectionTexts: { ABOUT: { heading: '   ', lead: '' } },
  }));
  assert(!('ABOUT' in e.sectionOptions), '空指定で ABOUT が出た: ' + JSON.stringify(e.sectionOptions));
  const inp = Object.assign({}, BASE, { sections: ['ABOUT'], sectionTexts: { ABOUT: { heading: 'H' } } });
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
console.log('KLK-027 dynamic smoke checks (Node / draft-gen/index.html から純ロジック抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log('[' + st + '] ' + name);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(results.length + ' checks, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
