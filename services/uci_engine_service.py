"""Threaded Stockfish UCI service with streaming MultiPV snapshots."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from models import EngineAnalysis, EngineLine, EngineSettings
from services.stockfish_locator import locate

AnalysisCallback = Callable[[EngineAnalysis], None]
ErrorCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]


@dataclass
class _SearchJob:
    generation: int
    fen: str
    multi_pv: int
    movetime_ms: int
    callback: AnalysisCallback
    on_error: Optional[ErrorCallback] = None
    lines: dict[int, EngineLine] = field(default_factory=dict)
    depth: int = 0
    best_move_uci: Optional[str] = None
    ponder_uci: Optional[str] = None
    done: threading.Event = field(default_factory=threading.Event)

    def snapshot(self, complete: bool = False) -> EngineAnalysis:
        return EngineAnalysis(
            fen=self.fen,
            lines=[self.lines[key] for key in sorted(self.lines)],
            depth=self.depth,
            best_move_uci=self.best_move_uci,
            ponder_uci=self.ponder_uci,
            is_complete=complete,
        )


class UciEngineService:
    """Manages one Stockfish process and one serialized search worker.

    The stdout reader is independent from the worker, so streamed ``info``
    messages are parsed while the worker waits. New positions stop the active
    search and replace any pending position with the newest request.
    """

    def __init__(
        self,
        status_callback: Optional[StatusCallback] = None,
        custom_path: Optional[str] = None,
    ) -> None:
        self._status_callback = status_callback
        self._custom_path = custom_path
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._process: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._active_job: Optional[_SearchJob] = None
        self._pending_job: Optional[_SearchJob] = None
        self._generation = 0
        self._closed = False
        self._uciok = threading.Event()
        self._readyok = threading.Event()
        self._engine_path: Optional[str] = None
        self._settings = EngineSettings()
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    @property
    def engine_path(self) -> Optional[str]:
        with self._lock:
            return self._engine_path

    def set_settings(self, settings: EngineSettings) -> None:
        with self._lock:
            self._settings = settings

    def set_engine_path(self, path: Optional[str]) -> None:
        """Set the user-selected Stockfish executable for future starts."""
        with self._lock:
            self._custom_path = path.strip() if path and path.strip() else None

    def analyze(
        self,
        fen: str,
        *,
        multi_pv: int,
        movetime_ms: int,
        callback: AnalysisCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> int:
        """Queue a search and return its generation number immediately."""
        with self._condition:
            if self._closed:
                if on_error:
                    on_error("The engine service has been stopped.")
                return self._generation
            self._generation += 1
            job = _SearchJob(
                generation=self._generation,
                fen=fen,
                multi_pv=max(1, min(int(multi_pv), 5)),
                movetime_ms=max(100, int(movetime_ms)),
                callback=callback,
                on_error=on_error,
            )
            # Keep only the newest queued position.
            self._pending_job = job
            active = self._active_job
            if active is not None and not active.done.is_set():
                self._write_locked("stop")
                self._emit_status("Stopping previous analysis…")
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(
                    target=self._worker_loop,
                    name="ChessCheat-UCI-worker",
                    daemon=True,
                )
                self._worker_thread.start()
            self._condition.notify_all()
            self._emit_status("Analysis queued")
            return job.generation

    def cancel(self) -> None:
        """Cancel active and pending analysis without stopping Stockfish."""
        with self._condition:
            self._generation += 1
            self._pending_job = None
            if self._active_job is not None:
                self._write_locked("stop")
            self._condition.notify_all()

    def new_game(self) -> None:
        """Reset Stockfish's internal game state when it is idle."""
        with self._lock:
            if self._process and self._process.poll() is None:
                self._write_locked("ucinewgame")
                self._readyok.clear()
                self._write_locked("isready")

    def stop(self) -> None:
        """Terminate the engine and worker cleanly."""
        with self._condition:
            self._closed = True
            self._generation += 1
            self._pending_job = None
            self._write_locked("quit")
            process = self._process
            if process and process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
            if self._active_job:
                self._active_job.done.set()
            self._condition.notify_all()
        if process:
            try:
                process.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                except OSError:
                    pass
        self._emit_status("Engine stopped")

    # ------------------------------------------------------------------
    # Worker / process lifecycle
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while self._pending_job is None and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                job = self._pending_job
                self._pending_job = None
                if job is None:
                    continue
                self._active_job = job
                settings = self._settings

            try:
                if not self._ensure_process(settings):
                    self._report_error(job, self._last_error or "Stockfish could not start.")
                    continue
                if self._is_stale(job):
                    continue

                self._emit_status("Stockfish connected")
                # Options take effect before a search starts.
                self._write("setoption name Threads value %d" % max(1, settings.threads))
                self._write("setoption name Hash value %d" % max(16, settings.hash_mb))
                self._write("setoption name Skill Level value %d" % settings.skill_level)
                self._write("setoption name MultiPV value %d" % job.multi_pv)
                if not self._wait_ready(5):
                    raise RuntimeError("Stockfish did not answer isready.")
                if self._is_stale(job):
                    continue

                self._write("position fen " + job.fen)
                self._write("go movetime %d" % job.movetime_ms)
                self._emit_status("Thinking (MultiPV %d)…" % job.multi_pv)

                deadline = time.monotonic() + (job.movetime_ms / 1000) + 8
                stop_sent = False
                while not job.done.wait(0.1):
                    if self._closed:
                        return
                    if self._is_stale(job) and not stop_sent:
                        # New analysis normally already sent `stop`; this
                        # also handles a generation change from cancel().
                        self._write("stop")
                        stop_sent = True
                    if time.monotonic() > deadline:
                        self._write("stop")
                        if not job.done.wait(3):
                            raise TimeoutError("Stockfish search timed out.")
                        break

            except Exception as exc:  # keep the GUI alive on process errors
                self._report_error(job, str(exc))
                self._terminate_process()
            finally:
                with self._condition:
                    if self._active_job is job:
                        self._active_job = None
                    self._condition.notify_all()

            if not self._closed:
                self._emit_status("Ready")

    def _ensure_process(self, settings: EngineSettings) -> bool:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                return True

        path = locate(self._custom_path)
        if path is None:
            self._last_error = (
                "Stockfish was not found. Place stockfish.exe beside the app, "
                "in assets/stockfish, or set CHESSCHEAT_ENGINE."
            )
            return False

        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        try:
            process = subprocess.Popen(
                [path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(Path(path).parent),
                creationflags=creationflags,
            )
        except (OSError, ValueError) as exc:
            self._last_error = f"Could not launch Stockfish: {exc}"
            return False

        with self._lock:
            self._process = process
            self._engine_path = path
            self._settings = settings
            self._uciok.clear()
            self._readyok.clear()
            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                args=(process,),
                name="ChessCheat-UCI-reader",
                daemon=True,
            )
            self._reader_thread.start()

        self._write("uci")
        if not self._uciok.wait(12):
            self._last_error = "Stockfish UCI handshake timed out (uciok missing)."
            self._terminate_process()
            return False
        self._write("isready")
        if not self._readyok.wait(8):
            self._last_error = "Stockfish startup timed out (readyok missing)."
            self._terminate_process()
            return False
        self._last_error = None
        return True

    def _reader_loop(self, process: subprocess.Popen[str]) -> None:
        stream = process.stdout
        if stream is None:
            return
        try:
            for raw_line in stream:
                line = raw_line.strip()
                if not line:
                    continue
                if line == "uciok":
                    self._uciok.set()
                    continue
                if line == "readyok":
                    self._readyok.set()
                    continue
                job: Optional[_SearchJob]
                callback: Optional[AnalysisCallback] = None
                snapshot: Optional[EngineAnalysis] = None
                with self._lock:
                    job = self._active_job
                    if job is None or self._process is not process:
                        continue
                    if line.startswith("info "):
                        parsed = self._parse_info(line, job.depth)
                        if parsed is not None:
                            job.depth = max(job.depth, parsed.depth)
                            job.lines[parsed.multipv] = parsed
                            if parsed.uci_pv:
                                snapshot = job.snapshot()
                                if job.generation == self._generation:
                                    callback = job.callback
                    elif line.startswith("bestmove"):
                        parts = line.split()
                        if len(parts) > 1 and parts[1] != "(none)":
                            job.best_move_uci = parts[1]
                        if "ponder" in parts:
                            index = parts.index("ponder")
                            if index + 1 < len(parts):
                                job.ponder_uci = parts[index + 1]
                        snapshot = job.snapshot(complete=True)
                        if job.generation == self._generation:
                            callback = job.callback
                        job.done.set()
                if callback is not None and snapshot is not None:
                    try:
                        callback(snapshot)
                    except Exception:
                        # UI callbacks must never kill the UCI reader.
                        pass
        except (OSError, ValueError):
            pass
        finally:
            failed_job = None
            with self._lock:
                if self._process is process:
                    self._process = None
                active = self._active_job
                if active is not None and not active.done.is_set():
                    failed_job = active
                    active.done.set()
                self._uciok.set()
                self._readyok.set()
            if failed_job is not None and not self._closed:
                self._report_error(failed_job, "Stockfish process exited unexpectedly.")

    @staticmethod
    def _parse_info(line: str, default_depth: int) -> Optional[EngineLine]:
        tokens = line.split()
        depth = default_depth
        multipv = 1
        cp: Optional[int] = None
        mate: Optional[int] = None
        nodes = nps = elapsed = 0
        pv: list[str] = []
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token == "pv":
                pv = tokens[index + 1:]
                break
            if token == "depth" and index + 1 < len(tokens):
                depth = UciEngineService._to_int(tokens[index + 1], depth)
                index += 2
            elif token == "multipv" and index + 1 < len(tokens):
                multipv = UciEngineService._to_int(tokens[index + 1], 1)
                index += 2
            elif token == "score" and index + 2 < len(tokens):
                score_type = tokens[index + 1]
                value = UciEngineService._to_int(tokens[index + 2], 0)
                if score_type == "cp":
                    cp = value
                elif score_type == "mate":
                    mate = value
                index += 3
                if index < len(tokens) and tokens[index] in ("lowerbound", "upperbound"):
                    index += 1
            elif token in ("nodes", "nps", "time") and index + 1 < len(tokens):
                value = UciEngineService._to_int(tokens[index + 1], 0)
                if token == "nodes":
                    nodes = value
                elif token == "nps":
                    nps = value
                else:
                    elapsed = value
                index += 2
            else:
                index += 1
        if cp is None and mate is None and not pv:
            return None
        return EngineLine(
            multipv=multipv, depth=depth, score_cp=cp, score_mate=mate,
            uci_pv=pv, nodes=nodes, nps=nps, time_ms=elapsed,
        )

    @staticmethod
    def _to_int(value: str, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------------
    # Synchronization / protocol helpers
    # ------------------------------------------------------------------

    def _wait_ready(self, timeout: float) -> bool:
        self._readyok.clear()
        self._write("isready")
        return self._readyok.wait(timeout)

    def _write(self, command: str) -> None:
        with self._lock:
            self._write_locked(command)

    def _write_locked(self, command: str) -> None:
        process = self._process
        if process is None or process.poll() is not None or process.stdin is None:
            return
        try:
            process.stdin.write(command + "\n")
            process.stdin.flush()
        except (OSError, BrokenPipeError, ValueError):
            pass

    def _is_stale(self, job: _SearchJob) -> bool:
        with self._lock:
            return self._closed or job.generation != self._generation

    def _report_error(self, job: _SearchJob, message: str) -> None:
        job.done.set()
        self._emit_status(message)
        if job.on_error is not None and not self._is_stale(job):
            try:
                job.on_error(message)
            except Exception:
                pass

    def _terminate_process(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            if process is None:
                return
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=1)
        except (subprocess.TimeoutExpired, OSError):
            try:
                process.kill()
            except OSError:
                pass

    def _emit_status(self, message: str) -> None:
        if self._status_callback:
            try:
                self._status_callback(message)
            except Exception:
                pass
