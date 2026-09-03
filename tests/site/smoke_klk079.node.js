/*
 * KLK-079 動的スモーク（Node.js）— compare.html の 🔄 コントロール JS を、
 * 最小の DOM シムと fetch スタブの上で**実際に動かして**検証する（smoke_klk022 と同型）。
 *
 * なぜ必要か:
 *   check_klk078/079 の S群は compare.html を**文字列一致**で見ているだけなので、
 *   「その文字列はあるが動かない」を検出できない。UI はこの機能の入口そのものなので、
 *   ・番地セレクタが /sections の結果で埋まるか
 *   ・型セレクタが現在の型に「（現在）」を付けて既定選択するか
 *   ・**現在と違う型のときだけ** desiredType を送るか
 *   ・typeApplied:false を成功と同じ扱いにしないか（リロードしない・警告を出す）
 *   ・プール無しの番地で型セレクタを無効化するか
 *   を実挙動で確かめる。
 *
 * Run: node tests/site/smoke_klk079.node.js
 * exit 0 = all pass / 1 = fail / 2 = harness error。ネットワーク非使用・Node標準のみ。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(path.dirname(__dirname));
const TARGET = path.join(ROOT, 'samples', '03_クリニック_ナビ下配置', 'compare.html');

const results = [];
function check(name, passed, detail) { results.push([name, !!passed, detail]); }

// ---------------------------------------------------------------------------
// 最小 DOM シム
// ---------------------------------------------------------------------------
class El {
  constructor(tag) {
    this.tagName = (tag || 'div').toUpperCase();
    this.children = [];
    this.attrs = {};
    this._text = '';
    this.value = '';
    this.disabled = false;
    this.id = '';
    this.listeners = {};
  }
  get firstChild() { return this.children[0] || null; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter(x => x !== c); return c; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  removeAttribute(k) { delete this.attrs[k]; }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  fire(ev) { (this.listeners[ev] || []).forEach(fn => fn({ target: this })); }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text; }
  // <select> の便宜: 選択肢のラベル一覧
  get optionLabels() { return this.children.map(c => c.textContent); }
  get optionValues() { return this.children.map(c => c.value); }
}

function makeDom(folder) {
  const body = new El('body');
  body.setAttribute('data-folder', folder);
  const btn = new El('button'); btn.id = 'regen-btn'; btn.disabled = true;
  const addr = new El('select'); addr.id = 'regen-addr';
  const type = new El('select'); type.id = 'regen-type'; type.disabled = true;
  const msg = new El('div'); msg.id = 'regen-msg';
  const radios = ['ra', 'rb', 'rc'].map(id => { const r = new El('input'); r.id = id; r.name = 'variant'; r.checked = (id === 'ra'); return r; });
  const byId = { 'regen-btn': btn, 'regen-addr': addr, 'regen-type': type, 'regen-msg': msg };
  const doc = {
    body,
    getElementById: id => byId[id] || null,
    createElement: tag => new El(tag),
    querySelector: sel => {
      if (sel === 'body') return body;
      if (sel === 'input[name=variant]:checked') return radios.find(r => r.checked) || null;
      return body;
    },
    querySelectorAll: sel => (sel === 'input[name=variant]' ? radios : []),
  };
  return { doc, body, btn, addr, type, msg, radios };
}

// ---------------------------------------------------------------------------
// fetch スタブ
// ---------------------------------------------------------------------------
function makeFetch(opts) {
  const calls = [];
  const sections = {
    a: [
      { addr: 'MV-01', current: 'overlap', pool: ['full', 'split', 'band', 'overlap', 'center-scroll', 'panel-band'] },
      { addr: 'NAV-01', current: null, pool: [] },
      { addr: 'FLOW-01', current: 'flow-arrow-band', pool: ['flow-row', 'flow-timeline', 'flow-number-card', 'flow-arrow-band', 'flow-vertical-split', 'flow-zigzag'] },
    ],
    b: [
      { addr: 'MV-01', current: 'center-scroll', pool: ['full', 'split', 'band', 'overlap', 'center-scroll', 'panel-band'] },
    ],
  };
  function json(obj) { return Promise.resolve({ ok: true, json: () => Promise.resolve(obj) }); }
  const fetchStub = (url, init) => {
    calls.push({ url, init });
    if (url.indexOf('/health') >= 0) {
      return opts.healthOk === false ? Promise.reject(new Error('down')) : json({ ok: true });
    }
    if (url.indexOf('/sections') >= 0) {
      const m = /letter=([abc])/.exec(url);
      return json({ letter: m ? m[1] : 'a', sections: sections[m ? m[1] : 'a'] || [] });
    }
    if (url.indexOf('/regenerate') >= 0) return json({ jobId: 'job1' });
    if (url.indexOf('/status/') >= 0) {
      return json(opts.status || { state: 'done', typeApplied: null, message: 'ok' });
    }
    return json({});
  };
  return { fetchStub, calls };
}

const tick = (n) => new Promise(r => setTimeout(r, n || 12));

function runUi(opts) {
  const src = fs.readFileSync(TARGET, 'utf8');
  const i = src.indexOf('<script>');
  const j = src.indexOf('</script>', i);
  if (i < 0 || j < 0) { console.error('[HARNESS ERROR] <script> を抽出できません'); process.exit(2); }
  const code = src.slice(i + '<script>'.length, j);

  const dom = makeDom('mockups/2026-09-04_smoke');
  const { fetchStub, calls } = makeFetch(opts || {});
  let reloaded = false;
  const sandbox = {
    document: dom.doc,
    fetch: fetchStub,
    AbortController: function () { this.signal = {}; this.abort = () => {}; },
    setTimeout, clearTimeout, setInterval, clearInterval,
    location: { reload: () => { reloaded = true; } },
    Promise, Array, JSON, Error, encodeURIComponent, console,
  };
  const keys = Object.keys(sandbox);
  // eslint-disable-next-line no-new-func
  new Function(...keys, code)(...keys.map(k => sandbox[k]));
  return Object.assign(dom, { calls, reloaded: () => reloaded });
}

// ---------------------------------------------------------------------------
(async function main() {
  // --- 1) 番地が /sections で埋まり、型セレクタが現在型を既定選択する ---------
  let ui = runUi({});
  await tick(); await tick();
  check('N1 番地セレクタが /sections の結果で埋まる（焼き込みでない）',
    JSON.stringify(ui.addr.optionValues) === JSON.stringify(['MV-01', 'NAV-01', 'FLOW-01']),
    '選択肢=' + JSON.stringify(ui.addr.optionValues));

  check('N2 /sections が現在の letter で呼ばれる',
    ui.calls.some(c => /\/sections\?folder=.*&letter=a$/.test(c.url)),
    '呼出=' + JSON.stringify(ui.calls.map(c => c.url.replace(/^http:\/\/[^/]+/, ''))));

  ui.addr.value = 'MV-01'; ui.addr.fire('change');
  check('N3 型セレクタが現在の型に「（現在）」を付け、既定で選択する',
    ui.type.value === 'overlap' && ui.type.optionLabels.indexOf('overlap（現在）') >= 0
      && ui.type.disabled === false,
    'value=' + ui.type.value + ' labels=' + JSON.stringify(ui.type.optionLabels));

  // --- 2) プール無しの番地では型セレクタを無効化 -----------------------------
  ui.addr.value = 'NAV-01'; ui.addr.fire('change');
  check('N4 プール無しの番地で型セレクタが無効になる',
    ui.type.disabled === true && ui.type.optionLabels[0] === 'この番地に型はありません',
    'disabled=' + ui.type.disabled + ' labels=' + JSON.stringify(ui.type.optionLabels));

  // --- 3) 現在と同じ型のままなら desiredType を送らない -----------------------
  ui = runUi({});
  await tick(); await tick();
  ui.addr.value = 'MV-01'; ui.addr.fire('change');
  ui.btn.fire('click');
  await tick();
  let regen = ui.calls.filter(c => c.url.indexOf('/regenerate') >= 0);
  let body = regen.length ? JSON.parse(regen[0].init.body) : {};
  check('N5 現在と同じ型のときは desiredType を送らない（従来の作り直しになる）',
    regen.length === 1 && !('desiredType' in body) && body.addr === 'MV-01' && body.letter === 'a',
    'body=' + JSON.stringify(body));

  // --- 4) 型を変えたときだけ desiredType を送る ------------------------------
  ui = runUi({});
  await tick(); await tick();
  ui.addr.value = 'FLOW-01'; ui.addr.fire('change');
  ui.type.value = 'flow-timeline';
  ui.btn.fire('click');
  await tick();
  regen = ui.calls.filter(c => c.url.indexOf('/regenerate') >= 0);
  body = regen.length ? JSON.parse(regen[0].init.body) : {};
  check('N6 現在と違う型を選んだときだけ desiredType を送る',
    regen.length === 1 && body.desiredType === 'flow-timeline' && body.addr === 'FLOW-01',
    'body=' + JSON.stringify(body));

  // --- 5) typeApplied:false を成功と同じ扱いにしない -------------------------
  ui = runUi({ status: { state: 'done', typeApplied: false, message: '型は flow-timeline になりませんでした（現在 flow-arrow-band）。' } });
  await tick(); await tick();
  ui.addr.value = 'FLOW-01'; ui.addr.fire('change');
  ui.type.value = 'flow-timeline';
  ui.btn.fire('click');
  await tick(); await tick(); await tick(1100);   // ポーリング間隔 900ms を跨ぐまで待つ
  check('N7 typeApplied:false のときリロードせず、警告として見せる',
    ui.reloaded() === false
      && ui.msg.getAttribute('data-warn') === '1'
      && ui.msg.textContent.indexOf('なりませんでした') >= 0
      && ui.btn.disabled === false,
    'reloaded=' + ui.reloaded() + ' warn=' + ui.msg.getAttribute('data-warn')
      + ' msg=' + JSON.stringify(ui.msg.textContent) + ' btnDisabled=' + ui.btn.disabled);

  // --- 6) 成功時はリロードする ----------------------------------------------
  ui = runUi({ status: { state: 'done', typeApplied: true, message: 'FLOW-01 を flow-timeline にしました。' } });
  await tick(); await tick();
  ui.addr.value = 'FLOW-01'; ui.addr.fire('change');
  ui.type.value = 'flow-timeline';
  ui.btn.fire('click');
  await tick(); await tick(); await tick(1100);
  check('N8 typeApplied:true のときはリロードして反映する',
    ui.reloaded() === true && ui.msg.getAttribute('data-warn') === null,
    'reloaded=' + ui.reloaded() + ' warn=' + ui.msg.getAttribute('data-warn'));

  // --- 7) ブリッジ未起動なら graceful に無効化 -------------------------------
  ui = runUi({ healthOk: false });
  await tick(); await tick();
  check('N9 ブリッジ未起動でボタン・型セレクタを無効化し、手動手順を案内する',
    ui.btn.disabled === true && ui.type.disabled === true
      && ui.msg.textContent.indexOf('ローカルブリッジ未起動') >= 0
      && ui.calls.every(c => c.url.indexOf('/sections') < 0),
    'btn=' + ui.btn.disabled + ' type=' + ui.type.disabled + ' msg=' + JSON.stringify(ui.msg.textContent.slice(0, 40)));

  // --- 8) 案を切り替えたら読み直す ------------------------------------------
  ui = runUi({});
  await tick(); await tick();
  const before = ui.calls.filter(c => c.url.indexOf('/sections') >= 0).length;
  ui.radios[0].checked = false; ui.radios[1].checked = true;
  ui.radios[1].fire('change');
  await tick(); await tick();
  const after = ui.calls.filter(c => c.url.indexOf('/sections') >= 0);
  check('N10 案を切り替えると /sections を読み直す（案ごとに型が違うため）',
    after.length === before + 1 && /letter=b$/.test(after[after.length - 1].url)
      && ui.addr.optionValues.length === 1,
    '呼出数=' + after.length + ' 最後=' + (after[after.length - 1] || {}).url);

  // --- 出力 -----------------------------------------------------------------
  console.log('='.repeat(78));
  console.log('KLK-079 compare.html の 🔄 コントロール 動的スモーク（DOM シム）');
  console.log('='.repeat(78));
  let failed = 0;
  for (const [name, passed, detail] of results) {
    if (!passed) failed++;
    console.log('[' + (passed ? 'PASS' : 'FAIL') + '] ' + name);
    console.log('        ' + detail);
  }
  console.log('-'.repeat(78));
  console.log(results.length + ' checks, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error('[HARNESS ERROR]', e); process.exit(2); });
