# KLK-020 MVフリー実写真アタリ（REQ-104 b方式・アップロード＋検索リンク）のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk020.py（S1-S19・Python標準のみ・
#   対象＝draft-gen/index.html(静的+純ロジックslice) / draft-gen/bridge.py(import+ソース静的) /
#   DRAFT_RULES.md・SKILL.md・docs/SPEC.md(文言) / tests/fixtures/klk020(ゴールデン・ダミー)）。
# - D群（動的・設計書 KLK-020 §9 D群を正とする）:
#   - D1: check_klk020.py を subprocess 実行し exit 0（S群 subprocess）。
#   - D2: `python3 -m unittest discover -s tests` の回帰全緑（KLK-006〜019 が回帰しない）は
#     スイート全体の実行そのものが担保する（本ラッパーは additive・既存を触らない）。
#   - D3: standard 等価回帰。buildInstruction の純ロジック slice が mvPhoto を free-photo ガード下
#     でのみ後付けすること＋fixtures（instruction.standard.json に mvPhoto 無・instruction.free.json
#     に mvPhoto:{file} 安全名）が bridge.validate_instruction で整合することを Python のみで確認する
#     （node 非依存＝設計 §9 D3「純ロジック実行 or slice」の slice 経路）。
#   - D4: /upload 実HTTPスモーク。bridge を GET/POST 層のみ 127.0.0.1 デーモンで起動し
#     （**claude は起動しない**＝subprocess.run を noop 化しブラウザ自動オープンも抑止）、
#     ①有効 JPEG/PNG ダミー画像バイト POST /upload→200・savedName・mockups/.uploads/ 保存／
#     ②不正 Origin→403／③UPLOAD_MAX_BODY_BYTES 超過→413／④非画像バイト→400 を確認。
#     bind 不可・起動失敗は skip 可。git check-ignore は別クラス（git 不在時 skip）。
#
# M群（ブリッジ実起動＋ブラウザ実機＋実生成）は自動化不能のため tester が手動確認し
# チケットのログへ記録する（test_palette_klk013/019 ラッパーと同型）。
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import types
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk020.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"
INDEX_HTML_PATH = ROOT / "draft-gen" / "index.html"
FIXTURES = ROOT / "tests" / "fixtures" / "klk020"
UPLOADS_DIR = ROOT / "mockups" / ".uploads"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk020_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _can_bind_localhost():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.close()
        return True
    except OSError:
        return False


class TestKLK020Static(unittest.TestCase):
    """D1: check_klk020.py（設計書 KLK-020 §9 S群 S1-S19）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk020.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK020StandardEquivalence(unittest.TestCase):
    """D3: standard 等価回帰（純ロジック slice＋fixtures 整合・Python のみ）。

    buildInstruction は mvPhoto を「atari==='free-photo' かつ 保存名あり」のときだけ後付けする。
    standard 入力では mvPhoto キーを出さない＝従来 standard 出力とバイト等価（R-2）。
    fixtures（standard に mvPhoto 無・free に mvPhoto:{安全名}）が bridge.validate_instruction を
    通ることも併せて確認する（後方互換・スキーマ additive）。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        cls.index_html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        cls.std = json.loads((FIXTURES / "instruction.standard.json").read_text(encoding="utf-8"))
        cls.free = json.loads((FIXTURES / "instruction.free.json").read_text(encoding="utf-8"))

    def _build_slice(self):
        m = re.search(r"function buildInstruction\(input\)\s*\{", self.index_html)
        self.assertIsNotNone(m, "buildInstruction が index.html に存在するべき")
        i = m.end()
        m2 = re.search(r"\nfunction render\(", self.index_html[i:])
        return self.index_html[i:i + m2.start()] if m2 else self.index_html[i:]

    def test_d3_mvphoto_guarded_by_free_photo(self):
        seg = self._build_slice()
        # 無条件の out リテラルに mvPhoto が無い（standard で確実にキー非出力）。
        m = re.search(r"const out = \{", seg)
        self.assertIsNotNone(m, "const out リテラルが存在するべき")
        lit_end = re.search(r"\n  \};", seg[m.end():])
        literal = seg[m.end(): m.end() + lit_end.start()] if lit_end else ""
        self.assertNotIn("mvPhoto", literal,
                         "無条件の out リテラルに mvPhoto を含めてはならない（standard 等価が崩れる）")
        # mvPhoto 代入は free-photo ガード下でのみ行う。
        self.assertRegex(seg, r"input\.atari\s*===\s*'free-photo'",
                         "mvPhoto 出力は atari==='free-photo' でガードされるべき")
        self.assertRegex(seg, r"out\.mvPhoto\s*=\s*\{\s*file\s*:",
                         "free-photo 時のみ out.mvPhoto={file:...} を後付けするべき")

    def test_d3_standard_fixture_no_mvphoto_and_valid(self):
        self.assertEqual(self.std.get("atari"), "standard")
        self.assertNotIn("mvPhoto", self.std,
                         "standard fixture は mvPhoto キーを持たない（等価）")
        ok, errors = self.bridge.validate_instruction(self.std)
        self.assertTrue(ok, "standard instruction は従来どおり受理されるべき: " + "・".join(errors))

    def test_d3_free_fixture_mvphoto_safe_and_valid(self):
        self.assertEqual(self.free.get("atari"), "free-photo")
        mv = self.free.get("mvPhoto")
        self.assertIsInstance(mv, dict, "free fixture の mvPhoto は dict")
        fname = mv.get("file")
        self.assertTrue(self.bridge.is_safe_catalog_name(fname),
                        f"mvPhoto.file は安全名であるべき: {fname!r}")
        self.assertRegex(fname, r"^upl-[0-9a-f]+\.(jpg|png)$",
                         "mvPhoto.file はサーバ生成名 upl-<hex>.<ext> 形（架空）であるべき")
        ok, errors = self.bridge.validate_instruction(self.free)
        self.assertTrue(ok, "free-photo instruction は受理されるべき: " + "・".join(errors))

    def test_d3_traversal_mvphoto_rejected(self):
        # /generate 直POST の悪意ある mvPhoto.file をブリッジ側でも弾く（R-3・多層防御）。
        evil = dict(self.free, mvPhoto={"file": "../../etc/passwd"})
        ok, _ = self.bridge.validate_instruction(evil)
        self.assertFalse(ok, "traversal を含む mvPhoto.file は reject されるべき")


@unittest.skipUnless(_can_bind_localhost(), "127.0.0.1 へ bind できないため /upload 実HTTPスモークをskip")
class TestKLK020UploadSmoke(unittest.TestCase):
    """D4: POST /upload の実HTTP挙動（GET/POST 層のみ・claude は起動しない）。

    有効 JPEG/PNG→200＋savedName＋mockups/.uploads/ 保存、不正 Origin→403、
    UPLOAD_MAX_BODY_BYTES 超過→413、非画像バイト→400。subprocess.run を noop 化して
    起動時のブラウザ自動オープン／万一の claude 実行を抑止する（防御・保存は worker 非依存）。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout="", stderr="")

        cls.port = _free_port()
        cls._created = []  # 後始末する保存ファイル名

        cls._server_thread = threading.Thread(
            target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._server_thread.start()
        if not cls._wait_health(cls.port, timeout=8.0):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため /upload 実HTTPスモークをskip")

        cls.jpg = (FIXTURES / "dummy.jpg").read_bytes()
        cls.png = (FIXTURES / "dummy.png").read_bytes()

    @classmethod
    def tearDownClass(cls):
        # アップロードで保存したダミーを掃除（.uploads は Git除外だが試験の後片付け）。
        for name in getattr(cls, "_created", []):
            try:
                os.remove(os.path.join(str(UPLOADS_DIR), name))
            except OSError:
                pass
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run

    @staticmethod
    def _wait_health(port, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1.0)
                conn.request("GET", "/health")
                res = conn.getresponse()
                res.read()
                conn.close()
                if res.status == 200:
                    return True
            except OSError:
                pass
            time.sleep(0.1)
        return False

    # -- helper ------------------------------------------------------------
    def _upload(self, body, content_type="image/jpeg", origin=None, raw_len=None):
        """POST /upload。origin 未指定=Origin ヘッダ無し（None=許可）。
        raw_len 指定時は Content-Length を偽装しボディ非送信（413 は読取前に返る）。"""
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        conn.putrequest("POST", "/upload", skip_host=False, skip_accept_encoding=True)
        if origin is not None:
            conn.putheader("Origin", origin)
        conn.putheader("Content-Type", content_type)
        if raw_len is not None:
            conn.putheader("Content-Length", str(raw_len))
            conn.endheaders()  # ボディ非送信
        else:
            conn.putheader("Content-Length", str(len(body)))
            conn.endheaders()
            conn.send(body)
        res = conn.getresponse()
        status = res.status
        data = res.read()
        conn.close()
        try:
            payload = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = {}
        return status, payload

    # -- tests -------------------------------------------------------------
    def test_d4_jpeg_200_saved(self):
        st, payload = self._upload(self.jpg, content_type="image/jpeg")
        self.assertEqual(st, 200, "有効な JPEG は200であるべき")
        saved = payload.get("savedName")
        self.assertTrue(saved, "savedName が返るべき")
        self.__class__._created.append(saved)
        self.assertRegex(saved, r"^upl-[0-9a-f]{32}\.jpg$",
                         "保存名はサーバ生成 upl-<32hex>.jpg であるべき（マジックバイト判定）")
        self.assertTrue(os.path.isfile(os.path.join(str(UPLOADS_DIR), saved)),
                        "mockups/.uploads/ に保存されるべき")

    def test_d4_png_200_saved(self):
        st, payload = self._upload(self.png, content_type="image/png")
        self.assertEqual(st, 200, "有効な PNG は200であるべき")
        saved = payload.get("savedName")
        self.assertTrue(saved, "savedName が返るべき")
        self.__class__._created.append(saved)
        self.assertRegex(saved, r"^upl-[0-9a-f]{32}\.png$",
                         "保存名はサーバ生成 upl-<32hex>.png であるべき（マジックバイト判定）")

    def test_d4_content_type_ignored_magic_wins(self):
        # Content-Type を image/png と偽っても、JPEG マジックなら .jpg で保存される。
        st, payload = self._upload(self.jpg, content_type="image/png")
        self.assertEqual(st, 200)
        saved = payload.get("savedName")
        self.__class__._created.append(saved)
        self.assertTrue(saved.endswith(".jpg"),
                        "拡張子はマジックバイトが正（Content-Type は信用しない）")

    def test_d4_bad_origin_403(self):
        st, _ = self._upload(self.jpg, origin="http://evil.example")
        self.assertEqual(st, 403, "別オリジンは403で拒否されるべき")

    def test_d4_oversize_413(self):
        big = self.bridge.UPLOAD_MAX_BODY_BYTES + 1
        st, _ = self._upload(b"", raw_len=big)
        self.assertEqual(st, 413, "UPLOAD_MAX_BODY_BYTES 超過は413で拒否されるべき")

    def test_d4_non_image_400(self):
        st, _ = self._upload(b"GIF89a not an image at all", content_type="image/jpeg")
        self.assertEqual(st, 400, "非画像（JPEG/PNG マジック無）は400で拒否されるべき")

    def test_d4_empty_body_400(self):
        st, _ = self._upload(b"", content_type="image/jpeg")
        self.assertEqual(st, 400, "空ボディは400で拒否されるべき")


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK020UploadsGitIgnored(unittest.TestCase):
    """D4（除外成立）: mockups/.uploads/ 配下（アップロード実写真＝機密）が Git 追跡外であること。
    保存先は mockups/ の Git除外に内包され .gitignore 変更不要（§3.4・R-5）。"""

    def test_d4_uploads_git_ignored(self):
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if pre.returncode != 0:
            self.skipTest("git リポジトリ外のため skip")
        proc = subprocess.run(
            ["git", "check-ignore", "mockups/.uploads/x.jpg"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0,
            "mockups/.uploads/ 配下が Git 除外されていない（機密の実写真が追跡対象になる）\n"
            f"{proc.stdout}{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
