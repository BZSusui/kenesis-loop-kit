/*
 * KLK-138 生成側アダプタ（Node 標準のみ・CommonJS）
 *
 * palette/index.html を**読むだけ**。'const KEYWORDS = {' 〜 '\nfunction render() {' を切り出し、
 * smoke_klk004.node.js の resetState 相当のフェイクDOMと一緒に new Function で実行する。
 * マーカーが無ければ HarnessError（CLI は終了コード 2）。
 *
 * 設計: docs/designs/KLK-138.md §4.8「生成側アダプタ」
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
function __generate(label, ageSlider, s) {
  __reset(ageSlider);
  const cat = Object.keys(KEYWORDS).find(c => Object.prototype.hasOwnProperty.call(KEYWORDS[c], label));
  if (!cat) throw new Error('NO_LABEL:' + label);
  const el = __kwInputs.find(i => i.value === cat + '/' + label);
  if (!el) throw new Error('NO_LABEL:' + label);
  el.checked = true;
  const pats = makePatterns(computeBase(), s);
  return pats.map(p => ({ scheme: p.name, bg: hslToHex(...p.bg), main: hslToHex(...p.main),
                          sub: hslToHex(...p.sub), accent: hslToHex(...p.accent) }));
}
return { generate: __generate, hasLabel: __hasLabel, initialSeed: (__SEED_EXPR__) };
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
    generate({ dictLabel, age = 0, seed }) {
      try {
        return api.generate(dictLabel, Math.round(age * 100), seed === undefined ? api.initialSeed : seed);
      } catch (e) {
        if (String(e.message).startsWith('NO_LABEL:')) throw new HarnessError('辞書ラベルが見つからない: ' + dictLabel);
        throw e;
      }
    },
  };
  return _cache;
}

module.exports = { load, HarnessError, HTML_PATH };
