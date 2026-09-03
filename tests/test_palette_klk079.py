# KLK-079 型入れ替えの end-to-end を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk079.py（規約・スキル・UI・純関数）
# - 追加: **ブリッジの後段検証が本当に効くか**を、従うスキルと従わないスキルの
#   両方を模した stub で実HTTP経由に確かめる。
#
#   ★ここが本チケットの安全装置そのもの。
#     このリポジトリは「ブリッジが指示 → LLM が生成 → 守ったかは誰も見ていない」形で
#     4回失敗している（KLK-064 の登録未到達、KLK-072〜076 の規約無視）。
#     「守らなかったときに false が返る」ことをテストで固定しないと、
#     この装置自体が壊れても誰も気づけない。
import importlib.util
import json
import shutil as _shutil
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
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk079.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk079.node.js"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"
SAMPLE = ROOT / "samples" / "03_クリニック_ナビ下配置"
WORK_NAME = "2026-09-04_klk079_smoke"
WORK = ROOT / "mockups" / WORK_NAME


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk079_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestKLK079Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk079.py failed:\n" + proc.stdout + proc.stderr
        )


@unittest.skipUnless(_shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK079CompareUiSmoke(unittest.TestCase):
    """compare.html の 🔄 コントロール JS を DOM シムの上で実際に動かす（N1-N10）。

    静的 checker は compare.html を**文字列一致**で見ているだけなので、
    「その文字列はあるが動かない」を検出できない。UI はこの機能の入口そのものなので、
    実挙動（型の送り分け・typeApplied:false の扱い・案切替での読み直し）を確かめる。
    """

    def test_dynamic_smoke_passes(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk079.node.js failed:\n" + proc.stdout + proc.stderr,
        )


class _LiveBase(unittest.TestCase):
    """claude を stub に差し替えたブリッジを立て、実HTTPで /regenerate を回す土台。"""

    OBEY = True     # サブクラスで切り替え：スキルが desiredType に従うか
    SOURCE = None   # コピー元の見本（既定は 03）

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = cls._make_stub()

        if WORK.exists():
            shutil.rmtree(WORK)
        shutil.copytree(cls.SOURCE or SAMPLE, WORK)

        cls.port = _free_port()
        cls._t = threading.Thread(target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._t.start()
        if not cls._wait_health(cls.port):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため skip")

    @classmethod
    def tearDownClass(cls):
        if WORK.exists():
            shutil.rmtree(WORK, ignore_errors=True)
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run

    @classmethod
    def _make_stub(cls):
        """claude 呼び出しを模す。

        従うスキル : ジョブ仕様を読み、対象セクションのマーカーを desiredType へ置き換える
        従わないスキル: ファイルに触るだけ（mtime は進むので「成果物あり」と判定される）
                        ＝「成功したように見えて何もしていない」の再現
        """
        obey = cls.OBEY
        bridge = None

        def stub(cmd, *a, **kw):
            nonlocal bridge
            ok = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if not (isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "claude"):
                return ok  # open 等はそのまま成功扱い
            prompt = cmd[2] if len(cmd) > 2 else ""
            m = re.search(r"(\S+\.regen\.json)$", prompt)
            if not m:
                return ok
            spec_path = ROOT / m.group(1)
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            target = ROOT / spec["target"]
            html = target.read_text(encoding="utf-8")
            desired = spec.get("desiredType")
            if obey and desired:
                if bridge is None:
                    bridge = _load_bridge()
                addr = spec["addr"]
                cur = bridge.read_section_marker(html, addr)
                start, end = bridge.find_target_section(html, addr)
                if cur and start is not None:
                    block = html[start:end].replace(cur, desired)
                    html = html[:start] + block + html[end:]
            target.write_text(html, encoding="utf-8")  # 従わない場合も mtime は進む
            return ok

        return stub

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

    def _post(self, body):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10.0)
        conn.request("POST", "/regenerate", json.dumps(body),
                     {"Content-Type": "application/json"})
        res = conn.getresponse()
        raw = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(raw) if raw else {}

    def _wait_done(self, job_id, timeout=30.0):
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
            conn.request("GET", "/status/" + job_id)
            res = conn.getresponse()
            last = json.loads(res.read().decode("utf-8"))
            conn.close()
            if last.get("state") in ("done", "error"):
                return last
            time.sleep(0.15)
        return last


class TestKLK079TypeSwapApplied(_LiveBase):
    """スキルが指示に従ったとき: 型が入れ替わり typeApplied=true。"""

    OBEY = True

    def test_swap_is_applied_and_verified(self):
        before = (WORK / "index-c.html").read_text(encoding="utf-8")
        cur = self.bridge.read_section_marker(before, "GALLERY-01") \
            or self.bridge.read_section_marker(before, "MENU-01")
        self.assertIsNotNone(cur)
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c",
            "addr": "MENU-01", "desiredType": "pat-list",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "done", st)
        self.assertIs(st.get("typeApplied"), True, st)
        self.assertIn("pat-list", st.get("message", ""))
        after = (WORK / "index-c.html").read_text(encoding="utf-8")
        self.assertEqual(self.bridge.read_section_marker(after, "MENU-01"), "pat-list")


class TestKLK079TypeSwapIgnored(_LiveBase):
    """★スキルが指示を無視したとき: 黙って成功と言わず typeApplied=false。"""

    OBEY = False

    def test_ignored_instruction_is_reported_not_hidden(self):
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c",
            "addr": "MENU-01", "desiredType": "pat-list",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "done", st)
        self.assertIs(
            st.get("typeApplied"), False,
            "型が変わっていないのに typeApplied が false になっていない（安全装置が壊れている）:\n%s" % st,
        )
        self.assertIn("なりませんでした", st.get("message", ""))
        # 実ファイルは元の型のまま
        after = (WORK / "index-c.html").read_text(encoding="utf-8")
        self.assertEqual(self.bridge.read_section_marker(after, "MENU-01"), "feature-large")


class TestKLK079OldMarkerLeftBehind(_LiveBase):
    """★旧マーカーを外し忘れたとき: 新しい型が付いていても成功にしない。

    `class="m-gallery pat-grid pat-masonry"` のように2つ残ると CSS が競合して崩れる。
    「最長一致で1つ返す」実装だとこれを見逃し、後段検証が誤って成功と判定していた
    （KLK-079 の実装レビューで発見）。

    ★見本01・GALLERY-01 を使うのは、**新しい型のほうが文字列として長い**組合せだから
      （旧 `pat-grid` 8字 → 新 `pat-masonry` 11字）。
      旧 `feature-large` のように**古い型のほうが長い**組合せでは、
      壊れた実装（最長一致）でもたまたま False になり、テストが穴を検出できない。
      実際、最初に書いた MENU 版はこの理由で「壊しても落ちない」テストになっていた。
    """

    OBEY = False   # stub は型を変えない → 下で「両方付いた」状態を自分で作る
    SOURCE = ROOT / "samples" / "01_カフェ_1カラム"

    @classmethod
    def _make_stub(cls):
        def stub(cmd, *a, **kw):
            ok = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if not (isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "claude"):
                return ok
            m = re.search(r"(\S+\.regen\.json)$", cmd[2] if len(cmd) > 2 else "")
            if not m:
                return ok
            spec = json.loads((ROOT / m.group(1)).read_text(encoding="utf-8"))
            target = ROOT / spec["target"]
            html = target.read_text(encoding="utf-8")
            desired = spec.get("desiredType")
            if desired:
                # 旧マーカー(pat-grid)を外さずに新マーカーを足す（＝外し忘れの再現）
                html = html.replace('class="m-gallery pat-grid"',
                                    'class="m-gallery pat-grid %s"' % desired, 1)
            target.write_text(html, encoding="utf-8")
            return ok
        return stub

    def test_two_markers_is_not_success(self):
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "a",
            "addr": "GALLERY-01", "desiredType": "pat-masonry",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "done", st)
        # 実ファイルには両方が残っている（新しい型のほうが長い＝最長一致では見逃す組合せ）
        after = (WORK / "index-a.html").read_text(encoding="utf-8")
        self.assertEqual(
            self.bridge.read_section_markers(after, "GALLERY-01"),
            ["pat-grid", "pat-masonry"],
        )
        self.assertIs(
            st.get("typeApplied"), False,
            "旧マーカーが残っているのに成功と判定している（CSS が競合して崩れる）:\n%s" % st,
        )
        self.assertIn("古い型が残っています", st.get("message", ""))


class TestKLK079NoTypeIsBackwardCompatible(_LiveBase):
    """desiredType を送らない従来の呼び出しは、そのまま動き typeApplied=None。"""

    OBEY = True

    def test_without_desired_type(self):
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c", "addr": "MENU-01",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "done", st)
        self.assertIsNone(st.get("typeApplied"), st)
        self.assertNotIn("なりませんでした", st.get("message", ""))

    def test_job_spec_omits_desired_type_when_absent(self):
        """★後方互換: 型指定が無いときジョブ仕様に desiredType を書かない。"""
        seen = {}
        orig = self.bridge.subprocess.run

        def spy(cmd, *a, **kw):
            if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "claude":
                m = re.search(r"(\S+\.regen\.json)$", cmd[2] if len(cmd) > 2 else "")
                if m:
                    seen["spec"] = json.loads((ROOT / m.group(1)).read_text(encoding="utf-8"))
            return orig(cmd, *a, **kw)

        self.bridge.subprocess.run = spy
        try:
            status, obj = self._post({
                "folder": "mockups/" + WORK_NAME, "letter": "c", "addr": "ABOUT-01",
            })
            self.assertEqual(status, 202, obj)
            self._wait_done(obj["jobId"])
        finally:
            self.bridge.subprocess.run = orig
        self.assertIn("spec", seen, "ジョブ仕様を観測できなかった")
        self.assertNotIn("desiredType", seen["spec"], "型指定が無いのにキーを書いている")


class TestKLK079StallIsBounded(_LiveBase):
    """★スキルが止まったとき: タイムアウトで error になり、成功と誤認しない。

    実機検証中に `claude -p` が **0% CPU のまま34分無反応**になる事象を実際に踏んだ
    （ファイルは1バイトも変わらず、標準エラーも空）。原因は外部要因と見られるが、
    起きたときに何が返るかは**この経路の契約**なので固定しておく。
    ブリッジは BRIDGE_TIMEOUT_SEC(900秒) で打ち切り、state=error を返す。
    型指定つきでも typeApplied は None のまま＝「適用した」と言わない。
    """

    OBEY = True

    @classmethod
    def _make_stub(cls):
        def stub(cmd, *a, **kw):
            if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "claude":
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout") or 900)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        return stub

    def test_timeout_is_error_not_success(self):
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c",
            "addr": "MENU-01", "desiredType": "pat-list",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "error", st)
        self.assertIn("タイムアウト", st.get("message", ""))
        self.assertIsNone(
            st.get("typeApplied"),
            "止まったのに型の適用可否を断定している:\n%s" % st,
        )

    def test_timeout_leaves_file_untouched(self):
        before = (WORK / "index-c.html").read_bytes()
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c",
            "addr": "MENU-01", "desiredType": "pat-list",
        })
        self.assertEqual(status, 202, obj)
        self._wait_done(obj["jobId"])
        self.assertEqual((WORK / "index-c.html").read_bytes(), before)


class TestKLK079Validation(_LiveBase):
    """語彙外・型なし番地・型違いの拒否（claude を起動する前に止まること）。"""

    OBEY = True

    def test_rejects_out_of_pool(self):
        for addr, t in (
            ("MV-01", "pat-grid"),        # 別セクションの型
            ("MV-01", "OVERLAP"),         # 大文字違い
            ("MV-01", "overlap; rm -rf /"),  # 注入風
            ("NAV-01", "full"),           # プールを持たない番地
        ):
            status, obj = self._post({
                "folder": "mockups/" + WORK_NAME, "letter": "c",
                "addr": addr, "desiredType": t,
            })
            self.assertEqual(status, 400, "addr=%s type=%r を拒否していない" % (addr, t))
            self.assertIn("pool", obj)

    def test_rejects_non_string(self):
        status, _ = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c",
            "addr": "MV-01", "desiredType": 123,
        })
        self.assertEqual(status, 400)

    def test_rejected_request_leaves_file_untouched(self):
        """拒否したときファイルを変更しないこと（SPEC §7・ラフを壊さない）。"""
        before = (WORK / "index-c.html").read_bytes()
        self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "c",
            "addr": "MV-01", "desiredType": "pat-grid",
        })
        self.assertEqual((WORK / "index-c.html").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
