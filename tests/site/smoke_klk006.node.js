#!/usr/bin/env node
/*
 * KLK-006 動的スモークテスト（tester所有・Node.js標準のみ・ブラウザ不要）
 *
 * draft-gen/index.html の <script> から純粋ロジック部
 * （const COLUMN_KEYS 〜 function render() の直前）を切り出し、
 * フェイクDOM不要の純粋関数を実行して動的挙動を機械検証する。
 * check_klk006.py（静的S1-S15）を補完する位置づけ（設計書 §9 D群）:
 *
 *   D1 parsePalette CSS変数形式（大文字混在→4役割小文字・error null・matched4）
 *   D2 parsePalette HEX一覧形式（ROLE_NAMES対応・小文字化）
 *   D3 parsePalette 部分・失敗（メインのみ / 非配色文字列で error）
 *   D4 normalizeHex（#ABC→#aabbcc / #2E7D6B→#2e7d6b / 不正→null）
 *   D5 validateRequired 欠落検出（業種/カラム/配色 と ok）
 *   D6 配色充足=メインのみ（sub/accent/bg 無しでもゲート通過）
 *   D7 buildInstruction スキーマ・契約固定（schema/version/columns/resolved/autofill/widthPx・非破壊）
 *   D8 例外安全（空/非配色/undefined/最小入力で例外を投げない）
 *
 * 実行: node tests/site/smoke_klk006.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常
 */
'use strict';
const fs = require('fs');
const path = require('path');

const HTML_PATH = path.join(__dirname, '..', '..', 'draft-gen', 'index.html');
const src = fs.readFileSync(HTML_PATH, 'utf8');

// ---- draft-gen/index.html から純粋ロジック部を切り出す ------------------
const START = 'const COLUMN_KEYS';
const END = '\nfunction render() {';
const iStart = src.indexOf(START);
const iEnd = src.indexOf(END);
if (iStart < 0 || iEnd < 0 || iEnd <= iStart) {
  console.error('[HARNESS ERROR] draft-gen/index.html のスライスマーカーが見つかりません');
  process.exit(2);
}
const slice = src.slice(iStart, iEnd);

const testBody = `
// ===== ミニテストランナー =====
const results = [];
function check(name, fn) {
  try { fn(); results.push(['PASS', name, '']); }
  catch (e) { results.push(['FAIL', name, String(e && e.message || e)]); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }

// ===== D1: parsePalette CSS変数形式 =====
check('D1 parsePalette CSS変数形式: 大文字混在→4役割小文字・error null・matched 4件', () => {
  const txt = ':root { --color-main:#2E7D6B; --color-sub:#8FB9AE; --color-accent:#E8A33D; --color-bg:#F7F5F0; }';
  const r = parsePalette(txt);
  assert(r.error === null, 'error が null でない: ' + r.error);
  assert(r.matched.length === 4, 'matched が4件でない: ' + JSON.stringify(r.matched));
  assert(r.colors.main === '#2e7d6b', 'main 小文字化不一致: ' + r.colors.main);
  assert(r.colors.sub === '#8fb9ae', 'sub 不一致: ' + r.colors.sub);
  assert(r.colors.accent === '#e8a33d', 'accent 不一致: ' + r.colors.accent);
  assert(r.colors.bg === '#f7f5f0', 'bg 不一致: ' + r.colors.bg);
});

// ===== D2: parsePalette HEX一覧形式 =====
check('D2 parsePalette HEX一覧形式: メイン/サブ/アクセント/背景 ラベル→4役割・小文字化', () => {
  const txt = 'メイン #3b5ba5\\nサブ #a9c0e8\\nアクセント #e8a33b\\n背景 #f5f7fb';
  const r = parsePalette(txt);
  assert(r.error === null, 'error が null でない: ' + r.error);
  assert(r.matched.length === 4, 'matched が4件でない: ' + JSON.stringify(r.matched));
  assert(r.colors.main === '#3b5ba5', 'main 不一致: ' + r.colors.main);
  assert(r.colors.sub === '#a9c0e8', 'sub 不一致: ' + r.colors.sub);
  assert(r.colors.accent === '#e8a33b', 'accent 不一致: ' + r.colors.accent);
  assert(r.colors.bg === '#f5f7fb', 'bg 不一致: ' + r.colors.bg);
});

// ===== D3: parsePalette 部分・失敗 =====
check('D3 parsePalette 部分/失敗: メインのみ→matched[main]・error null / 非配色→error・matched空', () => {
  const partial = parsePalette('--color-main:#2e7d6b;');
  assert(partial.error === null, '部分入力で error が非null: ' + partial.error);
  assert(partial.colors.main === '#2e7d6b', 'main 抽出不一致: ' + partial.colors.main);
  assert(partial.colors.sub === null && partial.colors.accent === null && partial.colors.bg === null,
    '未抽出役割が null でない');
  assert(partial.matched.length === 1 && partial.matched[0] === 'main',
    'matched が [main] でない: ' + JSON.stringify(partial.matched));

  const fail = parsePalette('hello world');
  assert(typeof fail.error === 'string' && fail.error.length > 0, '非配色で error 理由が無い');
  assert(fail.matched.length === 0, '非配色で matched が空でない: ' + JSON.stringify(fail.matched));
});

// ===== D4: normalizeHex =====
check('D4 normalizeHex: #ABC→#aabbcc / #2E7D6B→#2e7d6b / abc・#12・空→null', () => {
  assert(normalizeHex('#ABC') === '#aabbcc', '#ABC 展開不一致: ' + normalizeHex('#ABC'));
  assert(normalizeHex('#2E7D6B') === '#2e7d6b', '#2E7D6B 小文字化不一致: ' + normalizeHex('#2E7D6B'));
  assert(normalizeHex('#abc') === '#aabbcc', '#abc 展開不一致: ' + normalizeHex('#abc'));
  assert(normalizeHex('  #2e7d6b  ') === '#2e7d6b', '前後空白trim不一致: ' + normalizeHex('  #2e7d6b  '));
  assert(normalizeHex('abc') === null, 'abc(＃なし) が null でない');
  assert(normalizeHex('#12') === null, '#12 が null でない');
  assert(normalizeHex('') === null, '空文字が null でない');
  assert(normalizeHex('#12345') === null, '#12345 が null でない');
});

// ===== D5: validateRequired 欠落検出 =====
check('D5 validateRequired 欠落検出: 業種空/カラムnull/メイン無効→missing・ok false / 全充足→ok true', () => {
  const bad = validateRequired({ industryPreset: '', industryCustom: '', column: null, colors: { main: 'xxx' } });
  assert(bad.ok === false, '欠落時 ok が false でない');
  assert(bad.missing.indexOf('業種') >= 0, 'missing に 業種 が無い: ' + JSON.stringify(bad.missing));
  assert(bad.missing.indexOf('カラム構成') >= 0, 'missing に カラム構成 が無い');
  assert(bad.missing.indexOf('配色') >= 0, 'missing に 配色 が無い');

  const good = validateRequired({ industryPreset: '美容', column: '1col', colors: { main: '#2e7d6b' } });
  assert(good.ok === true, '全充足で ok が true でない: ' + JSON.stringify(good.missing));
  assert(good.missing.length === 0, '全充足で missing が空でない');

  // industryCustom(自由入力)のみでも業種ゲート通過
  const custom = validateRequired({ industryCustom: 'カフェ', column: '3col', colors: { main: '#123456' } });
  assert(custom.ok === true, '自由入力のみで業種ゲート通過しない');
});

// ===== D6: 配色充足=メインのみ（U5） =====
check('D6 配色充足=メインのみ: main有効・sub/accent/bg null でも validateRequired().ok true', () => {
  const input = {
    industryPreset: '美容', column: '2col-body-right',
    colors: { main: '#2e7d6b', sub: null, accent: null, bg: null },
  };
  const v = validateRequired(input);
  assert(v.ok === true, 'メインのみで ok が true でない: ' + JSON.stringify(v.missing));
  // メイン無効ならゲート不通過
  const bad = validateRequired({ industryPreset: '美容', column: '1col', colors: { main: null } });
  assert(bad.ok === false && bad.missing.indexOf('配色') >= 0, 'メイン無効で配色ゲートが不通過にならない');
});

// ===== D7: buildInstruction スキーマ・契約固定・非破壊 =====
check('D7 buildInstruction: schema/version/columns列挙/resolved/autofill/output.mobile 非出力・入力非破壊', () => {
  const input = {
    projectName: 'サンプル案件',
    industryPreset: '美容・サロン', industryCustom: 'オーガニックカフェ',
    column: '2col-body-left', taste: 'ナチュラル・やさしい',
    colors: { main: '#2E7D6B', sub: null, accent: '#E8A33D', bg: null, mode: 'explicit' },
    refThumbs: [{ id: 'm1', label: 'サロン内観', tags: '美容 / ナチュラル' }],
    sampleUrls: ['https://example.com/', '', 'https://example.org/'],
    // KLK-062: mobile は廃止。旧入力を渡しても壊れず、出力に mobile が現れないことを確認する
    atari: 'standard', variants: 3, mobile: { enabled: true, widthPx: 375 },
  };
  const snapshot = JSON.stringify(input);
  const out = buildInstruction(input);

  assert(out.schema === 'design-draft-instruction', 'schema 不一致: ' + out.schema);
  assert(out.version === 1, 'version が 1 でない: ' + out.version);
  assert(COLUMN_KEYS.indexOf(out.layout.columns) >= 0, 'columns が列挙キーでない: ' + out.layout.columns);
  // resolved = custom.trim() || preset （custom 優先）
  assert(out.industry.resolved === 'オーガニックカフェ', 'resolved が custom 優先でない: ' + out.industry.resolved);
  // main は正規化・小文字
  assert(out.colors.main === '#2e7d6b', 'colors.main 正規化不一致: ' + out.colors.main);
  // autofill に null 役割（sub, bg）が列挙・accent は有効なので含まない
  assert(out.colors.autofill.indexOf('sub') >= 0 && out.colors.autofill.indexOf('bg') >= 0,
    'autofill に sub/bg が無い: ' + JSON.stringify(out.colors.autofill));
  assert(out.colors.autofill.indexOf('accent') < 0, 'autofill に accent(有効)が誤混入');
  // KLK-062: output.mobile は廃止（スマホ確認は比較画面の幅切替へ移行）。
  // 旧入力に mobile があっても出力には現れないこと＝廃止の実証かつ後方互換の実証。
  assert(!('mobile' in out.output), 'output.mobile は KLK-062 で廃止されたはず: ' + JSON.stringify(out.output));
  assert(out.output.variants === 3, 'variants 不一致: ' + out.output.variants);
  // R-A/KLK-008: output.animation は boolean。未指定入力（この input に animation キーは無い）で既定 true
  assert(typeof out.output.animation === 'boolean', 'output.animation が boolean でない: ' + out.output.animation);
  assert(out.output.animation === true, 'animation 未指定時の既定が true でない: ' + out.output.animation);
  // 明示 false は透過（buildInstruction の !== false 挙動）
  const animOff = buildInstruction({ column: '1col', colors: { main: '#123456' }, animation: false });
  assert(animOff.output.animation === false, 'animation:false 入力が透過されない: ' + animOff.output.animation);
  const animOn = buildInstruction({ column: '1col', colors: { main: '#123456' }, animation: true });
  assert(animOn.output.animation === true, 'animation:true 入力が透過されない: ' + animOn.output.animation);
  // 空URL除外
  assert(out.references.sampleUrls.length === 2, 'sampleUrls 空除外不備: ' + JSON.stringify(out.references.sampleUrls));
  // 必須キーの存在
  ['schema', 'version', 'meta', 'industry', 'layout', 'taste', 'colors', 'references', 'atari', 'output']
    .forEach(k => assert(k in out, '必須キー欠落: ' + k));
  assert('project' in out.meta && 'thumbnails' in out.references && 'variants' in out.output, '入れ子キー欠落');

  // 入力オブジェクトを破壊的変更しない
  assert(JSON.stringify(input) === snapshot, 'buildInstruction が入力を破壊的変更した');

  // resolved フォールバック（preset のみ）
  const presetOnly = buildInstruction({ industryPreset: '士業', industryCustom: '', column: '1col', colors: { main: '#123456' } });
  assert(presetOnly.industry.resolved === '士業', 'preset のみで resolved 不一致: ' + presetOnly.industry.resolved);
});

// ===== D8: 例外安全 =====
check('D8 例外安全: 空/非配色/undefined/最小入力/引数なし で例外を投げない', () => {
  parsePalette('');
  parsePalette('hello world');
  normalizeHex(undefined);
  normalizeHex(null);
  validateRequired({});
  buildInstruction({ colors: { main: '#2e7d6b' } });
  buildInstruction();
  buildInstruction({});
  // 何も throw されなければ到達
  assert(true, 'unreachable');
});

return results;
`;

// ---- 実行 ---------------------------------------------------------------
let results;
try {
  results = new Function(slice + '\n' + testBody)();
} catch (e) {
  console.error('[HARNESS ERROR] スライス実行に失敗:', e && e.stack || e);
  process.exit(2);
}

console.log('='.repeat(78));
console.log('KLK-006 dynamic smoke checks (Node / draft-gen/index.html から純粋関数抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log(`[${st}] ${name}`);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(`${results.length} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
