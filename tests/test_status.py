#!/usr/bin/env python3
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "bin" / "omarchy-fingerprint-status"
loader = SourceFileLoader("fingerprint_status", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
status = importlib.util.module_from_spec(spec)
loader.exec_module(status)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"XDG_STATE_HOME": self.temp.name}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def inspect(self, *, devices=None, props=None, service=(True, ""), error=(0, ""), now=1000):
        devices = ["/net/reactivated/Fprint/Device/0"] if devices is None else devices
        props = {"name": "Test Reader", "finger-needed": "false", "finger-present": "false"} if props is None else props
        with patch.object(status, "service_condition", return_value=service), \
             patch.object(status, "get_devices", return_value=devices), \
             patch.object(status, "get_property", side_effect=lambda _device, key: props[key]), \
             patch.object(status, "recent_error", return_value=error):
            return status.inspect(now=now)

    def test_ready_reader_is_green_class(self):
        payload = self.inspect()
        self.assertEqual(payload["class"], "ready")
        self.assertIn("reader is ready", payload["tooltip"])

    def test_waiting_reader_is_active(self):
        payload = self.inspect(props={"name": "Test Reader", "finger-needed": "true", "finger-present": "false"})
        self.assertEqual(payload["class"], "active")

    def test_continuously_active_reader_becomes_stuck(self):
        props = {"name": "Test Reader", "finger-needed": "true", "finger-present": "false"}
        self.inspect(props=props, now=1000)
        payload = self.inspect(props=props, now=1031)
        self.assertEqual(payload["class"], "stuck")
        self.assertIn("31s", payload["tooltip"])

    def test_missing_reader_is_disabled(self):
        payload = self.inspect(devices=[])
        self.assertEqual(payload["class"], "disabled")

    def test_recent_claim_error_is_stuck(self):
        payload = self.inspect(error=(995, "reader is already claimed"), now=1000)
        self.assertEqual(payload["class"], "stuck")


if __name__ == "__main__":
    unittest.main()
