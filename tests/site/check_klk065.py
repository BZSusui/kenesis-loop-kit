#!/usr/bin/env python3
"""
KLK-065 acceptance-condition checker (static + 純関数の実行 / no browser required).

Verifies Q1-Q9 from docs/designs/KLK-065.md §4.4 / §9:
提案フェーズが `sips` のコマンド承認待ちで停止し、提案が1件も作られなかった不具合の修正。

  縦串 ブリッジ  draft-gen/bridge.py     （build_catalog_import_command の allowedTools）
  縦串 スキル    catalog-import/SKILL.md （提案モードでの非対話規律）
  縦串 SCR-004   draft-gen/catalog.html  （提案0件のときに無言で終わらない）

★この checker が守っているもの:
  **非対話（claude -p）で走らせる経路に、対話を必要とするゲートを置いてはならない。**
  人間への質問（KLK-064）でもコマンド承認（KLK-065）でも、結果は同じ
  「成功したように見えて何もしていない」状態になる。3層（権限・スキル規律・UI）で塞ぐ。

Run: python3 tests/site/check_klk065.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# Q1-Q4 権限（純関数を実行して検証）
# ---------------------------------------------------------------------------
cmd = bridge.build_catalog_import_command("catalog/.pending/x.import.json")
cmd_open = bridge.build_catalog_import_command("catalog/.pending/x.import.json", allow_open=True)


def allowed_tools(c):
    return c[c.index("--allowedTools") + 1] if "--allowedTools" in c else ""


check(
    "Q1 build_catalog_import_command が --allowedTools に Bash(sips *) を含む",
    "--allowedTools" in cmd and "Bash(sips *)" in allowed_tools(cmd),
    "allowedTools=%r" % allowed_tools(cmd),
)
check(
    "Q2 allow_open=True で Bash(open *) も含み、1つの --allowedTools にまとまる",
    cmd_open.count("--allowedTools") == 1
    and "Bash(sips *)" in allowed_tools(cmd_open)
    and "Bash(open *)" in allowed_tools(cmd_open),
    "allowedTools=%r / --allowedTools の出現=%d" % (allowed_tools(cmd_open), cmd_open.count("--allowedTools")),
)
DANGEROUS = ["--dangerously-skip-permissions", "--permission-mode=bypassPermissions",
             "bypassPermissions", "--allow-all", "--yolo"]
hits = [d for d in DANGEROUS if any(d in str(x) for x in cmd_open)]
check(
    "Q3 危険な全許可フラグを含まない（最小権限の維持・既存3関数と同一方針）",
    not hits and "acceptEdits" in cmd_open,
    "危険フラグ=%s / permission-mode=acceptEdits=%s" % (hits or "なし", "acceptEdits" in cmd_open),
)
gen = bridge.build_claude_command("mockups/.pending/x.json")
regen = bridge.build_regenerate_command("mockups/.pending/x.json")
check(
    "Q4 生成・再生成のコマンドには sips を足していない（影響の局所性）",
    "Bash(sips *)" not in allowed_tools(gen) and "Bash(sips *)" not in allowed_tools(regen),
    "generate=%r / regenerate=%r" % (allowed_tools(gen) or "なし", allowed_tools(regen) or "なし"),
)

# ---------------------------------------------------------------------------
# Q5-Q7 スキルの非対話規律
# ---------------------------------------------------------------------------
# 「提案モード」は §起動と入力 でも触れられるため、**手順3' の節**を範囲にする
# （初出から数千字では手順3' の規律まで届かず、検査が空振りする）。
_i = SKILL.find("### 3'. 提案モード")
_j = SKILL.find("### 3. 人間確認", _i) if _i >= 0 else -1
SEG = SKILL[_i:_j] if (_i >= 0 and _j > _i) else SKILL
check(
    "Q5 SKILL.md の提案モードに「人間に質問してはならない」が明記されている",
    "質問してはならない" in SEG,
    "明記=%s" % ("質問してはならない" in SEG),
)
check(
    "Q6 SKILL.md に「1件も処理できなくても items: [] を必ず書き出す」が明記されている",
    "items: []" in SEG and "必ず書き出して終了する" in SEG,
    "items:[]=%s / 必ず書き出す=%s" % ("items: []" in SEG, "必ず書き出して終了する" in SEG),
)
check(
    "Q7 SKILL.md に「処理できない画像は外して残りを出力する」が明記されている",
    "提案から外して残りを出力する" in SEG,
    "明記=%s" % ("提案から外して残りを出力する" in SEG),
)

# ---------------------------------------------------------------------------
# Q8-Q9 UI（無言で終わらせない）
# ---------------------------------------------------------------------------
_i = CATHTML.find('if (j.state === "done")')
DONE = CATHTML[_i:_i + 1400] if _i >= 0 else ""
check(
    "Q8 SCR-004 が提案0件のときに理由と次の手を表示する（無言で終わらない）",
    bool(DONE) and "else {" in DONE and "タグ付け案を作れませんでした" in DONE
    and "/catalog-import" in DONE,
    "else 分岐=%s / メッセージ=%s / 代替手段の案内=%s"
    % ("else {" in DONE, "タグ付け案を作れませんでした" in DONE, "/catalog-import" in DONE),
)
check(
    "Q9 SCR-004 が取り込み完了後に refreshPendingCount() を呼ぶ（件数を実態へ）",
    "refreshPendingCount();" in DONE,
    "呼び出し=%s" % ("refreshPendingCount();" in DONE),
)

print("=" * 78)
print("KLK-065 提案フェーズの承認待ち停止の修正（非対話実行での質問禁止）静的チェック")
print("対象: bridge.py（allowedTools）/ catalog-import SKILL（非対話規律）/ SCR-004（無言禁止）")
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
