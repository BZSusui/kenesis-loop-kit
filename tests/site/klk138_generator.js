/*
 * KLK-138 生成側アダプタ（Node 標準のみ・CommonJS）
 *
 * palette/index.html を**読むだけ**。'const KEYWORDS = {' 〜 '\nfunction render() {' を切り出し、
 * smoke_klk004.node.js の resetState 相当のフェイクDOMと一緒に new Function で実行する。
 * マーカーが無ければ HarnessError（CLI は終了コード 2）。
 *
 * 設計: docs/designs/KLK-138.md §4.8「生成側アダプタ」
 *       docs/designs/KLK-140.md §4.8.5（generate の任意オプション・keywords()。既定の振る舞いは不変）
 *       docs/designs/KLK-140.md §4.12.7（任意オプション mv。既定の振る舞いは不変）
 *       docs/designs/KLK-140.md §4.13.10（任意オプション baseHex。既定の振る舞いは不変）
 *       docs/designs/KLK-142.md §4.8（任意オプション accentfam・accentFams()。既定の振る舞いは不変）
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const HTML_PATH = path.join(__dirname, '..', '..', 'palette', 'index.html');
const START = 'const KEYWORDS = {';
const END = '\nfunction render() {';

class HarnessError extends Error {}

const PRELUDE = `
var __ids = {}, __inputs = [], __kwInputs = [];
function __mkInput(name, value, type, checked) {
  const el = { name, value, type, _checked: !!checked };
  Object.defineProperty(el, 'checked', {
    get() { return this._checked; },
    set(v) {
      if (v && this.type === 'radio') __inputs.forEach(o => { if (o !== this && o.name === this.name) o._checked = false; });
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
var history = { replaceState: () => {} };
var CSS = { escape: (s) => String(s) };
function syncBaseUI() {} function syncAccentUI() {} function syncBgUI() {}
function syncMetallicUI() {} function render() {}
`;

// 生成の本体。グローバル seed は書き換えず、makePatterns に引数で渡す
const BODY = `
const GENRE = 'ジャンル（業種）';
function __reset(age) {
  __inputs.length = 0; __kwInputs.length = 0; __ids = {};
  ['warm','gender','formal','light','vivid','muted','contrast','age','season']
    .forEach(id => { __ids[id] = { value: '0' }; });
  __ids.age.value = String(age);
  ['useBase','useAccent','useBg','sameHue','cvdCheck'].forEach(id => { __ids[id] = { checked: false }; });
  ['basePick','baseHex','accentPick','accentHex','bgPick','bgHex'].forEach(id => { __ids[id] = { value: '#888888' }; });
  __mkInput('colorfam', '', 'radio', true);
  COLORS.forEach(c => __mkInput('colorfam', c.key, 'radio', false));
  Object.keys(METALLICS).forEach(famKey => {
    METALLICS[famKey].variants.forEach((v, i) => __mkInput('mv-' + famKey, v.key, 'radio', i === 0));
  });
  if (typeof ACCENT_FAMS === 'object') { // KLK-142: アクセントカラーの傾向（v1.3 の palette には無い）
    __mkInput('accentfam', '', 'radio', true);
    COLORS.filter(c => ACCENT_FAMS[c.key]).forEach(c => __mkInput('accentfam', c.key, 'radio', false));
  }
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
}
function __hasLabel(label) {
  return Object.keys(KEYWORDS).some(cat => Object.prototype.hasOwnProperty.call(KEYWORDS[cat], label));
}
function __check(label) {
  const cat = Object.keys(KEYWORDS).find(c => Object.prototype.hasOwnProperty.call(KEYWORDS[c], label));
  if (!cat) throw new Error('NO_LABEL:' + label);
  const el = __kwInputs.find(i => i.value === cat + '/' + label);
  if (!el) throw new Error('NO_LABEL:' + label);
  el.checked = true;
}
// opt（KLK-140・任意）: { sliders, disp, sameHue, accentHex, bgHex, colorfam, mv, baseHex, accentfam（KLK-142） }
function __generate(labels, ageSlider, s, opt) {
  __reset(ageSlider);
  labels.forEach(__check);
  if (opt) {
    Object.keys(opt.sliders || {}).forEach(id => {
      if (!__ids[id] || id === 'age') throw new Error('BAD_OPTION:sliders.' + id);
      __ids[id].value = String(opt.sliders[id]);
    });
    if (opt.disp !== undefined) {
      const el = __inputs.find(i => i.name === 'dispmode' && i.value === opt.disp);
      if (!el) throw new Error('BAD_OPTION:disp=' + opt.disp);
      el.checked = true;
    }
    if (opt.sameHue) __ids.sameHue.checked = true;
    if (opt.accentHex) { __ids.useAccent.checked = true; __ids.accentPick.value = opt.accentHex; __ids.accentHex.value = opt.accentHex; }
    if (opt.bgHex) { __ids.useBg.checked = true; __ids.bgPick.value = opt.bgHex; __ids.bgHex.value = opt.bgHex; }
    if (opt.baseHex) { __ids.useBase.checked = true; __ids.basePick.value = opt.baseHex; __ids.baseHex.value = opt.baseHex; }
    if (opt.colorfam !== undefined) {
      const el = __inputs.find(i => i.name === 'colorfam' && i.value === opt.colorfam);
      if (!el) throw new Error('BAD_OPTION:colorfam=' + opt.colorfam);
      el.checked = true;
    }
    if (opt.mv !== undefined) { // 金属の色味バリエーション（colorfam が gold/silver のときだけ有効）
      const fam = opt.colorfam !== undefined && METALLICS[opt.colorfam] ? opt.colorfam : null;
      const el = fam && __inputs.find(i => i.name === 'mv-' + fam && i.value === opt.mv);
      if (!el) throw new Error('BAD_OPTION:mv=' + opt.mv);
      el.checked = true;
    }
    if (opt.accentfam !== undefined) { // KLK-142: アクセントカラーの傾向（ACCENT_FAMS の key。'' は指定なし）
      const el = __inputs.find(i => i.name === 'accentfam' && i.value === opt.accentfam);
      if (!el) throw new Error('BAD_OPTION:accentfam=' + opt.accentfam);
      el.checked = true;
    }
  }
  const pats = makePatterns(computeBase(), s);
  return pats.map(p => ({ scheme: p.name, bg: hslToHex(...p.bg), main: hslToHex(...p.main),
                          sub: hslToHex(...p.sub), accent: hslToHex(...p.accent) }));
}
return { generate: __generate, hasLabel: __hasLabel, initialSeed: (__SEED_EXPR__),
         keywords: () => JSON.parse(JSON.stringify(KEYWORDS)),
         accentFams: () => (typeof ACCENT_FAMS === 'object' ? JSON.parse(JSON.stringify(ACCENT_FAMS)) : null) };
`;

let _cache = null;

function load() {
  if (_cache) return _cache;
  let src;
  try { src = fs.readFileSync(HTML_PATH, 'utf8'); } catch (e) { throw new HarnessError('palette/index.html が読めない: ' + e.message); }
  const iStart = src.indexOf(START), iEnd = src.indexOf(END);
  if (iStart < 0 || iEnd < 0 || iEnd <= iStart) throw new HarnessError('palette/index.html のスライスマーカーが見つからない');
  const slice = src.slice(iStart, iEnd);
  // 初期シードは切り出し範囲の外（let seed = …;）にあるので、式だけを取り出して同じ文脈で評価する
  const m = /\nlet seed = ([^;\n]+);/.exec(src);
  if (!m) throw new HarnessError('palette/index.html の初期シード式（let seed = …;）が見つからない');
  let api;
  try {
    api = new Function(PRELUDE + slice + BODY.replace('__SEED_EXPR__', m[1]))();
  } catch (e) {
    throw new HarnessError('切り出したロジックの実行に失敗: ' + e.message);
  }
  const fingerprint = crypto.createHash('sha256').update(slice).digest('hex').slice(0, 16);
  _cache = {
    fingerprint,
    initialSeed: api.initialSeed,
    hasLabel: label => api.hasLabel(label),
    keywords: () => api.keywords(),
    accentFams: () => api.accentFams(),
    // 既存の呼び出し { dictLabel, age, seed } は従来どおり。KLK-140 の任意オプション:
    //  labels（語の配列・dictLabel と併用不可）/ sliders（age 以外。-100..100）/ disp（'auto'|'light'|'dark'）/
    //  sameHue / accentHex・bgHex（固定）/ colorfam（COLORS の key）/
    //  mv（金属の色味バリエーションの key。colorfam が gold/silver のときだけ有効。KLK-140 改善ループ1）/
    //  baseHex（基準カラー。useBase を ON にして値を入れる。KLK-140 改善ループ2）/
    //  accentfam（アクセントカラーの傾向。ACCENT_FAMS の key。KLK-142）
    generate({ dictLabel, labels, age = 0, seed, sliders, disp, sameHue, accentHex, bgHex, colorfam, mv, baseHex, accentfam }) {
      if (dictLabel !== undefined && labels !== undefined) throw new HarnessError('dictLabel と labels は併用できない');
      const list = labels !== undefined ? labels : [dictLabel];
      const hasOpt = [sliders, disp, sameHue, accentHex, bgHex, colorfam, mv, baseHex, accentfam].some(v => v !== undefined);
      const opt = hasOpt ? { sliders, disp, sameHue, accentHex, bgHex, colorfam, mv, baseHex, accentfam } : null;
      try {
        return api.generate(list, Math.round(age * 100), seed === undefined ? api.initialSeed : seed, opt);
      } catch (e) {
        const msg = String(e.message);
        if (msg.startsWith('NO_LABEL:')) throw new HarnessError('辞書ラベルが見つからない: ' + msg.slice(9));
        if (msg.startsWith('BAD_OPTION:')) throw new HarnessError('オプションが不正: ' + msg.slice(11));
        throw e;
      }
    },
  };
  return _cache;
}

module.exports = { load, HarnessError, HTML_PATH };
