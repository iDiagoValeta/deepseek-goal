import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "deepseek-goal" / "scripts" / "ds.py"


def load_ds():
    spec = importlib.util.spec_from_file_location("ds", DS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ds = load_ds()


class ModelTests(unittest.TestCase):
    def test_model_is_the_paid_flash_one(self):
        self.assertEqual(ds.MODEL, ("deepseek", "deepseek-flash"))


class SettledTests(unittest.TestCase):
    def test_finished_session_is_settled(self):
        session = {"outcome": "completed", "time": {"idle": 10, "updated": 5}}
        self.assertTrue(ds.settled(session))

    def test_idle_equal_to_updated_is_settled(self):
        session = {"outcome": "completed", "time": {"idle": 5, "updated": 5}}
        self.assertTrue(ds.settled(session))

    def test_session_updated_after_idle_is_not_settled(self):
        session = {"outcome": "completed", "time": {"idle": 5, "updated": 10}}
        self.assertFalse(ds.settled(session))

    def test_session_without_outcome_is_not_settled(self):
        session = {"time": {"idle": 10, "updated": 5}}
        self.assertFalse(ds.settled(session))

    def test_session_without_idle_is_not_settled(self):
        session = {"outcome": "completed", "time": {"updated": 5}}
        self.assertFalse(ds.settled(session))

    def test_session_without_time_is_not_settled(self):
        self.assertFalse(ds.settled({"outcome": "completed"}))


class AsListTests(unittest.TestCase):
    def test_keeps_only_dict_items(self):
        self.assertEqual(ds.as_list([{"a": 1}, "x", 3, {"b": 2}]), [{"a": 1}, {"b": 2}])

    def test_non_list_becomes_empty(self):
        self.assertEqual(ds.as_list(None), [])
        self.assertEqual(ds.as_list({"a": 1}), [])
        self.assertEqual(ds.as_list("text"), [])


class UsageTests(unittest.TestCase):
    def test_no_arguments_exits_with_the_usage_text(self):
        with mock.patch.object(sys, "argv", ["ds.py"]):
            with self.assertRaises(SystemExit) as caught:
                ds.main()

        usage = caught.exception.code
        self.assertIsInstance(usage, str)
        self.assertIn("ds.py run", usage)
        self.assertIn("ds.py probe", usage)


if __name__ == "__main__":
    unittest.main()
