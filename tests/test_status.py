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
             patch.object(status, "service_is_active", return_value=True), \
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

    def test_tooltip_documents_click_actions(self):
        payload = self.inspect()
        self.assertIn("Left-click: test reader", payload["tooltip"])
        self.assertIn("Middle-click: clear status history", payload["tooltip"])
        self.assertIn("Right-click: actions menu", payload["tooltip"])

    def test_clear_history_sets_journal_cutoff(self):
        path = status.state_path()
        path.parent.mkdir(parents=True)
        path.write_text('{"active":true,"last_error":900}')
        with patch.object(status.time, "time", return_value=1000), \
             patch.object(status, "notify") as notify:
            self.assertEqual(status.clear_history(), 0)
        saved = status.load_state(path)
        self.assertFalse(saved["active"])
        self.assertEqual(saved["last_check"], 1000)
        self.assertEqual(saved["ignore_errors_before"], 1000)
        self.assertNotIn("last_error", saved)
        notify.assert_called_once_with("Fingerprint status", "Status history cleared")

    def test_cleared_pre_reset_error_does_not_turn_red_again(self):
        with patch.object(status.time, "time", return_value=1000), \
             patch.object(status, "notify"):
            status.clear_history()
        payload = self.inspect(error=(995, "reader is already claimed"), now=1001)
        self.assertEqual(payload["class"], "ready")

    def test_inactive_daemon_uses_cache_without_waking_fprintd(self):
        path = status.state_path()
        status.save_state(path, {
            "device_discovered": True,
            "devices": ["Test Reader"],
            "active": False,
            "last_check": 990,
        })
        with patch.object(status, "service_condition", return_value=(True, "")), \
             patch.object(status, "service_is_active", return_value=False), \
             patch.object(status, "get_devices") as get_devices, \
             patch.object(status, "recent_error", return_value=(0, "")):
            payload = status.inspect(now=1000)
        self.assertEqual(payload["class"], "ready")
        get_devices.assert_not_called()

    def test_menu_dispatches_test_to_floating_terminal(self):
        completed = status.subprocess.CompletedProcess([], 0, "Test fingerprint reader\n", "")
        with patch.object(status, "run", return_value=completed), \
             patch.object(status, "launch_terminal", return_value=0) as launch:
            self.assertEqual(status.actions_menu(), 0)
        launch.assert_called_once_with("test")

    def test_menu_adds_selected_finger_in_floating_terminal(self):
        selections = (
            status.subprocess.CompletedProcess([], 0, "Add fingerprint\n", ""),
            status.subprocess.CompletedProcess([], 0, "Right index finger\n", ""),
        )
        with patch.object(status, "run", side_effect=selections), \
             patch.object(status, "launch_terminal", return_value=0) as launch:
            self.assertEqual(status.actions_menu(), 0)
        launch.assert_called_once_with("enroll", "right-index-finger")

    def test_menu_replaces_selected_finger_in_floating_terminal(self):
        selections = (
            status.subprocess.CompletedProcess([], 0, "Replace fingerprint\n", ""),
            status.subprocess.CompletedProcess([], 0, "Left thumb\n", ""),
        )
        with patch.object(status, "run", side_effect=selections), \
             patch.object(status, "launch_terminal", return_value=0) as launch:
            self.assertEqual(status.actions_menu(), 0)
        launch.assert_called_once_with("replace", "left-thumb")

    def test_menu_resets_fingerprints_in_floating_terminal(self):
        completed = status.subprocess.CompletedProcess([], 0, "Reset all fingerprints\n", "")
        with patch.object(status, "run", return_value=completed), \
             patch.object(status, "launch_terminal", return_value=0) as launch:
            self.assertEqual(status.actions_menu(), 0)
        launch.assert_called_once_with("reset-fingerprints")

    def test_enroll_uses_selected_finger_and_clears_history(self):
        with patch.dict(os.environ, {"USER": "alice"}), \
             patch.object(status, "run_fprintd", return_value=0) as run_fprintd, \
             patch.object(status, "clear_history") as clear:
            self.assertEqual(status.enroll_fingerprint("right-thumb"), 0)
        run_fprintd.assert_called_once_with(
            "fprintd-enroll", "-f", "right-thumb", "alice"
        )
        clear.assert_called_once_with(notify_user=False)

    def test_replace_deletes_only_selected_finger_before_enrolling(self):
        with patch.dict(os.environ, {"USER": "alice"}), \
             patch.object(status, "confirm", return_value=True), \
             patch.object(status, "run_fprintd", return_value=0) as run_fprintd, \
             patch.object(status, "enroll_fingerprint", return_value=0) as enroll:
            self.assertEqual(status.replace_fingerprint("left-index-finger"), 0)
        run_fprintd.assert_called_once_with(
            "fprintd-delete", "alice", "-f", "left-index-finger"
        )
        enroll.assert_called_once_with("left-index-finger")

    def test_reset_fingerprints_requires_confirmation_and_deletes_all(self):
        with patch.dict(os.environ, {"USER": "alice"}), \
             patch.object(status, "confirm", return_value=True), \
             patch.object(status, "run_fprintd", return_value=0) as run_fprintd, \
             patch.object(status, "clear_history") as clear:
            self.assertEqual(status.reset_fingerprints(), 0)
        run_fprintd.assert_called_once_with("fprintd-delete", "alice")
        clear.assert_called_once_with(notify_user=False)

    def test_destructive_fingerprint_action_can_be_cancelled(self):
        with patch.object(status, "confirm", return_value=False), \
             patch.object(status, "run_fprintd") as run_fprintd:
            self.assertEqual(status.reset_fingerprints(), 0)
        run_fprintd.assert_not_called()

    def test_unknown_finger_is_rejected(self):
        with patch.object(status, "run_fprintd") as run_fprintd:
            self.assertEqual(status.enroll_fingerprint("nose"), 2)
        run_fprintd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
