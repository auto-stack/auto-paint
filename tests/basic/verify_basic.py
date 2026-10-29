#!/usr/bin/env python3
"""PAINT-001 basic-capabilities acceptance entry (T-05).

Real-app, real-UI acceptance for both render tracks:

  python tests/basic/verify_basic.py --profile vm
  python tests/basic/verify_basic.py --profile vue

- vm  : `auto run -r vm` + isolated AUTO_VM_STORAGE_FILE + autoui MCP driving
        (same harness family as tests/desktop_mcp.py).
- vue : `auto run -r vue --server vm` (front 17834 via vite, back 17835 via
        VM HTTP service) + Playwright chromium driving the real browser UI.
        Project save/load uses browser localStorage (fresh context = clean
        state); export goes through the back api to a real file.

Coverage per plan §6:
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

Evidence policy: this script writes a JSON report with versions, fixture
hashes, per-check results and original failure details to --report-dir
(default: docs/plans/attachments/001/, local-only, never committed).
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
        env = {**os.environ, "AUTOUI_MCP_PORT": str(self.port),
               "AUTO_VM_STORAGE_FILE": storage_path}
        self.proc = subprocess.Popen(
            [AUTO_BIN, "run", "-r", "vm"], cwd=PROJ, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def click(self, frag):
        snap = self.snapshot()
        btns = {label: vid for vid, label in
                re.findall(r'button #(vnode_\d+) "([^"]+)"', snap)}
        vid = next((v for k, v in btns.items() if frag in k), None)
        if vid is None:
            return "button not found: " + frag
        return self.call("autoui_action", element_id=vid, action="press")

    def containers(self, snap=None):
        snap = snap or self.snapshot()
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
        m = re.search(r'input #(vnode_\d+)', self.snapshot())
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

    def paint(self, index, swatch_pos):
        self.click("Pencil")
        sw = self.swatches()
        self.call("autoui_action", element_id=sw[swatch_pos], action="press")
        cells = self.cells()
        self.call("autoui_action", element_id=cells[index], action="press")

    def close(self):
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
    try:
        # ── V-01: pixel vector fidelity through real UI ops ──
        print("\nV-01 [vm]: pixel vector fidelity (256 items, per-cell)")
        check = lambda name, cond, detail="": report.check("V-01", name, cond, detail)

        px = s.px()
        check("initial 256 white vector", len(px) == 256 and all(c == WHITE for c in px),
              f"len={len(px)} first={px[:3]}")

        # single point: red at (0,0), undo, redo
        s.paint(0, 1)
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
        s.paint(3, 0)
        s.click("Fill")
        cells = s.cells()
        s.call("autoui_action", element_id=cells[4], action="press")
        time.sleep(0.5)
        px = s.px()
        check("flood -> uniform 256 dark",
              len(px) == 256 and all(c == DARK for c in px),
              f"dark={px.count(DARK) if px else 0}")
        s.click("Save")
        time.sleep(0.5)
        saved_px = px
        s.click("New")
        time.sleep(0.5)
        s.click("Load")
        time.sleep(0.8)
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
        pts = [(0, 0), (15, 0), (7, 0), (0, 7),
               (7, 7), (8, 8), (15, 8), (0, 15), (8, 15), (15, 15)]
        want = [WHITE] * 256
        for c, r in pts:
            want[r * 16 + c] = RED
        report.fixtures["sparse_points"] = sha256(json.dumps(pts))
        for c, r in pts:
            s.paint(r * 16 + c, 1)
        px = s.px()
        check("sparse pattern painted per-cell exact",
              px == want, f"red={px.count(RED) if px else 0}")
        s.click("Save")
        time.sleep(0.5)
        s.click("New")
        time.sleep(0.5)
        s.click("Load")
        time.sleep(0.8)
        px = s.px()
        check("sparse pattern save -> new -> load identical vector", px == want,
              f"red={px.count(RED) if px else 0}")

        # ── V-02: SVG export fidelity + real render ──
        print("\nV-02 [vm]: SVG export")
        check2 = lambda name, cond, detail="": report.check("V-02", name, cond, detail)
        s.click("Export")
        time.sleep(1)
        check2("empty path -> 'export: path required'",
               s.status() == "export: path required", s.status())
        ok = s.set_path(out_svg)
        check2("path input set via UI", ok, "input value mismatch")
        s.click("Export")
        time.sleep(2)
        check2("status exported", s.status() == "exported", s.status())
        oracle = expected_svg(want)
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
        s.click("Export")
        time.sleep(2)
        check2("unwritable path -> 'export failed' visible",
               s.status() == "export failed", s.status())
        check2("canvas preserved after failed export", s.px() == px_before, "px changed")

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
        s.click("Load")
        time.sleep(0.8)
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
        s.click("Load")
        time.sleep(0.8)
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
        s.click("Load")
        time.sleep(0.8)
        check3("v1 illegal color rejected", s.status() == "bad save data", s.status())
        check3("canvas unchanged after illegal v1",
               len(s.px()) == 256 and all(c == WHITE for c in s.px()), "px changed")
        # undo cap + explicit status
        for _ in range(3):
            s.click("Undo")
        time.sleep(0.8)
        check3("undo to stack bottom -> 'nothing to undo' visible",
               s.status() == "nothing to undo", s.status())
    finally:
        s.close()
    return 0


# ─────────────────────────── vue profile (Playwright) ──────────────────────

FRONT = "http://localhost:17834"
BACK = "http://127.0.0.1:17835"


class VueSession:
    def __init__(self, report):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.ready = False
        for _ in range(60):
            try:
                r = requests.get(FRONT + "/", timeout=3)
                if r.status_code == 200:
                    break
            except Exception:
                time.sleep(2)
        try:
            self.page.goto(FRONT, wait_until="networkidle", timeout=60000)
            self.page.wait_for_selector(".w-5.h-5", timeout=30000)
            self.ready = True
        except Exception as e:
            report.check("vue-boot", "vue app rendered first frame", False, str(e))

    def cells(self):
        return self.page.locator(".w-5.h-5.cursor-pointer")

    def swatches(self):
        return self.page.locator(".w-6.h-6.rounded")

    def button(self, label):
        return self.page.get_by_role("button", name=label, exact=False)

    def click_cell(self, index):
        self.cells().nth(index).click()
        self.page.wait_for_timeout(120)

    def click_swatch(self, pos):
        self.swatches().nth(pos).click()
        self.page.wait_for_timeout(120)

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

    def set_path(self, path):
        inp = self.page.locator("input")
        inp.fill(path)
        self.page.wait_for_timeout(150)
        return inp.input_value() == path

    def close(self):
        try:
            self.context.close()
            self.browser.close()
        finally:
            self.pw.stop()


class VueApp:
    """Restart-tolerant handle for `auto run -r vue --server vm`.

    Framework observation (T-05): the dev-server supervisor exits on its own
    ~90-100s after start (`pnpm exited with code Some(143)`); project state
    lives in browser localStorage, so a restart + page reload is transparent
    to acceptance flow. The driver restarts the app at phase boundaries.
    """

    def __init__(self):
        self.proc = None
        self.log = None

    @staticmethod
    def _port_pid(port):
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True).stdout
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                return line.split()[-1]
        return None

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
            pid = self._port_pid(port)
            if pid:
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                               capture_output=True)
        wait_port_free(17834)
        wait_port_free(17835)

    def start(self):
        self.stop()
        self.log = open(os.path.join(tempfile.gettempdir(),
                                     "paint-verify-vue.log"), "w")
        self.proc = subprocess.Popen(
            [AUTO_BIN, "run", "-r", "vue", "--server", "vm"], cwd=PROJ,
            stdout=self.log, stderr=subprocess.STDOUT)
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
    out_svg = os.path.join(tempfile.gettempdir(),
                           f"paint-verify-vue-{int(time.time())}.svg").replace("\\", "/")
    s = None
    try:
        if not app.start():
            report.check("vue-boot", "vue dev server up (front+back)", False,
                         "not listening within 150s")
            return 1
        s = VueSession(report)
        if not s.ready:
            return 1

        def ensure(tag, restore_load):
            """Restart the dev server if the framework ended it; after a
            restart the in-memory canvas is gone, so optionally restore via
            Load (localStorage survives in the browser context)."""
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
                s.button("Load").click()
                s.page.wait_for_timeout(500)
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
        pts = [(0, 0), (15, 0), (7, 0), (0, 7),
               (7, 7), (8, 8), (15, 8), (0, 15), (8, 15), (15, 15)]
        want = [WHITE] * 256
        for c, r in pts:
            want[r * 16 + c] = RED
        report.fixtures["sparse_points"] = sha256(json.dumps(pts))
        s.click_swatch(1)
        for c, r in pts:
            s.click_cell(r * 16 + c)
        px = s.px()
        check("sparse pattern painted per-cell exact", px == want,
              f"red={px.count(RED)}")
        s.button("Save").click()
        s.page.wait_for_timeout(300)
        check("status saved", s.status() == "saved", s.status())
        s.button("New").click()
        s.page.wait_for_timeout(300)
        s.page.reload(wait_until="networkidle")   # 真“重开”：整页重载
        s.page.wait_for_selector(".w-5.h-5", timeout=30000)
        s.button("Load").click()
        s.page.wait_for_timeout(500)
        px = s.px()
        check("save -> reload -> load identical vector", px == want,
              f"red={px.count(RED)}")

        print("\nV-02 [vue]: SVG export")
        check2 = lambda name, cond, detail="": report.check("V-02", name, cond, detail)
        if not ensure("V-02", restore_load=True):
            return 1
        if os.path.exists(out_svg):
            os.remove(out_svg)
        s.button("Export").click()
        s.page.wait_for_timeout(300)
        check2("empty path -> 'export: path required'",
               s.status() == "export: path required", s.status())
        check2("path input set via UI", s.set_path(out_svg), "input value mismatch")
        s.button("Export").click()
        s.page.wait_for_timeout(1500)
        check2("status exported", s.status() == "exported", s.status())
        oracle = expected_svg(want)
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
        render_page = s.context.new_page()
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
        s.button("Export").click()
        s.page.wait_for_timeout(1500)
        check2("unwritable path -> 'export failed' visible",
               s.status() == "export failed", s.status())
        check2("canvas preserved after failed export", s.px() == px_before,
               "px changed")

        print("\nV-03 [vue]: failure paths & migration (localStorage)")
        check3 = lambda name, cond, detail="": report.check("V-03", name, cond, detail)
        if not ensure("V-03", restore_load=False):
            return 1
        s.button("New").click()
        s.page.wait_for_timeout(300)
        # bad v2 via localStorage seeding
        bad_v2 = "PAINT-V2|16|16|" + "|".join([RED] * 255)
        report.fixtures["bad_v2_255"] = sha256(bad_v2)
        s.page.evaluate("v => localStorage.setItem('paint.project.v2', v)", bad_v2)
        px_before = s.px()
        s.button("Load").click()
        s.page.wait_for_timeout(400)
        check3("bad v2 (255 items) rejected", s.status() == "bad save data",
               s.status())
        check3("canvas unchanged after bad v2 load", s.px() == px_before,
               "px changed")
        # v1 migration
        v1_all_red = "|".join([" bg-[#ef4444] "] * 256)
        report.fixtures["v1_all_red"] = sha256(v1_all_red)
        s.page.evaluate("v => localStorage.setItem('paint.canvas.v1', v)", v1_all_red)
        s.page.evaluate("localStorage.removeItem('paint.project.v2')")
        s.button("Load").click()
        s.page.wait_for_timeout(400)
        check3("v1 all-red migrates", s.status() == "loaded v1", s.status())
        px = s.px()
        check3("v1 migration vector exact (256 red)",
               len(px) == 256 and all(c == RED for c in px),
               f"red={px.count(RED)}")
        # illegal color
        v1_bad = "|".join([" bg-[#ef4444] "] * 255 + [" bg-[#00ff00] "])
        report.fixtures["v1_illegal"] = sha256(v1_bad)
        s.page.evaluate("v => localStorage.setItem('paint.canvas.v1', v)", v1_bad)
        px_before = s.px()
        s.button("Load").click()
        s.page.wait_for_timeout(400)
        check3("v1 illegal color rejected", s.status() == "bad save data",
               s.status())
        check3("canvas unchanged after illegal v1", s.px() == px_before,
               "px changed")
    finally:
        app.stop()
        if s is not None:
            s.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=["vm", "vue"], required=True)
    ap.add_argument("--report-dir",
                    default=os.path.join(PROJ, "docs", "plans", "attachments",
                                         "001"))
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
