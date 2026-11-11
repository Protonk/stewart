"""Compile and exercise the offline Rust MCP prototype; never invoke Claude.

Uses Cargo offline, rustc and Python's standard library. The peer keeps its own bytes outside
the owner's captures. Unix socketpairs test duplex forwarding without claiming
to test the future named-socket rendezvous or the service's archive writer.
"""

import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parent
INIT = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
    "protocolVersion": "2025-11-25", "capabilities": {},
    "clientInfo": {"name": "offline-peer", "version": "1"}}}
READY = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def line(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def request(number, method, **params):
    return line({"jsonrpc": "2.0", "id": number, "method": method, "params": params})


class ProtocolControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="stewart-offline-mcp-build-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.binary = Path(cls.build.name) / "protocol-check"
        service = HERE.parent.parent / "service"
        target = service / "target-local/protocol-check"
        subprocess.run(["cargo", "build", "--locked", "--offline", "--lib", "--target-dir", str(target)],
                       cwd=service, check=True)
        linkage = ["--extern", "stewart=" + str(target / "debug/libstewart.rlib"),
                   "-L", "dependency=" + str(target / "debug/deps")]
        subprocess.run(["rustc", "--edition=2024", "-Dwarnings", *linkage, str(HERE / "protocol_check.rs"),
                        "-o", str(cls.binary)], check=True)
        unit = Path(cls.build.name) / "protocol-unit"
        subprocess.run(["rustc", "--edition=2024", "-Dwarnings", *linkage, "--test", str(HERE / "protocol_check.rs"),
                        "-o", str(unit)], check=True)
        subprocess.run([str(unit)], check=True)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="stewart-offline-mcp-case-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.capture = self.root / "owner"
        self.capture.mkdir()

    def run_owner(self, payload):
        # Independent input witness, outside the owner directory.
        (self.root / "peer-sent.bin").write_bytes(payload)
        p = subprocess.run([str(self.binary), "serve", str(self.capture)], input=payload,
                           capture_output=True, timeout=10)
        (self.root / "peer-received.bin").write_bytes(p.stdout)
        return p

    def replies(self, process):
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual((self.capture / "incoming.bin").read_bytes(), (self.root / "peer-sent.bin").read_bytes())
        self.assertEqual((self.capture / "outgoing.bin").read_bytes(), process.stdout)
        return [json.loads(raw) for raw in process.stdout.splitlines()]

    def test_observed_discovery_fallback_and_version_negotiation(self):
        init = dict(INIT, params=dict(INIT["params"], protocolVersion="2099-01-01"))
        p = self.run_owner(request(-1, "server/discover") + line(init) + line(READY) + request(2, "tools/list"))
        replies = self.replies(p)
        self.assertEqual(replies[0]["error"]["code"], -32601)
        self.assertEqual(replies[0]["id"], -1)
        self.assertEqual(replies[1]["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(replies[1]["result"]["capabilities"], {"tools": {}})
        self.assertEqual([v["name"] for v in replies[2]["result"]["tools"]], ["record_note"])

    def test_initialization_notification_required_and_never_answered(self):
        replies = self.replies(self.run_owner(request(1, "tools/list") + line(INIT)
            + request(2, "tools/list") + line(READY) + request(3, "tools/list")))
        self.assertEqual([r["id"] for r in replies], [1, 0, 2, 3])
        self.assertIn("error", replies[0])
        self.assertIn("error", replies[2])
        self.assertIn("tools", replies[3]["result"])

    def test_raw_arguments_and_metadata_are_distinct(self):
        call = (b'{ "jsonrpc":"2.0", "id":"note", "method":"tools/call", "params":'
                b'{"name":"record_note", "arguments":{ "text" : "orch\\u0061rd" },'
                b'"_meta":{"progressToken":-2,"fraction":1.5,"opaque":"\\u0000"}}}\r\n')
        replies = self.replies(self.run_owner(line(INIT) + line(READY) + call))
        self.assertFalse(replies[-1]["result"]["isError"])
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b'{ "text" : "orch\\u0061rd" }\n')

    def test_argument_refusal_is_a_tool_result(self):
        bad = b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"record_note","arguments":{"text":"a","te\\u0078t":"b"}}}\n'
        replies = self.replies(self.run_owner(line(INIT) + line(READY) + bad))
        self.assertTrue(replies[-1]["result"]["isError"])
        self.assertIn("input_invalid", replies[-1]["result"]["content"][0]["text"])
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b"")

    def test_malformed_unknown_and_unsupported_calls_keep_distinct_errors(self):
        payload = line(INIT) + line(READY) + b'{broken\n' + request(1, "tools/call", name="missing")
        payload += request(2, "tools/call", name="record_note", arguments=[])
        payload += request(3, "tools/call", name="record_note", arguments={"text": "a"}, task={})
        payload += request(4, "resources/list")
        replies = self.replies(self.run_owner(payload))
        self.assertEqual([r["error"]["code"] for r in replies[1:]], [-32700, -32602, -32602, -32602, -32601])
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b"")

    def test_notifications_are_silent_and_do_not_execute_tools(self):
        payload = line(INIT) + line(READY)
        payload += line({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "record_note", "arguments": {"text": "a"}}})
        payload += line({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 999}})
        payload += request(1, "ping")
        replies = self.replies(self.run_owner(payload))
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[-1]["result"], {})
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b"")

    def test_ids_keep_type_and_reject_reuse_or_ambiguity(self):
        payload = line(INIT) + request(-1, "ping") + request("-1", "ping") + request(-1, "ping")
        payload += b'{"jsonrpc":"2.0","id":3,"i\\u0064":4,"method":"ping"}\n'
        payload += request(None, "ping")
        replies = self.replies(self.run_owner(payload))
        self.assertEqual([r["id"] for r in replies[:3]], [0, -1, "-1"])
        self.assertEqual([r["error"]["code"] for r in replies[3:]], [-32600] * 3)

    def test_ambiguous_control_fields_never_execute(self):
        payload = line(INIT) + line(READY)
        for i, extra in enumerate([b'"task":{},"task":{}', b'"arguments":{},"arguments":{}'], 1):
            payload += b'{"jsonrpc":"2.0","id":' + str(i).encode() + b',"method":"tools/call","params":{"name":"record_note",' + extra + b'}}\n'
        payload += b'{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{"cursor":"a","cursor":"b"}}\n'
        replies = self.replies(self.run_owner(payload))
        self.assertEqual([r["error"]["code"] for r in replies[1:]], [-32602] * 3)
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b"")

    def test_truncated_frame_is_retained_without_effect(self):
        raw = line(INIT) + b'{"jsonrpc":"2.0","method":"tools/call"'
        p = self.run_owner(raw)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"truncated", p.stderr)
        self.assertEqual((self.capture / "incoming.bin").read_bytes(), raw)
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b"")

    def test_capture_unavailable_prevents_processing(self):
        (self.capture / "incoming.bin").mkdir()
        p = self.run_owner(line(INIT) + line(READY) + request(1, "tools/call", name="record_note", arguments={"text": "a"}))
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")
        self.assertFalse((self.capture / "effects.jsonl").exists())

    def test_oversized_frame_retains_received_prefix_and_stops(self):
        raw = b" " * (8 * 1024 * 1024 + 8192)
        p = self.run_owner(raw)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"bound", p.stderr)
        captured = (self.capture / "incoming.bin").read_bytes()
        self.assertGreater(len(captured), 8 * 1024 * 1024)
        self.assertEqual(captured, raw[:len(captured)])
        self.assertEqual(p.stdout, b"")

    def child(self, *args, **kwargs):
        p = subprocess.Popen([str(self.binary), *args], **kwargs)
        def cleanup():
            if p.poll() is None:
                p.kill()
            p.wait(timeout=5)
            for stream in (p.stdin, p.stdout, p.stderr):
                if stream:
                    stream.close()
        self.addCleanup(cleanup)
        return p

    def test_real_relay_and_owner_preserve_pipelined_bytes(self):
        owner_sock, relay_sock = socket.socketpair()
        with owner_sock, relay_sock:
            owner = self.child("serve", str(self.capture), stdin=owner_sock, stdout=owner_sock, stderr=subprocess.PIPE)
            relay = self.child("relay", str(relay_sock.fileno()), pass_fds=(relay_sock.fileno(),),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw = line(INIT) + line(READY) + request(1, "tools/list") + request(2, "tools/call", name="record_note", arguments={"text": "orchard"})
        (self.root / "peer-sent.bin").write_bytes(raw)
        out, err = relay.communicate(raw, timeout=10)
        self.assertEqual(relay.returncode, 0, err)
        self.assertEqual(owner.wait(timeout=5), 0, owner.stderr.read())
        self.assertEqual((self.capture / "incoming.bin").read_bytes(), raw)
        self.assertEqual((self.capture / "outgoing.bin").read_bytes(), out)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertEqual((self.capture / "effects.jsonl").read_bytes(), b'{"text":"orchard"}\n')

    def test_relay_is_duplex_under_backpressure(self):
        owner, child = socket.socketpair()
        self.addCleanup(owner.close)
        owner.settimeout(5)
        incoming, outgoing = b"i" * 524288, b"o" * 524288
        received, failures = [], []
        def peer():
            try:
                # Deliberately writes before reading: a lockstep relay deadlocks.
                owner.sendall(outgoing)
                while True:
                    chunk = owner.recv(4096)
                    if not chunk:
                        break
                    received.append(chunk)
                owner.shutdown(socket.SHUT_WR)
            except Exception as exc:
                failures.append(exc)
        with child:
            relay = self.child("relay", str(child.fileno()), pass_fds=(child.fileno(),),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        worker = threading.Thread(target=peer, daemon=True)
        worker.start()
        out, err = relay.communicate(incoming, timeout=10)
        worker.join(6)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(relay.returncode, 0, err)
        self.assertEqual(out, outgoing)
        self.assertEqual(b"".join(received), incoming)

    def test_owner_loss_ends_relay_even_with_open_stdin(self):
        owner, child = socket.socketpair()
        with child:
            relay = self.child("relay", str(child.fileno()), pass_fds=(child.fileno(),),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        owner.close()
        self.assertNotEqual(relay.wait(timeout=5), 0)
        self.assertEqual(relay.stdout.read(), b"")
        self.assertIn(b"no reconnect", relay.stderr.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
