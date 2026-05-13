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

import sys
import threading
import time
from typing import Callable

from .audio_utils import beep

from .recorder import SAMPLE_RATE, CHANNELS, DTYPE, record_until_silence
from .stt import transcribe

# ── Config ────────────────────────────────────────────────────────────────

WAKE_PHRASES: list[str] = [
    "hey dulus", "okey dulus", "ok dulus", "dale dulus",
    "oye dulus", "escucha dulus", "dulus",
]

# VAD: chunk size and energy threshold.
# 0.3 s chunks give fast reaction; threshold tuned for close/loud speech.
# DEFAULT lowered to 0.020 — works with most laptop / headset mics.
# If you get false wakes from background noise, raise it via /wake threshold.
_VAD_CHUNK_SECS = 0.30
_VAD_RMS_THRESHOLD = 0.020  # ~quiet room ≈ 0.005; normal speech close ≈ 0.05+

# After VAD fires, collect this many seconds of audio for the wake-word STT.
_WAKE_RECORD_SECS = 2.5

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
        """Poll mic energy → trigger STT on loud speech → check wake phrase
        → if wake detected, record the real command and fire on_command.

        Keeps one InputStream open the whole time for instant reaction.
        """
        try:
            import sounddevice as sd
            import numpy as np
        except Exception:
            return

        chunk_samples = int(SAMPLE_RATE * _VAD_CHUNK_SECS)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=chunk_samples,
                device=self.device_index,
            ) as stream:
                while not self._stop_evt.is_set():
                    # ── 1. Quick energy poll ─────────────────────────────
                    triggered = False
                    for _ in range(3):  # up to 3 chunks (~0.9 s)
                        if self._stop_evt.is_set():
                            return
                        pcm, overflowed = stream.read(chunk_samples)
                        if overflowed:
                            pass
                        pcm_bytes = pcm.tobytes()
                        rms = _rms_of_chunk(pcm_bytes)
                        if self.debug:
                            _bar = " ▁▂▃▄▅▆▇█"
                            _lvl = min(int(rms * 8 / 0.08), 8)
                            print(f"\r  [wake debug] RMS: {rms:.4f} {_bar[_lvl]}  thresh={self.rms_threshold}", end="", flush=True)
                        if rms >= self.rms_threshold:
                            triggered = True
                            if self.debug:
                                print(f"\n  [wake debug] 🔊 TRIGGERED (RMS {rms:.4f} >= {self.rms_threshold})")
                            break
                        time.sleep(0.05)

                    if not triggered:
                        continue

                    # ── 2. Capture audio for wake-word STT ───────────────
                    if self.debug:
                        print("  [wake debug] Recording wake-word audio…")
                    try:
                        pcm = record_until_silence(
                            max_seconds=int(self.record_secs) + 1,
                            device_index=self.device_index,
                        )
                    except Exception as e:
                        if self.debug:
                            print(f"  [wake debug] Record failed: {e}")
                        continue

                    if not pcm or self._stop_evt.is_set():
                        if self.debug:
                            print("  [wake debug] No PCM or stopped")
                        continue

                    # ── 3. STT wake-word check ───────────────────────────
                    if self.debug:
                        print("  [wake debug] Running STT on wake audio…")
                    try:
                        text = transcribe(pcm, language=self._wake_lang)
                    except Exception as e:
                        if self.debug:
                            print(f"  [wake debug] STT failed: {e}")
                        continue

                    if self.debug:
                        print(f'  [wake debug] STT result: "{text}"')

                    matched = _contains_wake(text, self.wake_phrases)
                    if not matched:
                        if self.debug:
                            print(f"  [wake debug] No wake phrase found in: '{text}'")
                        continue

                    if self.debug:
                        print(f"  [wake debug] ✅ Wake phrase matched: '{matched}'")

                    if on_wake:
                        try:
                            on_wake(matched)
                        except Exception:
                            pass

                    # ── 4. Listen for the real command ───────────────────
                    # The on_wake() callback (in dulus.py) calls say() which 
                    # is blocking. This ensures we don't start recording the
                    # command until Dulus finished speaking.
                    
                    # We add a tiny extra buffer just to be sure we don't
                    # catch any echo/tail.
                    self._stop_evt.wait(0.3)
                    if self._stop_evt.is_set():
                        return

                    # Audio feedback signaling the start of command recording
                    beep(1100, 150)

                    def _cmd_energy_bar(rms: float) -> None:
                        # Show a small energy bar in the toolbar status safely
                        try:
                            import input as _dulus_input
                            _bar = " ▁▂▃▄▅▆▇█"
                            _lvl = min(int(rms * 8 / 0.08), 8)
                            # Cyan "Listening..." + Mic icon + Energy bar
                            _txt = f"\x1b[36mListening...\x1b[0m  🎙️  {_bar[_lvl]}"
                            # Try both toolbar and terminal fallback
                            _dulus_input.set_toolbar_status(_txt)
                            # Only print to terminal if we don't have a split app toolbar
                            if not getattr(_dulus_input, "_split_app", None):
                                _dulus_input.safe_print_notification(f"\r  {_txt}  ", end="", flush=True)
                        except Exception:
                            pass

                    try:
                        # Use a longer silence timeout (2.5s) for wake commands 
                        # to give the user time to think/start.
                        command_pcm = record_until_silence(
                            max_seconds=_COMMAND_MAX_SECS,
                            on_energy=_cmd_energy_bar,
                            device_index=self.device_index,
                            silence_secs=2.5,
                        )
                        # Signal the end of recording
                        beep(800, 100) # Lower pitch to indicate "received/done"
                        # Clear the status/line
                        import input as _dulus_input
                        _dulus_input.set_toolbar_status("")
                        _dulus_input.safe_print_notification("\r                                \r", end="", flush=True)
                    except Exception:
                        continue

                    if not command_pcm or self._stop_evt.is_set():
                        continue

                    try:
                        command_text = transcribe(command_pcm, language=self.language)
                    except Exception:
                        continue

                    if on_command and command_text.strip():
                        try:
                            on_command(command_text.strip())
                        except Exception:
                            pass

                    # Cool-down so one utterance doesn't wake twice
                    self._stop_evt.wait(_COOLDOWN_SECS)
        except Exception:
            # Stream creation failed — mic not available or bad device_index
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
