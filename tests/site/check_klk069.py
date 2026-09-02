#!/usr/bin/env python3
"""
KLK-069 acceptance-condition checker (static + スクリプトの実行 / no browser required).

Verifies R1-R12 from docs/designs/KLK-069.md §4.2 / §9:
README とローカル配布パッケージ（Git ではなくフォルダを手渡しする方式）。

  縦串 README        README.md
  縦串 組み立て      tools/make-package.sh（**実際に実行して**出力を検証する）

★この checker が守っているもの:
  配布物に **社外秘を混ぜない**こと。`catalog/`（実績画像・案件名・第三者著作物）と
  `mockups/`（生成物・案件名）と `tickets/active|done`（作業ログ）は、
  既定では絶対に含まれてはならない。R7/R9/R11 がこれを実行結果で確かめる。

  R11 は一時ディレクトリへ**実際に組み立てて**検証する。`--with-catalog` は付けない
  （テストで社外秘を複製しないため）。

Run: python3 tests/site/check_klk069.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README_PATH = os.path.join(ROOT, "README.md")
SCRIPT_PATH = os.path.join(ROOT, "tools", "make-package.sh")
README = open(README_PATH, encoding="utf-8").read() if os.path.exists(README_PATH) else ""
SCRIPT = open(SCRIPT_PATH, encoding="utf-8").read() if os.path.exists(SCRIPT_PATH) else ""

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# R1-R5 README
# ---------------------------------------------------------------------------
SECTIONS = ["できること / できないこと", "動かすのに必要なもの", "はじめかた",
            "画面の使い分け", "実績カタログについて", "困ったときは", "取り扱いの注意"]
missing = [s for s in SECTIONS if ("## " + s) not in README]
check(
    "R1 README が空でなく、必須の節をすべて持つ",
    len(README) > 2000 and not missing,
    "文字数=%d / 欠落した節=%s" % (len(README), missing or "なし"),
)
check(
    "R2 README に動作前提（python3 / claude / VSCode）が書かれている",
    all(k in README for k in ("python3 --version", "claude --version", "VSCode")),
    "python3=%s / claude=%s / VSCode=%s"
    % ("python3 --version" in README, "claude --version" in README, "VSCode" in README),
)
# 「できないこと」に、実際に未実装な4点が書かれているか（機能追加時に FAIL して気づける）
_i = README.find("### できないこと")
CANT = README[_i:README.find("\n---", _i)] if _i >= 0 else ""
cant_items = {
    "見本サイトURL": "見本サイトのURL" in CANT and "反映されません" in CANT,
    "履歴画面": "履歴" in CANT and "未実装" in CANT,
    "MV写真の限定": "メインビジュアル1枚だけ" in CANT,
    "webp/macOS": "WebP" in CANT and "macOS" in CANT,
}
check(
    "R3 「できないこと」に実際に未実装の4点が書かれている",
    all(cant_items.values()),
    "内訳=%s" % cant_items,
)
check(
    "R4 README に catalog/.trash が自動で消えない旨がある",
    "catalog/.trash/" in README and "自動では消えません" in README,
    "退避先=%s / 自動削除しない旨=%s"
    % ("catalog/.trash/" in README, "自動では消えません" in README),
)
# 手順に出てくるパスが実在するか（README が現実とずれるのを防ぐ）
REFERENCED = ["draft-gen/bridge.py", "palette/index.html", "docs/SPEC.md",
              "CLAUDE.md", "tickets/Templates/"]
absent = [p for p in REFERENCED if p in README and not os.path.exists(os.path.join(ROOT, p))]
kigou = os.path.join(ROOT, "draft-gen", "起動.command")
check(
    "R5 README の手順に出てくるコマンド・パスが実在する",
    not absent and "起動.command" in README and os.path.exists(kigou),
    "実在しない参照=%s / 起動.command=%s" % (absent or "なし", os.path.exists(kigou)),
)

# ---------------------------------------------------------------------------
# R6-R10 スクリプト（静的）
# ---------------------------------------------------------------------------
check(
    "R6 tools/make-package.sh が存在し実行可能である",
    os.path.isfile(SCRIPT_PATH) and os.access(SCRIPT_PATH, os.X_OK),
    "存在=%s / 実行可能=%s" % (os.path.isfile(SCRIPT_PATH), os.access(SCRIPT_PATH, os.X_OK)),
)
check(
    "R7 カタログ同梱が既定 OFF で、明示フラグを要求する（安全側の既定）",
    "WITH_CATALOG=0" in SCRIPT and "--with-catalog" in SCRIPT
    and 'if [ "$WITH_CATALOG" -eq 1 ]' in SCRIPT,
    "既定OFF=%s / フラグ=%s / 分岐=%s"
    % ("WITH_CATALOG=0" in SCRIPT, "--with-catalog" in SCRIPT,
       'if [ "$WITH_CATALOG" -eq 1 ]' in SCRIPT),
)
check(
    "R8 --with-catalog のときだけ catalog/img と catalog.json をコピーする",
    re.search(r'if \[ "\$WITH_CATALOG" -eq 1 \];[\s\S]{0,400}catalog/img', SCRIPT) is not None
    and re.search(r'if \[ "\$WITH_CATALOG" -eq 1 \];[\s\S]{0,400}catalog\.json', SCRIPT) is not None,
    "img=%s / json=%s"
    % (re.search(r'if \[ "\$WITH_CATALOG" -eq 1 \];[\s\S]{0,400}catalog/img', SCRIPT) is not None,
       re.search(r'if \[ "\$WITH_CATALOG" -eq 1 \];[\s\S]{0,400}catalog\.json', SCRIPT) is not None),
)
# 危険な丸ごとコピーをしていないこと
check(
    "R9 リポジトリ全体を丸ごとコピーしていない（mockups・tickets の中身・.git を持っていかない）",
    "cp -R ." not in SCRIPT and 'cp -R "$ROOT"' not in SCRIPT
    and "cp -R mockups" not in SCRIPT and "cp -R tickets " not in SCRIPT
    and "cp -R .git" not in SCRIPT,
    "丸ごとコピーの痕跡=なし" if "cp -R ." not in SCRIPT else "★丸ごとコピーあり",
)
check(
    "R10 tickets/Templates を含める（ループを回すのに必要な雛形）",
    "tickets/Templates" in SCRIPT,
    "含む=%s" % ("tickets/Templates" in SCRIPT),
)
check(
    "R12 カタログを含めたときに社外秘の警告を出す",
    "社外秘" in SCRIPT and "誰に渡したかを記録" in SCRIPT,
    "警告=%s / 記録の依頼=%s" % ("社外秘" in SCRIPT, "誰に渡したかを記録" in SCRIPT),
)

# ---------------------------------------------------------------------------
# R11 スクリプトを実際に実行して出力を検証（--with-catalog は付けない）
# ---------------------------------------------------------------------------
if not (os.path.isfile(SCRIPT_PATH) and shutil.which("bash")):
    check("R11 スクリプトを実行して出力を検証 [SKIP]", True, "bash かスクリプトが無い")
else:
    tmp = tempfile.mkdtemp(prefix="klk069-")
    out = os.path.join(tmp, "pkg")
    try:
        proc = subprocess.run(["bash", SCRIPT_PATH, out],
                              capture_output=True, text=True, cwd=ROOT, timeout=180)
        must = ["draft-gen/bridge.py", "draft-gen/index.html", "draft-gen/catalog.html",
                "draft-gen/起動.command", "palette/index.html", "README.md", "CLAUDE.md",
                "agents/orchestrator.md", "docs/SPEC.md", "tickets/Templates/ticket.md",
                ".claude/skills/draft-generate/SKILL.md"]
        must_missing = [p for p in must if not os.path.exists(os.path.join(out, p))]
        forbidden = ["catalog/img", "catalog/catalog.json", ".git", "tests"]
        forbidden_present = [p for p in forbidden if os.path.exists(os.path.join(out, p))]
        mock = os.path.join(out, "mockups")
        mock_files = os.listdir(mock) if os.path.isdir(mock) else ["(mockups が無い)"]
        act = os.path.join(out, "tickets", "active")
        act_files = [n for n in (os.listdir(act) if os.path.isdir(act) else []) if n != ".gitkeep"]
        exec_ok = os.access(os.path.join(out, "draft-gen", "起動.command"), os.X_OK)
        ok = (proc.returncode == 0 and not must_missing and not forbidden_present
              and not mock_files and not act_files and exec_ok)
        check(
            "R11 スクリプトを実際に実行し、必須が揃い・除外対象が無いこと（--with-catalog なし）",
            ok,
            "exit=%d / 欠落=%s / 混入=%s / mockups=%s / tickets.active=%s / 起動.command実行可=%s"
            % (proc.returncode, must_missing or "なし", forbidden_present or "なし",
               mock_files or "空", act_files or "空", exec_ok),
        )
    except Exception as exc:
        check("R11 スクリプトを実際に実行し、必須が揃い・除外対象が無いこと", False, "実行失敗: %s" % exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print("=" * 78)
print("KLK-069 README とローカル配布パッケージ 静的チェック")
print("対象: README.md / tools/make-package.sh（実行して出力も検証）")
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
