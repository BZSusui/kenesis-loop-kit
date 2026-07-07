#!/usr/bin/env node
/*
 * KLK-005 動的スモークテスト（tester所有・Node.js標準のみ・ブラウザ不要）
 *
 * palette/index.html の <script> から純粋ロジック部
 * （const KEYWORDS 〜 function render() の直前）を切り出し、
 * 最小のフェイクDOM上で実行して動的挙動を機械検証する。
 * check_klk005.py（静的S1-S12）を補完する位置づけ（設計書 §9 D群）:
 *
 *   D1 バッジ出力の3段（読みやすい◎/小さい文字は注意△/読みにくい✕・信号クラス・title集約・aa非出力）
 *   D2 判定ロジック不変（contrastRatio 既知値・境界での WCAG 等級切替）
 *   D3 hexListOf 形式（{名前} #hex の4行・ROLE_NAMES順・単色HEXのみ・metallic案でも同一）
 *   D4 cssVarsOf 不変（:root+4変数・単色HEX・KLK-004 と同一）
 *   D5 copyTextOf 呼び分け（cssvars/hexlist・切替後の p 書き換えで最新値を都度参照）
 *   D6 例外安全（極端色でも contrastBadge/hexListOf/copyTextOf が例外を投げない）
 *
 * 実行: node tests/site/smoke_klk005.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常
 */
'use strict';
const fs = require('fs');
const path = require('path');

const HTML_PATH = path.join(__dirname, '..', '..', 'palette', 'index.html');
const src = fs.readFileSync(HTML_PATH, 'utf8');

// ---- palette/index.html から純粋ロジック部を切り出す --------------------
const START = 'const KEYWORDS = {';
const END = '\nfunction render() {';
const iStart = src.indexOf(START);
const iEnd = src.indexOf(END);
if (iStart < 0 || iEnd < 0 || iEnd <= iStart) {
  console.error('[HARNESS ERROR] palette/index.html のスライスマーカーが見つかりません');
  process.exit(2);
}
const slice = src.slice(iStart, iEnd);

// ---- フェイクDOM（computeBase/makePatterns が使う分のみ・D3 の metallic 案生成用）----
const prelude = `
var __ids = {};        // getElementById レジストリ
var __inputs = [];     // radio/checkbox（name/value/checked/type）
var __kwInputs = [];   // #keywords 配下のみ
var __lastURL = null;

function __mkInput(name, value, type, checked) {
  const el = { name, value, type, _checked: !!checked };
  Object.defineProperty(el, 'checked', {
    get() { return this._checked; },
    set(v) {
      if (v && this.type === 'radio') {
        __inputs.forEach(o => { if (o !== this && o.name === this.name) o._checked = false; });
      }
      this._checked = !!v;
    },
  });
  __inputs.push(el);
  return el;
}

var document = {
  getElementById: (id) => __ids[id],
  querySelector: (sel) => {
    let m = /^input\\[name=(.+?)\\]:checked$/.exec(sel);
    if (m) return __inputs.find(i => i.name === m[1] && i.checked) || null;
    m = /^input\\[name=(.+?)\\]\\[value="(.*)"\\]$/.exec(sel);
    if (m) return __inputs.find(i => i.name === m[1] && i.value === m[2]) || null;
    return null;
  },
  querySelectorAll: (sel) => {
    if (sel === '#keywords input:checked') return __kwInputs.filter(i => i.checked);
    if (sel === '#keywords input') return __kwInputs.slice();
    return [];
  },
};
var location = { pathname: '/palette/index.html', search: '' };
var history = { replaceState: (_s, _t, url) => { __lastURL = url; } };
var CSS = { escape: (s) => String(s) };
function syncBaseUI() {} function syncAccentUI() {} function syncBgUI() {}
function syncMetallicUI() {} function render() {}
`;

const testBody = `
// ===== フィクスチャ（buildColors/buildKeywords 相当の初期状態を再現）=====
const GENRE = 'ジャンル（業種）';
function resetState() {
  __inputs.length = 0; __kwInputs.length = 0; __lastURL = null;
  location.search = '';
  __ids = {};
  ['warm','gender','formal','light','vivid','muted','contrast','age','season']
    .forEach(id => { __ids[id] = { value: '0' }; });
  ['useBase','useAccent','useBg','sameHue','cvdCheck'].forEach(id => { __ids[id] = { checked: false }; });
  ['basePick','baseHex','accentPick','accentHex','bgPick','bgHex'].forEach(id => { __ids[id] = { value: '#888888' }; });
  __mkInput('colorfam', '', 'radio', true);
  COLORS.forEach(c => __mkInput('colorfam', c.key, 'radio', false));
  Object.keys(METALLICS).forEach(famKey => {
    METALLICS[famKey].variants.forEach((v, i) => __mkInput('mv-' + famKey, v.key, 'radio', i === 0));
  });
  __mkInput('tone', '', 'radio', true);
  TONES.forEach(t => __mkInput('tone', t.key, 'radio', false));
  ['auto','light','dark'].forEach((v, i) => __mkInput('dispmode', v, 'radio', i === 0));
  Object.keys(KEYWORDS).forEach(cat => {
    if (cat === GENRE) {
      __kwInputs.push(__mkInput('kwgenre', '', 'radio', true));
      Object.keys(KEYWORDS[cat]).forEach(k => __kwInputs.push(__mkInput('kwgenre', cat + '/' + k, 'radio', false)));
    } else {
      Object.keys(KEYWORDS[cat]).forEach(k => __kwInputs.push(__mkInput('kw', cat + '/' + k, 'checkbox', false)));
    }
  });
  seed = Math.floor(mulberry32(1234)() * 1e9) || 1;
}
function setRadio(name, value) {
  const el = __inputs.find(i => i.name === name && i.value === value);
  if (!el) throw new Error('no such radio: ' + name + '=' + value);
  el.checked = true;
}

// ===== ミニテストランナー =====
const results = [];
function check(name, fn) {
  try { fn(); results.push(['PASS', name, '']); }
  catch (e) { results.push(['FAIL', name, String(e && e.message || e)]); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }
// バッジ文字列から body（>...</span>）と title を取り出す
function badgeParts(html) {
  const cls = (/class="cbadge ([a-z]+)"/.exec(html) || [])[1] || null;
  const title = (/title="([^"]*)"/.exec(html) || [])[1] || '';
  const body = (/>([^<]*)<\\/span>/.exec(html) || [])[1] || '';
  return { cls, title, body };
}
// 3≦r<4.5 / r<3 になる作為色を輝度から探索する（純粋ロジック検証用）
function grayFor(targetRatio) {
  // 白背景に対し contrastRatio(gray, #ffffff) ≈ targetRatio になる灰色を二分探索
  const ratioOf = (v) => {
    const hex = '#' + [v, v, v].map(x => x.toString(16).padStart(2, '0')).join('');
    return contrastRatio(hex, '#ffffff');
  };
  let lo = 0, hi = 255, best = 0;
  for (let it = 0; it < 40; it++) {
    const mid = (lo + hi) / 2;
    const r = ratioOf(Math.round(mid));
    if (r > targetRatio) lo = mid; else hi = mid;
    best = Math.round(mid);
  }
  return '#' + [best, best, best].map(x => x.toString(16).padStart(2, '0')).join('');
}

// ===== D1: バッジ出力の3段 =====
check('D1 バッジ3段: 読みやすい◎(aaa)/小さい文字は注意△(lg)/読みにくい✕(ng)・title集約・aa非出力', () => {
  // 高コントラスト（黒×白 ≒ 21）→ ◎ / aaa
  const hi = badgeParts(contrastBadge('本文×背景', '#000000', '#ffffff'));
  assert(hi.cls === 'aaa', '高コントラストで cls が aaa でない: ' + hi.cls);
  assert(hi.body.includes('読みやすい ◎'), 'body に 読みやすい◎ が無い: ' + hi.body);
  assert(!/\\d\\.\\d/.test(hi.body), 'body に生数値が残っている: ' + hi.body);
  assert(hi.title.includes('コントラスト比') && hi.title.includes('AAA'),
    'title に コントラスト比/AAA が無い: ' + hi.title);

  // 中間（3≦r<4.5）→ △ / lg / hint 文字を濃く
  const midHex = grayFor(3.7);
  const mid = badgeParts(contrastBadge('本文×背景', midHex, '#ffffff'));
  const midR = contrastRatio(midHex, '#ffffff');
  assert(midR >= 3 && midR < 4.5, '作為色が 3≦r<4.5 帯に無い: r=' + midR);
  assert(mid.cls === 'lg', '中間で cls が lg でない: ' + mid.cls);
  assert(mid.body.includes('小さい文字は注意 △'), 'body に 小さい文字は注意△ が無い: ' + mid.body);
  assert(mid.body.includes('文字を濃く'), '△ に直し方(文字を濃く)が無い: ' + mid.body);

  // 近似（r<3）→ ✕ / ng / hint 背景を明るく
  const loHex = grayFor(2.0);
  const lo = badgeParts(contrastBadge('本文×背景', loHex, '#ffffff'));
  const loR = contrastRatio(loHex, '#ffffff');
  assert(loR < 3, '作為色が r<3 帯に無い: r=' + loR);
  assert(lo.cls === 'ng', '近似色で cls が ng でない: ' + lo.cls);
  assert(lo.body.includes('読みにくい ✕'), 'body に 読みにくい✕ が無い: ' + lo.body);
  assert(lo.body.includes('背景を明るく'), '✕ に直し方(背景を明るく)が無い: ' + lo.body);

  // どのケースでも class に aa（単独）を出さない
  [hi, mid, lo].forEach(p => assert(p.cls !== 'aa', 'cls が aa になっている'));
});

// ===== D2: 判定ロジック不変 =====
check('D2 判定ロジック不変: contrastRatio既知値・境界でWCAG等級が閾値通りに切替', () => {
  const bw = contrastRatio('#000000', '#ffffff');
  assert(Math.abs(bw - 21) < 0.05, '黒×白が21近傍でない: ' + bw);
  assert(Math.abs(contrastRatio('#123456', '#123456') - 1) < 1e-9, '同色が1でない');
  // 各帯の代表色で title の WCAG 等級が閾値通りか
  const gradeOf = (fg, bg) => (/WCAG (AAA|AA|大文字のみ|✕)/.exec(badgeParts(contrastBadge('x', fg, bg)).title) || [])[1];
  assert(gradeOf('#000000', '#ffffff') === 'AAA', 'r≧7 が AAA でない');
  const aa = grayFor(5.5);   // 4.5≦r<7
  assert(contrastRatio(aa, '#ffffff') >= 4.5 && contrastRatio(aa, '#ffffff') < 7, 'AA帯の作為色が外れ');
  assert(gradeOf(aa, '#ffffff') === 'AA', '4.5≦r<7 が AA でない');
  const lg = grayFor(3.7);   // 3≦r<4.5
  assert(gradeOf(lg, '#ffffff') === '大文字のみ', '3≦r<4.5 が 大文字のみ でない');
  const ng = grayFor(2.0);   // r<3
  assert(gradeOf(ng, '#ffffff') === '✕', 'r<3 が ✕ でない');
});

// ===== D3: hexListOf 形式 =====
check('D3 hexListOf: {名前} #hex の4行・ROLE_NAMES順・単色HEXのみ・metallic案でも同一形式', () => {
  const cases = [
    { main: [210, .6, .5], sub: [180, .4, .7], accent: [30, .8, .55], bg: [45, .1, .97] },
    { main: [46, .60, .54], sub: [222, .18, .88], accent: [222, .48, .24], bg: [45, .10, .97], metal: true },
  ];
  const names = ['メイン', 'サブ', 'アクセント', '背景'];
  for (const p of cases) {
    const out = hexListOf(p);
    const lines = out.split('\\n');
    assert(lines.length === 4, '4行でない: ' + JSON.stringify(out));
    lines.forEach((ln, i) => {
      const m = /^(\\S+) (#[0-9a-f]{6})$/.exec(ln);
      assert(m, '「名前 #hex」形式でない: ' + ln);
      assert(m[1] === names[i], 'ROLE_NAMES順でない: ' + ln + ' 期待=' + names[i]);
    });
    assert(!/gradient|hsl\\(/i.test(out), '単色HEX以外が混入: ' + out);
    assert((out.match(/#[0-9a-f]{6}/g) || []).length === 4, 'HEXが4件でない');
  }
  // makePatterns 由来の実 metallic 案（metal:true）でも同一形式
  resetState();
  setRadio('colorfam', 'gold');
  makePatterns(computeBase(), 42).forEach((p, i) => {
    const out = hexListOf(p);
    assert(out.split('\\n').length === 4 && !/gradient|hsl\\(/i.test(out),
      'metallic案' + i + 'のHEX一覧が形式外: ' + out);
  });
});

// ===== D4: cssVarsOf 不変（退行なし） =====
check('D4 cssVarsOf 不変: :root＋4変数・HEX単色（KLK-004 と同一形式）', () => {
  const re = new RegExp('^:root \\\\{\\\\n' +
    '  --color-main: #[0-9a-f]{6};\\\\n' +
    '  --color-sub: #[0-9a-f]{6};\\\\n' +
    '  --color-accent: #[0-9a-f]{6};\\\\n' +
    '  --color-bg: #[0-9a-f]{6};\\\\n\\\\}$');
  const p = { main: [46, .60, .54], sub: [222, .18, .88], accent: [222, .48, .24], bg: [45, .10, .97] };
  const out = cssVarsOf(p);
  assert(re.test(out), '形式不一致: ' + JSON.stringify(out));
  assert(!/gradient|hsl\\(/i.test(out), '単色HEX以外が混入: ' + out);
  assert((out.match(/#[0-9a-f]{6}/g) || []).length === 4, 'HEXが4件でない');
});

// ===== D5: copyTextOf 呼び分け＋都度参照 =====
check('D5 copyTextOf: cssvars/hexlist で呼び分け・切替後の p 書き換えで最新値を都度参照', () => {
  const p = { main: [210, .6, .5], sub: [180, .4, .7], accent: [30, .8, .55], bg: [45, .1, .97] };
  copyFormat = 'cssvars';
  assert(copyTextOf(p) === cssVarsOf(p), 'cssvars で cssVarsOf と一致しない');
  copyFormat = 'hexlist';
  assert(copyTextOf(p) === hexListOf(p), 'hexlist で hexListOf と一致しない');
  // 切替後に p を書き換えて呼ぶと最新 p が反映される（都度参照）
  const before = copyTextOf(p);
  p.main = [0, 0, 0]; // 微調整相当
  const after = copyTextOf(p);
  assert(before !== after, 'p 書き換えが反映されていない（都度参照でない）');
  assert(after === hexListOf(p), '書き換え後も hexListOf と一致すべき');
  copyFormat = 'cssvars'; // 後続に影響しないよう既定へ戻す
});

// ===== D6: 例外安全 =====
check('D6 例外安全: 極端色でも contrastBadge/hexListOf/copyTextOf が例外を投げない', () => {
  const extremes = [
    ['#000000', '#000000'], ['#ffffff', '#ffffff'], ['#000000', '#ffffff'],
    ['#808080', '#808080'], ['#ff0000', '#00ff00'],
  ];
  extremes.forEach(([a, b]) => { contrastBadge('x', a, b); });
  const ps = [
    { main: [0, 0, 0], sub: [0, 0, 0], accent: [0, 0, 0], bg: [0, 0, 0] },
    { main: [359.9, 1, 1], sub: [0, 0, 1], accent: [180, 1, 0], bg: [45, 0, .5] },
  ];
  ps.forEach(p => { hexListOf(p); copyFormat = 'hexlist'; copyTextOf(p); copyFormat = 'cssvars'; copyTextOf(p); });
});

return results;
`;

// ---- 実行 ---------------------------------------------------------------
let results;
try {
  results = new Function(prelude + '\n' + slice + '\n' + testBody)();
} catch (e) {
  console.error('[HARNESS ERROR] スライス実行に失敗:', e && e.stack || e);
  process.exit(2);
}

console.log('='.repeat(78));
console.log('KLK-005 dynamic smoke checks (Node / palette/index.html から関数抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log(`[${st}] ${name}`);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(`${results.length} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
