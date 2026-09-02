#!/usr/bin/env python3
"""
KLK-071 acceptance-condition checker (static / no browser required).

Verifies S1-S12 from docs/designs/KLK-071.md §4.5 / §9:
見本となる生成ページの同梱（samples/ 新設・既存 mockups の整理）。

  縦串 見本      samples/*/（実際にツールで生成した成果物）
  縦串 配布      tools/make-package.sh（見本を含めるか）
  縦串 案内      README.md / samples/README.md
  縦串 除外設定  .gitignore（samples は追跡・mockups は除外を維持）

★この checker が守っているもの:
  見本は **配布物の一部**（追跡対象・ダミー案件名・カタログ非依存）であり、
  `mockups/`（利用者の作業場・Git除外・案件名を含む機密）とは役割が違う。
  この線引きが崩れると、見本が配布物に入らない／実在の案件名が配られる、のどちらかが起きる。

Run: python3 tests/site/check_klk071.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLES = os.path.join(ROOT, "samples")
SCRIPT = open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()
README = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
GITIGNORE = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def sample_dirs():
    if not os.path.isdir(SAMPLES):
        return []
    return sorted(
        os.path.join(SAMPLES, n) for n in os.listdir(SAMPLES)
        if os.path.isdir(os.path.join(SAMPLES, n))
    )


DIRS = sample_dirs()

# ---------------------------------------------------------------------------
# S1-S2 見本の中身
# ---------------------------------------------------------------------------
incomplete = []
for d in DIRS:
    for f in ("index-a.html", "instruction.json"):
        if not os.path.isfile(os.path.join(d, f)):
            incomplete.append(os.path.basename(d) + "/" + f)
check(
    "S1 samples/ に見本が3点以上あり、各々に index-a.html と instruction.json がある",
    len(DIRS) >= 3 and not incomplete,
    "見本=%d件 %s / 欠落=%s"
    % (len(DIRS), [os.path.basename(d) for d in DIRS], incomplete or "なし"),
)

bad_compare = []
for d in DIRS:
    p = os.path.join(d, "compare.html")
    if not os.path.isfile(p):
        bad_compare.append(os.path.basename(d) + ": compare.html なし")
        continue
    body = open(p, encoding="utf-8").read()
    if 'name="variant"' not in body:
        bad_compare.append(os.path.basename(d) + ": 案切り替えなし")
    if 'name="vw"' not in body:
        bad_compare.append(os.path.basename(d) + ": 幅切り替えなし")
check(
    "S2 各見本の compare.html が案切り替えと幅切り替えを持つ（生成規約に追随している）",
    bool(DIRS) and not bad_compare,
    "不備=%s" % (bad_compare or "なし"),
)

# ---------------------------------------------------------------------------
# S3 Git 追跡（配布物に入る）
# ---------------------------------------------------------------------------
if not shutil.which("git"):
    check("S3 見本が Git 追跡対象である [SKIP]", True, "git が無い")
else:
    ignored = []
    for d in DIRS:
        rel = os.path.relpath(os.path.join(d, "compare.html"), ROOT)
        proc = subprocess.run(["git", "check-ignore", rel],
                              capture_output=True, text=True, cwd=ROOT, timeout=60)
        if proc.returncode == 0:
            ignored.append(rel)
    check(
        "S3 見本が Git 追跡対象である（除外されていない＝配布物に入る）",
        bool(DIRS) and not ignored,
        "除外されている見本=%s" % (ignored or "なし"),
    )

# ---------------------------------------------------------------------------
# S4-S5 案件名とカタログ依存
# ---------------------------------------------------------------------------
bad_name, cat_dep = [], []
for d in DIRS:
    p = os.path.join(d, "instruction.json")
    if not os.path.isfile(p):
        continue
    try:
        inst = json.load(open(p, encoding="utf-8"))
    except ValueError:
        bad_name.append(os.path.basename(d) + ": JSON 不正")
        continue
    proj = ((inst.get("meta") or {}).get("project") or "")
    if not proj.startswith("サンプル"):
        bad_name.append("%s: project=%r" % (os.path.basename(d), proj))
    thumbs = ((inst.get("references") or {}).get("thumbnails") or [])
    if thumbs:
        cat_dep.append("%s: thumbnails=%d件" % (os.path.basename(d), len(thumbs)))
check(
    "S4 見本の案件名がダミー（「サンプル」で始まる＝実在を思わせない）",
    bool(DIRS) and not bad_name,
    "違反=%s" % (bad_name or "なし"),
)
check(
    "S5 見本がカタログ非依存（references.thumbnails が空）",
    bool(DIRS) and not cat_dep,
    "カタログ依存=%s" % (cat_dep or "なし"),
)

# ---------------------------------------------------------------------------
# S6-S7 生成規約（外部依存ゼロ・レスポンシブ）
# ---------------------------------------------------------------------------
# ローカルブリッジ（127.0.0.1）・プレースホルダ・w3.org は「外部依存」ではない。
# DRAFT_RULES §13 が「localhost fetch は §1 が禁じる外部CDN/フォント/画像ではない（外部URL 0 を保つ）」と
# 明記しており、compare.html の 🔄 再生成コントロールは正当にこれを使う。
# 既存 checker（check_klk012/013 の _external_urls）と同じ除外規則に合わせる。
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}
_ALLOW_HOSTS = {"www.w3.org", "w3.org", "example.com", "example.org", "example.net"}


def _external_urls(txt):
    out = []
    for m in re.findall(r'https?://[^\s"\')（]+', txt):
        host = m.split("//", 1)[1].split("/", 1)[0] if "//" in m else ""
        noport = host.split(":", 1)[0]
        if not host or noport in _LOCAL_HOSTS or noport in _ALLOW_HOSTS:
            continue
        if "{" in host or "%" in host:   # format プレースホルダ
            continue
        out.append(m)
    return out


ext_hits, not_responsive = [], []
for d in DIRS:
    for n in os.listdir(d):
        if not n.endswith(".html"):
            continue
        body = open(os.path.join(d, n), encoding="utf-8").read()
        for u in _external_urls(body):
            ext_hits.append("%s/%s: %s" % (os.path.basename(d), n, u))
        # 空白ゆれに強くする: 実際の生成物は "@media (max-width:640px)" とスペース無しで書く。
        # DRAFT_RULES 自体も §8 は空白あり・§12 は空白なしで記載しており、どちらも正しい CSS。
        # 文字列一致で固定すると「実物は正しいのにテストが落ちる」ことになる。
        if n.startswith("index-") and not re.search(r"@media\s*\(\s*max-width\s*:\s*640px\s*\)", body):
            not_responsive.append("%s/%s" % (os.path.basename(d), n))
check(
    "S6 見本に外部URL参照が無い（NFR-005・ローカルブリッジ127.0.0.1は対象外）",
    bool(DIRS) and not ext_hits,
    "外部URL=%s" % (ext_hits[:3] or "なし"),
)
check(
    "S7 見本の各案がレスポンシブ（max-width:640px のメディアクエリを持つ・空白ゆれ許容）",
    bool(DIRS) and not not_responsive,
    "非レスポンシブ=%s" % (not_responsive or "なし"),
)

# ---------------------------------------------------------------------------
# S8 samples/README.md
# ---------------------------------------------------------------------------
sreadme_path = os.path.join(SAMPLES, "README.md")
SREADME = open(sreadme_path, encoding="utf-8").read() if os.path.isfile(sreadme_path) else ""
check(
    "S8 samples/README.md に 🔄 が使えない旨と、案件名がダミーである旨がある",
    "🔄 セクション再生成は、見本では使えません" in SREADME and "ダミー" in SREADME,
    "🔄の注意=%s / ダミーの明記=%s"
    % ("🔄 セクション再生成は、見本では使えません" in SREADME, "ダミー" in SREADME),
)

# ---------------------------------------------------------------------------
# S9-S10 配布と導線
# ---------------------------------------------------------------------------
check(
    "S9 make-package.sh が samples を含める",
    re.search(r"for d in [^\n]*\bsamples\b", SCRIPT) is not None,
    "コピー対象に samples=%s" % (re.search(r"for d in [^\n]*\bsamples\b", SCRIPT) is not None),
)
check(
    "S10 README に見本への導線がある",
    "## まず見本を開いてみる" in README and "samples/01" in README,
    "見出し=%s / パス言及=%s"
    % ("## まず見本を開いてみる" in README, "samples/01" in README),
)

# ---------------------------------------------------------------------------
# S11-S12 mockups の整理と除外設定
# ---------------------------------------------------------------------------
MOCK = os.path.join(ROOT, "mockups")
leftovers = []
if os.path.isdir(MOCK):
    leftovers = [n for n in os.listdir(MOCK)
                 if os.path.isdir(os.path.join(MOCK, n)) and not n.startswith(".")]
check(
    "S11 mockups/ に開発中の生成物が残っていない（利用者の作業場として空で配る）",
    not leftovers,
    "残存=%d件 %s" % (len(leftovers), leftovers[:5] or "なし"),
)
check(
    "S12 .gitignore が samples/ を除外せず、mockups/ の除外は維持している",
    not re.search(r"^\s*samples/\s*$", GITIGNORE, re.M)
    and re.search(r"^\s*mockups/\s*$", GITIGNORE, re.M) is not None,
    "samples 除外=%s / mockups 除外=%s"
    % (bool(re.search(r"^\s*samples/\s*$", GITIGNORE, re.M)),
       bool(re.search(r"^\s*mockups/\s*$", GITIGNORE, re.M))),
)

print("=" * 78)
print("KLK-071 見本となる生成ページの同梱 静的チェック")
print("対象: samples/ / make-package.sh / README / .gitignore / mockups の整理")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print("[%s] %s" % (status, name))
    print("        %s" % detail)
print("-" * 78)
print("%d checks, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
