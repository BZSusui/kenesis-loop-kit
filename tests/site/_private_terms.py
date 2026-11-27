"""KLK-141 個人名の照合（共有モジュール）。**このファイルは照合語を持たない。**

★なぜ照合語をここに書かないか（KLK-108 の教訓）
  秘密を見張る検査が自分で秘密を持つと、その検査ファイル自身が漏洩源になる。
  tests/ は `make-package.sh --with-tests` で配布物に入る。
  そこで照合語は Git 管理外の `.private/personal-terms.txt` にだけ置き、実行時に読む。
  ファイルが無い環境（clone 直後・配布先）では照合不能として素通りする（fail-open）。

★照合語ファイルの書式（UTF-8・1行1件）
  - 空行と `#` で始まる行は無視
  - 通常の行 = 照合語
  - `!` で始まる行 = 誤検知の除外語（照合語を部分に含む一般語）。照合の前に本文から取り除く
  - ASCII 英字だけの照合語は、大文字小文字を無視し単語境界つきで照合する

★出力の約束
  一致した語そのものは返さない・表示しない（端末や CI のログへの再漏洩を防ぐ）。
  呼び出し側へ返すのは「ファイルと行番号」だけにする。
  照合語ファイルが無く素通りした場合、checker は集計行の後に印の行（UNVERIFIED_MARKER）を出す（KLK-143）。

check_klk141（再発防止）と check_klk077 R7 がこのモジュールを使う。
照合規則を2か所に書かない（KLK-131 で起きかけた食い違いを避ける）。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TERMS_PATH = os.path.join(ROOT, ".private", "personal-terms.txt")

_ASCII_WORD = re.compile(r"[A-Za-z]+")

# 照合語ファイルが無く、照合を行わずに PASS 扱いにした（素通り）ことを示す印（KLK-143）。
# checker が集計行の後に1行で出し、unittest ラッパーがこれを見て skipTest にする。
# ASCII 固定。文言を変えるときは checker・ラッパーの両方がこの定数を参照しているので1か所で済む。
UNVERIFIED_MARKER = "UNVERIFIED personal-terms-missing:"


def unverified_line(ids):
    """素通りした検査 ID の一覧から印の行を作る。例: 'UNVERIFIED personal-terms-missing: K0,K2'"""
    return "%s %s" % (UNVERIFIED_MARKER, ",".join(ids))


def load_terms(path=TERMS_PATH):
    """(terms, allows) を返す。ファイルが無い/読めない/照合語0件なら None（照合不能）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    terms, allows = [], []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("!"):
            if s[1:]:
                allows.append(s[1:])
        else:
            terms.append(s)
    if not terms:
        return None
    return terms, allows


def _pattern(term):
    if _ASCII_WORD.fullmatch(term):
        return re.compile(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", re.IGNORECASE)
    return re.compile(re.escape(term))


def find_hits(text, terms, allows):
    """allows を本文から取り除いた後、terms の一致を [(term, 位置)] で返す。

    除外語は同じ長さの空白に置き換えて取り除く（位置がずれないように）。
    ASCII 英字のみの term は大文字小文字無視・単語境界つき。
    """
    for a in sorted(allows, key=len, reverse=True):
        text = text.replace(a, " " * len(a))
    hits = []
    for t in terms:
        for m in _pattern(t).finditer(text):
            hits.append((t, m.start()))
    hits.sort(key=lambda h: h[1])
    return hits


def scan_text(text, terms, allows):
    """本文の一致を行番号の一覧で返す（語は返さない）。"""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if find_hits(line, terms, allows):
            out.append(i)
    return out


def scan_file(path, terms, allows):
    """UTF-8 で読めるテキストファイルの一致行番号を返す。読めない（バイナリ等）なら []。"""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return []
    return scan_text(text, terms, allows)


def scan_tree(root, terms, allows, skip=()):
    """root 以下のテキストファイルを走査し、[(相対パス, 行番号)] を返す。

    画像等のバイナリ（UTF-8 で読めないもの）は飛ばす。skip は相対パスの先頭一致で除外する。
    **一致した語そのものは返さない。**
    """
    out = []
    for base, _dirs, names in os.walk(root):
        for n in names:
            p = os.path.join(base, n)
            rel = os.path.relpath(p, root)
            if any(rel.startswith(s) for s in skip):
                continue
            for ln in scan_file(p, terms, allows):
                out.append((rel, ln))
    out.sort()
    return out


def summarize(hits, limit=6):
    """[(相対パス, 行番号)] を表示用に縮める（語は含まない）。"""
    if not hits:
        return "なし"
    shown = ["%s:%d" % h for h in hits[:limit]]
    more = "" if len(hits) <= limit else " ほか%d件" % (len(hits) - limit)
    return "%d件 %s%s" % (len(hits), ", ".join(shown), more)
