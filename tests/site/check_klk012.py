#!/usr/bin/env python3
"""
KLK-012 acceptance-condition checker (static / core / no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S12 from
docs/designs/KLK-012.md §9（S群）against 部分再生成（番地ラベル指定でセクション単位に
作り直す・REQ-103 / SCR-002）:

  ブリッジ本体(純関数 import + ソース静的検査)  draft-gen/bridge.py
  新スキル(静的検査)                            .claude/skills/draft-regenerate/SKILL.md
  生成規約(静的検査)                            .claude/skills/draft-generate/templates/DRAFT_RULES.md
  生成スキル(🔄導線・静的検査)                  .claude/skills/draft-generate/SKILL.md
  ゴールデン(before/after 不変保持・🔄導線)     tests/fixtures/klk012/*.html

Source of truth = 設計書 KLK-012 §9（S群 S1-S12）。S番号は S1 から開始する独立ファイル
（check_klk009/010/011 と同型: import 単体＋正規表現・文字列検索・波括弧/入れ子均衡・
tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用）。bridge.py は
`if __name__ == "__main__"` ガードでサーバ起動を隔離しているため import で副作用
（bind/実行）は起きない。D群（discover 回帰・git check-ignore）と /regenerate の実HTTP
疎通（403/413/400/404 の防御）は tests/test_palette_klk012.py が、M群（実
/draft-regenerate ＋ブラウザ実機の再生成品質）は tester が確認しチケットのログへ記録する。
プロダクション成果物（bridge.py / SKILL / DRAFT_RULES / ゴールデン）は変更しない。

Run: python3 tests/site/check_klk012.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")
REGEN_SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md")
GEN_SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")
DRAFT_RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
FIX_DIR = os.path.join(ROOT, "tests", "fixtures", "klk012")
BEFORE_PATH = os.path.join(FIX_DIR, "index-a-before.html")
AFTER_PATH = os.path.join(FIX_DIR, "index-a-after.html")
COMPARE_PATH = os.path.join(FIX_DIR, "compare-regen.html")

BRIDGE_SRC = open(BRIDGE_PATH, encoding="utf-8").read()
REGEN_SKILL = open(REGEN_SKILL_PATH, encoding="utf-8").read()
GEN_SKILL = open(GEN_SKILL_PATH, encoding="utf-8").read()
DRAFT_RULES = open(DRAFT_RULES_PATH, encoding="utf-8").read()
BEFORE = open(BEFORE_PATH, encoding="utf-8").read()
AFTER = open(AFTER_PATH, encoding="utf-8").read()
COMPARE = open(COMPARE_PATH, encoding="utf-8").read()

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk012_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# 危険フラグ（決して含めてはならない・最小権限）。
DANGER_FLAGS = ("--dangerously-skip-permissions", "bypassPermissions")

# 外部URL検査で除外するホスト（ローカル/プレースホルダ/ドキュメント慣用）。
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0")

# 配色5変数（対象HTMLのルート .mock から読む・U-2）。
PALETTE_VARS = ("--m-main", "--m-nav", "--m-accent", "--m-bg", "--m-text")
# 番地6種（各ファイル内で一意・DRAFT_RULES §2）。
ADDR6 = ("NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01")


def _host(url):
    m = re.match(r"https?://([^/\s\"')（]+)", url)
    return m.group(1).lower() if m else ""


def _external_urls(txt):
    """外部URL（ローカル・プレースホルダ・許可ホストを除く）を列挙する（check_klk010 S10 同配慮）。"""
    out = []
    for m in re.findall(r'https?://[^\s"\')（]+', txt):
        host = _host(m)
        noport = host.split(":", 1)[0]
        if noport in _LOCAL_HOSTS or noport in _ALLOW_HOSTS:
            continue
        if not host:  # 'http://' + '127.0.0.1' の分割連結（直後がクォート）
            continue
        if "{" in host or "%" in host:  # format プレースホルダ
            continue
        out.append(m)
    return out


_SECRET_RE = re.compile(
    r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
# 実際の秘密“値”のみ（key = "value" / token: 'xxx' 形式）。禁止事項の散文（「secret を
# 含めない」等の指示語）は誤検知しない。スキルは秘密の混入を禁じる文を持つのが正常。
_SECRET_VALUE_RE = re.compile(
    r"(api[_-]?key|secret|password|token|private[_ ]key)\s*[:=]\s*['\"][^'\"\s]{4,}", re.I)


def _secret_hits(txt):
    return [ln for ln, line in enumerate(txt.splitlines(), 1)
            if _SECRET_RE.search(line)]


def _secret_value_hits(txt):
    return [ln for ln, line in enumerate(txt.splitlines(), 1)
            if _SECRET_VALUE_RE.search(line)]


# ===========================================================================
# S1 番地/letter/folder バリデーション純関数（is_valid_addr / is_valid_letter /
#    is_safe_mockups_folder・traversal 防止・U-3 / U-5 / SPEC §7 / NFR-004）
# ===========================================================================
va = bridge.is_valid_addr
vl = bridge.is_valid_letter
vf = bridge.is_safe_mockups_folder
# is_valid_addr
a_ok = va("MV-01") and va("NAV-01") and va("SECTION-12")  # 6種＋SECTION-NN 拡張
a_lower = va("hero-01") is False
a_trav = va("../x") is False
a_inject = (va("MV-01; rm -rf /") is False and va("HERO 01") is False
            and va("HERO-1") is False and va("$(x)-01") is False)
a_nonstr = va(None) is False and va(123) is False
s1_addr = a_ok and a_lower and a_trav and a_inject and a_nonstr
# is_valid_letter
l_ac = vl("a") and vl("b") and vl("c")
l_none = vl(None) and vl("")             # 単一案(index.html)
l_bad = (vl("d") is False and vl("A") is False and vl("ab") is False
         and vl(1) is False)
s1_letter = l_ac and l_none and l_bad
# is_safe_mockups_folder
f_ok = vf("mockups/2026-07-08_案件") and vf("mockups/x")
f_trav = vf("mockups/../x") is False
f_abs = vf("/mockups/x") is False and vf("/etc/passwd") is False
f_back = vf("mockups\\x") is False and vf("mockups/a\\b") is False
f_slash = vf("mockups/") is False        # 空セグメント
f_prefix = vf("notmockups/x") is False and vf("x/mockups/y") is False
f_nonstr = vf(None) is False
s1_folder = f_ok and f_trav and f_abs and f_back and f_slash and f_prefix and f_nonstr
s1 = s1_addr and s1_letter and s1_folder
check(
    "S1 番地/letter/folder 検証純関数 (is_valid_addr: 6種+SECTION-NN○/小文字・traversal・注入×; "
    "is_valid_letter: a-c/None/''○・d/A/ab×; is_safe_mockups_folder: mockups/配下○・../絶対/\\/空/接頭辞不一致×)",
    s1,
    f"addr={s1_addr}(6種+拡張={a_ok},小文字拒否={a_lower},traversal拒否={a_trav},注入拒否={a_inject}), "
    f"letter={s1_letter}(a-c={l_ac},None/''={l_none},不正拒否={l_bad}), "
    f"folder={s1_folder}(mockups配下={f_ok},..拒否={f_trav},絶対拒否={f_abs},\\拒否={f_back},空拒否={f_slash},接頭辞={f_prefix})",
)

# ===========================================================================
# S2 対象セクション特定・一意性（find_target_section・unknown/duplicate・SPEC §7）
# ===========================================================================
fts = bridge.find_target_section
# MV-01 → 唯一の .sec 範囲(start,end)。範囲は HERO のみを含み、他番地を含まない。
h_start, h_end = fts(BEFORE, "MV-01")
s2_hero_span = isinstance(h_start, int) and isinstance(h_end, int) and h_start < h_end
if s2_hero_span:
    block = BEFORE[h_start:h_end]
    s2_hero_scope = (
        "MV-01" in block and "m-hero" in block
        and "NAV-01" not in block and "ABOUT-01" not in block
        and block.strip().startswith('<div class="sec')
        and block.rstrip().endswith("</div>"))
else:
    s2_hero_scope = False
# 未知番地（パターン合致だが不在）→ (None, "unknown")
u_span, u_info = fts(BEFORE, "XXXX-01")
s2_unknown = u_span is None and u_info == "unknown"
# 重複（人工的に2回 pin を持つ HTML）→ (None, "duplicate")
dup_html = (
    '<div class="mock"><div class="sec reveal"><div class="addr">'
    '<span class="pin">MV-01</span></div><div class="m-hero">A</div></div>'
    '<div class="sec reveal"><div class="addr"><span class="pin">MV-01</span>'
    '</div><div class="m-hero">B</div></div></div>')
d_span, d_info = fts(dup_html, "MV-01")
s2_dup = d_span is None and d_info == "duplicate"
s2 = s2_hero_span and s2_hero_scope and s2_unknown and s2_dup
check(
    "S2 対象セクション特定・一意性 (find_target_section: MV-01→唯一の.sec範囲[HERO限定]・未知→(None,unknown)・重複→(None,duplicate))",
    s2,
    f"HERO範囲一意={s2_hero_span}, 範囲がHERO限定={s2_hero_scope}, "
    f"未知→unknown={s2_unknown}, 重複→duplicate={s2_dup}",
)

# ===========================================================================
# S3 配色5変数を対象HTMLから読む（read_root_palette・instruction.json ではない・U-2）
# ===========================================================================
pal = bridge.read_root_palette(BEFORE)
expected = {
    "--m-main": "#2e7d6b", "--m-nav": "#24463e", "--m-accent": "#e8a33d",
    "--m-bg": "#f7f5f0", "--m-text": "#333",
}
s3_all = all(pal.get(k) == v for k, v in expected.items())
s3_keys = set(pal.keys()) >= set(PALETTE_VARS)
s3 = s3_all and s3_keys
check(
    "S3 配色5変数を対象HTMLから読む (read_root_palette: .mock ルート定義の --m-* 実値を抽出・指示書非依存)",
    s3,
    f"5変数一致={s3_all}(読取={pal}), 5キー網羅={s3_keys}",
)

# ===========================================================================
# S4 保存パス解決（上書き・resolve_target_html・U-4 / U-5）
# ===========================================================================
rth = bridge.resolve_target_html
FOLD = "mockups/2026-07-08_案件"
s4_a = rth(FOLD, "a") == FOLD + "/index-a.html"
s4_c = rth(FOLD, "c") == FOLD + "/index-c.html"
s4_none = rth(FOLD, None) == FOLD + "/index.html"
s4_empty = rth(FOLD, "") == FOLD + "/index.html"
s4 = s4_a and s4_c and s4_none and s4_empty
check(
    "S4 保存パス解決 (resolve_target_html: letter=a→index-a.html / None・''→index.html を決定論構築)",
    s4,
    f"a→index-a={s4_a}, c→index-c={s4_c}, None→index={s4_none}, ''→index={s4_empty}",
)

# ===========================================================================
# S5 再生成コマンド最小権限（build_regenerate_command・危険フラグ非含有・U-5 / NFR-005）
# ===========================================================================
brc = bridge.build_regenerate_command
cmd = brc("mockups/.pending/x.regen.json")
cmd_flat = " ".join(cmd)
s5_base = (cmd[:2] == ["claude", "-p"]
           and "/draft-regenerate mockups/.pending/x.regen.json" in cmd
           and "--permission-mode" in cmd and "acceptEdits" in cmd
           and "--output-format" in cmd and "json" in cmd)
s5_no_danger = not any(f in cmd_flat for f in DANGER_FLAGS)
s5_no_open_default = "--allowedTools" not in cmd
cmd_open = brc("/x.regen.json", allow_open=True)
s5_open = ("--allowedTools" in cmd_open and "Bash(open *)" in cmd_open
           and not any(f in " ".join(cmd_open) for f in DANGER_FLAGS))
s5 = s5_base and s5_no_danger and s5_no_open_default and s5_open
check(
    "S5 再生成コマンド最小権限 (build_regenerate_command: /draft-regenerate {path} --permission-mode acceptEdits --output-format json・危険フラグ非含有・allow_openでopenのみ追加)",
    s5,
    f"基本形={s5_base}, 危険フラグ非含有={s5_no_danger}, 既定open非付与={s5_no_open_default}, allow_open時open追加={s5_open}",
)

# ===========================================================================
# S6 /regenerate ルーティング＋検証（claude 起動前に一意性確認・ファイル無変更・SPEC §7）
# ===========================================================================
# do_POST に /regenerate 分岐がある
s6_route = re.search(r'path\s*==\s*["\']/regenerate["\']', BRIDGE_SRC) is not None \
    and re.search(r"self\._regenerate\(\)", BRIDGE_SRC) is not None
# _regenerate が定義され、防御が静的に存在（Origin 403 / サイズ 413 / 検証 400 / 一意性 404,400）
_ri = BRIDGE_SRC.find("def _regenerate")
_seg = BRIDGE_SRC[_ri:] if _ri >= 0 else ""
s6_origin = ("is_allowed_origin(" in _seg and "403" in _seg)
s6_size = ("MAX_BODY_BYTES" in _seg and "413" in _seg)
s6_valid = ("is_safe_mockups_folder(" in _seg and "is_valid_letter(" in _seg
            and "is_valid_addr(" in _seg)
s6_missing = re.search(r"os\.path\.isfile\(", _seg) is not None and "404" in _seg
s6_unique = ("find_target_section(" in _seg
             and re.search(r'"unknown"', _seg) is not None
             and re.search(r'"duplicate"', _seg) is not None)
# claude 起動(worker/build_regenerate_command)は一意性判定より後（起動前にファイル無変更）
_uniq_idx = _seg.find("find_target_section(")
_worker_idx = _seg.find("_run_regen_job")
_brc_idx = _seg.find("job_id = uuid")
s6_order = (0 <= _uniq_idx < _worker_idx) and (0 <= _uniq_idx < _brc_idx)
s6 = s6_route and s6_origin and s6_size and s6_valid and s6_missing and s6_unique and s6_order
check(
    "S6 /regenerate ルーティング＋検証 (do_POST に /regenerate 分岐・_regenerate で Origin403/サイズ413/folder/letter/addr検証400/isfile404/一意性 unknown404・duplicate400 を claude起動前に実施)",
    s6,
    f"分岐={s6_route}, Origin403={s6_origin}, サイズ413={s6_size}, 3検証={s6_valid}, "
    f"不在404={s6_missing}, 一意性判定={s6_unique}, 起動前判定順序={s6_order}",
)

# ===========================================================================
# S7 Origin/localhost/サイズ上限の再利用＋プロンプトは pending パスのみ（KLK-010/011 継承）
# ===========================================================================
s7_call = re.search(
    r"is_allowed_origin\(\s*self\.headers\.get\(\s*[\"']Origin[\"']\s*\)\s*,\s*BRIDGE_HOST\s*,\s*port\s*\)",
    _seg) is not None
s7_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
s7_maxbody = "MAX_BODY_BYTES" in _seg
# プロンプトに載る可変値は bridge 生成 pending パスのみ（build_regenerate_command は
# pending_path のみを受け、folder/addr を直挿ししない）。_run_regen_job が
# build_regenerate_command(pending_path) を使う。
s7_prompt = re.search(r"build_regenerate_command\(\s*pending_path\s*\)", BRIDGE_SRC) is not None
# .regen.json（検証済みジョブ仕様）を pending へ書く（プロンプトはそのパスのみ）
s7_pending = ".regen.json" in _seg and "design-regenerate-job" in _seg
s7 = s7_call and s7_host and s7_maxbody and s7_prompt and s7_pending
check(
    "S7 Origin/localhost/サイズ再利用 (_regenerate が is_allowed_origin(Origin,BRIDGE_HOST,port)・MAX_BODY_BYTES を用い・BRIDGE_HOST==127.0.0.1・build_regenerate_command(pending_path) のみでプロンプトに可変値非混入)",
    s7,
    f"Origin呼出形={s7_call}, 127.0.0.1={s7_host}, MAX_BODY={s7_maxbody}, "
    f"pendingパスのみ={s7_prompt}, .regen.json書出し={s7_pending}",
)

# ===========================================================================
# S8 before/after 不変保持（中核）— MV-01 のみ差分・他は等価（U-2 / SPEC §7 / REQ-103）
# ===========================================================================
# (a) 配色5変数が同一
pal_before = bridge.read_root_palette(BEFORE)
pal_after = bridge.read_root_palette(AFTER)
s8_pal = (pal_before == pal_after
          and all(k in pal_before for k in PALETTE_VARS))
# (b) data-columns が同一


def _dcol(h):
    m = re.search(r'data-columns="([^"]*)"', h)
    return m.group(1) if m else None


s8_dcol = _dcol(BEFORE) == _dcol(AFTER) and _dcol(BEFORE) is not None
# (c) 6番地ラベルの集合が同一で全て存在


def _addrs(h):
    return set(re.findall(r'<span class="pin">([A-Z0-9-]+)</span>', h))


s8_addr = (_addrs(BEFORE) == _addrs(AFTER) == set(ADDR6))
# (d) <head>…</head>（CSS＋アニメ script の CSS 部）が同一


def _head(h):
    m = re.search(r"<head>.*?</head>", h, re.DOTALL)
    return m.group(0) if m else None


s8_head = _head(BEFORE) == _head(AFTER) and _head(BEFORE) is not None
# (e) MV-01 以外の5 .sec ブロックがバイト等価 /（f）HERO は差分だが pin 保持
sec_equal = {}
hero_diff = None
hero_pin_kept = None
for addr in ADDR6:
    sb, eb = fts(BEFORE, addr)   # (start, end) 文字範囲 or (None, info)
    sa, ea = fts(AFTER, addr)
    if sb is None or sa is None:
        sec_equal[addr] = False
        continue
    block_b = BEFORE[sb:eb]
    block_a = AFTER[sa:ea]
    if addr == "MV-01":
        hero_diff = (block_b != block_a)
        hero_pin_kept = ('<span class="pin">MV-01</span>' in block_a
                         and 'class="sec' in block_a and 'class="addr"' in block_a)
    else:
        sec_equal[addr] = (block_b == block_a)
s8_others = all(sec_equal.get(a, False) for a in ADDR6 if a != "MV-01")
s8_hero = bool(hero_diff) and bool(hero_pin_kept)
s8 = s8_pal and s8_dcol and s8_addr and s8_head and s8_others and s8_hero
check(
    "S8 before/after 不変保持 (配色5変数=同一・data-columns=同一・6番地=同一集合・<head>=同一・HERO以外5.sec=バイト等価・HERO=差分だが pin/.sec/.addr 保持)",
    s8,
    f"配色={s8_pal}, data-columns={s8_dcol}({_dcol(BEFORE)}), 6番地={s8_addr}, head={s8_head}, "
    f"他5.sec等価={s8_others}({ {a: sec_equal.get(a) for a in ADDR6 if a != 'MV-01'} }), "
    f"HERO差分={hero_diff}, HERO_pin保持={hero_pin_kept}",
)

# ===========================================================================
# S9 新スキル /draft-regenerate 規約（入力2経路・手順・保持不変・上書き・停止・U-1〜U-4）
# ===========================================================================
sk_fm = ("name: draft-regenerate" in REGEN_SKILL and "REQ-103" in REGEN_SKILL)
sk_two = (".regen.json" in REGEN_SKILL and "$ARGUMENTS" in REGEN_SKILL
          and "design-regenerate-job" in REGEN_SKILL)
sk_steps = ("受付" in REGEN_SKILL and "書き戻し" in REGEN_SKILL and "報告" in REGEN_SKILL)
# 配色は対象HTMLから読む（instruction.json からは読まない）
sk_pal = ("instruction.json" in REGEN_SKILL
          and ("対象HTML" in REGEN_SKILL or "対象 `index" in REGEN_SKILL)
          and "読まない" in REGEN_SKILL)
sk_invariant = ("data-columns" in REGEN_SKILL and "番地ラベル" in REGEN_SKILL
                and "<head>" in REGEN_SKILL and "script" in REGEN_SKILL
                and "他5" in REGEN_SKILL)
sk_overwrite = "上書き" in REGEN_SKILL
sk_rules = "DRAFT_RULES" in REGEN_SKILL and "§14" in REGEN_SKILL
sk_stop = (("未知" in REGEN_SKILL or "見つから" in REGEN_SKILL) and "重複" in REGEN_SKILL
           and "§7" in REGEN_SKILL and "変更せず" in REGEN_SKILL)
s9 = (sk_fm and sk_two and sk_steps and sk_pal and sk_invariant
      and sk_overwrite and sk_rules and sk_stop)
check(
    "S9 新スキル規約 (draft-regenerate/SKILL.md: 入力2経路[.regen.json/$ARGUMENTS]・手順[受付→書き戻し→報告]・配色は対象HTMLから[指示書から読まない]・保持不変[data-columns/番地/head/script/他5]・上書き・DRAFT_RULES §14参照・未知/重複で停止 SPEC §7)",
    s9,
    f"frontmatter={sk_fm}, 2経路={sk_two}, 手順={sk_steps}, 配色は対象HTML={sk_pal}, "
    f"保持不変={sk_invariant}, 上書き={sk_overwrite}, DRAFT_RULES参照={sk_rules}, 停止規約={sk_stop}",
)

# ===========================================================================
# S10 UI導線（compare.html の🔄・DRAFT_RULES §13/§14＋draft-generate SKILL・ゴールデン）
# ===========================================================================
# ゴールデン compare-regen.html: 番地 select ＋ 再生成ボタン ＋ health-gated fetch ＋ graceful ＋ data-folder
g_select = ("<select" in COMPARE and "regenAddr" in COMPARE
            and all(a in COMPARE for a in ADDR6))
g_btn = "regenBtn" in COMPARE and "再生成" in COMPARE
g_fetch = "/regenerate" in COMPARE and "/health" in COMPARE and "/status/" in COMPARE
g_health_gate = "probeHealth" in COMPARE and "AbortController" in COMPARE
g_graceful = ("disableWithGuidance" in COMPARE
              and ("未起動" in COMPARE or "graceful" in COMPARE)
              and "/draft-regenerate" in COMPARE)
g_folder = 'data-folder="mockups/' in COMPARE
g_checked = "input[name=variant]:checked" in COMPARE
g_ext = _external_urls(COMPARE)
g_local_only = ("127.0.0.1" in COMPARE and not g_ext)
s10_golden = (g_select and g_btn and g_fetch and g_health_gate and g_graceful
              and g_folder and g_checked and g_local_only)
# DRAFT_RULES §13 に🔄導線が additive 記述され、§14 部分再生成規約が存在
dr_regen = ("🔄" in DRAFT_RULES and "セクション再生成" in DRAFT_RULES
            and "data-folder" in DRAFT_RULES and "/regenerate" in DRAFT_RULES
            and "/health" in DRAFT_RULES and "graceful" in DRAFT_RULES)
dr_s14 = ("## 14" in DRAFT_RULES and "部分再生成" in DRAFT_RULES
          and "保持すべき不変" in DRAFT_RULES and "上書き" in DRAFT_RULES)
# draft-generate SKILL に🔄導線を焼き込む旨（additive）
gs_regen = ("🔄" in GEN_SKILL and "/regenerate" in GEN_SKILL
            and "data-folder" in GEN_SKILL)
s10 = s10_golden and dr_regen and dr_s14 and gs_regen
check(
    "S10 UI導線 (compare-regen.html: 番地select＋🔄ボタン＋health-gated fetch(/regenerate,/status,/health)＋graceful(手動案内)＋data-folder＋checkedラジオ・外部URL0; DRAFT_RULES §13🔄導線＋§14部分再生成規約; draft-generate SKILL に🔄焼込み追記)",
    s10,
    f"golden(select={g_select},btn={g_btn},fetch={g_fetch},health={g_health_gate},"
    f"graceful={g_graceful},folder={g_folder},checked={g_checked},外部URL0={not g_ext}[{g_ext or 0}]), "
    f"DRAFT_RULES§13={dr_regen}, DRAFT_RULES§14={dr_s14}, genSKILL={gs_regen}",
)

# ===========================================================================
# S11 セキュリティ/依存（S-SEC）— 外部URL0・秘密0・危険フラグ非含有・shell=True/0.0.0.0非使用
# ===========================================================================
# 対象: bridge.py・draft-regenerate SKILL・klk012 ゴールデン3ファイル
scope_all = {
    "bridge.py": BRIDGE_SRC, "draft-regenerate/SKILL.md": REGEN_SKILL,
    "index-a-before.html": BEFORE, "index-a-after.html": AFTER,
    "compare-regen.html": COMPARE,
}
ext_hits = {n: _external_urls(t) for n, t in scope_all.items()}
ext_hits = {n: v for n, v in ext_hits.items() if v}
# 秘密: bridge/ゴールデンは loose 走査（実際の値も語も0）。SKILL は禁止事項の散文に
# 秘密語を含むのが正常なため、実際の“値”パターンのみで走査する（誤検知回避）。
sec_hits = {}
for n, t in scope_all.items():
    hits = _secret_value_hits(t) if n.endswith("SKILL.md") else _secret_hits(t)
    if hits:
        sec_hits[n] = hits
danger = [f for f in DANGER_FLAGS if f in BRIDGE_SRC or f in REGEN_SKILL or f in COMPARE]
b_shell = "shell=True" in BRIDGE_SRC
b_wildcard = ('"0.0.0.0"' in BRIDGE_SRC) or ("'0.0.0.0'" in BRIDGE_SRC)
s11 = (not ext_hits and not sec_hits and not danger
       and not b_shell and not b_wildcard)
check(
    "S11 S-SEC (bridge.py/draft-regenerate SKILL/klk012 ゴールデン: 外部URL0[local/placeholder除外]・秘密0[SKILLは値パターン]・危険フラグ非含有・shell=True非使用・0.0.0.0リテラル非使用)",
    s11,
    f"外部URL={ext_hits or 0}, 秘密={sec_hits or 0}, 危険フラグ={danger or 0}, "
    f"shellTrue={b_shell}, 0.0.0.0リテラル={b_wildcard}",
)

# ===========================================================================
# S12 既存回帰の保持（縦串静的）— bridge 純関数/定数・SKILL/DRAFT_RULES 既存依存文字列
# ===========================================================================
# bridge.py の既存純関数・定数が残存
b_funcs = all(callable(getattr(bridge, fn, None)) for fn in
              ("build_claude_command", "is_allowed_origin", "validate_instruction",
               "select_open_target", "build_open_command"))
b_maxbody = isinstance(getattr(bridge, "MAX_BODY_BYTES", None), int) \
    and not isinstance(getattr(bridge, "MAX_BODY_BYTES", None), bool)
b_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
# 既存 /generate 経路が残存（回帰保護）
b_generate = re.search(r'path\s*==\s*["\']/generate["\']', BRIDGE_SRC) is not None \
    and BRIDGE_SRC.find("def _generate") >= 0
# draft-generate SKILL の既存依存文字列（version==1 不変・schema・保存規約）
gs_ver = (re.search(r"`version`[^\n]*`1`", GEN_SKILL) is not None) and "不変" in GEN_SKILL
gs_schema = "design-draft-instruction" in GEN_SKILL
gs_save = ("index.html" in GEN_SKILL and "instruction.json" in GEN_SKILL
           and "mockups/" in GEN_SKILL)
# DRAFT_RULES §13 の既存構造規約（隠しラジオ/iframe/@media print）が残存
dr_radio = 'name="variant"' in DRAFT_RULES
dr_iframe = "iframe" in DRAFT_RULES
dr_print = "@media print" in DRAFT_RULES
s12 = (b_funcs and b_maxbody and b_host and b_generate
       and gs_ver and gs_schema and gs_save and dr_radio and dr_iframe and dr_print)
check(
    "S12 既存回帰の保持 (bridge 既存純関数/定数[build_claude_command/is_allowed_origin/MAX_BODY_BYTES/BRIDGE_HOST==127.0.0.1/_generate]残存・draft-generate SKILL[version1不変/schema/保存規約]・DRAFT_RULES §13[name=variant/iframe/@media print]の依存文字列を削除していない)",
    s12,
    f"bridge純関数={b_funcs}, MAX_BODY={b_maxbody}, 127.0.0.1={b_host}, /generate残存={b_generate}, "
    f"SKILL(version1不変={gs_ver},schema={gs_schema},保存規約={gs_save}), "
    f"DRAFT_RULES(radio={dr_radio},iframe={dr_iframe},print={dr_print})",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-012 static/core acceptance checks (docs/designs/KLK-012.md §9 S群 S1-S12 を正とする)")
print("対象: draft-gen/bridge.py(import 純関数 + ソース静的) + draft-regenerate/SKILL.md +")
print("      DRAFT_RULES.md + draft-generate/SKILL.md + tests/fixtures/klk012/*.html(ゴールデン)")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print(f"[{status}] {name}")
    print(f"        {detail}")
print("-" * 78)
print(f"{len(results)} checks, {failed} failed")
print()
print("D群（test_palette_klk012.py で discover 回帰・git check-ignore・/regenerate 実HTTP疎通）:")
print("  - D1 Quality Gate 全緑（python3 -m unittest discover -s tests・KLK-006〜011 回帰なし）")
print("  - D2 mockups/.pending/*.regen.json・mockups/{…}/index-a.html の Git 除外成立")
print("  - /regenerate 実HTTP疎通（別オリジン403・巨大body413・traversal/検証400・不在/unknown404・")
print("    duplicate400＝claude 非起動・.regen.json 未作成・対象ファイル無変更）")
print()
print("M群（環境制約で静的検証外 = tester がブリッジ起動＋実 /draft-regenerate＋ブラウザで手動確認）:")
print("  - M1 実部分再生成: MV-01 のみ自然に差替・他5セクション/配色5変数/data-columns/番地/head/script 保持")
print("  - M2 番地エラー（未知/重複）でラフを壊さない（400/404 or スキル停止案内・ファイル無変更）")
print("  - M3 compare.html の🔄導線（ブリッジ経由起動＋更新版再表示・非稼働時 graceful フォールバック）")
print("  - M4 上書き後の再オープン再表示（compare.html or 対象 index-{letter}.html）")
print("  - M5 手動スキル経路 /draft-regenerate {folder} {letter} {addr} も M1 と同結果")
print("  - M6 別オリジン403・巨大body413・traversal400（claude 起動しない・生成物/一時ファイル Git 非管理）")
sys.exit(1 if failed else 0)
