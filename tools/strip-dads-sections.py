#!/usr/bin/env python3
"""
tools/strip-dads-sections.py — 配布物からデザインシステム（DADS）の記述を外す (KLK-115)

★なぜ必要か
  モック生成システムのパッケージに DADS 関連は含めない（理恵さんの指示・2026-09-09）。
  ところが `docs/design-system/` を外すだけでは終わらない。CLAUDE.md と
  agents/{architect,implementer,reviewer}.md が `docs/design-system/...` を参照して
  いるため、DADS だけ抜くと**参照先が存在しない記述**が配布物に残る。
  受け取った人は書いてあるファイルを探して見つけられない。

★方式
  リポジトリ本体からは消さない（リポジトリは分割しないと決まっている・2026-09-10）。
  DADS の記述を次のマーカーで囲んでおき、**パッケージを組むときだけ**取り除く。

      <!-- DADS:BEGIN -->
      ... DADS の記述 ...
      <!-- DADS:END -->

  Markdown 中の HTML コメントなので、GitHub でもエディタでも表示されない。

★安全側の設計
  マーカーの対応が取れていなければ **例外を投げて止まる**。黙って中途半端な
  ファイルを吐かない。組み立て側（make-package.sh）はこれを検知して組み立てを中止する。

使い方:
  python3 tools/strip-dads-sections.py <ファイル>...   # その場で書き換える
  python3 tools/strip-dads-sections.py --check <ファイル>...  # 書き換えずに件数だけ報告
"""
import io
import sys

BEGIN = "<!-- DADS:BEGIN -->"
END = "<!-- DADS:END -->"


def strip_dads_sections(text):
    """DADS マーカーで囲まれた区間を取り除く（純粋関数）。

    返り値は (処理後のテキスト, 取り除いたブロック数)。
    マーカーの対応が取れない場合は ValueError を投げる。
    """
    lines = text.split("\n")
    out = []
    skipping = False
    removed = 0
    begin_line = 0
    # 区間を取り除くと空行が連続することがある。継ぎ目だけを詰める
    # （ファイル全体の空行を触ると、関係ない箇所の書式まで変えてしまう）
    just_removed = False

    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s == BEGIN:
            if skipping:
                raise ValueError("DADS:BEGIN が入れ子になっています（%d行目・開始は%d行目）"
                                 % (i, begin_line))
            skipping = True
            begin_line = i
            continue
        if s == END:
            if not skipping:
                raise ValueError("対応する DADS:BEGIN が無い DADS:END です（%d行目）" % i)
            skipping = False
            removed += 1
            just_removed = True
            continue
        if skipping:
            continue
        if just_removed:
            # 区間の直前が空行で直後も空行なら、片方だけ残す
            if s == "" and out and out[-1].strip() == "":
                continue
            just_removed = False
        out.append(line)

    if skipping:
        raise ValueError("DADS:END が見つかりません（開始は%d行目）" % begin_line)
    return "\n".join(out), removed


def main(argv):
    check_only = "--check" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__.strip().split("使い方:")[-1].strip(), file=sys.stderr)
        return 2

    total = 0
    for path in paths:
        try:
            text = io.open(path, encoding="utf-8").read()
        except OSError as e:
            print("【エラー】読めません: %s (%s)" % (path, e), file=sys.stderr)
            return 1
        try:
            stripped, removed = strip_dads_sections(text)
        except ValueError as e:
            print("【エラー】%s: %s" % (path, e), file=sys.stderr)
            return 1
        total += removed
        if removed and not check_only:
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(stripped)
        print("  %s: %d ブロック%s" % (path, removed, "" if check_only else " 除去"))

    if total == 0:
        # マーカーが1つも無いのは、付け忘れか消し忘れの疑いがある。
        # ただし組み立てを止めるほどではないので警告に留める（検査側が落とす）。
        print("  【注意】DADS マーカーが1つも見つかりませんでした", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
