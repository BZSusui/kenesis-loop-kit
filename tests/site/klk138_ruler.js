/*
 * KLK-138 言葉と色の物差し — 採点ライブラリ（Node 標準のみ・CommonJS）
 *
 * 設計: docs/designs/KLK-138.md §4.4〜§4.7・§4.9
 *   - 色変換（sRGB → HSL / HSV / OKLab / OKLCH）
 *   - マス判定 classify（HSL の最寄りマス＋無彩色・金属8マスとは OKLab 距離で比較）
 *   - 1案の採点（cells / elegant / combo）と集計
 *   - 人間の判定との一致（判定データが Git 外にあるときだけ使う）
 *
 * 合格範囲そのものは tests/fixtures/klk138/ruler.json（生成物）が持つ。
 * このファイルには判定データの色コードを書かない。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const RULER_PATH = path.join(ROOT, 'tests', 'fixtures', 'klk138', 'ruler.json');
const DATA_DIR = path.join(ROOT, 'tickets', 'work', 'KLK-138');

// ---------------------------------------------------------------------------
// 色変換（すべて純関数）
// ---------------------------------------------------------------------------
function hexToRgb(hex) {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(String(hex).trim());
  if (!m) throw new Error('bad hex: ' + hex);
  const n = parseInt(m[1], 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function rgbToHsl([r, g, b]) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  if (d === 0) return [0, 0, l];
  const s = d / (1 - Math.abs(2 * l - 1));
  let h;
  if (max === r) h = 60 * (((g - b) / d) % 6);
  else if (max === g) h = 60 * ((b - r) / d + 2);
  else h = 60 * ((r - g) / d + 4);
  if (h < 0) h += 360;
  return [h, Math.min(1, s), l];
}

function rgbToHsv([r, g, b]) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = 60 * (((g - b) / d) % 6);
    else if (max === g) h = 60 * ((b - r) / d + 2);
    else h = 60 * ((r - g) / d + 4);
    if (h < 0) h += 360;
  }
  return [h, max === 0 ? 0 : d / max, max];
}

function srgbToLinear(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

// sRGB → 線形 → LMS → OKLab（Ottosson の係数）
function rgbToOklab(rgb) {
  const [r, g, b] = rgb.map(srgbToLinear);
  const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;
  const l_ = Math.cbrt(l), m_ = Math.cbrt(m), s_ = Math.cbrt(s);
  return [
    0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
    1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
    0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
  ];
}

function rgbToOklch(rgb) {
  const [L, a, b] = rgbToOklab(rgb);
  const C = Math.sqrt(a * a + b * b);
  let h = Math.atan2(b, a) * 180 / Math.PI;
  if (h < 0) h += 360;
  return [L, C, h];
}

// judge.html の hslToHex と同じ丸め（マスの代表色を作る）
function hslToHex(h, s, l) {
  const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = l - c / 2;
  let r, g, b;
  if (h < 60) [r, g, b] = [c, x, 0]; else if (h < 120) [r, g, b] = [x, c, 0]; else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c]; else if (h < 300) [r, g, b] = [x, 0, c]; else [r, g, b] = [c, 0, x];
  const to = v => Math.round((v + m) * 255).toString(16).padStart(2, '0');
  return '#' + to(r) + to(g) + to(b);
}

const oklchOf = hex => rgbToOklch(hexToRgb(hex));
const hsvOf = hex => rgbToHsv(hexToRgb(hex));

function labDist(a, b) {
  return Math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2);
}

const pad3 = h => String(h).padStart(3, '0');

// ---------------------------------------------------------------------------
// マス判定（§4.4）
// ---------------------------------------------------------------------------
const _gridCache = new WeakMap();
function gridOf(ruler) {
  let g = _gridCache.get(ruler);
  if (g) return g;
  const tones = ruler.grid.tones;
  const reps = {};
  for (const t of tones) for (const h of ruler.grid.hues) {
    const id = `${t.key}-${pad3(h)}`;
    const hex = hslToHex(h, t.s, t.l);
    reps[id] = { id, hex, lab: rgbToOklab(hexToRgb(hex)) };
  }
  const neutrals = ruler.grid.neutrals.map(n => ({ id: `n-${n.key}`, hex: n.hex, lab: rgbToOklab(hexToRgb(n.hex)) }));
  const allIds = new Set(Object.keys(reps).concat(neutrals.map(n => n.id)));
  g = { reps, neutrals, allIds };
  _gridCache.set(ruler, g);
  return g;
}

function classify(hex, ruler) {
  const g = gridOf(ruler);
  const rgb = hexToRgb(hex);
  const [h, s, l] = rgbToHsl(rgb);
  const lab = rgbToOklab(rgb);
  const band = (Math.round(h / 30) % 12) * 30;
  const w = ruler.grid.toneLightnessWeight;
  let best = null, bestD = Infinity;
  for (const t of ruler.grid.tones) {
    const d = (s - t.s) ** 2 + (w * (l - t.l)) ** 2;
    if (d < bestD) { bestD = d; best = t; }
  }
  const gridId = `${best.key}-${pad3(band)}`;
  const gridDist = labDist(lab, g.reps[gridId].lab);
  let nBest = null, nD = Infinity;
  for (const n of g.neutrals) {
    const d = labDist(lab, n.lab);
    if (d < nD) { nD = d; nBest = n; }
  }
  if (nD < gridDist) return { cell: nBest.id, dist: nD };
  return { cell: gridId, dist: gridDist };
}

function cellRepHex(id, ruler) {
  const g = gridOf(ruler);
  if (g.reps[id]) return g.reps[id].hex;
  const n = g.neutrals.find(x => x.id === id);
  if (n) return n.hex;
  throw new Error('unknown cell: ' + id);
}

// ---------------------------------------------------------------------------
// 減点の検出（§4.5）
// ---------------------------------------------------------------------------
function isNeon(hex, ruler) {
  const t = ruler.thresholds.neon.value;
  const [h, s, v] = hsvOf(hex);
  if (s < t.sMin || v < t.vMin) return false;
  return t.hueRanges.some(([a, b]) => h >= a && h <= b);
}

function isWarmVivid(hex, ruler) {
  const t = ruler.thresholds.warmVivid.value;
  const [, C, h] = oklchOf(hex);
  return (h <= t.hueMax || h >= t.hueMin) && C >= t.cMin;
}

const ROLES = ['bg', 'main', 'sub', 'accent'];
const POINTS_DEFAULT = { ok: 1, maybe: 0.5, ng: 0 };
const pointsOf = (ruler, v) => (ruler.scoring && ruler.scoring.points ? ruler.scoring.points : POINTS_DEFAULT)[v];
const r4 = x => Math.round(x * 10000) / 10000;
const r2 = x => Math.round(x * 100) / 100;

function bgLabel(hex) { return 'L' + oklchOf(hex)[0].toFixed(2); }

function rolesSummary(pal, ruler) {
  return {
    main: classify(pal.main, ruler).cell,
    sub: classify(pal.sub, ruler).cell,
    accent: classify(pal.accent, ruler).cell,
    bg: bgLabel(pal.bg),
  };
}

// ---------------------------------------------------------------------------
// 1案の採点: kind = cells（§4.5）
// ---------------------------------------------------------------------------
function scoreCells(pal, def, ruler, ctx) {
  const age = ctx && typeof ctx.age === 'number' ? ctx.age : 0;
  const ok = new Set(def.cells.ok), maybe = new Set(def.cells.maybe);
  const cond = (def.okWhen || []).map(c => ({ cells: new Set(c.cells), ageMin: c.ageMin }));
  const inCond = id => cond.some(c => c.cells.has(id));
  const condOk = id => cond.some(c => c.cells.has(id) && age >= c.ageMin);

  const mainCell = classify(pal.main, ruler).cell;
  const subCell = classify(pal.sub, ruler).cell;
  const accCell = classify(pal.accent, ruler).cell;
  let main = 0;
  if (ok.has(mainCell) || condOk(mainCell)) main = 1;
  else if (maybe.has(mainCell)) main = 0.5;
  const anyOf = id => (ok.has(id) || maybe.has(id) || inCond(id)) ? 1 : 0;
  const sub = anyOf(subCell), accent = anyOf(accCell);

  const L = oklchOf(pal.bg)[0];
  const lightMin = ruler.thresholds.bgLightMinL.value, darkMax = ruler.thresholds.bgDarkMaxL.value;
  let bg = 1;
  if (def.bg === 'light') bg = L >= lightMin ? 1 : (L < darkMax ? 0 : 0.5);
  else if (def.bg === 'dark') bg = L <= darkMax ? 1 : (L > lightMin ? 0 : 0.5);

  const penalties = [];
  const policy = def.neonPolicy || 'standard';
  let mainNeon = false, nNeon = 0;
  if (policy !== 'allow') {
    if (isNeon(pal.main, ruler)) { mainNeon = true; penalties.push('neon:main'); }
    for (const r of ['sub', 'accent', 'bg']) {
      if (policy === 'accentOnly' && r === 'accent') continue;
      if (isNeon(pal[r], ruler)) { nNeon++; penalties.push('neon:' + r); }
    }
  }
  const warm = def.warmAccentPolicy === 'weak' && isWarmVivid(pal.accent, ruler);
  if (warm) penalties.push('warmAccent');

  let verdict;
  if (main === 0 || bg === 0 || mainNeon || nNeon >= 2) verdict = 'ng';
  else if (main === 1 && bg === 1 && sub === 1 && accent === 1 && nNeon === 0 && !warm) verdict = 'ok';
  else verdict = 'maybe';

  const st = v => (v === 1 ? 'ok' : v === 0.5 ? 'maybe' : 'ng');
  return {
    verdict, points: pointsOf(ruler, verdict),
    roles: {
      main: { cell: mainCell, status: st(main) },
      sub: { cell: subCell, status: st(sub) },
      accent: { cell: accCell, status: st(accent) },
      bg: { L: r2(L), status: st(bg) },
    },
    penalties,
  };
}

// ---------------------------------------------------------------------------
// 1案の採点: kind = elegant（§4.6.1）
// ---------------------------------------------------------------------------
function scoreElegant(pal, def, ruler) {
  const t = ruler.thresholds.elegant;
  const lch = {};
  for (const r of ROLES) lch[r] = oklchOf(pal[r]);
  const penalties = [];
  for (const r of ROLES) if (isNeon(pal[r], ruler)) penalties.push('neon:' + r);
  const [, mC, mH] = lch.main;
  const hueOk = mH >= t.hueMin.value || mH <= t.hueMax.value;
  const be = t.beige.value;
  const isBeige = ([L, C, h]) => C >= be.cMin && C < be.cMax && h >= be.hMin && h <= be.hMax && L >= be.lMin;
  let verdict, type = 'none';
  if (penalties.length) verdict = 'ng';
  else if (hueOk && mC > t.mainCMax.value) { verdict = 'ng'; type = 'A'; penalties.push('vividMain'); }
  else if (hueOk) {
    type = 'A';
    // △理由を積む（複数あっても△のまま。×には落とさない。改訂 2026-11-26）
    const darkBg = lch.bg[0] < t.darkBgMaxL.value;
    if (mC > t.mainCOkMax.value) penalties.push('semiVividMain');
    if (darkBg && lch.accent[0] < t.darkBgAccentMinL.value) penalties.push('darkBgAccent');
    if (darkBg && lch.main[0] < t.darkBgMainMinL.value) penalties.push('darkBgMain');
    verdict = penalties.length ? 'maybe' : 'ok';
  } else if (isBeige(lch.main) || isBeige(lch.bg)) {
    type = 'B';
    const dark = lch.sub[0] <= t.darkPointMaxL.value || lch.accent[0] <= t.darkPointMaxL.value;
    verdict = dark ? 'ok' : 'maybe';
    if (!dark) penalties.push('noDarkPoint');
  } else verdict = 'ng';
  return { verdict, points: pointsOf(ruler, verdict), type, roles: rolesSummary(pal, ruler), penalties };
}

// ---------------------------------------------------------------------------
// 1案の採点: kind = combo（§4.6.2）
// ---------------------------------------------------------------------------
function hueClusters(hues, gapDeg) {
  if (!hues.length) return 0;
  const hs = hues.slice().sort((a, b) => a - b);
  let gaps = 0;
  for (let i = 0; i < hs.length; i++) {
    const next = i + 1 < hs.length ? hs[i + 1] : hs[0] + 360;
    if (next - hs[i] > gapDeg) gaps++;
  }
  return Math.max(1, gaps);
}

function comboMetrics(pal, ruler) {
  const t = ruler.thresholds.combo;
  const lch = {};
  for (const r of ROLES) lch[r] = oklchOf(pal[r]);
  const vivid = ROLES.filter(r => lch[r][1] >= t.vividCMin.value).length;
  const chromHues = ROLES.filter(r => lch[r][1] >= t.chromaticCMin.value).map(r => lch[r][2]);
  const clusters = hueClusters(chromHues, t.hueGapDeg.value);
  const [mL, mC] = lch.main;
  const mono = mC < t.monoMain.value.cMax || mL <= t.monoMain.value.lMax;
  const pastel = mL >= t.pastelMain.value.lMin && mC >= t.pastelMain.value.cMin;
  const cb = t.creamBg.value, [bL, bC, bH] = lch.bg;
  const cream = bL >= cb.lMin && bC >= cb.cMin && bC < cb.cMax && (bH <= cb.hueMax || bH >= cb.hueMin);
  const pb = t.pureBlack.value;
  const pureBlack = ROLES.some(r => lch[r][0] < pb.lMax && lch[r][1] < pb.cMax);
  const neon = ROLES.filter(r => isNeon(pal[r], ruler));
  const cells = {};
  for (const r of ROLES) cells[r] = classify(pal[r], ruler).cell;
  const metal = new Set(t.simpleMetalCells.value);
  const warmAccent = isWarmVivid(pal.accent, ruler);
  return { vivid, clusters, mono, pastel, cream, pureBlack, neon, cells, metal, warmAccent };
}

function scoreCombo(pal, def, ruler) {
  const m = comboMetrics(pal, ruler);
  const penalties = m.neon.map(r => 'neon:' + r);
  let verdict;
  if (def.comboType === 'cool' || def.comboType === 'stylish') {
    if (m.neon.length) verdict = 'ng';
    else if (m.pastel) { verdict = 'ng'; penalties.push('pastelMain'); }
    else if (m.vivid >= 2 && m.clusters >= 3) { verdict = 'ng'; penalties.push('colorful'); }
    else if (def.comboType === 'stylish' && m.cream) { verdict = 'ng'; penalties.push('creamBg'); }
    else if (m.mono && !m.warmAccent) verdict = 'ok';
    else {
      verdict = 'maybe';
      if (m.warmAccent) penalties.push('warmAccent');
      if (!m.mono) penalties.push('notMono');
    }
  } else if (def.comboType === 'simple') {
    const anyMetal = ROLES.some(r => m.metal.has(m.cells[r]));
    if (m.neon.length) verdict = 'ng';
    else if (m.vivid >= 2) { verdict = 'ng'; penalties.push('vivid>=2'); }
    else if (m.metal.has(m.cells.main)) { verdict = 'ng'; penalties.push('metalMain'); }
    else if (m.vivid === 0 && m.clusters <= 2 && !m.pureBlack && !anyMetal) verdict = 'ok';
    else {
      verdict = 'maybe';
      if (m.vivid) penalties.push('vivid');
      if (m.clusters > 2) penalties.push('clusters');
      if (m.pureBlack) penalties.push('pureBlack');
      if (anyMetal) penalties.push('metal');
    }
  } else {
    throw new Error('unknown comboType: ' + def.comboType);
  }
  return { verdict, points: pointsOf(ruler, verdict), roles: rolesSummary(pal, ruler), penalties,
    metrics: { vivid: m.vivid, clusters: m.clusters, mono: m.mono } };
}

function scorePalette(word, pal, ruler, ctx) {
  const def = ruler.words[word];
  if (!def) throw new Error('unknown word: ' + word);
  if (def.kind === 'cells') return scoreCells(pal, def, ruler, ctx || {});
  if (def.kind === 'elegant') return scoreElegant(pal, def, ruler);
  if (def.kind === 'combo') return scoreCombo(pal, def, ruler);
  throw new Error('unknown kind: ' + def.kind);
}

// 案の点の平均（§4.7）
function rateOf(results) {
  if (!results.length) return null;
  return results.reduce((a, r) => a + r.points, 0) / results.length;
}

function loadRuler(p) {
  return JSON.parse(fs.readFileSync(p || RULER_PATH, 'utf8'));
}

// ---------------------------------------------------------------------------
// 人間の判定との一致（§4.9）。判定データは Git 外。無ければ null。
// ---------------------------------------------------------------------------
// 判定データは全部そろっているか全部無いかのどちらか。一部だけ欠けていたら黙って SKIP せず例外にする
const JUDGMENT_FILES = ['klk138-judgments.json', 'amendments.json', 'klk138-round2.json',
  'klk138-round3.json', 'klk138-round3b.json'];
class PartialDataError extends Error {}

function loadJudgmentData(dir) {
  dir = dir || DATA_DIR;
  const f = n => path.join(dir, n);
  const missing = JUDGMENT_FILES.filter(n => !fs.existsSync(f(n)));
  if (missing.length === JUDGMENT_FILES.length) return null;
  if (missing.length) throw new PartialDataError('判定データが一部だけ欠けている: ' + missing.join(', '));
  const rd = n => JSON.parse(fs.readFileSync(f(n), 'utf8'));
  return { round2: rd('klk138-round2.json'), round3: rd('klk138-round3.json'), round3b: rd('klk138-round3b.json') };
}

const V_ORDER = ['ok', 'maybe', 'ng'];

function compareSet(items, ruler, scoreWord) {
  const conf = {};
  for (const h of V_ORDER) { conf[h] = {}; for (const r of V_ORDER) conf[h][r] = 0; }
  let exact = 0, adj = 0, rev = 0, ae = 0, aeMaybe = 0;
  const mismatches = [];
  for (const c of items) {
    const ctx = c.context ? { age: 0.4 } : { age: 0 };
    const res = scorePalette(scoreWord || c.word, c, ruler, ctx);
    const hp = pointsOf(ruler, c.verdict), rp = res.points;
    conf[c.verdict][res.verdict]++;
    if (c.verdict === res.verdict) exact++;
    else mismatches.push({ id: c.id, source: c.source, human: c.verdict, ruler: res.verdict });
    if (Math.abs(hp - rp) <= 0.5) adj++;
    if ((c.verdict === 'ok' && res.verdict === 'ng') || (c.verdict === 'ng' && res.verdict === 'ok')) rev++;
    ae += Math.abs(hp - rp);
    aeMaybe += Math.abs(hp - pointsOf(ruler, 'maybe'));
  }
  const n = items.length;
  return {
    n, exact: r4(exact / n), adjacent: r4(adj / n), reversal: r4(rev / n),
    mae: r4(ae / n), maeAllMaybe: r4(aeMaybe / n), confusion: conf,
    _mismatches: mismatches,
  };
}

function validateAgainstHumans(ruler, data) {
  if (!data) return null;
  const cand = data.round2.candidates;
  const kindOf = w => (ruler.words[w] || {}).kind;
  const vm = cand.filter(c => kindOf(c.word) === 'cells');
  const vg = cand.filter(c => c.source === 'G1' || c.source === 'G2');
  const vc = cand.filter(c => kindOf(c.word) === 'combo');
  const ve = data.round3.candidates.concat(data.round3b.candidates);
  const old = cand.filter(c => c.word === 'エレガント');

  const VM = compareSet(vm, ruler);
  const VC = compareSet(vc, ruler);
  const VE = compareSet(ve, ruler, 'エレガント');
  const REF = compareSet(old, ruler, '高級感');

  // V-G: 現行案を人間と物差しで採点し、得点率を比べる
  const VG = compareSet(vg, ruler);
  const byWord = {};
  let hSum = 0, rSum = 0;
  for (const c of vg) {
    const res = scorePalette(c.word, c, ruler, c.context ? { age: 0.4 } : { age: 0 });
    const hp = pointsOf(ruler, c.verdict);
    hSum += hp; rSum += res.points;
    byWord[c.word] = byWord[c.word] || { h: 0, r: 0, n: 0 };
    byWord[c.word].h += hp; byWord[c.word].r += res.points; byWord[c.word].n++;
  }
  const words = {};
  for (const w of Object.keys(byWord).sort()) {
    words[w] = { human: r4(byWord[w].h / byWord[w].n), ruler: r4(byWord[w].r / byWord[w].n) };
  }
  VG.humanRate = r4(hSum / vg.length);
  VG.rulerRate = r4(rSum / vg.length);
  VG.diff = r4(VG.rulerRate - VG.humanRate);
  VG.words = words;

  return {
    'V-M': Object.assign(VM, { nature: '主の検証（合格範囲は第1回から作成。ただし w と組み合わせ方は第2回を見て選んだ）' }),
    'V-G': Object.assign(VG, { nature: '現行案 G1・G2 の得点率を人間と物差しで比べる' }),
    'V-C': Object.assign(VC, { nature: '当てはめ（規則をこの判定から作った。さらに結果を見てから規則を修正した＝シンプルの金属を金だけに）' }),
    'V-E': Object.assign(VE, { nature: '当てはめ（規則をこの判定から作った）' }),
    reference: Object.assign(REF, { nature: '第2回の旧エレガント6案を高級感の物差しで採点（食い違いの確認だけ・目安なし）' }),
  };
}

// 目安（§4.9）。ok=false の項目を返す
const TARGETS = {
  'V-M': [['exact', '>=', 0.50], ['adjacent', '>=', 0.85], ['reversal', '<=', 0.12], ['mae', '<=', 0.30]],
  'V-G': [['absDiff', '<=', 0.10]],
  'V-C': [['exact', '>=', 0.80]],
  'V-E': [['exact', '>=', 0.90]],
};
function checkTargets(val) {
  const out = [];
  for (const set of Object.keys(TARGETS)) {
    for (const [key, op, th] of TARGETS[set]) {
      const v = key === 'absDiff' ? Math.abs(val[set].diff) : val[set][key];
      const ok = op === '>=' ? v >= th - 1e-12 : v <= th + 1e-12;
      out.push({ set, key, op, th, value: r4(v), ok });
    }
  }
  return out;
}

// 公開用（_mismatches を除く）
function publicValidation(val) {
  if (!val) return null;
  const out = {};
  for (const k of Object.keys(val)) {
    const o = {};
    for (const kk of Object.keys(val[k])) if (!kk.startsWith('_')) o[kk] = val[k][kk];
    out[k] = o;
  }
  return out;
}

module.exports = {
  ROOT, RULER_PATH, DATA_DIR,
  hexToRgb, rgbToHsl, rgbToHsv, rgbToOklab, rgbToOklch, hslToHex,
  classify, cellRepHex, isNeon, isWarmVivid, hueClusters,
  scoreCells, scoreElegant, scoreCombo, scorePalette, rateOf, loadRuler,
  loadJudgmentData, PartialDataError, JUDGMENT_FILES, validateAgainstHumans, checkTargets, publicValidation, TARGETS,
  r4, r2,
};
