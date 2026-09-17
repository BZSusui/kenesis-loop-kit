#!/usr/bin/env python3
"""
KLK-132 acceptance-condition checker — 起動.bat が Windows のバッチとして成立していること。

★経緯（2026-09-16 の実使用レビュー / Windows 実機）
  配布した 起動.bat は macOS で書かれたままの形（改行 LF のみ・文字コード UTF-8）で、
  日本語 Windows の cmd.exe が読めなかった。症状は「ダブルクリックしても無反応」
  「'ode' is not recognized」「@echo off が効かない」。原因は2つ重なっている:
    ① 改行が LF のみ    → cmd.exe は CRLF 前提で行を読む
    ② 文字コードが UTF-8 → cmd.exe は既定で CP932 として読むため読み取り位置がずれ、
                            日本語を含む行の後半が別コマンドとして実行される
  chcp 65001 は5行目にあったが、ずれはそれより前の読み取り段階で起きるので効かない。
  BOM 付き UTF-8 は実機で悪化（BOM が先頭行に食い込み @echo off すら効かない）。
  → **CP932(Shift_JIS) + CRLF** を正とする（docs/designs/KLK-132.md §3）。

★この checker が守っているもの
  1. 起動.bat が CP932 で読め、**UTF-8 では読めない**こと（UTF-8 で保存し直したら落ちる）
  2. すべての改行が CRLF で、BOM が無いこと
  3. chcp が残っていないこと／ダメ文字（2バイト目が 0x5C の CP932 文字）を含まないこと
  4. 処理の骨格と日本語メッセージが壊れていないこと
  5. 起動.command（macOS）は UTF-8+LF のままであること（mac 側を巻き込まない）
  6. .gitattributes が改行を保護していること（Git に LF へ潰されると元の木阿弥）
  7. ★実効果 — 実際にパッケージを組み、配布物の 起動.bat がリポジトリのものと
     **バイト一致**すること（リポジトリだけ直っている状態を許さない）
  8. 判定そのものが効いていること（自己検査 A12）

Run: python3 tests/site/check_klk132.py [--fast]   (--fast はパッケージ実ビルドを省く)
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BAT_PATH = os.path.join(ROOT, "起動.bat")
CMD_PATH = os.path.join(ROOT, "起動.command")
ATTR_PATH = os.path.join(ROOT, ".gitattributes")
PKG_SH = os.path.join(ROOT, "tools", "make-package.sh")
results = []

BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")

# 骨格（ASCII のみ。ここが欠けるとバッチとして動かない）
SKELETON = ("@echo off", "setlocal", "endlocal", 'cd /d "%~dp0"', "draft-gen\\bridge.py")
# 日本語メッセージ（CP932 で復号したあとに読めること）
MESSAGES = ("【エラー】", "ローカルブリッジを起動します")


# ---------------------------------------------------------------------------
# 判定（純粋関数・バイト列だけを見る）。末尾の A12 で自己検査する
# ---------------------------------------------------------------------------
def decodes_as(data, enc):
    """data が enc として復号できるか。"""
    try:
        data.decode(enc)
        return True
    except (UnicodeDecodeError, LookupError):
        return False


def has_bom(data):
    """先頭に BOM（UTF-8 / UTF-16 LE / BE）が付いているか。"""
    return any(data.startswith(b) for b in BOMS)


def lone_lf_count(data):
    """CR を伴わない単独の LF の個数（0 でなければ Windows のバッチとして危うい）。"""
    return data.replace(b"\r\n", b"").count(b"\n")


def dame_moji(text):
    """ダメ文字 = CP932 の2バイト目が 0x5C（\\）になる文字。

    日本語 Windows では問題にならないが、別のコードページでは `\\` と解釈される余地が残る。
    骨格はすべて ASCII なので致命傷にはならないが、残す理由も無いのでゼロを保つ。
    """
    out = []
    for ch in sorted(set(text)):
        if ord(ch) < 128:
            continue
        try:
            b = ch.encode("cp932")
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and b[1] == 0x5C:
            out.append(ch)
    return out


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# A1-A8 起動.bat の形
# ---------------------------------------------------------------------------
BAT = open(BAT_PATH, "rb").read() if os.path.isfile(BAT_PATH) else b""

check("A1 起動.bat が CP932(Shift_JIS) として復号できる",
      bool(BAT) and decodes_as(BAT, "cp932"),
      "サイズ=%d / cp932=%s" % (len(BAT), decodes_as(BAT, "cp932")))

TEXT = BAT.decode("cp932", errors="replace")

check("A2 ★UTF-8 としては復号**できない**（UTF-8 で保存し直したら落ちる）",
      bool(BAT) and not decodes_as(BAT, "utf-8"),
      "utf-8 で復号できる=%s" % decodes_as(BAT, "utf-8"))

check("A3 すべての改行が CRLF（単独 LF が無い）",
      bool(BAT) and lone_lf_count(BAT) == 0 and BAT.count(b"\r\n") > 0,
      "単独LF=%d / CRLF=%d" % (lone_lf_count(BAT), BAT.count(b"\r\n")))

check("A4 BOM が無い",
      not has_bom(BAT),
      "先頭4バイト=%r" % BAT[:4])

check("A5 chcp が残っていない（CP932 化により不要）",
      b"chcp" not in BAT,
      "chcp の出現=%s" % (b"chcp" in BAT))

_dame = dame_moji(TEXT)
check("A6 ダメ文字（CP932 の2バイト目が 0x5C の文字）を含まない",
      not _dame,
      "検出=%s" % (_dame or "なし"))

_missing_skel = [s for s in SKELETON if s not in TEXT]
check("A7 バッチの骨格が壊れていない（%s）" % " / ".join(SKELETON),
      not _missing_skel,
      "欠落=%s" % (_missing_skel or "なし"))

_missing_msg = [m for m in MESSAGES if m not in TEXT]
check("A8 日本語メッセージが CP932 復号後に読める",
      not _missing_msg,
      "欠落=%s" % (_missing_msg or "なし"))

# ---------------------------------------------------------------------------
# A9 macOS 側を巻き込んでいないこと
# ---------------------------------------------------------------------------
CMD = open(CMD_PATH, "rb").read() if os.path.isfile(CMD_PATH) else b""
check("A9 起動.command は UTF-8 + LF のまま（mac 側を CP932 化していない）",
      bool(CMD) and decodes_as(CMD, "utf-8") and b"\r\n" not in CMD and not has_bom(CMD),
      "utf8=%s / CRLF=%s / BOM=%s"
      % (decodes_as(CMD, "utf-8"), b"\r\n" in CMD, has_bom(CMD)))

# ---------------------------------------------------------------------------
# A10 Git に改行を触らせない
# ---------------------------------------------------------------------------
ATTR = io.open(ATTR_PATH, encoding="utf-8").read() if os.path.isfile(ATTR_PATH) else ""
check("A10 .gitattributes が 起動.bat の改行を保護している（`起動.bat -text`）",
      "起動.bat" in ATTR and "-text" in ATTR,
      "記述=%s" % (next((l for l in ATTR.split("\n")
                   if "起動.bat" in l and "-text" in l), "（無し）")))

# ---------------------------------------------------------------------------
# A11 ★実効果 — 実際に組んだ配布物とバイト一致する（--fast で省略可）
# ---------------------------------------------------------------------------
if "--fast" not in sys.argv:
    tmp = tempfile.mkdtemp(prefix="klk132_pkg_")
    dest = os.path.join(tmp, "pkg")
    try:
        r = subprocess.run(["bash", PKG_SH, dest],
                           capture_output=True, text=True, timeout=600)
        built = os.path.join(dest, "起動.bat")
        built_bytes = open(built, "rb").read() if os.path.isfile(built) else b""
        check("A11 ★実ビルドした配布物の 起動.bat がリポジトリのものとバイト一致する",
              r.returncode == 0 and built_bytes == BAT and len(BAT) > 0,
              "rc=%d / 配布物=%dバイト / リポジトリ=%dバイト"
              % (r.returncode, len(built_bytes), len(BAT)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
# A12 自己検査 — 判定が効いていることを、壊したバイト列で確かめる
#     ★壊したこと自体を先に assert してから判定する（素通り防止）
# ---------------------------------------------------------------------------
_utf8_lf = TEXT.replace("\r\n", "\n").encode("utf-8")      # 事故そのもの（UTF-8 / LF へ戻した形）
_bom = b"\xef\xbb\xbf" + BAT                                # BOM を付けた形
assert decodes_as(_utf8_lf, "utf-8"), "妨害注入が効いていない（UTF-8 になっていない）"
assert lone_lf_count(_utf8_lf) > 0, "妨害注入が効いていない（LF に戻っていない）"
assert has_bom(_bom), "妨害注入が効いていない（BOM が付いていない）"
check("A12 自己検査: UTF-8/LF へ戻すと A2・A3 が落ち、BOM を付けると A4 が落ちる",
      decodes_as(_utf8_lf, "utf-8") and lone_lf_count(_utf8_lf) > 0 and has_bom(_bom),
      "UTF-8復号可=%s / 単独LF=%d / BOM検出=%s"
      % (decodes_as(_utf8_lf, "utf-8"), lone_lf_count(_utf8_lf), has_bom(_bom)))

print("=" * 78)
print("KLK-132 起動.bat が Windows のバッチとして成立していること チェック")
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
