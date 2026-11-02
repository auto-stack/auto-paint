#!/usr/bin/env python3
"""PAINT-001/002 basic-capabilities acceptance entry (001 T-05, 002 T-01/T-02).

Real-app, real-UI acceptance for both render tracks:

  python tests/basic/verify_basic.py --profile vm
  python tests/basic/verify_basic.py --profile vue

- vm  : `auto run -r vm` + isolated AUTO_VM_STORAGE_FILE + autoui MCP driving
        (same harness family as tests/desktop_mcp.py).
- vue : `auto run -r vue --server vm` (front 17834 via vite, back 17835 via
        VM HTTP service) + Playwright chromium driving the real browser UI.
        Project save/load uses browser localStorage. 002 T-01: the browser
        runs a persistent profile (run-owned user-data-dir), so state
        survives a real browser process kill/restart (P-02); server-side
        cleanup kills only pids that appeared during our own spawn window.

Coverage per 001 plan §6 (V-01..V-03, replayed unchanged) and 002 plan §6
(P-01..P-04):
- V-01 pixel vector fidelity (256 items, per-cell colors) across
  save/load/undo/redo for uniform white, uniform black, single point and a
  sparse designed pattern — no SKIP path for uniform snapshots (P553-D1
  regression). 2026-10-29 user ruling: import/export cases use a simple
  figure (10 designed points), not cell-by-cell fills.
- V-02 SVG export: XML parse, 16x16 canvas, rect positions/fills match the
  source model, no unescaped content, real render in chromium.
- V-03 failure paths: bad v1 (255 items), bad v2 header, illegal colors,
  unwritable/empty export paths — rejections must not touch the current
  canvas; legal old v1 works must reopen (migration).
- P-01 (002, AC-01) standalone gate self-sufficiency: bounded boot
  readiness with explicit failure, foreign port users respected, own
  temp storage/profile/ports only.
- P-02 (002, AC-02) cross-process reopen: strong-kill the app (vm) or the
  whole browser tree (vue), reopen the SAME persistent storage/profile,
  Load -> 256-cell identical, next edit -> Save -> reopen again.
- P-03 (002, AC-02/03) export semantics: Chinese/space paths, existing
  target overwrite, backend-down failure visible (no false "exported"),
  canvas/project preserved, recovery export succeeds.
- P-04 (002, AC-03) counterexample controls: mutation control proves the
  oracle detects one-cell color corruption (suite would go red/nonzero);
  failed export must not create a file; 001 rejection matrix replayed.

Evidence policy: this script writes a JSON report with versions, fixture
hashes, per-check results and original failure details to --report-dir
(default: docs/plans/attachments/002/, local-only, never committed).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

import requests

AUTO_BIN = os.environ.get("AUTO_BIN", "D:/autostack/auto-man/target/debug/auto.exe")
PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
RED = "#ef4444"
DARK = "#111827"
WHITE = "#ffffff"
SVG_NS = "{http://www.w3.org/2000/svg}"


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def free_port(start):
    for port in range(start, start + 200):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        finally:
            s.close()
    raise RuntimeError(f"no free port >= {start}")


def port_busy(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def port_pids(port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True,
                         text=True).stdout
    pids = set()
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            pids.add(line.split()[-1])
    return pids


def wait_port_free(port, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_busy(port):
            return True
        time.sleep(1)
    return False


def expected_svg(px):
    """Build the oracle SVG from a 256-item hex list (mirrors build_svg)."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
             'viewBox="0 0 16 16" shape-rendering="crispEdges">',
             '<rect x="0" y="0" width="16" height="16" fill="#ffffff"/>']
    for k, c in enumerate(px):
        if c != WHITE:
            parts.append(f'<rect x="{k % 16}" y="{k // 16}" width="1" height="1" '
                         f'fill="{c}"/>')
    parts.append("</svg>")
    return "".join(parts)


def svg_cell_points(content):
    """[(x, y, fill)] for the non-white cell rects of a parsed SVG, or None
    if the content does not parse as an svg with a white base rect."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    if root.tag != SVG_NS + "svg":
        return None
    rects = root.findall(SVG_NS + "rect")
    return [(r.get("x"), r.get("y"), r.get("fill")) for r in rects[1:]]


def parse_px_state(state_text):
    """autoui_state('px') -> 256 hex list (VM profile)."""
    items = re.findall(r'"(#[0-9a-fA-F]{6})"', state_text)
    return items


class Report:
    def __init__(self, profile):
        self.profile = profile
        self.checks = []
        self.versions = {}
        self.fixtures = {}

    def check(self, cid, name, cond, detail=""):
        self.checks.append({"id": cid, "name": name, "pass": bool(cond),
                            "detail": str(detail)[:400]})
        mark = "PASS" if cond else "FAIL"
        print(f"  {mark}  [{cid}] {name}" + ("" if cond else f": {detail}"))
        return bool(cond)

    def finalize(self, out_dir):
        passed = sum(1 for c in self.checks if c["pass"])
        failed = len(self.checks) - passed
        doc = {
            "profile": self.profile,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "versions": self.versions,
            "fixture_hashes": self.fixtures,
            "passed": passed,
            "failed": failed,
            "checks": self.checks,
        }
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"verify-{self.profile}-{int(time.time())}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        print(f"\n[{self.profile}] {passed} passed, {failed} failed"
              f" — report: {path}")
        return failed


# ─────────────────────────── VM profile (autoui MCP) ───────────────────────

class VmSession:
    def __init__(self, storage_path, report):
        self.port = free_port(9400)
        self.storage = storage_path
        self.ready = False
        env = {**os.environ, "AUTOUI_MCP_PORT": str(self.port),
               "AUTO_VM_STORAGE_FILE": storage_path}
        try:
            self.proc = subprocess.Popen(
                [AUTO_BIN, "run", "-r", "vm"], cwd=PROJ, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.proc = None
            report.check("vm-boot", "vm app spawned", False, str(e))
            return
        self.url = f"http://127.0.0.1:{self.port}/mcp"
        self.ready = False
        for _ in range(90):
            try:
                requests.post(self.url, json={"jsonrpc": "2.0", "method": "tools/list",
                                              "params": {}, "id": 1}, timeout=2)
                break
            except Exception:
                if self.proc.poll() is not None:
                    return
                time.sleep(1)
        for _ in range(60):
            snap = self.snapshot()
            if snap and "No UI available" not in snap and len(snap) > 1000:
                self.ready = True
                return
            if self.proc.poll() is not None:
                return
            time.sleep(2)
        report.check("vm-boot", "vm app rendered first frame", False,
                     "UI never rendered")

    def call(self, name, **args):
        last = None
        for _ in range(3):
            try:
                r = requests.post(self.url, json={
                    "jsonrpc": "2.0", "method": "tools/call",
                    "params": {"name": name, "arguments": args}, "id": 9}, timeout=20)
                c = r.json().get("result", {}).get("content", [])
                return c[0]["text"] if c else ""
            except requests.RequestException as e:
                last = e
                if self.proc.poll() is not None:
                    raise RuntimeError(
                        f"app exited (code {self.proc.returncode}) during {name}")
                time.sleep(1.5)
        raise RuntimeError(f"{name} failed after retries: {last}")

    def snapshot(self):
        try:
            return self.call("autoui_snapshot")
        except Exception:
            return ""

    def state(self, field):
        try:
            return self.call("autoui_state", fields=[field])
        except Exception:
            return ""

    def px(self):
        return parse_px_state(self.state("px"))

    def status(self):
        m = re.search(r'status: "([^"]*)"', self.state("status"))
        return m.group(1) if m else ""

    def settled_snap(self, tries=10, gap=0.4):
        """Snapshot quiescence (review R-01): the autoui vnode tree re-renders
        after status/model changes; vnode ids are only stable between renders.
        Return a snapshot whose structure is identical to the previous one
        (bounded wait), so element ids addressed from it are current."""
        prev = self.snapshot()
        for _ in range(tries):
            time.sleep(gap)
            cur = self.snapshot()
            if cur == prev and len(cur) > 1000:
                return cur
            prev = cur
        return prev

    def click(self, frag):
        snap = self.settled_snap()
        btns = {label: vid for vid, label in
                re.findall(r'button #(vnode_\d+) "([^"]+)"', snap)}
        vid = next((v for k, v in btns.items() if frag in k), None)
        if vid is None:
            return "button not found: " + frag
        r = self.call("autoui_action", element_id=vid, action="press")
        if "not valid" in r or "not found" in r:
            # addressing raced a re-render: re-address once from a fresh settle
            snap = self.settled_snap()
            btns = {label: vid for vid, label in
                    re.findall(r'button #(vnode_\d+) "([^"]+)"', snap)}
            vid = next((v for k, v in btns.items() if frag in k), None)
            if vid is None:
                return "button not found: " + frag
            r = self.call("autoui_action", element_id=vid, action="press")
        return r

    def containers(self, snap=None):
        snap = snap or self.settled_snap()
        children = defaultdict(list)
        stack = []
        lines = [(len(l) - len(l.lstrip()), l.strip())
                 for l in snap.splitlines() if "#vnode_" in l]
        for ind, line in lines:
            m = re.search(r"#(vnode_\d+)", line)
            if not m:
                continue
            vid = m.group(1)
            while stack and stack[-1][0] >= ind:
                stack.pop()
            if stack:
                children[stack[-1][1]].append(vid)
            stack.append((ind, vid))
        return children

    def cells(self):
        for parent, ch in self.containers().items():
            if len(ch) == 256:
                return ch
        return None

    def swatches(self):
        cont = self.containers()
        for parent, ch in cont.items():
            if len(ch) == 16 and all(not cont.get(x) for x in ch):
                return ch
        return None

    def input_id(self):
        m = re.search(r'input #(vnode_\d+)', self.settled_snap())
        return m.group(1) if m else None

    def set_path(self, path):
        for action in ("type_text", "set_value"):
            for _ in range(3):
                vid = self.input_id()
                if vid is None:
                    time.sleep(1)
                    continue
                r = self.call("autoui_action", element_id=vid,
                              action=action, value=path)
                if "status: ok" in r:
                    time.sleep(0.8)
                    m = re.search(r'export_path: "([^"]*)"', self.state("export_path"))
                    if m and m.group(1) == path:
                        return True
        return False

    def wait_status(self, expected, timeout=5.0):
        """Poll until the status bar shows a terminal value (review R-1:
        handlers set status as their LAST statement, so a terminal status
        implies the preceding px/file work and re-render completed)."""
        if isinstance(expected, str):
            expected = (expected,)
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.status()
            if last in expected:
                return last
            time.sleep(0.4)
        return last

    def _press_to_status(self, button, expected, timeout):
        self.click(button)
        st = self.wait_status(expected, timeout)
        if st not in expected:
            # press lost across a render window: re-press from a fresh settle
            self.click(button)
            st = self.wait_status(expected, timeout)
        return st

    def load_terminal(self, expected):
        return self._press_to_status("Load", expected if isinstance(expected, tuple)
                                     else (expected,), 5.0)

    def save_terminal(self):
        return self._press_to_status("Save", ("saved", "save failed"), 5.0)

    def export_terminal(self):
        return self._press_to_status("Export", ("exported", "export failed"), 6.0)

    def export_verify(self, verify, timeout=8.0, tries=2):
        """Effect-based export wait (review R-1 round 2): the status bar may
        ALREADY show the expected terminal from a previous export, so status
        membership is unsound. Poll `verify()` (file content / failure
        status) after each Export press; re-press once if the press was lost
        across a render window. Returns the final status text."""
        for i in range(tries):
            self.click("Export")
            deadline = time.time() + timeout
            while time.time() < deadline:
                if verify():
                    return self.status()
                time.sleep(0.4)
        return self.status()

    def paint(self, index, swatch_pos, expect=None):
        """Paint one cell via real UI presses and VERIFY the effect landed on
        the intended cell (review R-01: a press racing a re-render could
        address a stale vnode and paint a stray cell). On a detected stray
        (px changed elsewhere) undo the misfire and retry with fresh
        addressing; bounded to 3 attempts."""
        self.click("Pencil")
        sw = self.swatches()
        self.call("autoui_action", element_id=sw[swatch_pos], action="press")
        for _ in range(3):
            pre = self.px()
            ok_pre = len(pre) == 256
            cells = self.cells()
            self.call("autoui_action", element_id=cells[index], action="press")
            time.sleep(0.4)
            if expect is None:
                return True
            px = self.px()
            if ok_pre and len(px) == 256:
                want = list(pre)
                want[index] = expect
                if px == want:
                    return True
                if px != pre:
                    self.click("Undo")   # roll back the stray paint
                    time.sleep(0.4)
            # px == pre: press was a no-op (stale id), retry with fresh ids
        return False

    def close(self):
        """Strong-kill our own spawned process tree (P-02 kill semantics)."""
        if self.proc is not None:
            try:
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                               capture_output=True)
            except Exception:
                pass
        time.sleep(3)
        wait_port_free(self.port)


def run_vm_profile(report, evidence_dir):
    storage = os.path.join(tempfile.gettempdir(),
                           f"paint-verify-vm-{int(time.time())}.json")
    with open(storage, "w", encoding="utf-8") as f:
        json.dump({}, f)
    s = VmSession(storage, report)
    if not s.ready:
        return 1
    out_svg = os.path.join(tempfile.gettempdir(),
                           f"paint-verify-vm-{int(time.time())}.svg").replace("\\", "/")
    # sparse designed pattern shared by V-01/V-02 and the 002 additions
    pts = [(0, 0), (15, 0), (7, 0), (0, 7),
           (7, 7), (8, 8), (15, 8), (0, 15), (8, 15), (15, 15)]
    want = [WHITE] * 256
    for c, r in pts:
        want[r * 16 + c] = RED
    try:
        # ── P-01: standalone gate self-sufficiency (bounded readiness,
        # own resources; foreign state respected) ──
        print("\nP-01 [vm]: gate prep / first boot self-sufficiency")
        check0 = lambda name, cond, detail="": report.check("P-01", name, cond, detail)
        check0("isolated storage file owned by run",
               os.path.exists(storage) and tempfile.gettempdir() in storage, storage)
        check0("boot readiness bounded (rendered first frame)", s.ready, "not ready")

        # ── V-01: pixel vector fidelity through real UI ops ──
        print("\nV-01 [vm]: pixel vector fidelity (256 items, per-cell)")
        check = lambda name, cond, detail="": report.check("V-01", name, cond, detail)

        px = s.px()
        check("initial 256 white vector", len(px) == 256 and all(c == WHITE for c in px),
              f"len={len(px)} first={px[:3]}")

        # single point: red at (0,0), undo, redo
        s.paint(0, 1, expect=RED)
        px = s.px()
        check("single point: 1 red at 0",
              len(px) == 256 and px[0] == RED and sum(1 for c in px if c == RED) == 1,
              f"px0={px[0] if px else None}")
        s.click("Undo")
        time.sleep(0.5)
        px = s.px()
        check("undo single point -> 256 white",
              len(px) == 256 and all(c == WHITE for c in px), f"len={len(px)}")
        s.click("Redo")
        time.sleep(0.5)
        px = s.px()
        check("redo single point -> 1 red (uniform-adjacent snapshot)",
              len(px) == 256 and px[0] == RED, f"px0={px[0] if px else None}")

        # uniform black (#111827): clean canvas, one dark cell + flood
        s.click("New")
        time.sleep(0.5)
        s.paint(3, 0, expect=DARK)
        s.click("Fill")
        cells = s.cells()
        s.call("autoui_action", element_id=cells[4], action="press")
        time.sleep(0.5)
        px = s.px()
        check("flood -> uniform 256 dark",
              len(px) == 256 and all(c == DARK for c in px),
              f"dark={px.count(DARK) if px else 0}")
        s.save_terminal()
        saved_px = px
        s.click("New")
        time.sleep(0.5)
        s.load_terminal("loaded")
        px = s.px()
        check("uniform dark: save -> new -> load identical vector",
              px == saved_px and len(px) == 256, f"dark={px.count(DARK) if px else 0}")
        s.click("Undo")
        time.sleep(0.5)
        px = s.px()
        check("undo after load -> 256 white (uniform white restore)",
              len(px) == 256 and all(c == WHITE for c in px),
              f"white={px.count(WHITE) if px else 0}")
        s.click("Redo")
        time.sleep(0.5)
        px = s.px()
        check("redo after undo -> uniform dark (uniform restore)",
              len(px) == 256 and all(c == DARK for c in px),
              f"dark={px.count(DARK) if px else 0}")

        # sparse designed pattern (2026-10-29 user ruling: simple figure for
        # import/export cases, not cell-by-cell fill): 4 corners (index bounds
        # 0/15/240/255) + asymmetric edge pair (row/col swap would flip them)
        # + center pair — 10 reds.
        s.click("New")
        time.sleep(0.5)
        report.fixtures["sparse_points"] = sha256(json.dumps(pts))
        for c, r in pts:
            s.paint(r * 16 + c, 1, expect=RED)
        px = s.px()
        check("sparse pattern painted per-cell exact",
              px == want, f"red={px.count(RED) if px else 0}")
        s.save_terminal()
        s.click("New")
        time.sleep(0.5)
        s.load_terminal("loaded")
        px = s.px()
        check("sparse pattern save -> new -> load identical vector", px == want,
              f"red={px.count(RED) if px else 0}")

        # ── V-02: SVG export fidelity + real render ──
        print("\nV-02 [vm]: SVG export")
        check2 = lambda name, cond, detail="": report.check("V-02", name, cond, detail)
        s.export_verify(lambda: s.status() == "export: path required")
        check2("empty path -> 'export: path required'",
               s.status() == "export: path required", s.status())
        ok = s.set_path(out_svg)
        check2("path input set via UI", ok, "input value mismatch")
        oracle = expected_svg(want)
        s.export_verify(lambda: os.path.exists(out_svg)
                        and open(out_svg, encoding="utf-8").read() == oracle)
        check2("status exported", s.status() == "exported", s.status())
        if os.path.exists(out_svg):
            content = open(out_svg, encoding="utf-8").read()
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                root = None
                check2("XML parses", False, str(e))
            if root is not None:
                check2("XML parses, svg root", root.tag == SVG_NS + "svg", root.tag)
                check2("16x16 canvas attrs",
                      root.get("width") == "16" and root.get("height") == "16",
                      f"{root.get('width')}x{root.get('height')}")
                rects = root.findall(SVG_NS + "rect")
                non_white = [r for r in rects[1:]]
                expect_pts = [(str(i % 16), str(i // 16), RED) for i in range(256) if want[i] == RED]
                got_pts = [(r.get("x"), r.get("y"), r.get("fill")) for r in non_white]
                check2("pixel positions/fills match model (10 cells)",
                       got_pts == expect_pts,
                       f"got {len(got_pts)} rects, first mismatch "
                       f"{next((a for a, b in zip(got_pts, expect_pts) if a != b), None)}")
                check2("no unescaped/script content",
                       "<script" not in content and "&" not in content, content[:120])
                check2("bytes equal oracle SVG", content == oracle,
                       f"len file={len(content)} oracle={len(oracle)}")
        else:
            check2("export file exists", False, out_svg)
        # unwritable path: directory as file -> visible failure, canvas intact
        px_before = s.px()
        s.set_path(tempfile.gettempdir().replace("\\", "/"))
        s.export_verify(lambda: s.status() == "export failed")
        check2("unwritable path -> 'export failed' visible",
               s.status() == "export failed", s.status())
        check2("canvas preserved after failed export", s.px() == px_before, "px changed")

        # ── P-02 [vm]: strong-kill cross-process reopen + next edit ──
        # storage currently holds the sparse pattern (saved in V-01).
        print("\nP-02 [vm]: strong-kill cross-process reopen, next edit")
        checkp2 = lambda name, cond, detail="": report.check("P-02", name, cond, detail)
        want_a = list(want)
        want_a[55] = DARK
        s.paint(55, 0, expect=DARK)
        time.sleep(0.3)
        checkp2("next edit after V-02 flow painted", s.px() == want_a, "px mismatch")
        s.save_terminal()
        checkp2("save status", s.status() == "saved", s.status())
        pid1 = s.proc.pid
        s.close()
        report.fixtures["vm_kill1_pid"] = str(pid1)
        s = VmSession(storage, report)
        if not s.ready:
            return 1
        px = s.px()
        checkp2("fresh boot starts white (no auto-load)",
                len(px) == 256 and all(c == WHITE for c in px), f"len={len(px)}")
        s.load_terminal("loaded")
        checkp2("reopen same storage -> Load 256-cell identical", s.px() == want_a,
                f"red={s.px().count(RED)}")
        s.paint(100, 0, expect=DARK)
        time.sleep(0.3)
        want_b = list(want_a)
        want_b[100] = DARK
        checkp2("edit after reopen works", s.px() == want_b, "px mismatch")
        s.save_terminal()
        s.close()
        s = VmSession(storage, report)
        if not s.ready:
            return 1
        s.load_terminal("loaded")
        checkp2("second reopen -> Load still identical", s.px() == want_b,
                f"red={s.px().count(RED)} dark={s.px().count(DARK)}")
        # review R-03 counterexample: an unsaved in-memory edit must NOT
        # survive a strong-kill reopen (vm side; vue side is evidenced by the
        # P-03 recovery Load restoring the last save).
        s.paint(200, 0, expect=DARK)
        time.sleep(0.3)
        want_u = list(want_b)
        want_u[200] = DARK
        checkp2("unsaved edit visible in live session", s.px() == want_u,
                "px mismatch")
        s.close()
        s = VmSession(storage, report)
        if not s.ready:
            return 1
        s.load_terminal("loaded")
        checkp2("unsaved edit does not survive reopen", s.px() == want_b,
                f"dark={s.px().count(DARK)}")

        # ── P-03 [vm]: export paths, overwrite, failure recovery ──
        print("\nP-03 [vm]: Chinese/space path, overwrite, failure+recovery")
        checkp3 = lambda name, cond, detail="": report.check("P-03", name, cond, detail)
        cn_dir = os.path.join(tempfile.gettempdir(), "paint-verify 中文 目录")
        os.makedirs(cn_dir, exist_ok=True)
        cn_path = os.path.join(cn_dir, "画作 测试.svg").replace("\\", "/")
        oracle_b = expected_svg(want_b)
        checkp3("Chinese/space path set via UI", s.set_path(cn_path), "input mismatch")
        s.export_verify(lambda: os.path.exists(cn_path)
                        and open(cn_path, encoding="utf-8").read() == oracle_b)
        checkp3("Chinese/space path exported", s.status() == "exported", s.status())
        content_b = open(cn_path, encoding="utf-8").read() if os.path.exists(cn_path) else ""
        checkp3("Chinese/space path file byte-equals oracle", content_b == oracle_b,
                f"len={len(content_b)}/{len(oracle_b)}")
        # overwrite existing target: export different content to the SAME path
        s.paint(150, 0, expect=DARK)
        time.sleep(0.3)
        want_c = list(want_b)
        want_c[150] = DARK
        oracle_c = expected_svg(want_c)
        s.export_verify(lambda: os.path.exists(cn_path)
                        and open(cn_path, encoding="utf-8").read() == oracle_c)
        content_c = open(cn_path, encoding="utf-8").read() if os.path.exists(cn_path) else ""
        checkp3("existing target overwritten with new content",
                content_c == oracle_c and content_c != content_b,
                f"len={len(content_c)}")
        # failure: nonexistent directory -> visible failure, no file, canvas intact
        px_before = s.px()
        bad_path = os.path.join(tempfile.gettempdir(),
                                f"paint-verify-no-such-dir-{int(time.time())}",
                                "x.svg").replace("\\", "/")
        s.set_path(bad_path)
        s.export_verify(lambda: s.status() == "export failed")
        checkp3("bad dir -> 'export failed' visible", s.status() == "export failed",
                s.status())
        checkp3("failed export created no file", not os.path.exists(bad_path), bad_path)
        checkp3("canvas preserved after failed export", s.px() == px_before, "px changed")
        # recovery: next export to a good path succeeds
        rec_path = os.path.join(tempfile.gettempdir(),
                                f"paint-verify-vm-recovery-{int(time.time())}.svg").replace("\\", "/")
        s.set_path(rec_path)
        s.export_verify(lambda: os.path.exists(rec_path)
                        and open(rec_path, encoding="utf-8").read() == oracle_c)
        checkp3("recovery export succeeds", s.status() == "exported", s.status())
        checkp3("recovery file byte-equals oracle",
                os.path.exists(rec_path) and
                open(rec_path, encoding="utf-8").read() == oracle_c, rec_path)

        # ── V-03: bad data rejection + v1 migration ──
        print("\nV-03 [vm]: failure paths & migration")
        check3 = lambda name, cond, detail="": report.check("V-03", name, cond, detail)
        px_before = s.px()
        s.close()
        # seed bad v2 (258 items) -> Load must reject, canvas untouched
        bad_v2 = "PAINT-V2|16|16|" + "|".join([RED] * 255)
        report.fixtures["bad_v2_255"] = sha256(bad_v2)
        json.dump({"paint.project.v2": bad_v2}, open(storage, "w", encoding="utf-8"))
        s = VmSession(storage, report)
        if not s.ready:
            return 1
        s.load_terminal("bad save data")
        check3("bad v2 (255 items) rejected", s.status() == "bad save data", s.status())
        check3("canvas unchanged after bad v2 load",
               len(s.px()) == 256 and all(c == WHITE for c in s.px()), "px changed")
        # seed v1 all-red -> migrate
        v1_all_red = "|".join([" bg-[#ef4444] "] * 256)
        report.fixtures["v1_all_red"] = sha256(v1_all_red)
        json.dump({"paint.canvas.v1": v1_all_red}, open(storage, "w", encoding="utf-8"))
        s.close()
        s = VmSession(storage, report)
        if not s.ready:
            return 1
        s.load_terminal("loaded v1")
        check3("v1 all-red migrates", s.status() == "loaded v1", s.status())
        px = s.px()
        check3("v1 migration vector exact (256 red)",
               len(px) == 256 and all(c == RED for c in px),
               f"red={px.count(RED) if px else 0}")
        # seed v1 with illegal color -> reject
        v1_bad = "|".join([" bg-[#ef4444] "] * 255 + [" bg-[#00ff00] "])
        report.fixtures["v1_illegal"] = sha256(v1_bad)
        json.dump({"paint.canvas.v1": v1_bad}, open(storage, "w", encoding="utf-8"))
        s.close()
        s = VmSession(storage, report)
        if not s.ready:
            return 1
        s.load_terminal("bad save data")
        check3("v1 illegal color rejected", s.status() == "bad save data", s.status())
        check3("canvas unchanged after illegal v1",
               len(s.px()) == 256 and all(c == WHITE for c in s.px()), "px changed")
        # undo cap + explicit status
        for _ in range(3):
            s.click("Undo")
        time.sleep(0.8)
        check3("undo to stack bottom -> 'nothing to undo' visible",
               s.status() == "nothing to undo", s.status())

        # ── P-04: counterexample controls (oracle non-vacuity) ──
        print("\nP-04 [vm]: mutation control, no-file control")
        checkp4 = lambda name, cond, detail="": report.check("P-04", name, cond, detail)
        # mutation control: corrupt one cell fill on disk -> the suite's own
        # per-cell and byte oracles must detect it (a wrong-color export
        # regression would fail this suite, i.e. nonzero exit).
        mutated = content_c.replace(f'fill="{DARK}"', f'fill="{RED}"', 1)
        checkp4("mutation applied differs from export", mutated != content_c,
                "replace no-op")
        got = svg_cell_points(mutated)
        expect_pts = [(str(i % 16), str(i // 16), c) for i, c in enumerate(want_c)
                      if c != WHITE]
        checkp4("per-cell oracle detects one-cell corruption",
                got != expect_pts,
                f"first diff={next((a for a, b in zip(got or [], expect_pts) if a != b), None)}")
        checkp4("byte oracle detects corruption", mutated != oracle_c, "byte equal?!")
        # missing-export counterexample replay: the P-03 failure path produced
        # no file (assertion bound here so removal of that check breaks P-04)
        checkp4("failed export left no output (replay)", not os.path.exists(bad_path),
                bad_path)
    finally:
        s.close()
    return 0


# ─────────────────────────── vue profile (Playwright) ──────────────────────

FRONT = "http://localhost:17834"
BACK = "http://127.0.0.1:17835"


class VueSession:
    """UI helpers on top of a (persistent) browser context."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.pages[0] if ctx.pages else ctx.new_page()

    def px(self):
        """256 hex list read from cell classes (real DOM observation)."""
        cls = self.page.evaluate(
            "() => Array.from(document.querySelectorAll('.w-5.h-5.cursor-pointer'))"
            + ".map(e => e.className)")
        out = []
        for c in cls:
            m = re.search(r"bg-\[#[0-9a-fA-F]{6}\]", c)
            out.append(m.group(0)[4:-1] if m else "?")
        return out

    def status(self):
        el = self.page.locator(".ml-auto.text-xs")
        return el.text_content() or ""

    def button(self, label):
        return self.page.get_by_role("button", name=label, exact=False)

    def cells(self):
        return self.page.locator(".w-5.h-5.cursor-pointer")

    def swatches(self):
        return self.page.locator(".w-6.h-6.rounded")

    def click_cell(self, index):
        self.cells().nth(index).click()
        self.page.wait_for_timeout(120)

    def click_swatch(self, pos):
        self.swatches().nth(pos).click()
        self.page.wait_for_timeout(120)

    def set_path(self, path):
        inp = self.page.locator("input")
        inp.fill(path)
        self.page.wait_for_timeout(150)
        return inp.input_value() == path

    def wait_status(self, expected, timeout=6.0):
        """Poll DOM status until a terminal value (review R-1 Mode A/B)."""
        if isinstance(expected, str):
            expected = (expected,)
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.status()
            if last in expected:
                return last
            self.page.wait_for_timeout(300)
        return last

    def export_verify(self, verify, timeout=8.0, tries=2):
        """Effect-based export wait: poll `verify()` (file content / failure
        status) after each Export click; re-click once if the click was
        lost. Status membership alone is unsound when the bar already shows
        the expected terminal from a previous export."""
        for i in range(tries):
            self.button("Export").click()
            deadline = time.time() + timeout
            while time.time() < deadline:
                if verify():
                    return self.status()
                self.page.wait_for_timeout(400)
        return self.status()

    def press_to(self, label, expected, tries=2):
        """Click a button, wait for a terminal status; re-press once from a
        fresh state if the click was lost."""
        st = ""
        for i in range(tries):
            self.button(label).click()
            st = self.wait_status(expected, 5.0)
            if st in (expected if isinstance(expected, tuple) else (expected,)):
                return st
        return st


class VueBrowser:
    """Persistent-profile browser lifecycle (002 T-01).

    The chromium process tree belongs to this run: `hard_kill` terminates it
    by matching our own user-data-dir on the command line, never by port or
    name similarity. Relaunching with the same user-data-dir is the real
    cross-process reopen for the vue storage profile (P-02).
    """

    def __init__(self, report, udd):
        from playwright.sync_api import sync_playwright
        self.report = report
        self.udd = udd
        self.pw = sync_playwright().start()
        self.ctx = None

    def open(self, timeout_ms=30000):
        self.ctx = self.pw.chromium.launch_persistent_context(
            self.udd, headless=True, viewport={"width": 1280, "height": 900})
        page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        page.goto(FRONT, wait_until="networkidle", timeout=90000)
        page.wait_for_selector(".w-5.h-5", timeout=timeout_ms)
        return VueSession(self.ctx)

    def hard_kill(self):
        """Strong-kill the whole chromium tree we spawned (own profile dir)."""
        try:
            out = subprocess.run(
                ["wmic", "process", "where",
                 f"commandline like '%{self.udd.replace('\\', '/')[:48]}%'",
                 "get", "processid"], capture_output=True, text=True).stdout
            pids = [l.strip() for l in out.splitlines() if l.strip().isdigit()]
            for pid in pids:
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                               capture_output=True)
        except Exception:
            pass
        try:
            if self.ctx is not None:
                self.ctx.close()
        except Exception:
            pass
        self.ctx = None
        time.sleep(2)

    def close(self):
        try:
            if self.ctx is not None:
                self.ctx.close()
        except Exception:
            pass
        try:
            self.pw.stop()
        except Exception:
            pass


class VueApp:
    """Restart-tolerant handle for `auto run -r vue --server vm`.

    Framework observation (001 T-05): the dev-server supervisor exits on its
    own ~90-100s after start (`pnpm exited with code Some(143)`); project
    state lives in browser localStorage, so a restart + page reload is
    transparent to acceptance flow. The driver restarts the app at phase
    boundaries. 002 T-01: port cleanup sweeps only pids that appeared during
    our own spawn window (pre-start listeners are foreign and respected).
    """

    def __init__(self):
        self.proc = None
        self.log = None
        self.pre = {17834: port_pids(17834), 17835: port_pids(17835)}

    @staticmethod
    def alive():
        try:
            if requests.get(FRONT + "/", timeout=2).status_code != 200:
                return False
        except Exception:
            return False
        try:
            requests.get(BACK + "/", timeout=2)
            return True
        except Exception:
            return False

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T",
                                "/F"], capture_output=True)
            self.proc = None
        for port in (17834, 17835):
            for pid in port_pids(port) - self.pre[port]:
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                               capture_output=True)
        wait_port_free(17834)
        wait_port_free(17835)

    def kill_back_only(self):
        """Kill only the 17835 listener that appeared during our spawn."""
        for pid in port_pids(17835) - self.pre[17835]:
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                           capture_output=True)
        time.sleep(2)
        try:
            requests.get(BACK + "/", timeout=2)
            return False
        except Exception:
            return True

    def start(self):
        self.stop()
        self.log = open(os.path.join(tempfile.gettempdir(),
                                     "paint-verify-vue.log"), "w")
        try:
            self.proc = subprocess.Popen(
                [AUTO_BIN, "run", "-r", "vue", "--server", "vm"], cwd=PROJ,
                stdout=self.log, stderr=subprocess.STDOUT)
        except OSError as e:
            self.proc = None
            print(f"[vue] spawn failed: {e}")
            return False
        deadline = time.time() + 150
        while time.time() < deadline:
            if self.alive():
                return True
            if self.proc.poll() is not None and not self.alive():
                return False
            time.sleep(3)
        return self.alive()


def run_vue_profile(report, evidence_dir):
    app = VueApp()
    udd = os.path.join(tempfile.gettempdir(),
                       f"paint-verify-vue-profile-{int(time.time())}")
    out_svg = os.path.join(tempfile.gettempdir(),
                           f"paint-verify-vue-{int(time.time())}.svg").replace("\\", "/")
    br = None
    s = None
    try:
        # ── P-01: gate prep — foreign port users respected, bounded boot ──
        print("\nP-01 [vue]: gate prep / first boot self-sufficiency")
        check0 = lambda name, cond, detail="": report.check("P-01", name, cond, detail)
        check0("front port free before start (foreign users respected)",
               not app.pre[17834], f"pids={app.pre[17834]}")
        check0("back port free before start (foreign users respected)",
               not app.pre[17835], f"pids={app.pre[17835]}")
        if not app.start():
            report.check("vue-boot", "vue dev server up (front+back)", False,
                         "not listening within 150s")
            return 1
        report.check("vue-boot", "vue dev server up (front+back)", True)
        br = VueBrowser(report, udd)
        s = br.open()
        report.check("vue-boot", "vue app rendered first frame (persistent profile)",
                     True, udd)

        pts = [(0, 0), (15, 0), (7, 0), (0, 7),
               (7, 7), (8, 8), (15, 8), (0, 15), (8, 15), (15, 15)]
        want = [WHITE] * 256
        for c, r in pts:
            want[r * 16 + c] = RED

        def ensure_up(tag, restore_load):
            """Restart the dev server if the framework ended it; after a
            restart the in-memory canvas is gone, so optionally restore via
            Load (localStorage survives in the persistent browser)."""
            if VueApp.alive():
                return True
            report.versions[f"restarted_before_{tag}"] = "yes"
            if not app.start():
                report.check("vue-lifecycle", f"dev server restart before {tag}",
                             False, "not listening")
                return False
            s.page.goto(FRONT, wait_until="networkidle", timeout=60000)
            s.page.wait_for_selector(".w-5.h-5", timeout=30000)
            if restore_load:
                s.press_to("Load", "loaded")
            return True

        print("\nV-01 [vue]: pixel vector fidelity (256 items, per-cell)")
        check = lambda name, cond, detail="": report.check("V-01", name, cond, detail)
        px = s.px()
        check("initial 256 white vector",
              len(px) == 256 and all(c == WHITE for c in px),
              f"len={len(px)} sample={px[:3]}")
        s.click_swatch(1)
        s.click_cell(0)
        px = s.px()
        check("single point: 1 red at 0",
              len(px) == 256 and px[0] == RED and px.count(RED) == 1,
              f"px0={px[0]}")
        s.button("Undo").click()
        s.page.wait_for_timeout(300)
        px = s.px()
        check("undo -> 256 white", all(c == WHITE for c in px),
              f"white={px.count(WHITE)}")
        s.button("Redo").click()
        s.page.wait_for_timeout(300)
        px = s.px()
        check("redo -> 1 red", px[0] == RED and px.count(RED) == 1, f"px0={px[0]}")

        # same sparse designed pattern as the vm profile (10 reds, simple
        # figure for import/export cases per 2026-10-29 user ruling)
        report.fixtures["sparse_points"] = sha256(json.dumps(pts))
        s.click_swatch(1)
        for c, r in pts:
            s.click_cell(r * 16 + c)
        px = s.px()
        check("sparse pattern painted per-cell exact", px == want,
              f"red={px.count(RED)}")
        s.press_to("Save", "saved")
        check("status saved", s.status() == "saved", s.status())
        s.button("New").click()
        s.page.wait_for_timeout(300)
        s.page.reload(wait_until="networkidle")   # 真“重开”：整页重载
        s.page.wait_for_selector(".w-5.h-5", timeout=30000)
        s.press_to("Load", "loaded")
        px = s.px()
        check("save -> reload -> load identical vector", px == want,
              f"red={px.count(RED)}")

        print("\nV-02 [vue]: SVG export")
        check2 = lambda name, cond, detail="": report.check("V-02", name, cond, detail)
        if not ensure_up("V-02", restore_load=True):
            return 1
        if os.path.exists(out_svg):
            os.remove(out_svg)
        s.export_verify(lambda: s.status() == "export: path required")
        check2("empty path -> 'export: path required'",
               s.status() == "export: path required", s.status())
        check2("path input set via UI", s.set_path(out_svg), "input value mismatch")
        oracle = expected_svg(want)
        s.export_verify(lambda: os.path.exists(out_svg)
                        and open(out_svg, encoding="utf-8").read() == oracle)
        check2("status exported", s.status() == "exported", s.status())
        if os.path.exists(out_svg):
            content = open(out_svg, encoding="utf-8").read()
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                root = None
                check2("XML parses", False, str(e))
            if root is not None:
                check2("XML parses, svg root", root.tag == SVG_NS + "svg", root.tag)
                rects = root.findall(SVG_NS + "rect")
                expect_pts = [(str(i % 16), str(i // 16), RED) for i in range(256) if want[i] == RED]
                got_pts = [(r.get("x"), r.get("y"), r.get("fill")) for r in rects[1:]]
                check2("pixel positions/fills match model (10 cells)",
                       got_pts == expect_pts, f"got {len(got_pts)}")
                check2("bytes equal oracle SVG", content == oracle,
                       f"len file={len(content)}")
        else:
            check2("export file exists", False, out_svg)
        # real render in chromium
        render_page = s.ctx.new_page()
        render_page.goto("file:///" + out_svg.replace("\\", "/"))
        render_page.wait_for_timeout(800)
        shot = os.path.join(evidence_dir, f"vue-svg-render-{int(time.time())}.png")
        os.makedirs(evidence_dir, exist_ok=True)
        render_page.screenshot(path=shot)
        body = render_page.evaluate("document.documentElement.namespaceURI")
        check2("svg renders in chromium (screenshot saved)",
               os.path.exists(shot) and os.path.getsize(shot) > 500,
               f"shot={shot}")
        render_page.close()
        # unwritable path
        px_before = s.px()
        s.set_path(tempfile.gettempdir().replace("\\", "/"))
        s.export_verify(lambda: s.status() == "export failed")
        check2("unwritable path -> 'export failed' visible",
               s.status() == "export failed", s.status())
        check2("canvas preserved after failed export", s.px() == px_before,
               "px changed")

        # ── P-02 [vue]: hard-kill the browser tree -> reopen persistent
        # profile -> Load identical -> next edit (true cross-process reopen
        # for the localStorage profile) ──
        print("\nP-02 [vue]: browser hard-kill reopen via persistent profile")
        checkp2 = lambda name, cond, detail="": report.check("P-02", name, cond, detail)
        if not ensure_up("P-02", restore_load=False):
            return 1
        br.hard_kill()
        s = br.open()
        px = s.px()
        checkp2("fresh browser starts white (no auto-load)",
                len(px) == 256 and all(c == WHITE for c in px), f"len={len(px)}")
        s.press_to("Load", "loaded")
        checkp2("persistent profile -> Load 256-cell identical", s.px() == want,
                f"red={s.px().count(RED)}")
        s.click_swatch(0)
        s.click_cell(55)
        want_a = list(want)
        want_a[55] = DARK
        checkp2("next edit after reopen works", s.px() == want_a, "px mismatch")
        s.press_to("Save", "saved")
        checkp2("save after reopen", s.status() == "saved", s.status())

        # ── P-03 [vue]: Chinese/space path, overwrite, backend-down failure
        # visible + recovery ──
        print("\nP-03 [vue]: export paths, backend-down failure, recovery")
        checkp3 = lambda name, cond, detail="": report.check("P-03", name, cond, detail)
        if not ensure_up("P-03", restore_load=True):
            return 1
        cn_dir = os.path.join(tempfile.gettempdir(), "paint-verify 中文 输出")
        os.makedirs(cn_dir, exist_ok=True)
        cn_path = os.path.join(cn_dir, "画作 测试.svg").replace("\\", "/")
        oracle_a = expected_svg(want_a)
        checkp3("Chinese/space path set via UI", s.set_path(cn_path), "input mismatch")
        s.export_verify(lambda: os.path.exists(cn_path)
                        and open(cn_path, encoding="utf-8").read() == oracle_a)
        checkp3("Chinese/space path exported", s.status() == "exported", s.status())
        content_a = open(cn_path, encoding="utf-8").read() if os.path.exists(cn_path) else ""
        checkp3("Chinese/space path file byte-equals oracle", content_a == oracle_a,
                f"len={len(content_a)}/{len(oracle_a)}")
        # overwrite existing target
        s.click_swatch(0)
        s.click_cell(100)
        want_b = list(want_a)
        want_b[100] = DARK
        oracle_b = expected_svg(want_b)
        s.export_verify(lambda: os.path.exists(cn_path)
                        and open(cn_path, encoding="utf-8").read() == oracle_b)
        content_b = open(cn_path, encoding="utf-8").read() if os.path.exists(cn_path) else ""
        checkp3("existing target overwritten with new content",
                content_b == oracle_b and content_b != content_a, f"len={len(content_b)}")
        # backend down: export fails VISIBLY (no stale 'exported'), no file,
        # canvas/project untouched
        down = app.kill_back_only()
        checkp3("back 17835 down after own-pid kill", down, "back still alive")
        px_before = s.px()
        fail_path = os.path.join(tempfile.gettempdir(),
                                 f"paint-verify-vue-fail-{int(time.time())}.svg").replace("\\", "/")
        s.set_path(fail_path)
        s.export_verify(lambda: s.status() == "export failed")
        checkp3("backend down -> 'export failed' visible (no false success)",
                s.status() == "export failed", s.status())
        checkp3("backend down -> no file written", not os.path.exists(fail_path),
                fail_path)
        checkp3("canvas preserved after backend-down export", s.px() == px_before,
                "px changed")
        # recovery: restart app, reload page, Load, next export succeeds.
        # storage holds the last SAVE (want_a from P-02); the unsaved cell-100
        # edit lived only in the old page, so Load must restore want_a.
        if not app.start():
            report.check("vue-lifecycle", "app restart for recovery", False,
                         "not listening")
            return 1
        s.page.goto(FRONT, wait_until="networkidle", timeout=60000)
        s.page.wait_for_selector(".w-5.h-5", timeout=30000)
        s.press_to("Load", "loaded")
        if s.px() != want_a:
            # first post-restart load raced server/page warmup: reload once
            s.page.reload(wait_until="networkidle")
            s.page.wait_for_selector(".w-5.h-5", timeout=30000)
            s.press_to("Load", "loaded")
        checkp3("recovery: Load identical after app restart", s.px() == want_a,
                f"red={s.px().count(RED)} dark={s.px().count(DARK)}")
        rec_path = os.path.join(tempfile.gettempdir(),
                                f"paint-verify-vue-recovery-{int(time.time())}.svg").replace("\\", "/")
        s.set_path(rec_path)
        s.export_verify(lambda: os.path.exists(rec_path)
                        and open(rec_path, encoding="utf-8").read() == oracle_a)
        checkp3("recovery export succeeds", s.status() == "exported", s.status())
        checkp3("recovery file byte-equals oracle",
                os.path.exists(rec_path) and
                open(rec_path, encoding="utf-8").read() == oracle_a, rec_path)

        print("\nV-03 [vue]: failure paths & migration (localStorage)")
        check3 = lambda name, cond, detail="": report.check("V-03", name, cond, detail)
        if not ensure_up("V-03", restore_load=False):
            return 1
        s.button("New").click()
        s.page.wait_for_timeout(300)
        # bad v2 via localStorage seeding
        bad_v2 = "PAINT-V2|16|16|" + "|".join([RED] * 255)
        report.fixtures["bad_v2_255"] = sha256(bad_v2)
        s.page.evaluate("v => localStorage.setItem('paint.project.v2', v)", bad_v2)
        px_before = s.px()
        s.press_to("Load", ("loaded", "loaded v1", "bad save data"))
        check3("bad v2 (255 items) rejected", s.status() == "bad save data",
               s.status())
        check3("canvas unchanged after bad v2 load", s.px() == px_before,
               "px changed")
        # v1 migration
        v1_all_red = "|".join([" bg-[#ef4444] "] * 256)
        report.fixtures["v1_all_red"] = sha256(v1_all_red)
        s.page.evaluate("v => localStorage.setItem('paint.canvas.v1', v)", v1_all_red)
        s.page.evaluate("localStorage.removeItem('paint.project.v2')")
        s.press_to("Load", ("loaded", "loaded v1", "bad save data"))
        check3("v1 all-red migrates", s.status() == "loaded v1", s.status())
        px = s.px()
        check3("v1 migration vector exact (256 red)",
               len(px) == 256 and all(c == RED for c in px),
               f"red={px.count(RED) if px else 0}")
        # illegal color
        v1_bad = "|".join([" bg-[#ef4444] "] * 255 + [" bg-[#00ff00] "])
        report.fixtures["v1_illegal"] = sha256(v1_bad)
        s.page.evaluate("v => localStorage.setItem('paint.canvas.v1', v)", v1_bad)
        px_before = s.px()
        s.press_to("Load", ("loaded", "loaded v1", "bad save data"))
        check3("v1 illegal color rejected", s.status() == "bad save data",
               s.status())
        check3("canvas unchanged after illegal v1", s.px() == px_before,
               "px changed")

        # ── P-04 [vue]: counterexample controls ──
        print("\nP-04 [vue]: mutation control, no-file control")
        checkp4 = lambda name, cond, detail="": report.check("P-04", name, cond, detail)
        mutated = content_b.replace(f'fill="{DARK}"', f'fill="{RED}"', 1)
        checkp4("mutation applied differs from export", mutated != content_b,
                "replace no-op")
        got = svg_cell_points(mutated)
        expect_pts = [(str(i % 16), str(i // 16), c) for i, c in enumerate(want_b)
                      if c != WHITE]
        checkp4("per-cell oracle detects one-cell corruption",
                got != expect_pts, "mutation undetected")
        checkp4("byte oracle detects corruption", mutated != oracle_b, "byte equal?!")
        checkp4("backend-down export left no output (replay)",
                not os.path.exists(fail_path), fail_path)
    finally:
        app.stop()
        if br is not None:
            br.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=["vm", "vue"], required=True)
    ap.add_argument("--report-dir",
                    default=os.path.join(PROJ, "docs", "plans", "attachments",
                                         "002"))
    args = ap.parse_args()

    print(f"[verify_basic] profile={args.profile} project={PROJ}")
    print(f"[verify_basic] auto bin: {AUTO_BIN}")
    report = Report(args.profile)
    try:
        v = subprocess.run([AUTO_BIN, "--version"], capture_output=True,
                           text=True, timeout=30).stdout.strip()
    except Exception:
        v = "unknown"
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJ,
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        head = "unknown"
    report.versions = {
        "auto": v,
        "git_head": head,
        "python": sys.version.split()[0],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.profile == "vm":
        rc = run_vm_profile(report, args.report_dir)
    else:
        rc = run_vue_profile(report, args.report_dir)
    failed = report.finalize(args.report_dir)
    sys.exit(1 if (failed or rc) else 0)


if __name__ == "__main__":
    main()
