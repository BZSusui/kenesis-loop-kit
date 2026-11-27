#!/usr/bin/env node
/*
 * KLK-140 配色ジェネレーターに4語を新設 — 動的検査（Node 標準のみ・判定データは使わない）
 *
 *   K1 辞書: 4語が各カテゴリの末尾にあり、値が設計 §4.2 どおり。語の総数 43。最初の語は「きれい」のまま
 *   K2 差し色の蛍光なし: かっこいい・スタイリッシュ × シード（初期・1〜32）× 表示モード（auto/light/dark）
 *      × コントラスト（-100/0/+100）で、全案の accent が物差しの蛍光でない
 *   K3 差し色の性質: 上のうちスライダー0・表示モード auto/light で accent の OKLCH C>=0.10・色相 220〜285°
 *   K4 型B: エレガント × シード（初期・1〜32）で3案目が「ベージュ＋濃い一点」・物差しで型B ○、
 *      1・2案目は型A。4役割とも蛍光でない
 *   K5 適用しない条件（設計 §4.4）: アクセント固定・同系色・金属・表示モード dark・背景固定
 *   K6 両方のヒント: [エレガント, かっこいい] で3案目が型B、1・2案目の accent が K3 を満たす
 *   K7 ダーク×金属（改善ループ1）: ダーク × 金属6変種 × シード（初期・1〜32）・表示モード auto で、物差しが × でない・
 *      背景 ○・背景が純黒でなくチャコール寄り（OKLCH C<0.03）・4役割とも蛍光でない・メインと背景のコントラスト比 4.5 以上
 *   K8 高級×金属（改善ループ1）: 高級 × 同じ6変種 × 同じシードで、物差し（高級感）が × でない・背景 ○
 *   K9 利用者の指定を優先（改善ループ1）: ダーク × ゴールド黄み・シルバー青みで、表示モード light → 明るい背景／
 *      背景固定 → 指定色／表示モード dark → 既存の式のまま（ゴールド黄みで背景の HSL 彩度が 0.10 を超える案がある）
 *   K10 対象外（改善ループ1）: 言葉なし・明るい語（ポップ）× 金属（表示モード auto）→ 明るい背景のまま
 *   K11 割り振りの形（改善ループ2）: 11語＋ダーク単独 × シード（初期・1〜32）× {なし・ゴールド黄み・シルバー青み・ガンメタ}・
 *      自動で、背景の並び（OKLCH L<0.40＝D、>=0.80＝L）が 黒2・明1＝DDL／黒1・明2＝DLL／ダーク・ガンメタ・
 *      金属以外の神秘的・力強い・クール・金・銀の高級＝DDD
 *   K12 明るい案は表示モード「ライト」と同じ（改善ループ2）: K11 の割り振られた入力で、明るい案が同じ入力の
 *      表示モード light の同じ番号の案と完全一致（高級は accent を除く）
 *   K13 高級の例外（改善ループ2）: 高級 × シード × カラー系統（なし＋金属以外14）で、物差し scoreSet('高級感') が3案とも
 *      × でなく、3案目は背景が例外 ○・accent が金か銀のマス・メインが OKLCH L<=0.52 かつ C<0.10。4役割とも蛍光でない
 *   K14 複数の言葉（改善ループ2）: 区分の多数決・ダークや割り振らない語が混ざれば割り振らない・系統の範囲
 *   K15 適用しない条件（改善ループ2）: 表示モード明示・背景固定・基準カラーでは割り振らない。アクセント固定・同系色では割り振る
 *   K16 明るい案の質（改善ループ2）: K11 の明るい案すべてで蛍光なし・純黒なし・本文（textOn と同じ式）対背景 4.5 以上
 *
 * 実行: node tests/site/smoke_klk140.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常
 * 設計: docs/designs/KLK-140.md §4.9・§4.12.7・§4.13.10
 */
'use strict';
const R = require('./klk138_ruler.js');
const Gen = require('./klk138_generator.js');

const results = [];
function check(name, cond, detail) {
  results.push({ name, ok: !!cond, detail: detail || '' });
}

let ruler, gen;
try {
  ruler = R.loadRuler();
  gen = Gen.load();
} catch (e) {
  console.error('[HARNESS ERROR] ' + e.message);
  process.exit(2);
}

const SEEDS = [gen.initialSeed].concat(Array.from({ length: 32 }, (_, i) => i + 1));
const TYPE_B = 'ベージュ＋濃い一点';
const ROLES = ['bg', 'main', 'sub', 'accent'];
const lchOf = hex => R.rgbToOklch(R.hexToRgb(hex));
const hslOf = hex => R.rgbToHsl(R.hexToRgb(hex));
const hueDiff = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
function accentProps(hex) {
  const [, C, h] = lchOf(hex);
  return { C, h, ok: C >= 0.10 && h >= 220 && h <= 285 };
}

function run(fn) {
  try { fn(); } catch (e) {
    if (e instanceof Gen.HarnessError) { console.error('[HARNESS ERROR] ' + e.message); process.exit(2); }
    throw e;
  }
}

// ---- K1 辞書 ----------------------------------------------------------------
run(() => {
  const kw = gen.keywords();
  const cats = Object.keys(kw);
  const tail = (cat, n) => Object.keys(kw[cat] || {}).slice(-n);
  check('K1 印象の末尾2語がエレガント・かっこいい', tail('印象', 2).join(',') === 'エレガント,かっこいい', tail('印象', 2).join(','));
  check('K1 スタイルの末尾2語がスタイリッシュ・ダーク', tail('スタイル', 2).join(',') === 'スタイリッシュ,ダーク', tail('スタイル', 2).join(','));
  const want = {
    'エレガント': ['印象', { h: 320, s: .30, l: .66, warm: 0, gender: .7, formal: .6, hint: 'elegantBeige' }],
    'かっこいい': ['印象', { h: 220, s: .08, l: .28, warm: -.4, gender: -.5, formal: .3, hint: 'coolAccent', lightBgs: 1 }],
    'スタイリッシュ': ['スタイル', { h: 210, s: .06, l: .35, warm: -.3, gender: -.2, formal: .6, hint: 'coolAccent', lightBgs: 2 }],
    'ダーク': ['スタイル', { h: 230, s: .30, l: .20, warm: -.2, gender: -.3, formal: .4 }],
  };
  for (const w of Object.keys(want)) {
    const [cat, v] = want[w];
    const got = (kw[cat] || {})[w];
    check(`K1 ${w} の値が設計 §4.2 どおり`, JSON.stringify(got) === JSON.stringify(v), JSON.stringify(got));
  }
  const total = cats.reduce((a, c) => a + Object.keys(kw[c]).length, 0);
  check('K1 語の総数 43（39＋4）', total === 43, String(total));
  const firstCat = cats.find(c => c !== 'ジャンル（業種）');
  check('K1 ジャンル以外の最初のカテゴリの最初の語が「きれい」', Object.keys(kw[firstCat])[0] === 'きれい', Object.keys(kw[firstCat])[0]);
});

// ---- K2・K3 差し色 -----------------------------------------------------------
run(() => {
  for (const word of ['かっこいい', 'スタイリッシュ']) {
    const neon = [], weak = [];
    let n = 0, nProp = 0;
    for (const seed of SEEDS) for (const disp of ['auto', 'light', 'dark']) for (const contrast of [-100, 0, 100]) {
      const pals = gen.generate({ labels: [word], seed, disp, sliders: { contrast } });
      for (const p of pals) {
        n++;
        if (R.isNeon(p.accent, ruler)) neon.push(`seed${seed}/${disp}/${contrast}`);
        if (contrast === 0 && disp !== 'dark') {
          nProp++;
          const a = accentProps(p.accent);
          if (!a.ok) weak.push(`seed${seed}/${disp}: C${a.C.toFixed(3)} h${a.h.toFixed(0)}`);
        }
      }
    }
    check(`K2 ${word} の差し色が蛍光でない（${n}案）`, n === SEEDS.length * 27 && neon.length === 0, neon.slice(0, 5).join(' '));
    check(`K3 ${word} の差し色が C>=0.10・色相 220〜285°（スライダー0・auto/light ${nProp}案）`,
      nProp === SEEDS.length * 6 && weak.length === 0, weak.slice(0, 5).join(' '));
  }
});

// ---- K4 型B ------------------------------------------------------------------
run(() => {
  const def = ruler.words['エレガント'];
  const bad = [];
  for (const seed of SEEDS) {
    const pals = gen.generate({ labels: ['エレガント'], seed });
    const res = pals.map(p => R.scoreElegant(p, def, ruler));
    if (pals[2].scheme !== TYPE_B) bad.push(`seed${seed}: 3案目 ${pals[2].scheme}`);
    if (res[2].type !== 'B' || res[2].verdict !== 'ok') bad.push(`seed${seed}: 3案目 type${res[2].type} ${res[2].verdict}`);
    for (const i of [0, 1]) if (res[i].type !== 'A') bad.push(`seed${seed}: ${i + 1}案目 type${res[i].type}`);
    for (const p of pals) for (const r of ROLES) if (R.isNeon(p[r], ruler)) bad.push(`seed${seed}: neon ${r}`);
  }
  check(`K4 エレガントの3案目が型B ○・1・2案目は型A・蛍光なし（${SEEDS.length}シード）`, bad.length === 0, bad.slice(0, 5).join(' '));
});

// ---- K5 適用しない条件 ---------------------------------------------------------
run(() => {
  const labels = ['エレガント', 'かっこいい'];
  const ACC = '#e8590c';
  {
    const bad = [];
    for (const seed of SEEDS) {
      const pals = gen.generate({ labels, seed, accentHex: ACC });
      pals.forEach((p, i) => { if (p.accent.toLowerCase() !== ACC) bad.push(`seed${seed}/${i + 1}: ${p.accent}`); });
      if (pals.some(p => p.scheme === TYPE_B)) bad.push(`seed${seed}: 型B`);
    }
    check('K5 アクセント固定: 3案の accent が指定色・型B なし', bad.length === 0, bad.slice(0, 5).join(' '));
  }
  {
    const bad = [];
    for (const seed of SEEDS) {
      const pals = gen.generate({ labels, seed, sameHue: true });
      if (pals.some(p => p.scheme === TYPE_B)) bad.push(`seed${seed}: 型B`);
      pals.forEach((p, i) => {
        const d = hueDiff(hslOf(p.accent)[0], hslOf(p.main)[0]);
        if (d > 35 + 2) bad.push(`seed${seed}/${i + 1}: 色相差 ${d.toFixed(1)}`);   // hex 丸めの余裕 2°
      });
    }
    check('K5 同系色: 型B なし・accent の色相がメインから ±35° 以内', bad.length === 0, bad.slice(0, 5).join(' '));
  }
  {
    const bad = [];
    for (const seed of SEEDS) {
      const pals = gen.generate({ labels, seed, colorfam: 'gold' });
      pals.forEach((p, i) => { if (!p.scheme.includes('×')) bad.push(`seed${seed}/${i + 1}: ${p.scheme}`); });
    }
    check('K5 金属（ゴールド）: 3案ともパートナー表（名前に「×」）', bad.length === 0, bad.slice(0, 5).join(' '));
  }
  for (const [name, opt] of [['表示モード dark', { disp: 'dark' }], ['背景固定', { bgHex: '#faf8f3' }]]) {
    const bad = [];
    for (const seed of SEEDS) {
      const pals = gen.generate(Object.assign({ labels: ['エレガント'], seed }, opt));
      if (pals.some(p => p.scheme === TYPE_B)) bad.push(`seed${seed}`);
    }
    check(`K5 ${name}: エレガントに型B なし`, bad.length === 0, bad.slice(0, 5).join(' '));
  }
});

// ---- K6 両方のヒント -----------------------------------------------------------
run(() => {
  const def = ruler.words['エレガント'];
  const bad = [];
  for (const seed of SEEDS) {
    const pals = gen.generate({ labels: ['エレガント', 'かっこいい'], seed });
    const r3 = R.scoreElegant(pals[2], def, ruler);
    if (pals[2].scheme !== TYPE_B || r3.type !== 'B') bad.push(`seed${seed}: 3案目 ${pals[2].scheme} type${r3.type}`);
    for (const i of [0, 1]) {
      const a = accentProps(pals[i].accent);
      if (!a.ok) bad.push(`seed${seed}/${i + 1}: C${a.C.toFixed(3)} h${a.h.toFixed(0)}`);
    }
  }
  check(`K6 エレガント＋かっこいい: 3案目が型B・1・2案目に寒色の差し色（${SEEDS.length}シード）`, bad.length === 0, bad.slice(0, 5).join(' '));
});

// ---- K7〜K10 金属でも暗い言葉なら暗い背景（改善ループ1・設計 §4.12.7）----------------
const METAL6 = [['gold', 'yellow'], ['gold', 'pink'], ['gold', 'green'],
                ['silver', 'cool'], ['silver', 'warm'], ['silver', 'gunmetal']];
function relLum(hex) {
  const lin = c => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));   // hexToRgb は 0〜1
  const [r, g, b] = R.hexToRgb(hex);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrastOf(a, b) {
  const x = relLum(a), y = relLum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
function metalDarkCheck(dictLabel, rulerWord, full) {
  const bad = [];
  let n = 0, minCr = Infinity;
  for (const [colorfam, mv] of METAL6) for (const seed of SEEDS) {
    const pals = gen.generate({ labels: [dictLabel], seed, colorfam, mv });
    pals.forEach((p, i) => {
      n++;
      const tag = `${colorfam}/${mv}/seed${seed}/${i + 1}`;
      const r = R.scorePalette(rulerWord, p, ruler);
      if (r.verdict === 'ng') bad.push(`${tag}: ×`);
      if (r.roles.bg.status !== 'ok') bad.push(`${tag}: bg ${r.roles.bg.status}`);
      if (!full) return;
      const [L, C] = lchOf(p.bg);
      if (!(L >= 0.20 || C >= 0.02)) bad.push(`${tag}: 純黒`);
      if (C >= 0.03) bad.push(`${tag}: bg C${C.toFixed(3)}`);
      for (const role of ROLES) if (R.isNeon(p[role], ruler)) bad.push(`${tag}: neon ${role}`);
      const cr = contrastOf(p.main, p.bg);
      minCr = Math.min(minCr, cr);
      if (cr < 4.5) bad.push(`${tag}: main/bg ${cr.toFixed(2)}`);
    });
  }
  return { bad, n, minCr };
}
run(() => {
  const r = metalDarkCheck('ダーク', 'ダーク', true);
  check(`K7 ダーク×金属6変種: × なし・背景 ○・チャコール寄り・蛍光なし・コントラスト4.5以上（${r.n}案・最小 ${r.minCr.toFixed(2)}）`,
    r.n === METAL6.length * SEEDS.length * 3 && r.bad.length === 0, r.bad.slice(0, 5).join(' '));
});
run(() => {
  const r = metalDarkCheck('高級', '高級感', false);
  check(`K8 高級×金属6変種: × なし・背景 ○（${r.n}案）`,
    r.n === METAL6.length * SEEDS.length * 3 && r.bad.length === 0, r.bad.slice(0, 5).join(' '));
});
run(() => {
  const BG = '#faf8f3';
  const bad = { light: [], bgHex: [], dark: [] };
  let darkSatOver = false;
  for (const [colorfam, mv] of [['gold', 'yellow'], ['silver', 'cool']]) for (const seed of SEEDS) {
    const base = { labels: ['ダーク'], seed, colorfam, mv };
    gen.generate(Object.assign({ disp: 'light' }, base)).forEach((p, i) => {
      if (lchOf(p.bg)[0] < 0.80) bad.light.push(`${colorfam}/${mv}/seed${seed}/${i + 1}`);
    });
    gen.generate(Object.assign({ bgHex: BG }, base)).forEach((p, i) => {
      if (p.bg.toLowerCase() !== BG) bad.bgHex.push(`${colorfam}/${mv}/seed${seed}/${i + 1}: ${p.bg}`);
    });
    gen.generate(Object.assign({ disp: 'dark' }, base)).forEach((p, i) => {
      if (lchOf(p.bg)[0] > 0.40) bad.dark.push(`${colorfam}/${mv}/seed${seed}/${i + 1}`);
      if (colorfam === 'gold' && hslOf(p.bg)[1] > 0.10) darkSatOver = true;
    });
  }
  check('K9 表示モード light: 3案とも背景 OKLCH L>=0.80', bad.light.length === 0, bad.light.slice(0, 5).join(' '));
  check('K9 背景固定: 3案の背景が指定色', bad.bgHex.length === 0, bad.bgHex.slice(0, 5).join(' '));
  check('K9 表示モード dark: 暗い背景で既存の式のまま（ゴールド黄みで HSL 彩度 0.10 超の案がある）',
    bad.dark.length === 0 && darkSatOver, bad.dark.slice(0, 5).join(' ') + (darkSatOver ? '' : ' 彩度0.10超の案なし'));
});
run(() => {
  const bad = [];
  for (const [labels, colorfam, mv] of [[[], 'gold', 'yellow'], [[], 'silver', 'cool'], [['ポップ'], 'gold', 'yellow']]) {
    for (const seed of SEEDS) {
      gen.generate({ labels, seed, colorfam, mv }).forEach((p, i) => {
        if (lchOf(p.bg)[0] < 0.80) bad.push(`[${labels.join(',')}]/${colorfam}/${mv}/seed${seed}/${i + 1}`);
      });
    }
  }
  check('K10 言葉なし・ポップ × 金属（auto）: 3案とも背景 OKLCH L>=0.80', bad.length === 0, bad.slice(0, 5).join(' '));
});

// ---- K11〜K16 暗い雰囲気の言葉の3案に明るい背景を混ぜる（改善ループ2・設計 §4.13.10）----------
const DDL_WORDS = ['高級', 'ラグジュアリー', 'かっこいい', '神秘的', '力強い', 'クール'];
const DLL_WORDS = ['スタイリッシュ', '知的', '和風', 'コーポレート', 'ファッション'];
const METAL_ONLY = ['神秘的', '力強い', 'クール'];
const FAMS4 = [['none', undefined, undefined], ['gold/yellow', 'gold', 'yellow'],
               ['silver/cool', 'silver', 'cool'], ['silver/gunmetal', 'silver', 'gunmetal']];
const NON_METAL14 = ['red', 'pink', 'orange', 'yellow', 'ygreen', 'green', 'teal', 'blue', 'navy', 'purple',
                     'brown', 'beige', 'mono', 'colorful'];
const shapeOf = pals => pals.map(p => { const L = lchOf(p.bg)[0]; return L < 0.40 ? 'D' : (L >= 0.80 ? 'L' : '?'); }).join('');
function expectShape(word, famName) {
  if (word === 'ダーク' || famName === 'silver/gunmetal') return 'DDD';
  const metal = famName !== 'none';
  if (METAL_ONLY.includes(word) && !metal) return 'DDD';
  if (word === '高級' && metal) return 'DDD';
  return DDL_WORDS.includes(word) ? 'DDL' : 'DLL';
}
const optOf = (colorfam, mv) => (colorfam === undefined ? {} : { colorfam, mv });
// textOn（palette/index.html）と同じ式。暗い文字色は palette から読む（ここに色コードを書かない）
const DARK_TEXT = (() => {
  const src = require('fs').readFileSync(Gen.HTML_PATH, 'utf8');
  const m = /function textOn\(hex\) \{[\s\S]*?lum > 0\.6 \? '(#[0-9a-fA-F]{6})' : '(#[0-9a-fA-F]{6})'/.exec(src);
  if (!m) { console.error('[HARNESS ERROR] textOn の式が見つからない'); process.exit(2); }
  return [m[1], m[2]];
})();
function textOnOf(hex) {
  const [r, g, b] = R.hexToRgb(hex);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 0.6 ? DARK_TEXT[0] : DARK_TEXT[1];
}
const allocated = [];   // K12・K16 用: 割り振られた入力 { word, seed, opt, pals, from }
run(() => {
  const bad = [];
  let n = 0;
  for (const word of DDL_WORDS.concat(DLL_WORDS, ['ダーク'])) for (const [famName, colorfam, mv] of FAMS4) for (const seed of SEEDS) {
    n++;
    const opt = optOf(colorfam, mv);
    const pals = gen.generate(Object.assign({ labels: [word], seed }, opt));
    const got = shapeOf(pals), want = expectShape(word, famName);
    if (got !== want) bad.push(`${word}/${famName}/seed${seed}: ${got}≠${want}`);
    if (want !== 'DDD') allocated.push({ word, seed, opt, pals, from: want.indexOf('L') });
  }
  check(`K11 割り振りの形（${n}入力）`, n === 12 * FAMS4.length * SEEDS.length && bad.length === 0, bad.slice(0, 5).join(' '));
});
run(() => {
  const bad = [];
  let nLight = 0;
  for (const a of allocated) {
    const lp = gen.generate(Object.assign({ labels: [a.word], seed: a.seed, disp: 'light' }, a.opt));
    for (let i = a.from; i < 3; i++) {
      nLight++;
      const keys = a.word === '高級' ? ['scheme', 'bg', 'main', 'sub'] : ['scheme', 'bg', 'main', 'sub', 'accent'];
      const diff = keys.filter(k => a.pals[i][k] !== lp[i][k]);
      if (diff.length) bad.push(`${a.word}/seed${a.seed}/${i + 1}: ${diff.join(',')}`);
    }
  }
  check(`K12 明るい案が表示モード light の同じ番号の案と一致（${nLight}案）`, nLight > 0 && bad.length === 0, bad.slice(0, 5).join(' '));
});
run(() => {
  const bad = [];
  let n = 0;
  const t = ruler.thresholds.lightBgException.value;
  for (const colorfam of [undefined].concat(NON_METAL14)) for (const seed of SEEDS) {
    n++;
    const pals = gen.generate(Object.assign({ labels: ['高級'], seed }, colorfam ? { colorfam } : {}));
    const res = R.scoreSet('高級感', pals, ruler, { age: 0 });
    const tag = `${colorfam || 'none'}/seed${seed}`;
    res.forEach((r, i) => { if (r.verdict === 'ng') bad.push(`${tag}/${i + 1}: ×`); });
    const r3 = res[2];
    if (!(r3.roles.bg.exception === true && r3.roles.bg.status === 'ok')) bad.push(`${tag}: 3案目の背景が例外 ○ でない`);
    if (!['n-gold', 'n-silver'].includes(r3.roles.accent.cell)) bad.push(`${tag}: accent ${r3.roles.accent.cell}`);
    const [mL, mC] = lchOf(pals[2].main);
    if (!(mL <= t.mainLMax && mC < t.mainCMax)) bad.push(`${tag}: main L${mL.toFixed(3)} C${mC.toFixed(3)}`);
    for (const p of pals) for (const role of ROLES) if (R.isNeon(p[role], ruler)) bad.push(`${tag}: neon ${role}`);
  }
  check(`K13 高級の明るい案が例外 ○（${n}入力）`, n === 15 * SEEDS.length && bad.length === 0, bad.slice(0, 5).join(' '));
});
run(() => {
  const cases = [
    [['高級', '和風'], {}, 'DDL'],
    [['知的', '和風', 'かっこいい'], {}, 'DLL'],
    [['ダーク', '高級'], {}, 'DDD'],
    [['高級', '誠実'], {}, 'DDD'],
    [['神秘的', '和風'], {}, 'DDD'],
    [['神秘的', '和風'], { colorfam: 'gold' }, 'DDL'],
    [['高級', 'コーポレート'], { colorfam: 'gold' }, 'DDD'],
    [['エレガント', '高級'], {}, 'LLL'],
  ];
  for (const [labels, opt, want] of cases) {
    const got = shapeOf(gen.generate(Object.assign({ labels, seed: 1 }, opt)));
    check(`K14 [${labels.join(',')}]${opt.colorfam ? ' × ' + opt.colorfam : ''} = ${want}`, got === want, got);
  }
});
run(() => {
  const BG = '#faf8f3';
  const ACC = '#e8590c';
  const BASE = R.hslToHex(230, 0.40, 0.18);
  const g = opt => gen.generate(Object.assign({ labels: ['和風'], seed: 1 }, opt));
  check('K15 和風 × 表示モード light = LLL', shapeOf(g({ disp: 'light' })) === 'LLL', shapeOf(g({ disp: 'light' })));
  check('K15 和風 × 表示モード dark = DDD', shapeOf(g({ disp: 'dark' })) === 'DDD', shapeOf(g({ disp: 'dark' })));
  const pb = g({ bgHex: BG });
  check('K15 和風 × 背景固定: 3案とも指定色', pb.every(p => p.bg.toLowerCase() === BG), pb.map(p => p.bg).join(','));
  check('K15 和風 × 基準カラー（暗い）: 割り振らない（DDD）', shapeOf(g({ baseHex: BASE })) === 'DDD', shapeOf(g({ baseHex: BASE })));
  const pa = g({ accentHex: ACC });
  check('K15 和風 × アクセント固定: DLL・accent が指定色', shapeOf(pa) === 'DLL' && pa.every(p => p.accent.toLowerCase() === ACC),
    shapeOf(pa) + ' ' + pa.map(p => p.accent).join(','));
  check('K15 和風 × 同系色: DLL', shapeOf(g({ sameHue: true })) === 'DLL', shapeOf(g({ sameHue: true })));
  const pk = gen.generate({ labels: ['高級'], seed: 1, accentHex: ACC });
  check('K15 高級 × アクセント固定: DDL・accent が指定色（金・銀の輝きなし）',
    shapeOf(pk) === 'DDL' && pk.every(p => p.accent.toLowerCase() === ACC), shapeOf(pk) + ' ' + pk.map(p => p.accent).join(','));
});
run(() => {
  const bad = [];
  let n = 0, minCr = Infinity;
  for (const a of allocated) for (let i = a.from; i < 3; i++) {
    n++;
    const p = a.pals[i];
    const tag = `${a.word}/seed${a.seed}/${i + 1}`;
    for (const role of ROLES) {
      if (R.isNeon(p[role], ruler)) bad.push(`${tag}: neon ${role}`);
      const [L, C] = lchOf(p[role]);
      if (L < 0.20 && C < 0.02) bad.push(`${tag}: 純黒 ${role}`);
    }
    const cr = contrastOf(textOnOf(p.bg), p.bg);
    minCr = Math.min(minCr, cr);
    if (cr < 4.5) bad.push(`${tag}: 本文/背景 ${cr.toFixed(2)}`);
  }
  check(`K16 明るい案の質: 蛍光・純黒なし・本文対背景 4.5 以上（${n}案・最小 ${n ? minCr.toFixed(2) : '-'}）`,
    n > 0 && bad.length === 0, bad.slice(0, 5).join(' '));
});

console.log('='.repeat(72));
console.log('KLK-140 配色ジェネレーターの4語 動的検査（K1-K16）');
console.log('='.repeat(72));
for (const r of results) console.log(`[${r.ok ? 'PASS' : 'FAIL'}] ${r.name}${r.ok || !r.detail ? '' : '\n       ' + r.detail}`);
const fails = results.filter(r => !r.ok).length;
console.log('-'.repeat(72));
console.log(`${results.length - fails}/${results.length} PASS`);
process.exit(fails ? 1 : 0);
