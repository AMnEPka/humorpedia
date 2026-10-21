import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

from worker import Worker, WorkerError, _pid_running, atomic_json, validate_result


PYTHON = sys.executable
FAKE_CLI = r'''
import json, os, pathlib, signal, subprocess, sys, time, traceback
try:
    args = sys.argv[1:]
    def value(flag): return args[args.index(flag) + 1]
    prompt = sys.stdin.buffer.read().decode("utf-8")
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("MONGO_PASSWORD"):
        pathlib.Path("secret-env-leaked.txt").write_text("leaked", encoding="utf-8")
    pathlib.Path("fake-debug.json").write_text(json.dumps({"args": args, "prompt": prompt}, ensure_ascii=False), encoding="utf-8")
    if "FAKE_MARKER" in prompt:
        pathlib.Path("prompt.txt").write_text(prompt, encoding="utf-8")
        pathlib.Path("fake-started.txt").write_text("started", encoding="utf-8")
    if "FAKE_CHILD" in prompt:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
        pathlib.Path("child-pid.txt").write_text(str(child.pid), encoding="ascii")
    if "FAKE_SLEEP" in prompt:
        time.sleep(20)
    if "FAKE_BAD_JSON" in prompt:
        pathlib.Path(value("-o")).write_text("{broken", encoding="utf-8")
        raise SystemExit(0)
    result = {"sections": [{"heading": "Биография", "paragraphs": ["Русский текст. Сначала факты: " + ("Иван" in prompt and "да" or "нет")], "fact_ids": ["f1"]}], "warnings": [], "questions": []}
    pathlib.Path(value("-o")).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
except BaseException:
    pathlib.Path("fake-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    raise
'''


def make_input(job_dir, text="Иван родился в Казани."):
    job_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": job_dir.name,
        "draft_id": "draft-1",
        "input_revision": 3,
        "kind": "person",
        "materials": {"bio": "Иван"},
        "facts": [{"id": "f1", "text": text}],
        "page": {"name": "Иван"},
        "prompt_version": 1,
    }
    (job_dir / "input.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.jobs = self.root / "jobs"
        self.jobs.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def worker(self, **kwargs):
        return Worker(self.root, codex_command=[PYTHON, "-c", FAKE_CLI], poll_interval=0.03, **kwargs)

    def add_job(self, name="00000000-0000-0000-0000-000000000001", **kwargs):
        folder = self.jobs / name
        make_input(folder, **kwargs)
        return folder

    def test_completes_job_with_utf8_and_strict_result(self):
        folder = self.add_job()
        self.assertEqual(self.worker().run_once(), "completed")
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["sections"][0]["heading"], "Биография")
        self.assertEqual(json.loads((folder / "status.json").read_text(encoding="utf-8"))["status"], "completed")
        self.assertFalse(list(folder.glob("*.tmp")))

    def test_rejects_malformed_json_without_publishing_result(self):
        folder = self.add_job()
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["materials"]["marker"] = "FAKE_BAD_JSON"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.worker().run_once()
        self.assertFalse((folder / "result.json").exists())
        self.assertEqual(json.loads((folder / "status.json").read_text())["status"], "error")

    def test_rejects_unknown_fact_ids(self):
        with self.assertRaises(WorkerError):
            validate_result({"sections": [{"heading": "x", "paragraphs": ["y"], "fact_ids": ["other"]}], "warnings": [], "questions": []}, {"f1"})

    def test_windows_pid_probe_does_not_signal_process(self):
        with unittest.mock.patch("worker.os.name", "nt"), \
             unittest.mock.patch("worker._windows_process_running", return_value=True) as probe, \
             unittest.mock.patch("worker.os.kill") as kill:
            self.assertTrue(_pid_running(123))
            probe.assert_called_once_with(123)
            kill.assert_not_called()

    def test_atomic_heartbeat_retries_transient_windows_sharing_denial(self):
        target = self.root / "heartbeat.json"
        replace = os.replace
        transient = PermissionError(5, "Access is denied")
        transient.winerror = 5
        attempts = 0
        def replace_after_transient(src, dst):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise transient
            return replace(src, dst)
        with unittest.mock.patch("worker.os.replace", side_effect=replace_after_transient):
            atomic_json(target, {"status": "ready"})
        self.assertEqual(attempts, 2)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"status": "ready"})

    def test_atomic_json_does_not_bypass_persistent_access_denial(self):
        target = self.root / "heartbeat.json"
        target.write_text("old", encoding="utf-8")
        denied = PermissionError(5, "Access is denied")
        denied.winerror = 5
        with unittest.mock.patch("worker.os.replace", side_effect=denied):
            with self.assertRaises(PermissionError):
                atomic_json(target, {"status": "ready"})
        self.assertEqual(target.read_text(encoding="utf-8"), "old")

    def test_timeout_remains_active_while_stdin_writer_is_blocked(self):
        folder = self.add_job()
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["materials"]["large"] = "x" * 2_000_000
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        sleeper = "import pathlib,time; pathlib.Path('started').touch(); time.sleep(20)"
        worker = Worker(self.root, codex_command=[PYTHON, "-c", sleeper], timeout_seconds=0.2, poll_interval=0.02)
        started = time.monotonic()
        worker.run_once()
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(json.loads((folder / "status.json").read_text())["status"], "error")
        self.assertIn("timed out", json.loads((folder / "status.json").read_text())["error"].lower())

    def test_cancel_remains_active_while_stdin_writer_is_blocked(self):
        folder = self.add_job()
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["materials"]["large"] = "x" * 2_000_000
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        sleeper = "import pathlib,time; pathlib.Path('started').touch(); time.sleep(20)"
        thread = threading.Thread(target=Worker(self.root, codex_command=[PYTHON, "-c", sleeper], timeout_seconds=30, poll_interval=0.02).run_once)
        thread.start()
        for _ in range(250):
            if (folder / "started").exists():
                (folder / "cancel.request").write_text("cancel", encoding="utf-8")
                break
            time.sleep(0.02)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(json.loads((folder / "status.json").read_text())["status"], "cancelled")

    def test_cancel_request_kills_running_process(self):
        folder = self.add_job()
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        marker = folder / "fake-started.txt"
        payload["materials"]["marker"] = "FAKE_SLEEP FAKE_MARKER"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        thread = threading.Thread(target=self.worker(timeout_seconds=30).run_once)
        thread.start()
        for _ in range(200):
            status = folder / "status.json"
            if marker.exists():
                (folder / "cancel.request").write_text("cancel", encoding="utf-8")
                break
            time.sleep(0.02)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        final_status = json.loads((folder / "status.json").read_text())
        debug = (folder / "fake-error.txt").read_text(encoding="utf-8") if (folder / "fake-error.txt").exists() else ""
        self.assertEqual(final_status["status"], "cancelled", (final_status, debug))

    def test_cancel_request_kills_cli_descendants(self):
        folder = self.add_job()
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["materials"]["marker"] = "FAKE_CHILD FAKE_MARKER FAKE_SLEEP"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        thread = threading.Thread(target=self.worker(timeout_seconds=30).run_once)
        thread.start()
        pid_file = folder / "child-pid.txt"
        for _ in range(250):
            if pid_file.exists() and pid_file.stat().st_size > 0:
                (folder / "cancel.request").write_text("cancel", encoding="utf-8")
                break
            time.sleep(0.02)
        thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertEqual(json.loads((folder / "status.json").read_text())["status"], "cancelled")
        child_pid = int(pid_file.read_text(encoding="ascii"))
        time.sleep(0.1)
        if _pid_running(child_pid):
            try:
                os.kill(child_pid, signal.SIGTERM)
            except OSError:
                pass
            self.fail(f"Codex child process {child_pid} survived cancellation")

    def test_timeout_kills_process_and_marks_error(self):
        folder = self.add_job()
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["materials"]["marker"] = "FAKE_SLEEP"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.worker(timeout_seconds=0.15).run_once()
        status = json.loads((folder / "status.json").read_text())
        self.assertEqual(status["status"], "error")
        self.assertIn("timed out", status["error"].lower())

    def test_restart_marks_running_job_interrupted_without_regeneration(self):
        folder = self.add_job()
        (folder / "status.json").write_text(json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00Z"}))
        self.assertEqual(self.worker().run_once(), "idle")
        status = json.loads((folder / "status.json").read_text())
        self.assertEqual(status["status"], "error")
        self.assertIn("interrupted", status["error"].lower())
        self.assertFalse((folder / "result.json").exists())

    def test_stale_job_claim_is_recovered_atomically(self):
        folder = self.add_job()
        claim = folder / ".claim"
        claim.mkdir()
        (claim / "owner.json").write_text(json.dumps({"pid": 99999999}), encoding="utf-8")
        self.assertEqual(self.worker().run_once(), "completed")
        self.assertFalse(claim.exists())

    def test_second_worker_cannot_acquire_process_lock(self):
        first = self.worker()
        with first.process_lock():
            with self.assertRaises(WorkerError):
                with self.worker().process_lock():
                    pass

    def test_untrusted_prompt_text_is_data_and_never_shell_executed(self):
        sentinel = self.root / "shell-ran"
        folder = self.add_job(text=f"Текст $(touch {sentinel}) и 'кавычки' — ё.")
        input_path = folder / "input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["materials"]["marker"] = "FAKE_MARKER"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.worker().run_once()
        self.assertFalse(sentinel.exists())
        prompt = (folder / "prompt.txt").read_text(encoding="utf-8") if (folder / "prompt.txt").exists() else (folder / "fake-debug.json").read_text(encoding="utf-8")
        self.assertIn("$(touch", prompt, (folder / "fake-debug.json").read_text(encoding="utf-8") if (folder / "fake-debug.json").exists() else "no debug")
        self.assertIn("кавычки", prompt)
        self.assertTrue((folder / "result.json").exists())

    def test_environment_does_not_forward_api_or_database_secrets(self):
        folder = self.add_job()
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "secret", "MONGO_PASSWORD": "secret"}):
            self.worker().run_once()
        self.assertFalse((folder / "secret-env-leaked.txt").exists())


if __name__ == "__main__":
    unittest.main()
