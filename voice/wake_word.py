"""Wake-word (hotword) detection for Dulus.

Uses **energy-based VAD** — cheap RMS polling on small audio chunks.
Only runs STT when speech energy crosses a threshold (someone talking
loud / close to the mic, as you do when addressing an assistant).

Default wake phrases:
    "dulus", "hey dulus", "okey dulus", "ok dulus"

Flow
----
1. Poll mic energy in tiny chunks (~0.3 s).
2. If energy > threshold → someone is speaking close/loud.
3. Capture a short burst (~2.5 s) and STT it.
4. If the text contains a wake phrase → trigger `on_wake(phrase)`.
5. Immediately after wake, listen for the **actual command** (longer
   voice_input, up to silence) and deliver it via `on_command(text)`.

Usage
-----
    from voice.wake_word import WakeWordListener

    listener = WakeWordListener()
    listener.start(
        on_wake=lambda phrase: print(f"Woke by: {phrase}"),
        on_command=lambda text: print(f"Command: {text}"),
    )
    # ... later ...
    listener.stop()
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from collections import deque
from typing import Callable

from .audio_utils import beep

from .recorder import SAMPLE_RATE, CHANNELS, DTYPE, CHUNK_SECS, SILENCE_THRESHOLD_RMS
from .stt import transcribe

# ── Config ────────────────────────────────────────────────────────────────

WAKE_PHRASES: list[str] = [
    # --- Variantes con "dulus" (S) ---
    "hey dulus", "okey dulus", "ok dulus", "dale dulus",
    "oye dulus", "escucha dulus", "dulus",
    "dolus", "daulus", "doiulus",
    "adulus", "aduluz",
    # --- Variantes con "duluz" (Z) ---
    "hey duluz", "okey duluz", "ok duluz", "dale duluz",
    "oye duluz", "escucha duluz", "duluz",
    "dolus", "dauluz", "doiuluz",
    "aduluz", "adulus",
    # --- Variantes con signos de exclamación (como transcribe Whisper) ---
    "oye dulus", "oye duluz",
    "DOLOS.","DOLOS",
    "okey dulus", "okey duluz",
    "ok dulus", "ok duluz",
    "dale dulus", "dale duluz",
    "hey dulus", "hey duluz",
    # --- Variantes cortas / slang ---
    "dulus", "duluz", "dolus", "dulús", "dulúz",
    "oye", "okey", "ok", "dale", "escucha",
]

# VAD: energy threshold.
# DEFAULT lowered to 0.020 — works with most laptop / headset mics.
# If you get false wakes from background noise, raise it via /wake threshold.
_VAD_RMS_THRESHOLD = 0.020  # ~quiet room ≈ 0.005; normal speech close ≈ 0.05+

# After VAD fires, collect this many seconds of audio for the wake-word STT.
_WAKE_RECORD_SECS = 4.5

# Cool-down between wake-word checks so we don't spam STT.
_COOLDOWN_SECS = 1.5

# Max seconds for the follow-up command recording.
_COMMAND_MAX_SECS = 20


# ── Helpers ───────────────────────────────────────────────────────────────

def _rms_of_chunk(pcm: bytes) -> float:
    """Return RMS (0..1) of int16 PCM chunk."""
    import numpy as np
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr ** 2))) / 32768.0


def _contains_wake(text: str, phrases: list[str] | None = None) -> str | None:
    """Return the matched wake phrase (lower-case) or None."""
    lowered = text.lower().strip()
    for phrase in (phrases or WAKE_PHRASES):
        if phrase in lowered:
            return phrase
    return None


# ── Public class ──────────────────────────────────────────────────────────

class WakeWordListener:
    """Background thread that listens for a wake phrase and then captures
    the following voice command.

    Parameters
    ----------
    wake_phrases:
        Override the default list of wake phrases.
    rms_threshold:
        Energy level that triggers STT (0..1).  Increase if
        background noise causes false wakes; decrease if you
        have to shout.
    record_secs:
        How many seconds to capture after VAD fires (for wake-word check).
    device_index:
        sounddevice mic index (None = system default).
    language:
        STT language code ("auto" = let Whisper decide).
    """

    def __init__(
        self,
        wake_phrases: list[str] | None = None,
        rms_threshold: float = _VAD_RMS_THRESHOLD,
        record_secs: float = _WAKE_RECORD_SECS,
        device_index: int | None = None,
        language: str = "auto",
        debug: bool = False,
    ):
        self.wake_phrases = wake_phrases or list(WAKE_PHRASES)
        self.rms_threshold = rms_threshold
        self.record_secs = record_secs
        self.device_index = device_index
        self.language = language
        self.debug = debug
        # Wake-phrase detection uses a fixed language so short utterances
        # like "Hey Dulus" don't get mis-detected by Whisper's auto-lang.
        self._wake_lang = "es" if language in ("auto", "") else language

        # Force local STT (Whisper) for wake-word — avoids cloud latency
        # and 502 errors from NVIDIA Riva on the hotword path.
        os.environ["DULUS_WAKE_FORCE_LOCAL"] = "1"

        self._thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(
        self,
        on_wake: Callable[[str], None] | None = None,
        on_command: Callable[[str], None] | None = None,
    ) -> None:
        """Begin listening in a background thread.

        `on_wake(phrase)`  — called when the wake phrase is detected.
        `on_command(text)` — called with the follow-up voice command.
        """
        if self._running:
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._loop,
            args=(on_wake, on_command),
            daemon=True,
            name="dulus-wake-word",
        )
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        """Signal the listener to stop and wait for the thread."""
        if not self._running:
            return
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._running = False

    def is_running(self) -> bool:
        return self._running

    # ── Core loop ─────────────────────────────────────────────────────────

    def _loop(
        self,
        on_wake: Callable[[str], None] | None,
        on_command: Callable[[str], None] | None,
    ) -> None:
        """One continuous InputStream with ring-buffer pre-roll.

        No separate record_until_silence() calls — threshold detection,
        wake-word capture, and command capture all use the same stream.
        Zero audio gaps, and we never miss the start of the utterance.
        """
        try:
            import sounddevice as sd
            import numpy as np
        except Exception:
            return

        chunk_samples = int(SAMPLE_RATE * CHUNK_SECS)

        # Thread-safe shared state
        lock = threading.Lock()
        state = ["idle"]          # idle | wake_record | processing | command_record | cooldown
        ring_buffer: deque[bytes] = deque(maxlen=int(2.0 / CHUNK_SECS))
        _cb_accum: list[bytes] = []
        _silence_count = [0]

        result_q: queue.Queue[tuple[str, bytes]] = queue.Queue()

        def _cmd_energy_bar(rms: float) -> None:
            try:
                import input as _dulus_input
                _bar = " ▁▂▃▄▅▆▇█"
                _lvl = min(int(rms * 8 / 0.08), 8)
                _txt = f"\x1b[36mListening...\x1b[0m  🎙️  {_bar[_lvl]}"
                _dulus_input.set_toolbar_status(_txt)
                if not getattr(_dulus_input, "_split_app", None):
                    _dulus_input.safe_print_notification(f"\r  {_txt}  ", end="", flush=True)
            except Exception:
                pass

        def callback(indata: "np.ndarray", frames: int, time_info, status) -> None:
            pcm_bytes = indata[:, 0].copy().tobytes()
            rms = _rms_of_chunk(pcm_bytes)
            show_energy = False

            with lock:
                st = state[0]

                if st == "idle":
                    ring_buffer.append(pcm_bytes)
                    if rms >= self.rms_threshold:
                        state[0] = "wake_record"
                        _cb_accum.clear()
                        _cb_accum.extend(list(ring_buffer))
                        _cb_accum.append(pcm_bytes)
                        _silence_count[0] = 0
                        if self.debug:
                            print(f"\n  [wake debug] 🔊 TRIGGERED (RMS {rms:.4f} >= {self.rms_threshold})")

                elif st == "wake_record":
                    _cb_accum.append(pcm_bytes)
                    if rms < SILENCE_THRESHOLD_RMS:
                        _silence_count[0] += 1
                    else:
                        _silence_count[0] = 0
                    has_speech = len(_cb_accum) >= 3
                    silence_limit = int(2.0 / CHUNK_SECS)
                    max_limit = int(self.record_secs / CHUNK_SECS)
                    if (has_speech and _silence_count[0] >= silence_limit) or len(_cb_accum) >= max_limit:
                        state[0] = "processing"
                        result_q.put(("wake", b"".join(_cb_accum)))
                        if self.debug:
                            print("  [wake debug] Wake audio ready, sending to STT…")

                elif st == "command_record":
                    show_energy = True
                    _cb_accum.append(pcm_bytes)
                    if rms < SILENCE_THRESHOLD_RMS:
                        _silence_count[0] += 1
                    else:
                        _silence_count[0] = 0
                    has_speech = len(_cb_accum) >= 3
                    silence_limit = int(2.5 / CHUNK_SECS)
                    max_limit = int(_COMMAND_MAX_SECS / CHUNK_SECS)
                    if (has_speech and _silence_count[0] >= silence_limit) or len(_cb_accum) >= max_limit:
                        state[0] = "processing"
                        result_q.put(("command", b"".join(_cb_accum)))

                # "processing" / "cooldown" → drain, do nothing

            if show_energy:
                _cmd_energy_bar(rms)

        stream_kwargs = dict(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=chunk_samples,
            callback=callback,
        )
        if self.device_index is not None:
            stream_kwargs["device"] = self.device_index

        try:
            with sd.InputStream(**stream_kwargs):
                while not self._stop_evt.is_set():
                    try:
                        msg_type, pcm = result_q.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if self._stop_evt.is_set():
                        return

                    if msg_type == "wake":
                        if self.debug:
                            print("  [wake debug] Running STT on wake audio…")
                        try:
                            text = transcribe(pcm, language=self._wake_lang)
                        except Exception as e:
                            if self.debug:
                                print(f"  [wake debug] STT failed: {e}")
                            with lock:
                                state[0] = "idle"
                                _cb_accum.clear()
                                ring_buffer.clear()
                            continue

                        if self.debug:
                            print(f'  [wake debug] STT result: "{text}"')

                        matched = _contains_wake(text, self.wake_phrases)
                        if not matched:
                            if self.debug:
                                print(f"  [wake debug] No wake phrase found in: '{text}'")
                            with lock:
                                state[0] = "idle"
                                _cb_accum.clear()
                                ring_buffer.clear()
                            continue

                        if self.debug:
                            print(f"  [wake debug] ✅ Wake phrase matched: '{matched}'")

                        if on_wake:
                            try:
                                on_wake(matched)
                            except Exception:
                                pass

                        if self._stop_evt.is_set():
                            return

                        self._stop_evt.wait(0.3)
                        if self._stop_evt.is_set():
                            return

                        beep(1100, 150)

                        with lock:
                            state[0] = "command_record"
                            _cb_accum.clear()
                            _silence_count[0] = 0

                    elif msg_type == "command":
                        beep(800, 100)
                        try:
                            import input as _dulus_input
                            _dulus_input.set_toolbar_status("")
                            _dulus_input.safe_print_notification("\r                                \r", end="", flush=True)
                        except Exception:
                            pass

                        try:
                            command_text = transcribe(pcm, language=self.language)
                        except Exception:
                            with lock:
                                state[0] = "idle"
                                _cb_accum.clear()
                                ring_buffer.clear()
                            continue

                        if on_command and command_text.strip():
                            try:
                                on_command(command_text.strip())
                            except Exception:
                                pass

                        self._stop_evt.wait(_COOLDOWN_SECS)

                        with lock:
                            state[0] = "idle"
                            _cb_accum.clear()
                            ring_buffer.clear()
        except Exception:
            return


# ── Convenience entry-point ───────────────────────────────────────────────

def listen_once(
    wake_phrases: list[str] | None = None,
    rms_threshold: float = _VAD_RMS_THRESHOLD,
    record_secs: float = _WAKE_RECORD_SECS,
    device_index: int | None = None,
    language: str = "auto",
    timeout: float | None = None,
) -> str | None:
    """Block until a wake phrase is detected, then return the matched phrase.

    Returns None on timeout (if given) or on interrupt.
    """
    result: list[str] = []

    def _capture(phrase: str) -> None:
        result.append(phrase)

    listener = WakeWordListener(
        wake_phrases=wake_phrases,
        rms_threshold=rms_threshold,
        record_secs=record_secs,
        device_index=device_index,
        language=language,
    )
    listener.start(on_wake=_capture)
    try:
        if timeout:
            listener._thread.join(timeout=timeout)  # type: ignore[union-attr]
        else:
            listener._thread.join()  # type: ignore[union-attr]
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()

    return result[0] if result else None
