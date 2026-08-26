"""dsh_integration tests: status sources and bubble formatting."""

import json
import os
import time
import unittest

from dsh_pet.dsh_integration import (FileStatusSource, MockStatusSource,
                                     NoneStatusSource, StatusInfo,
                                     format_status, make_status_source,
                                     progress_bar)

from _tmp import tmp_dir


class MockSourceTests(unittest.TestCase):
    def test_progress_advances(self):
        src = MockStatusSource(cycle_seconds=2.0)
        a = src.poll()
        time.sleep(0.15)
        b = src.poll()
        self.assertEqual(a.task_name, "demo-task")
        self.assertIsNotNone(a.progress)
        self.assertGreaterEqual(b.progress, a.progress)

    def test_phase_and_temp_present(self):
        src = MockStatusSource()
        info = src.poll()
        self.assertTrue(info.phase)
        self.assertIsNotNone(info.gpu_temp)


class FileSourceTests(unittest.TestCase):
    def test_reads_json(self):
        with tmp_dir() as tmp:
            path = os.path.join(tmp, "status.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"task_name": "train", "phase": "running",
                           "progress": 42, "gpu_temp": 61}, fh)
            src = FileStatusSource(path)
            info = src.poll()
            self.assertIsNotNone(info)
            self.assertEqual(info.task_name, "train")
            self.assertAlmostEqual(info.progress, 42.0)
            self.assertAlmostEqual(info.gpu_temp, 61.0)

    def test_missing_file_returns_none(self):
        src = FileStatusSource("/nonexistent/status.json")
        self.assertIsNone(src.poll())

    def test_bad_json_returns_none(self):
        with tmp_dir() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            src = FileStatusSource(path)
            self.assertIsNone(src.poll())


class FactoryTests(unittest.TestCase):
    def test_make(self):
        self.assertIsInstance(make_status_source("mock"), MockStatusSource)
        self.assertIsInstance(make_status_source("file", "x.json"), FileStatusSource)
        self.assertIsInstance(make_status_source("none"), NoneStatusSource)


class FormatTests(unittest.TestCase):
    def test_progress_bar(self):
        bar = progress_bar(50.0, 12)
        self.assertIn("50%", bar)
        self.assertEqual(len(bar), 12)

    def test_progress_bar_none(self):
        bar = progress_bar(None, 10)
        self.assertEqual(len(bar), 10)
        self.assertIn("?", bar)

    def test_format_status(self):
        info = StatusInfo(task_name="demo", phase="running", progress=33.0,
                          gpu_temp=58.0, message="hi")
        lines = format_status(info, width=30)
        self.assertTrue(any("demo" in line for line in lines))
        self.assertTrue(any("33%" in line for line in lines))
        self.assertTrue(any("GPU 58" in line for line in lines))

    def test_format_status_empty(self):
        self.assertEqual(format_status(None), [])
        self.assertEqual(format_status(StatusInfo()), [])


if __name__ == "__main__":
    unittest.main()
