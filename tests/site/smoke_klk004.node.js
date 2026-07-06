#!/usr/bin/env node
/*
 * KLK-004 動的スモークテスト（tester所有・Node.js標準のみ・ブラウザ不要）
 *
 * palette/index.html の <script> から純粋ロジック部
 * （const KEYWORDS 〜 function render() の直前）を切り出し、
 * 最小のフェイクDOM上で実行して動的挙動を機械検証する。
 * check_klk004.py（静的S1-S12）を補完する位置づけ:
 *
 *   D1 clampMetalBand: 全6変種 × 極端入力（S=0/1・L=0/1・色相±180°）で帯内に収まる
 *   D2 生成パイプライン: metallic 6変種 × 極端スライダー/ダーク/sameHue でも main が帯内（M1の機械検証）
 *   D3 ジャンルradio空値: value=""・未知値・不正形式でも computeBase/makePatterns が例外を投げない
 *   D4 cssVarsOf: :root + 4変数・HEX単色のみ（グラデ混入なし）
 *   D5 URL往復: syncURL → restoreFromURL で入力状態・seed・生成3案が一致する
 *   D6 URL不正値: 不正/欠損パラメータで例外を投げず fail-safe に復元する
 *
 * 実行: node tests/site/smoke_klk004.node.js
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

// ---- フェイクDOM＋テスト本体（スライスと同一スコープで実行する） --------
const prelude = `
// ===== フェイクDOM（computeBase/makePatterns/syncURL/restoreFromURL が使う分のみ）=====
var __ids = {};        // getElementById レジストリ
var __inputs = [];     // radio/checkbox（name/value/checked/type）
var __kwInputs = [];   // #keywords 配下のみ
var __lastURL = null;  // history.replaceState の記録

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
// フェイクDOMのセレクタ照合は生文字列一致のため escape は恒等でよい
var CSS = { escape: (s) => String(s) };
// restoreFromURL が呼ぶ後続処理（本テストでは状態比較を自前で行うため no-op）
function syncBaseUI() {} function syncAccentUI() {} function syncBgUI() {}
function syncMetallicUI() {} function render() {}
`;

const testBody = `
// ===== フィクスチャ構築（buildColors/buildKeywords 相当の初期状態を再現）=====
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
  seed = Math.floor(mulberry32(1234)() * 1e9) || 1; // index.html の初期値と同じ式
}
function setRadio(name, value) {
  const el = __inputs.find(i => i.name === name && i.value === value);
  if (!el) throw new Error('no such radio: ' + name + '=' + value);
  el.checked = true;
}
function setKw(value, on) {
  const el = __kwInputs.find(i => i.value === value);
  if (!el) throw new Error('no such keyword: ' + value);
  el.checked = on;
}
function captureState() {
  const val = (name) => (__inputs.find(i => i.name === name && i.checked) || {}).value ?? null;
  return JSON.stringify({
    colorfam: val('colorfam'), mvGold: val('mv-gold'), mvSilver: val('mv-silver'),
    tone: val('tone'), dispmode: val('dispmode'),
    kw: __kwInputs.filter(i => i.checked && i.value).map(i => i.value).sort(),
    sliders: Object.fromEntries(URL_SLIDERS.map(id => [id, +__ids[id].value])),
    useBase: __ids.useBase.checked, basePick: __ids.basePick.value, baseHex: __ids.baseHex.value,
    useAccent: __ids.useAccent.checked, accentPick: __ids.accentPick.value,
    useBg: __ids.useBg.checked, bgPick: __ids.bgPick.value,
    sameHue: __ids.sameHue.checked, cvd: __ids.cvdCheck.checked, seed,
  });
}

// ===== ミニテストランナー =====
const results = [];
function check(name, fn) {
  try { fn(); results.push(['PASS', name, '']); }
  catch (e) { results.push(['FAIL', name, String(e && e.message || e)]); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }
const hueDist = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
const EPS = 1e-9;
function assertInBand(col, variant, isDark, ctx) {
  const b = variant.band, lb = isDark ? b.lDark : b.l;
  assert(hueDist(col[0], variant.h) <= b.hTol + EPS,
    ctx + ': H=' + col[0] + ' が ' + variant.h + '±' + b.hTol + ' 外');
  assert(col[1] >= b.s[0] - EPS && col[1] <= b.s[1] + EPS,
    ctx + ': S=' + col[1] + ' が帯[' + b.s + ']外');
  assert(col[2] >= lb[0] - EPS && col[2] <= lb[1] + EPS,
    ctx + ': L=' + col[2] + ' が帯[' + lb + ']外(isDark=' + isDark + ')');
}
const eachVariant = (fn) => Object.keys(METALLICS).forEach(famKey =>
  METALLICS[famKey].variants.forEach(v => fn(famKey, v)));

// ===== D1: clampMetalBand 極端入力 =====
check('D1 clampMetalBand: 全6変種×極端入力（S=0/1, L=0/1, 色相±180°）で帯内', () => {
  eachVariant((famKey, v) => {
    const extremes = [
      [v.h + 180, 0, 0], [v.h - 180, 1, 1], [v.h + 180, 1, 0], [v.h - 180, 0, 1],
      [0, 0.5, 0.5], [359.9, 1, 1], [v.h, 0, 1], [v.h, 1, 0],
      [v.h + 179.5, 0.5, 0.5], [-(360 - v.h), 0, 0],
    ];
    for (const isDark of [false, true]) {
      for (const col of extremes) {
        assertInBand(clampMetalBand(col, v, isDark), v, isDark,
          famKey + '/' + v.key + ' in=[' + col + ']');
      }
    }
  });
});

// ===== D2: 生成パイプライン全体で main が帯内（M1の機械検証） =====
check('D2 metallic 6変種×極端スライダー/ダーク/sameHue で3案の main が帯内・metal=true', () => {
  const sliderCases = [
    {}, { vivid: 100, light: 100 }, { vivid: -100, light: -100 },
    { muted: 100, contrast: 100 }, { formal: -100, gender: 100, warm: -100 },
    { age: -100, season: -100 }, { age: 100, season: 100, contrast: -100 },
  ];
  eachVariant((famKey, v) => {
    for (const disp of ['auto', 'dark', 'light']) {
      for (const sc of sliderCases) {
        for (const same of [false, true]) {
          resetState();
          setRadio('colorfam', famKey);
          setRadio('mv-' + famKey, v.key);
          setRadio('dispmode', disp);
          Object.entries(sc).forEach(([id, val]) => { __ids[id].value = String(val); });
          __ids.sameHue.checked = same;
          seed = 987654321;
          const b = computeBase();
          assert(b.metallic && b.metallic.variant.key === v.key, 'metallic変種が拾えない');
          const pats = makePatterns(b, seed);
          assert(pats.length === 3, '3案でない: ' + pats.length);
          const ctx = famKey + '/' + v.key + ' disp=' + disp + ' sameHue=' + same +
            ' sliders=' + JSON.stringify(sc);
          pats.forEach((p, i) => {
            assert(p.metal === true, ctx + ' 案' + i + ': metal フラグなし');
            assertInBand(p.main, v, p.bg[2] < 0.45, ctx + ' 案' + i);
          });
        }
      }
    }
  });
});

// ===== D3: ジャンルradio空値・不正値ガード =====
check('D3a ジャンル「指定なし」(value="") checked で生成が例外を投げない', () => {
  resetState(); // kwgenre value="" が checked の初期状態
  const b = computeBase();
  assert(!b.hasInput, '空値radioだけで hasInput が真になっている'); // hasInput は||連鎖のため truthy 判定

  makePatterns(b, seed); // 例外を投げないこと
});
check('D3b ジャンル選択＋他キーワード併用で生成できる', () => {
  resetState();
  const genreKey = GENRE + '/' + Object.keys(KEYWORDS[GENRE])[0];
  const otherCat = Object.keys(KEYWORDS).find(c => c !== GENRE);
  setKw(genreKey, true);
  setKw(otherCat + '/' + Object.keys(KEYWORDS[otherCat])[0], true);
  const b = computeBase();
  assert(b.hasInput, 'hasInput が偽');
  const pats = makePatterns(b, seed);
  assert(pats.length === 3 && pats.every(p => ['main','sub','accent','bg'].every(k => p[k].length === 3)), '3案×4色でない');
});
check('D3c 未知カテゴリ/未知キー/区切りなしの不正値でも例外を投げず無視される', () => {
  resetState();
  __kwInputs.push(__mkInput('kwgenre', GENRE + '/存在しないキー', 'radio', true));
  __kwInputs.push(__mkInput('kw', 'nocategory/x', 'checkbox', true));
  __kwInputs.push(__mkInput('kw', 'separatorless', 'checkbox', true));
  __kwInputs.push(__mkInput('kw', '/', 'checkbox', true));
  const b = computeBase();
  assert(!b.hasInput, '不正値が hasInput に数えられている'); // hasInput は||連鎖のため truthy 判定

  makePatterns(b, seed); // 例外を投げないこと
});

// ===== D4: cssVarsOf 出力形式 =====
check('D4 cssVarsOf: :root＋4変数・HEX単色のみ（グラデ・hsl()混入なし）', () => {
  const cases = [
    { main: [46, .60, .54], sub: [222, .18, .88], accent: [222, .48, .24], bg: [45, .10, .97] },
    { main: [0, 0, 0], sub: [359.9, 1, 1], accent: [210, .07, .72], bg: [220, .06, .30] },
  ];
  const re = new RegExp('^:root \\\\{\\\\n' +
    '  --color-main: #[0-9a-f]{6};\\\\n' +
    '  --color-sub: #[0-9a-f]{6};\\\\n' +
    '  --color-accent: #[0-9a-f]{6};\\\\n' +
    '  --color-bg: #[0-9a-f]{6};\\\\n\\\\}$');
  for (const p of cases) {
    const out = cssVarsOf(p);
    assert(re.test(out), '形式不一致: ' + JSON.stringify(out));
    assert(!/gradient|hsl\\(/i.test(out), '単色HEX以外が混入: ' + out);
    assert(out.match(/#[0-9a-f]{6}/g).length === 4, 'HEXが4件でない');
  }
  // metallic 案（metal:true 付き）でも出力は単色HEXのままであること
  resetState();
  setRadio('colorfam', 'gold');
  const pats = makePatterns(computeBase(), 42);
  pats.forEach((p, i) => assert(re.test(cssVarsOf(p)), 'metallic案' + i + 'のCSS変数が形式外'));
});

// ===== D5: URL往復（serialize → restore で状態一致・3案再現） =====
check('D5 syncURL→restoreFromURL の往復で入力状態・seed・生成3案が一致', () => {
  resetState();
  setRadio('colorfam', 'gold');
  setRadio('mv-gold', 'pink');
  setRadio('tone', TONES[6].key); // deep
  setRadio('dispmode', 'dark');
  const genreKey = GENRE + '/' + Object.keys(KEYWORDS[GENRE])[0];
  const otherCat = Object.keys(KEYWORDS).find(c => c !== GENRE);
  const otherKey = otherCat + '/' + Object.keys(KEYWORDS[otherCat])[0];
  setKw(genreKey, true); setKw(otherKey, true);
  __ids.warm.value = '-40'; __ids.vivid.value = '25'; __ids.contrast.value = '60';
  __ids.useBase.checked = true; __ids.basePick.value = '#a1b2c3'; __ids.baseHex.value = '#a1b2c3';
  __ids.sameHue.checked = true; __ids.cvdCheck.checked = true;
  seed = 424242;
  syncURL(true);
  assert(__lastURL && __lastURL.includes('?'), 'syncURL がURLを生成していない');
  const query = __lastURL.slice(__lastURL.indexOf('?'));
  const stateA = captureState();
  const patsA = JSON.stringify(makePatterns(computeBase(), seed));

  resetState();
  location.search = query;
  const restored = restoreFromURL();
  assert(restored === true, 'restoreFromURL が false を返した');
  assert(captureState() === stateA,
    '状態不一致:\\nA=' + stateA + '\\nB=' + captureState());
  const patsB = JSON.stringify(makePatterns(computeBase(), seed));
  assert(patsB === patsA, '生成3案が一致しない');
});
check('D5b 初期状態（hasInput=false）では syncURL がパラメータを消す', () => {
  resetState();
  syncURL(false);
  assert(__lastURL === location.pathname, 'クエリが残っている: ' + __lastURL);
});

// ===== D6: URL不正値・欠損値の fail-safe =====
check('D6a 不正値だらけのURLでも restoreFromURL が例外を投げず生成できる', () => {
  resetState();
  const defSeed = seed;
  location.search = '?v=1&c=zzz&mv=xx&t=nope&k=foo,bar/baz,' +
    encodeURIComponent(GENRE + '/偽物') +
    '&warm=abc&vivid=9999&light=-9999&base=nothex&accent=1234&bg=gggggg&sh=2&dm=purple&cvd=yes&seed=-7';
  const r = restoreFromURL();
  assert(r === true, '既知キーがあるのに false');
  assert(seed === defSeed, '不正seedが取り込まれた: ' + seed);
  assert(+__ids.vivid.value === 100 && +__ids.light.value === -100, 'スライダーが[-100,100]にclampされていない');
  assert(+__ids.warm.value === 0, 'NaNスライダーが無視されていない');
  assert(__ids.useBase.checked === false && __ids.useAccent.checked === false && __ids.useBg.checked === false,
    '不正hexで use* がONになった');
  makePatterns(computeBase(), seed); // 例外を投げないこと
});
check('D6b 未知キーのみのURLは false（従来どおり初期表示）', () => {
  resetState();
  location.search = '?foo=1&bar=2';
  assert(restoreFromURL() === false, '未知キーのみで true を返した');
});
check('D6c 欠損（seedのみ等の部分URL）でも例外なく復元する', () => {
  resetState();
  location.search = '?seed=555';
  assert(restoreFromURL() === true && seed === 555, 'seed単独の復元に失敗');
  resetState();
  location.search = '?c=silver'; // mv 欠損 → 既定変種(cool)で生成できること
  assert(restoreFromURL() === true, 'c単独の復元に失敗');
  const b = computeBase();
  assert(b.metallic && b.metallic.variant.key === 'cool', 'mv欠損時に既定変種へフォールバックしない');
  makePatterns(b, seed);
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
console.log('KLK-004 dynamic smoke checks (Node / palette/index.html から関数抽出)');
console.log('='.repeat(78));
let failed = 0;
for (const [st, name, msg] of results) {
  console.log(`[${st}] ${name}`);
  if (st === 'FAIL') { failed++; console.log('        ' + msg); }
}
console.log('-'.repeat(78));
console.log(`${results.length} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
