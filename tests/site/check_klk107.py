#!/usr/bin/env python3
"""
KLK-107 acceptance-condition checker — カタログ取り込みの不安定さを解消する。

理恵さんの報告（2026-09-08）:
  「複数枚登録を試みると何ページもモック生成画面が表示されたり、
    『取り込みできませんでした』とエラーが出て取り込みができなくなった」

★調べて分かった原因（すべて実測で確認）
  ① 取り込みに**枚数の上限が無く**、.pending の全部を1セッションで処理していた。
     1枚あたり110〜125秒（0.3MB=107秒 / 5.8MB=123秒。**容量より枚数**が効く）。
     10枚溜まっていた環境では約21分かかり、タイムアウト(1800秒)に対して余裕が無かった。
  ② 失敗しても画像は .pending に残るので、入れ直すと**同じ画像が二重**になる。
     実際に同じ5枚が2回ぶん（10枚・25MB）溜まっていた＝再試行のたびに悪化する。
  ③ すでに起動中に起動しなおすと **Python の生トレースバック**を吐いて落ちていた
     （Address already in use）。原因が分からず何度も押すことになり、
     起動に成功するたびに設定画面のタブが増えた。

★この checker が守っているもの
  **「失敗が次の失敗を呼ぶ」構造を作らないこと。**
  上限・重複排除・二重起動の検出は、どれか1つ欠けると悪循環が復活する。

Run: python3 tests/site/check_klk107.py
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "klk107_bridge", os.path.join(ROOT, "draft-gen", "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load_bridge()
BRIDGE_SRC = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
CATALOG_HTML = io.open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# ① 取り込みの上限（1回に処理する量を絞る）
# ---------------------------------------------------------------------------
check("A 上限の定数がある（枚数・容量）",
      hasattr(B, "CATALOG_IMPORT_MAX_FILES") and hasattr(B, "CATALOG_IMPORT_MAX_BYTES"),
      "枚数=%s / 容量=%s"
      % (getattr(B, "CATALOG_IMPORT_MAX_FILES", None),
         getattr(B, "CATALOG_IMPORT_MAX_BYTES", None)))

check("B 上限が実測に照らして安全（1枚125秒×枚数 が タイムアウトの半分以内）",
      getattr(B, "CATALOG_IMPORT_MAX_FILES", 99) * 125 < B.BRIDGE_TIMEOUT_SEC / 2,
      "%d枚 × 125秒 = %d秒 / タイムアウト %d秒"
      % (B.CATALOG_IMPORT_MAX_FILES, B.CATALOG_IMPORT_MAX_FILES * 125, B.BRIDGE_TIMEOUT_SEC))

_wd = tempfile.mkdtemp()
try:
    def _mk(name, size):
        with open(os.path.join(_wd, name), "wb") as fh:
            fh.write(b"\xff\xd8\xff" + bytes(max(0, size - 3)))
        return name

    names = [_mk("a.jpg", 1000), _mk("b.jpg", 1000), _mk("c.jpg", 1000),
             _mk("d.jpg", 1000), _mk("e.jpg", 1000)]
    take, rest, total = B.split_import_batch(_wd, names)
    check("C ★上限を超える分は**次回へ回す**（止めない）",
          len(take) == B.CATALOG_IMPORT_MAX_FILES and len(rest) == 5 - len(take),
          "今回=%d / 次回=%d" % (len(take), len(rest)))

    check("D 先頭から順に取る（毎回同じものが取り残されない）",
          take == names[:len(take)], "今回=%s" % take)

    # 容量でも切れること
    big = [_mk("big1.jpg", 12 << 20), _mk("big2.jpg", 12 << 20)]
    t2, r2, tot2 = B.split_import_batch(_wd, big)
    check("E 容量でも切る（特大画像が複数入らない）",
          len(t2) == 1 and len(r2) == 1,
          "今回=%d(%.1fMB) / 次回=%d" % (len(t2), tot2 / 1048576, len(r2)))

    # 1枚で上限超過でも、その1枚は必ず処理する（でないと永久に取り込めない）
    huge = [_mk("huge.jpg", 40 << 20)]
    t3, r3, _ = B.split_import_batch(_wd, huge)
    check("F ★1枚で上限を超えても、その1枚は処理する（取り込めない画像を作らない）",
          len(t3) == 1 and len(r3) == 0, "今回=%d / 次回=%d" % (len(t3), len(r3)))
finally:
    shutil.rmtree(_wd, ignore_errors=True)

check("G ハンドラが分割を使っている（定数を置いただけで終わっていない）",
      "split_import_batch(catalog_pending_dir, names)" in BRIDGE_SRC,
      "呼び出し=%s" % ("split_import_batch(catalog_pending_dir, names)" in BRIDGE_SRC))

check("H 残り件数を /status と 202 応答で返す（画面が知る手段がある）",
      "deferredFiles" in BRIDGE_SRC and BRIDGE_SRC.count("deferredFiles") >= 3,
      "出現 %d 回" % BRIDGE_SRC.count("deferredFiles"))

# ★文字列の有無では足りない。`j.deferredFiles > 0` を `false` に書き換えても
#   「deferredFiles」「残り」は別の行に残るので素通りする（実際に素通りした）。
#   **残りがあるときに分岐して案内する条件式**が在ることを見る。
import re as _re
_branch = _re.search(r"if\s*\(\s*j\.deferredFiles\s*>\s*0\s*\)", CATALOG_HTML)
_msg = _re.search(r"deferredFiles[^;]{0,400}?残り", CATALOG_HTML, _re.S)
check("I ★画面が「残り○枚」を必ず伝える（黙って終わらせない）",
      _branch is not None and _msg is not None,
      "分岐=%s / 文面=%s" % (bool(_branch), bool(_msg)))

# ---------------------------------------------------------------------------
# ② 重複アップロードの検出
# ---------------------------------------------------------------------------
_wd2 = tempfile.mkdtemp()
try:
    raw = b"\xff\xd8\xff" + b"same-content" * 100
    with open(os.path.join(_wd2, "pnd-existing.jpg"), "wb") as fh:
        fh.write(raw)
    check("J 同じ内容の画像を検出する（ファイル名では判定できない）",
          B.find_duplicate_pending(_wd2, raw) == "pnd-existing.jpg",
          "検出=%s" % B.find_duplicate_pending(_wd2, raw))
    check("K 違う内容は重複としない（誤検出しない）",
          B.find_duplicate_pending(_wd2, raw + b"x") is None,
          "結果=%s" % B.find_duplicate_pending(_wd2, raw + b"x"))
    check("L 空フォルダ・不在フォルダで落ちない（fail-open）",
          B.find_duplicate_pending(os.path.join(_wd2, "nope"), raw) is None,
          "結果=なし")
finally:
    shutil.rmtree(_wd2, ignore_errors=True)

check("M アップロードが重複を保存せず、そう応答する",
      "find_duplicate_pending(catalog_pending_dir, raw)" in BRIDGE_SRC
      and '"duplicate": True' in BRIDGE_SRC,
      "検出の呼び出し=%s / 応答=%s"
      % ("find_duplicate_pending(catalog_pending_dir, raw)" in BRIDGE_SRC,
         '"duplicate": True' in BRIDGE_SRC))

check("N ★画面が重複件数を伝える（成功にも失敗にも混ぜない）",
      "duplicate" in CATALOG_HTML and "同じ画像" in CATALOG_HTML,
      "画面の案内=%s" % ("同じ画像" in CATALOG_HTML))

# ---------------------------------------------------------------------------
# ③ 二重起動の検出
# ---------------------------------------------------------------------------
check("O 二重起動を検出する関数がある",
      hasattr(B, "is_bridge_already_running"), "関数=%s" % hasattr(B, "is_bridge_already_running"))

check("P 動いていないポートでは False（誤検出しない）",
      B.is_bridge_already_running("127.0.0.1", 59999) is False,
      "結果=%s" % B.is_bridge_already_running("127.0.0.1", 59999))

check("Q ★/health の中身で自分自身か確かめる（他アプリと取り違えない）",
      "klk-draft-bridge" in BRIDGE_SRC.split("def is_bridge_already_running")[1][:900],
      "自己確認=%s" % ("klk-draft-bridge" in BRIDGE_SRC.split("def is_bridge_already_running")[1][:900]))

check("R すでに起動中なら二重に起動せず、分かる言葉で案内する",
      "すでに起動しています" in BRIDGE_SRC and "is_bridge_already_running(BRIDGE_HOST, port)" in BRIDGE_SRC,
      "案内=%s / 分岐=%s"
      % ("すでに起動しています" in BRIDGE_SRC,
         "is_bridge_already_running(BRIDGE_HOST, port)" in BRIDGE_SRC))

check("S ★その分岐ではブラウザを開かない（タブを増やさない）",
      "タブは増やさない" in BRIDGE_SRC,
      "明記=%s" % ("タブは増やさない" in BRIDGE_SRC))

check("T bind 失敗でもトレースバックを見せない（原因不明の落ち方をしない）",
      "httpd = ThreadingHTTPServer((BRIDGE_HOST, port), Handler)" in BRIDGE_SRC
      and "except OSError as exc:" in BRIDGE_SRC
      and "ポート {0} を使えませんでした" in BRIDGE_SRC,
      "try/except=%s / 案内=%s"
      % ("except OSError as exc:" in BRIDGE_SRC, "ポート {0} を使えませんでした" in BRIDGE_SRC))

print("=" * 78)
print("KLK-107 カタログ取り込みの不安定さを解消する チェック")
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
