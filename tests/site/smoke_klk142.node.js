#!/usr/bin/env node
/*
 * KLK-142 アクセントカラーの傾向 — 動的検査（Node 標準のみ・判定データは使わない）
 *
 *   共通の入力: 語44（辞書43語＋語なし）× シード（初期・1〜8）× オプション18種 × 傾向14色
 *   A1  未指定時の一致: 傾向なしの出力の指紋 792 件が、v1.3 で書いたゴールデンと一致（ゴールデンが無ければ FAIL）
 *   A2  蛍光なし: 傾向ありの全案（fixed を除く）で accent が物差しの蛍光でなく、OKLCH「C>=0.20 かつ L>=0.65」でもない
 *   A3  アクセント以外は不変: 傾向ありと傾向なしで、全案の main・sub・bg が一致
 *   A4  選んだ色になる: 傾向ありの全案（fixed を除く）で accent の HSL 色相が light・dark の H のどちらかから
 *       ±(hJit＋3)° 以内（シルバーは HSL の S <= 0.10）
 *   A5  固定が勝つ: fixed で傾向あり＝傾向なし（案名を含む完全一致）
 *   A6  同系色: same で main・sub が傾向なしと一致し、accent が A4 を満たす
 *   A7  言葉の差し色を置き換える: かっこいい・スタイリッシュ・高級・エレガント（3案目は型B の名前のまま）で A4
 *   A8  金属の案名: メイン gold・silver（色味3種ずつ）× 傾向14色 × シード（初期・1〜8）で、3案の名前が「{金属}×{色名}」
 *   A9  背景とのコントラスト（cMinus・bgDark・bgLight・bgMid・fixed を除く）: 10色は 3.0 以上。
 *       イエロー・ベージュ・ゴールド・シルバーは暗い背景（相対輝度 < 0.18）で 3.0 以上、明るい背景で 1.6 以上
 *   A10 明るい案を混ぜる11語 × シード1〜32 × メイン{なし・ゴールド・シルバー}× 傾向14色・自動: A2・A9 と同じ基準
 *
 * 実行: node tests/site/smoke_klk142.node.js                 （検査）
 *       node tests/site/smoke_klk142.node.js --write-golden  （palette が v1.3 の指紋のときだけ、ゴールデンを新規に書く）
 * 終了コード: 0=全PASS（または書き出し成功）/ 1=FAILあり（または書き出し拒否）/ 2=ハーネス異常
 * 設計: docs/designs/KLK-142.md §4.7・§4.8
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const R = require('./klk138_ruler.js');
const Gen = require('./klk138_generator.js');

const ROOT = path.join(__dirname, '..', '..');
const GOLDEN_PATH = path.join(ROOT, 'tests', 'fixtures', 'klk142', 'unspecified-v1.3.json');
const BASELINE_V13 = path.join(ROOT, 'tests', 'fixtures', 'klk138', 'baseline-v1.3.json');

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

function run(fn) {
  try { fn(); } catch (e) {
    if (e instanceof Gen.HarnessError) { console.error('[HARNESS ERROR] ' + e.message); process.exit(2); }
    throw e;
  }
}

const NO_WORD = '(語なし)';
const SEEDS9 = [gen.initialSeed].concat(Array.from({ length: 8 }, (_, i) => i + 1));
const WORDS = [NO_WORD].concat(Object.values(gen.keywords()).flatMap(cat => Object.keys(cat)));
const OPTIONS = {
  auto: {}, dark: { disp: 'dark' }, light: { disp: 'light' }, same: { sameHue: true }, fixed: { accentHex: '#e8590c' },
  bgDark: { bgHex: '#1a1d24' }, bgLight: { bgHex: '#f4f1ea' }, bgMid: { bgHex: '#808080' },
  gold: { colorfam: 'gold' }, gunmetal: { colorfam: 'silver', mv: 'gunmetal' }, red: { colorfam: 'red' },
  cPlus: { sliders: { contrast: 100 } }, cMinus: { sliders: { contrast: -100 } },
  darkCPlus: { disp: 'dark', sliders: { contrast: 100 } }, vivid: { sliders: { vivid: 100 } },
  lightS: { sliders: { light: 100 } }, muted: { sliders: { muted: 100 } }, base: { baseHex: '#2f3a8c' },
};
// 傾向の key と名前（palette の COLORS と同じ。並びも同じ）
const FAM_NAMES = {
  red: 'レッド', pink: 'ピンク', orange: 'オレンジ', yellow: 'イエロー', ygreen: 'イエローグリーン', green: 'グリーン',
  teal: 'ミント・水色', blue: 'ブルー', navy: 'ネイビー', purple: 'パープル', brown: 'ブラウン', beige: 'ベージュ',
  gold: 'ゴールド', silver: 'シルバー',
};
const FAMS = Object.keys(FAM_NAMES);
const STRICT10 = ['red', 'pink', 'orange', 'ygreen', 'green', 'teal', 'blue', 'navy', 'purple', 'brown'];
const A9_EXCLUDE = ['cMinus', 'bgDark', 'bgLight', 'bgMid', 'fixed'];

const lchOf = hex => R.rgbToOklch(R.hexToRgb(hex));
const hslOf = hex => R.rgbToHsl(R.hexToRgb(hex));
const hueDiff = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
function relLum(hex) {
  const lin = c => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));   // hexToRgb は 0〜1
  const [r, g, b] = R.hexToRgb(hex);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrastOf(a, b) {
  const x = relLum(a), y = relLum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

function gen9(word, opt, accentfam) {
  const labels = word === NO_WORD ? [] : [word];
  const extra = accentfam === undefined ? {} : { accentfam };
  return SEEDS9.map(seed => gen.generate(Object.assign({ labels, seed }, opt, extra)));
}
function digest(sets) {
  return crypto.createHash('sha256').update(JSON.stringify(sets)).digest('hex').slice(0, 16);
}

// ---- --write-golden（palette を変える前に1回だけ）----------------------------
if (process.argv.includes('--write-golden')) {
  run(() => {
    const v13 = JSON.parse(fs.readFileSync(BASELINE_V13, 'utf8')).generator.fingerprint;
    if (gen.fingerprint !== v13) {
      console.error(`[REFUSED] palette の指紋 ${gen.fingerprint} が v1.3（${v13}）と違うので書かない`);
      process.exit(1);
    }
    if (fs.existsSync(GOLDEN_PATH)) {
      console.error('[REFUSED] ゴールデンが既にあるので上書きしない: ' + path.relative(ROOT, GOLDEN_PATH));
      process.exit(1);
    }
    const cases = {};
    for (const o of Object.keys(OPTIONS)) for (const w of WORDS) cases[`${o}|${w}`] = digest(gen9(w, OPTIONS[o]));
    fs.mkdirSync(path.dirname(GOLDEN_PATH), { recursive: true });
    fs.writeFileSync(GOLDEN_PATH, JSON.stringify({
      schema: 'klk142-unspecified-golden', version: 1, fingerprint: gen.fingerprint, cases,
    }, null, 2) + '\n');
    console.log(`[OK] ゴールデンを書いた（${Object.keys(cases).length} 件）: ${path.relative(ROOT, GOLDEN_PATH)}`);
    process.exit(0);
  });
}

const fams = gen.accentFams();
if (!fams) {
  console.error('[HARNESS ERROR] palette に ACCENT_FAMS が無い（v1.3 のままか、切り出し範囲の外にある）');
  process.exit(2);
}

function famHueOk(key, hex) {
  const t = fams[key];
  const [h, s] = hslOf(hex);
  if (key === 'silver') return s <= 0.10;
  const tol = t.hJit + 3;
  return hueDiff(h, t.light[0]) <= tol || hueDiff(h, t.dark[0]) <= tol;
}
function isOutNeon(hex) {
  const [L, C] = lchOf(hex);
  return C >= 0.20 && L >= 0.65;
}
function contrastOk(key, accent, bg) {
  const cr = contrastOf(accent, bg);
  if (STRICT10.includes(key)) return cr >= 3.0;
  return relLum(bg) < 0.18 ? cr >= 3.0 : cr >= 1.6;
}

// ---- A1 未指定時の一致 ------------------------------------------------------
const plain = {};   // `${option}|${word}` → 傾向なしの9シード分
run(() => {
  for (const o of Object.keys(OPTIONS)) for (const w of WORDS) plain[`${o}|${w}`] = gen9(w, OPTIONS[o]);
  if (!fs.existsSync(GOLDEN_PATH)) {
    check('A1 未指定時の出力が v1.3 のゴールデンと一致', false, 'ゴールデンが無い: ' + path.relative(ROOT, GOLDEN_PATH));
    return;
  }
  const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8'));
  const keys = Object.keys(plain);
  const diff = keys.filter(k => golden.cases[k] !== digest(plain[k]));
  const extra = Object.keys(golden.cases).filter(k => !(k in plain));
  check(`A1 未指定時の出力が v1.3 のゴールデンと一致（${keys.length}件）`,
    keys.length === 792 && Object.keys(golden.cases).length === 792 && diff.length === 0 && extra.length === 0,
    diff.slice(0, 5).concat(extra.slice(0, 5)).join(' '));
});

// ---- A2〜A6・A9 共通の入力 ----------------------------------------------------
run(() => {
  const bad = { A2: [], A3: [], A4: [], A5: [], A6: [], A9: [] };
  const n = { A2: 0, A3: 0, A4: 0, A5: 0, A6: 0, A9: 0 };
  const minCr = {};
  for (const o of Object.keys(OPTIONS)) for (const w of WORDS) {
    const base = plain[`${o}|${w}`];
    for (const key of FAMS) {
      const got = gen9(w, OPTIONS[o], key);
      got.forEach((pals, si) => pals.forEach((p, i) => {
        const q = base[si][i];
        const tag = `${o}/${w}/${key}/s${SEEDS9[si]}/${i + 1}`;
        n.A3++;
        if (p.main !== q.main || p.sub !== q.sub || p.bg !== q.bg) bad.A3.push(tag);
        if (o === 'fixed') {
          n.A5++;
          if (JSON.stringify(p) !== JSON.stringify(q)) bad.A5.push(tag);
          return;
        }
        n.A2++;
        if (R.isNeon(p.accent, ruler)) bad.A2.push(`${tag}: neon ${p.accent}`);
        if (isOutNeon(p.accent)) bad.A2.push(`${tag}: C/L ${p.accent}`);
        n.A4++;
        if (!famHueOk(key, p.accent)) bad.A4.push(`${tag}: ${p.accent}`);
        if (o === 'same') {
          n.A6++;
          if (p.main !== q.main || p.sub !== q.sub || !famHueOk(key, p.accent)) bad.A6.push(tag);
        }
        if (!A9_EXCLUDE.includes(o)) {
          n.A9++;
          const cr = contrastOf(p.accent, p.bg);
          minCr[key] = Math.min(minCr[key] === undefined ? Infinity : minCr[key], cr);
          if (!contrastOk(key, p.accent, p.bg)) bad.A9.push(`${tag}: ${cr.toFixed(2)}`);
        }
      }));
    }
  }
  check(`A2 蛍光なし（物差し・OKLCH C>=0.20 かつ L>=0.65。${n.A2}案）`, n.A2 > 0 && bad.A2.length === 0, bad.A2.slice(0, 5).join(' '));
  check(`A3 main・sub・bg が傾向なしと一致（${n.A3}案）`, n.A3 > 0 && bad.A3.length === 0, bad.A3.slice(0, 5).join(' '));
  check(`A4 accent が選んだ色系統（${n.A4}案）`, n.A4 > 0 && bad.A4.length === 0, bad.A4.slice(0, 5).join(' '));
  check(`A5 固定が勝つ（${n.A5}案・案名を含め傾向なしと完全一致）`, n.A5 > 0 && bad.A5.length === 0, bad.A5.slice(0, 5).join(' '));
  check(`A6 同系色: main・sub は同系色の結果、accent は傾向の色（${n.A6}案）`, n.A6 > 0 && bad.A6.length === 0, bad.A6.slice(0, 5).join(' '));
  const mins = FAMS.map(k => `${k} ${minCr[k] === undefined ? '-' : minCr[k].toFixed(2)}`).join(' / ');
  check(`A9 accent 対 bg のコントラスト（${n.A9}案。最小: ${mins}）`, n.A9 > 0 && bad.A9.length === 0, bad.A9.slice(0, 5).join(' '));
});

// ---- A7 言葉の差し色を置き換える --------------------------------------------
run(() => {
  const TYPE_B = 'ベージュ＋濃い一点';
  const bad = [];
  let n = 0, typeB = 0;
  for (const word of ['かっこいい', 'スタイリッシュ', '高級', 'エレガント']) {
    for (let seed = 1; seed <= 8; seed++) {
      const base = gen.generate({ labels: [word], seed });
      for (const key of FAMS) {
        const pals = gen.generate({ labels: [word], seed, accentfam: key });
        pals.forEach((p, i) => {
          n++;
          if (!famHueOk(key, p.accent)) bad.push(`${word}/s${seed}/${key}/${i + 1}: ${p.accent}`);
          if (p.scheme !== base[i].scheme) bad.push(`${word}/s${seed}/${key}/${i + 1}: 案名 ${p.scheme}`);
        });
        if (word === 'エレガント') {
          if (base[2].scheme === TYPE_B && pals[2].scheme === TYPE_B) typeB++;
          else bad.push(`エレガント/s${seed}/${key}: 3案目 ${pals[2].scheme}`);
        }
      }
    }
  }
  check(`A7 かっこいい・スタイリッシュ・高級・エレガントの差し色が傾向の色（${n}案・型B ${typeB}件）`,
    n === 4 * 8 * 14 * 3 && typeB === 8 * 14 && bad.length === 0, bad.slice(0, 5).join(' '));
});

// ---- A8 金属の案名 ----------------------------------------------------------
run(() => {
  const METAL6 = [['gold', 'yellow'], ['gold', 'pink'], ['gold', 'green'],
                  ['silver', 'cool'], ['silver', 'warm'], ['silver', 'gunmetal']];
  const bad = [];
  let n = 0;
  for (const [colorfam, mv] of METAL6) for (const key of FAMS) for (const seed of SEEDS9) {
    const want = `${FAM_NAMES[colorfam]}×${FAM_NAMES[key]}`;
    for (const p of gen.generate({ labels: [], seed, colorfam, mv, accentfam: key })) {
      n++;
      if (p.scheme !== want) bad.push(`${colorfam}-${mv}/${key}/s${seed}: ${p.scheme}`);
    }
  }
  check(`A8 金属メインの案名が「{金属}×{色名}」（${n}案）`, n === 6 * 14 * 9 * 3 && bad.length === 0, bad.slice(0, 5).join(' '));
});

// ---- A10 明るい案を混ぜる語 --------------------------------------------------
run(() => {
  const kw = gen.keywords();
  const words = Object.values(kw).flatMap(cat => Object.keys(cat).filter(w => cat[w].lightBgs));
  const bad = [];
  let n = 0, nLight = 0, nDark = 0;
  for (const word of words) for (let seed = 1; seed <= 32; seed++) for (const colorfam of [undefined, 'gold', 'silver']) {
    for (const key of FAMS) {
      const pals = gen.generate({ labels: [word], seed, colorfam, accentfam: key });
      pals.forEach((p, i) => {
        n++;
        if (relLum(p.bg) < 0.18) nDark++; else nLight++;
        const tag = `${word}/s${seed}/${colorfam || '-'}/${key}/${i + 1}`;
        if (R.isNeon(p.accent, ruler) || isOutNeon(p.accent)) bad.push(`${tag}: 蛍光 ${p.accent}`);
        if (!contrastOk(key, p.accent, p.bg)) bad.push(`${tag}: ${contrastOf(p.accent, p.bg).toFixed(2)}`);
      });
    }
  }
  check(`A10 明るい案を混ぜる${words.length}語: 蛍光なし・コントラスト（${n}案・明るい背景 ${nLight}・暗い背景 ${nDark}）`,
    words.length === 11 && nLight > 0 && nDark > 0 && bad.length === 0, bad.slice(0, 5).join(' '));
});

console.log('='.repeat(72));
console.log('KLK-142 アクセントカラーの傾向 動的検査（A1-A10）');
console.log('='.repeat(72));
for (const r of results) console.log(`[${r.ok ? 'PASS' : 'FAIL'}] ${r.name}${r.ok || !r.detail ? '' : '\n       ' + r.detail}`);
const fails = results.filter(r => !r.ok).length;
console.log('-'.repeat(72));
console.log(`${results.length - fails}/${results.length} PASS`);
process.exit(fails ? 1 : 0);
