#!/usr/bin/env python3
"""
KLK-088 acceptance-condition checker (static / no browser required).

ページ構成（composition）を**生成側**へ通す変更。規約（DRAFT_RULES）とスキル2本の改訂。
設計は docs/designs/KLK-086.md。

★このチェッカーが守っているもの:
  生成側は「規約に書いてあること」しか守らない。KLK-072〜076 で4回続けて
  「規約は正しいのに生成物が違う」を踏んだが、その手前に
  **「そもそも規約に書いていない」**という失敗もある。ここはそれを防ぐ。
  実際に守られたか（生成物が composition どおりか）は KLK-089 が実物で確かめる。

  A群 = §2 番地の採番 / B群 = §2.2 スキーマ / C群 = 型の決め方
  D群 = 不変条件の条件つき改訂 / E群 = スキル2本 / F群 = 後方互換の明記

Run: python3 tests/site/check_klk088.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = io.open(
    os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"),
    encoding="utf-8",
).read()
GEN = io.open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"),
              encoding="utf-8").read()
REGEN = io.open(os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md"),
                encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def seg(text, start, end):
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    return text[i:j if j > 0 else len(text)]


S201 = seg(RULES, "#### 2.0.1", "### 2.1")
S22 = seg(RULES, "### 2.2 ページ構成", "## 3. アタリ画像")
S1212 = seg(RULES, "**(3.1) インスタンス補正", "**(4) Claude の生成手順")
SINV = seg(RULES, "**★`composition` があるときの条件つき改訂", "#### 12.1.1")
S14 = seg(RULES, "## 14. 部分再生成規約", "\n## ")

# ===========================================================================
# A群 — §2 番地の採番
# ===========================================================================
check(
    "A1 §2.0.1 が「出現順に -01 -02 -03」を定めている",
    bool(S201) and "出現順に" in S201 and "-02" in S201 and "-03" in S201,
    "節=%s / 採番=%s" % (bool(S201), "出現順に" in S201),
)
check(
    "A2 §2.0.1 が「1個目は必ず -01」＝既存生成物と互換であることを明記",
    "1個目は必ず" in S201 and "完全互換" in S201,
    "互換の明記=%s" % ("完全互換" in S201),
)
check(
    "A3 §2.0.1 が番地のページ内一意性を要求している（🔄 が止まる理由つき）",
    "一意" in S201 and "重複" in S201,
    "一意性=%s" % ("一意" in S201),
)
check(
    "A4 §2.0.1 が NAV/MV/FOOTER を composition の対象外としている",
    "NAV-01" in S201 and "対象外" in S201,
    "対象外の明記=%s" % ("対象外" in S201),
)

# ===========================================================================
# B群 — §2.2 スキーマ
# ===========================================================================
check(
    "B1 §2.2 が新設され、composition の形を例つきで示している",
    bool(S22) and '"composition"' in S22 and '"key"' in S22 and '"type"' in S22,
    "節=%s（%d字）" % (bool(S22), len(S22)),
)
check(
    "B2 §2.2 が「配列の順＝ページの並び・全案共通」を定めている",
    "配列の順" in S22 and "全案共通" in S22,
    "並びの規定=%s" % ("配列の順" in S22),
)
check(
    "B3 §2.2 が「無ければ従来どおり」＝後方互換を明記している",
    "無ければ従来どおり" in S22 and "1バイトも解釈が変わらない" in S22,
    "後方互換=%s" % ("1バイトも解釈が変わらない" in S22),
)
check(
    "B4 §2.2 が上限（複製可11種・1個のみ3種・合計12）を表で示している",
    "本文合計" in S22 and "**12個**" in S22
    and all(k in S22 for k in ("ACCESS", "CONTACT", "SEARCH"))
    and "CTA" in S22,
    "上限表=%s" % ("本文合計" in S22),
)
check(
    "B5 §2.2 が CTA を複製可とし、その理由（上部と下部）を書いている",
    "CTA を複製できる" in S22 and "上部と下部" in S22,
    "CTA=%s" % ("CTA を複製できる" in S22),
)
check(
    "B6 §2.2 が SEARCH を並び順の対象外としている（HERO/NAV へ埋め込むため）",
    "SEARCH" in S22 and "埋め込む" in S22 and "並び順の影響を受けない" in S22,
    "SEARCH=%s" % ("並び順の影響を受けない" in S22),
)
check(
    "B7 §2.2 が sections と composition の食い違いで停止すると定めている",
    "受付チェックで停止" in S22,
    "停止=%s" % ("受付チェックで停止" in S22),
)
check(
    "B8 §2.2 が sectionOptions との優先関係を定めている（エントリ優先・CTA は共通）",
    "エントリ側が優先" in S22 and "全 CTA インスタンス共通" in S22,
    "優先関係=%s" % ("エントリ側が優先" in S22),
)

# ===========================================================================
# C群 — 型の決め方
# ===========================================================================
check(
    "C1 §12.1.2 にインスタンス補正 (idx+(k-1)) mod 6 がある",
    bool(S1212) and "(idx + (k-1)) mod 6" in S1212.replace("`", ""),
    "補正=%s" % ("(idx + (k-1)) mod 6" in S1212.replace("`", "")),
)
check(
    "C2 補正が3案とも同じ幅＝案間 distinct が保たれると説明している",
    "3案とも同じ幅" in S1212 and "distinct" in S1212,
    "説明=%s" % ("3案とも同じ幅" in S1212),
)
check(
    "C3 型を明示したインスタンスは補正の対象外と定めている",
    "補正の対象外" in S1212 and "全案で使う" in S1212,
    "明示優先=%s" % ("補正の対象外" in S1212),
)
check(
    "C4 明示型と補正結果の衝突時の決定的な解き方がある",
    "ぶつかったときは" in S1212 and "+1 ずつ送って" in S1212,
    "衝突解決=%s" % ("+1 ずつ送って" in S1212),
)
check(
    "C5 §12.2 参考準拠が第1インスタンス限定になっている",
    "第1インスタンス（`-01`）だけ" in RULES,
    "限定=%s" % ("第1インスタンス（`-01`）だけ" in RULES),
)
check(
    "C6 §14 の優先順位に composition が2段目として入っている",
    "**`composition` の当該インスタンスの `type`**（KLK-088）" in S14
    and "desiredType` があるときは 2〜4 を**見ない**" in S14,
    "優先順位=%s" % ("**`composition` の当該インスタンスの `type`**（KLK-088）" in S14),
)
check(
    "C7 §14 が出現順 k からエントリを引く手順を書いている",
    "出現順 k" in S14 and "k 番目のエントリ" in S14,
    "手順=%s" % ("出現順 k" in S14),
)

# ===========================================================================
# D群 — 不変条件の条件つき改訂
# ===========================================================================
check(
    "D1 不変条件の改訂表があり、composition 有無で分けている",
    bool(SINV) and "`composition` 無し" in SINV and "`composition` あり" in SINV,
    "改訂表=%s" % bool(SINV),
)
check(
    "D2 ⑤並び順が composition ありのとき全案同一へ反転している",
    "全案同一へ" in SINV,
    "反転=%s" % ("全案同一へ" in SINV),
)
check(
    "D3 ⑥〜⑨の型相違が「type を明示していない番地」に限定されている",
    "明示していない番地についてのみ" in SINV,
    "限定=%s" % ("明示していない番地についてのみ" in SINV),
)
check(
    "D4 ②セクション集合が多重集合として同一と明記されている",
    "多重集合" in SINV,
    "多重集合=%s" % ("多重集合" in SINV),
)
check(
    "D5 data-section-order が番地ベースへ拡張されている",
    "data-section-order` は**番地**を並べる" in SINV or "`ABOUT-01,MENU-01" in SINV,
    "番地ベース=%s" % ("`ABOUT-01,MENU-01" in SINV),
)
check(
    "D6 ⑤を反転させる理由が書かれている（原稿どおりと言えなくなる）",
    "原稿" in SINV and "配色とレイアウト型" in SINV,
    "理由=%s" % ("原稿" in SINV),
)

# ===========================================================================
# E群 — スキル2本
# ===========================================================================
check(
    "E1 draft-generate SKILL が composition を本文構成の正としている",
    "★ページ構成 `composition`（KLK-088" in GEN and "本文構成の正" in GEN,
    "記載=%s" % ("★ページ構成 `composition`（KLK-088" in GEN),
)
for key, label in [("出現順に `-01` `-02` `-03`", "採番"),
                   ("3案とも同じ", "並びは全案共通"),
                   ("そのインスタンスにだけ", "個別設定の適用範囲"),
                   ("全案でその型", "型指定は全案共通"),
                   ("インスタンス補正", "自動振り分けの補正"),
                   ("従来どおり", "後方互換"),
                   ("生成を始めずに停止", "受付チェック")]:
    check("E2 draft-generate SKILL に「%s」の指示がある" % label, key in GEN,
          "%s=%s" % (label, key in GEN))
check(
    "E3 draft-regenerate SKILL が composition を desiredType の次に強いと定めている",
    "★`composition` の型指定(KLK-088・`desiredType` の次に強い)" in REGEN,
    "記載=%s" % ("★`composition` の型指定(KLK-088" in REGEN),
)
check(
    "E4 draft-regenerate SKILL が出現順 k とインスタンス補正を書いている",
    "出現順 k" in REGEN and "(k-1)` を足して `mod 6`" in REGEN,
    "手順=%s" % ("出現順 k" in REGEN),
)

# ===========================================================================
# F群 — 後方互換の明記（規約側にも残す）
# ===========================================================================
check(
    "F1 §2.1 の並び順が composition 有無で分岐すると書かれている",
    "`composition` が**無い**とき" in RULES and "§2.2 が並び順の正" in RULES,
    "分岐=%s" % ("§2.2 が並び順の正" in RULES),
)
check(
    "F2 規約が「既存の指示書は解釈が変わらない」と明言している",
    "既存の指示書は1バイトも解釈が変わらない" in RULES,
    "明言=%s" % ("既存の指示書は1バイトも解釈が変わらない" in RULES),
)

# ===========================================================================
# V群 — verify-mockup.py の composition 照合（規約が効いたかを実物で見る道具）
# ===========================================================================
TOOL = os.path.join(ROOT, "tools", "verify-mockup.py")
TOOL_SRC = io.open(TOOL, encoding="utf-8").read() if os.path.isfile(TOOL) else ""
check(
    "V1 verify-mockup に composition 照合が入っている",
    "def check_composition(" in TOOL_SRC and "check_composition(folder, f, html, n)" in TOOL_SRC,
    "照合関数=%s" % ("def check_composition(" in TOOL_SRC),
)
# ★契約更新（KLK-089）: 型・見出しは **生成後に 🔄 で変えられる**ので、
#   「違反」ではなく「注意」へ移した。並び・連番は 🔄 では変わらないので違反のまま。
#   一律に違反とすると、意図的に型を入れ替えたフォルダが毎回赤くなり、
#   やがて警告そのものが信用されなくなる（KLK-080・KLK-088 と同じ学び）。
#   生成直後の厳密な検証は --strict で行う。
check(
    "V2 並び・連番は違反、型・見出しは注意として照合する（4点とも見ている）",
    all(t in TOOL_SRC for t in ("composition と並びが違う", "番地が重複している",
                                "の型が指示書と違う", "に指示書の見出しが無い"))
    and "notices.append(" in TOOL_SRC,
    "4点=%s / 注意の分離=%s"
    % (all(t in TOOL_SRC for t in ("composition と並びが違う", "番地が重複している",
                                   "の型が指示書と違う", "に指示書の見出しが無い")),
       "notices.append(" in TOOL_SRC),
)
check(
    "V2b --strict で注意を違反として扱える（生成直後の検証用）",
    'strict = "--strict" in argv' in TOOL_SRC and "findings = findings + notices" in TOOL_SRC,
    "--strict=%s" % ('strict = "--strict" in argv' in TOOL_SRC),
)
check(
    "V3 composition の無い指示書・instruction.json が無いフォルダでは黙る（fail-open）",
    "fail-open" in TOOL_SRC and "if not isinstance(comp, list) or not comp:" in TOOL_SRC,
    "fail-open=%s" % ("if not isinstance(comp, list) or not comp:" in TOOL_SRC),
)
check(
    "V4 SEARCH を並びの照合から除いている（HERO/NAV へ埋め込むため実体が出ない）",
    "expected_wo_search" in TOOL_SRC,
    "SEARCH 除外=%s" % ("expected_wo_search" in TOOL_SRC),
)
check(
    "V5 NAV / MV / FOOTER を本文の並びから除いている（composition の対象外）",
    '("NAV", "MV", "FOOTER")' in TOOL_SRC,
    "除外=%s" % ('("NAV", "MV", "FOOTER")' in TOOL_SRC),
)

print("=" * 78)
print("KLK-088 composition を生成側へ通す（規約・スキル）静的チェック")
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
