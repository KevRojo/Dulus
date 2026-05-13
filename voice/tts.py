"""Text-to-speech (TTS) backends.

Backend priority (tried in order):
  1. pyttsx3        — local, offline, robotic system voices (Windows SAPI5).
                       pip install pyttsx3
  2. edge-tts       — Microsoft Edge voices, fast, free, cloud.
                       pip install edge-tts
  3. gTTS           — cloud, free, needs internet.
                       pip install gTTS
  4. OpenAI TTS     — cloud, high quality, needs OPENAI_API_KEY.
  5. Azure          — cloud, Microsoft Azure Speech Services.
  6. NVIDIA Riva    — cloud, Magpie-Multilingual via NVCF gRPC.
                       pip install nvidia-riva-client + NVIDIA_API_KEY
"""

from __future__ import annotations

import os
import re
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

# ── Interrupt flag ────────────────────────────────────────────────────────
# `_say_lock` serializes calls to say(): two concurrent say()s would share
# `_stop_event` and the second .clear() would erase the first's cancel signal,
# leaving overlapping audio with no way to interrupt. Lock keeps audio sequential.
_stop_event = threading.Event()
_say_lock = threading.Lock()

def _watch_for_cancel() -> None:
    """Background thread: set _stop_event if user presses 'c'."""
    try:
        import msvcrt
        while not _stop_event.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch.lower() == 'c':
                    _stop_event.set()
                    print("\n  ⏹  TTS stopped.", flush=True)
                    return
    except Exception:
        pass

# ── Playback Helper ───────────────────────────────────────────────────────

def _play_audio_file(file_path: str | Path) -> None:
    """Play an audio file, interruptible with 'c' key."""
    file_path = str(file_path)

    # Try ffplay
    if shutil_which := __import__("shutil").which("ffplay"):
        proc = subprocess.Popen(
            [shutil_which, "-nodisp", "-autoexit", "-loglevel", "quiet", file_path])
        try:
            while proc.poll() is None:
                if _stop_event.is_set():
                    proc.terminate()
                    return
                time.sleep(0.05)
        finally:
            if proc.poll() is None:
                proc.kill()
        return

    # Try mpv
    if shutil_which := __import__("shutil").which("mpv"):
        proc = subprocess.Popen(
            [shutil_which, "--no-video", "--really-quiet", file_path])
        try:
            while proc.poll() is None:
                if _stop_event.is_set():
                    proc.terminate()
                    return
                time.sleep(0.05)
        finally:
            if proc.poll() is None:
                proc.kill()
        return

    # Windows MCI
    if os.name == "nt":
        _play_windows_mci(file_path)
        return

    print(f"  [TTS] Cannot play audio: no player found (install ffmpeg or mpv). File: {file_path}")


def _play_windows_mci(file_path: str) -> None:
    """Play via MCI, polling _stop_event every 50ms to allow 'c' cancel."""
    try:
        import ctypes
        winmm = ctypes.windll.winmm
        abs_path = str(Path(file_path).resolve())
        ext = Path(file_path).suffix.lower()
        mci_type = {".wav": "waveaudio", ".mp3": "mpegvideo",
                    ".mp4": "mpegvideo", ".avi": "avivideo"}.get(ext, "mpegvideo")
        winmm.mciSendStringW(f'open "{abs_path}" type {mci_type} alias _tts_track', None, 0, None)
        winmm.mciSendStringW('play _tts_track', None, 0, None)
        buf = ctypes.create_unicode_buffer(128)
        while True:
            if _stop_event.is_set():
                winmm.mciSendStringW('stop _tts_track', None, 0, None)
                break
            winmm.mciSendStringW('status _tts_track mode', buf, 128, None)
            if buf.value != 'playing':
                break
            time.sleep(0.05)
        winmm.mciSendStringW('close _tts_track', None, 0, None)
        time.sleep(0.1)  # let MCI fully release the file handle
    except Exception as e:
        print(f"  [TTS] Windows MCI playback error: {e}")


# ── pyttsx3 singleton ─────────────────────────────────────────────────────
# Recreating the engine on every call causes COM errors on Windows.
_pyttsx3_engine = None

def _get_pyttsx3_engine():
    global _pyttsx3_engine
    if _pyttsx3_engine is None:
        import pyttsx3
        _pyttsx3_engine = pyttsx3.init()
        # Pre-set properties one-time for speed
        try:
            _pyttsx3_engine.setProperty("rate", 175)
            voices = _pyttsx3_engine.getProperty("voices")
            # Prefer Zira (Spanish/English female) or Helena (Spanish) over David
            zira = next((v for v in voices if "zira" in v.name.lower()), None)
            if zira:
                _pyttsx3_engine.setProperty("voice", zira.id)
            else:
                helena = next((v for v in voices if "helena" in v.name.lower()), None)
                if helena:
                    _pyttsx3_engine.setProperty("voice", helena.id)
        except Exception:
            pass
    return _pyttsx3_engine


# ── Azure Speech Services ─────────────────────────────────────────────────

_AZURE_LANG_VOICES: dict[str, str] = {
    "es": "es-ES-AlvaroNeural",
    "en": "en-US-GuyNeural",
    "fr": "fr-FR-HenriNeural",
    "pt": "pt-BR-AntonioNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "ja": "ja-JP-KeitaNeural",
    "zh": "zh-CN-YunxiNeural",
}


def _azure_tts_available() -> bool:
    try:
        import azure.cognitiveservices.speech as _  # noqa: F401
    except ImportError:
        return False

    if os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"):
        return True

    # Fallback: read from Dulus config if env vars not set (e.g. key was
    # configured this session via /config but load_config() already ran).
    try:
        from config import load_config
        cfg = load_config()
        key = cfg.get("azure_speech_key")
        region = cfg.get("azure_speech_region")
        if key and region:
            os.environ["AZURE_SPEECH_KEY"] = key
            os.environ["AZURE_SPEECH_REGION"] = region
            return True
    except Exception:
        pass

    return False


def _say_azure(text: str, voice: Optional[str] = None, lang: str = "es") -> bool:
    if not _azure_tts_available():
        return False
    tmp_path: Optional[str] = None
    try:
        import azure.cognitiveservices.speech as speechsdk

        key = os.environ.get("AZURE_SPEECH_KEY", "")
        region = os.environ.get("AZURE_SPEECH_REGION", "")

        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)

        # Resolve voice: explicit arg > env var > config > language default
        if not voice:
            voice = os.environ.get("AZURE_TTS_VOICE", "")
        if not voice:
            try:
                from config import load_config
                voice = load_config().get("azure_tts_voice", "")
            except Exception:
                pass
        if not voice:
            voice = _AZURE_LANG_VOICES.get(lang.lower(), _AZURE_LANG_VOICES.get("en"))

        speech_config.speech_synthesis_voice_name = voice

        # Use mkstemp + close handle immediately so Azure (and later the player)
        # can open the file without Windows sharing violation.
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmp_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )
        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            _play_audio_file(tmp_path)
            return True
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            print(f"  [Azure TTS] Canceled: {cancellation.reason} — {cancellation.error_details}")
        return False
    except Exception as e:
        print(f"  [Azure TTS] Error: {e}")
        return False
    finally:
        if tmp_path:
            # Windows MCI may keep the file locked briefly after playback ends.
            # Retry a few times before giving up.
            for _ in range(15):
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.1)
                except Exception:
                    break


# ── NVIDIA Riva (Magpie-Multilingual via NVCF gRPC) ──────────────────────
RIVA_TTS_SERVER      = os.environ.get("DULUS_RIVA_SERVER", "grpc.nvcf.nvidia.com:443")
RIVA_TTS_FUNCTION_ID = os.environ.get("DULUS_RIVA_TTS_FUNCTION_ID",
                                      "877104f7-e885-42b9-8de8-f6e4c6303969")
RIVA_TTS_DEFAULT_VOICE = "Magpie-Multilingual.EN-US.Aria"
RIVA_TTS_SAMPLE_RATE = 44100

# Short BCP-47 → Riva language codes (Magpie expects xx-YY form).
_RIVA_LANG_MAP = {
    "es": "es-US", "en": "en-US", "fr": "fr-FR", "pt": "pt-BR",
    "de": "de-DE", "it": "it-IT", "ja": "ja-JP", "zh": "zh-CN",
}


def _riva_lang_code(lang: str) -> str:
    if not lang:
        return "en-US"
    return lang if "-" in lang else _RIVA_LANG_MAP.get(lang.lower(), f"{lang.lower()}-US")


def _riva_voice_for(lang: str) -> str:
    """Resolve voice via env var (per-language first, then global, then default).

    Set DULUS_RIVA_TTS_VOICE_ES="Magpie-Multilingual.ES-US.Lupe" etc. to map
    voices per language. Run `talk.py --list-voices` once to discover names.
    """
    specific = os.environ.get(f"DULUS_RIVA_TTS_VOICE_{(lang or 'en').upper().split('-')[0]}")
    if specific:
        return specific
    return os.environ.get("DULUS_RIVA_TTS_VOICE", RIVA_TTS_DEFAULT_VOICE)


def _pcm_to_wav(pcm: bytes, sample_rate: int = 44100) -> bytes:
    """Wrap raw int16 mono PCM in a minimal WAV container."""
    data_size = len(pcm)
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate,
        sample_rate * 2, 2, 16,
        b"data", data_size,
    ) + pcm


def _riva_tts_available() -> bool:
    if not os.environ.get("NVIDIA_API_KEY"):
        return False
    try:
        import riva.client  # noqa: F401
        return True
    except ImportError:
        return False


_RIVA_TTS_MAX_CHARS = 380  # Magpie hard limit is 400; leave headroom


def _split_for_riva(text: str, limit: int = _RIVA_TTS_MAX_CHARS) -> list[str]:
    """Split text into <=limit-char chunks at sentence/clause/word boundaries."""
    import re as _re
    text = text.strip()
    if not text:
        return []
    # First pass: sentence-ish split keeping the punctuation.
    parts = _re.split(r"(?<=[\.\!\?\u3002\uFF01\uFF1F\n])\s+", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= limit:
            out.append(p)
            continue
        # Sentence too long — split on commas / semicolons / colons.
        sub = _re.split(r"(?<=[,;:\u3001\uFF0C])\s+", p)
        buf = ""
        for s in sub:
            s = s.strip()
            if not s:
                continue
            if len(s) > limit:
                # Last resort: hard wrap on word boundaries.
                if buf:
                    out.append(buf)
                    buf = ""
                words = s.split(" ")
                w = ""
                for word in words:
                    if len(w) + len(word) + 1 > limit:
                        if w:
                            out.append(w)
                        w = word
                    else:
                        w = (w + " " + word).strip()
                if w:
                    buf = w
                continue
            if len(buf) + len(s) + 1 > limit:
                out.append(buf)
                buf = s
            else:
                buf = (buf + " " + s).strip()
        if buf:
            out.append(buf)
    return out


def _say_nvidia_riva(text: str, lang: str = "es") -> bool:
    if not _riva_tts_available():
        return False
    tmp_path = None
    try:
        import riva.client
        api_key = os.environ["NVIDIA_API_KEY"]
        auth = riva.client.Auth(
            None, True, RIVA_TTS_SERVER,
            [("function-id", RIVA_TTS_FUNCTION_ID),
             ("authorization", f"Bearer {api_key}")],
        )
        tts = riva.client.SpeechSynthesisService(auth)
        # Magpie caps inputs at ~400 chars per request — chunk by sentence.
        segments = _split_for_riva(text)
        if not segments:
            return False
        chunks = bytearray()
        voice = _riva_voice_for(lang)
        lang_code = _riva_lang_code(lang)
        enc = riva.client.AudioEncoding.LINEAR_PCM
        for seg in segments:
            try:
                stream = tts.synthesize_online(
                    seg, voice_name=voice, language_code=lang_code,
                    encoding=enc, sample_rate_hz=RIVA_TTS_SAMPLE_RATE,
                )
                for r in stream:
                    if getattr(r, "audio", None):
                        chunks.extend(r.audio)
            except AttributeError:
                resp = tts.synthesize(
                    seg, voice_name=voice, language_code=lang_code,
                    encoding=enc, sample_rate_hz=RIVA_TTS_SAMPLE_RATE,
                )
                chunks.extend(resp.audio)
        if not chunks:
            return False
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(_pcm_to_wav(bytes(chunks), sample_rate=RIVA_TTS_SAMPLE_RATE))
            tmp_path = f.name
        _play_audio_file(tmp_path)
        return True
    except Exception as e:
        print(f"  [Riva TTS] {e}")
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ── OpenAI TTS ────────────────────────────────────────────────────────────

def _say_openai(text: str, voice: str = "alloy", speed: float = 1.0) -> bool:
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    tmp_path = None
    try:
        from openai import OpenAI
        client = OpenAI(timeout=15.0)
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            speed=speed
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            response.stream_to_file(f.name)
            tmp_path = f.name
        _play_audio_file(tmp_path)
        return True
    except Exception as e:
        print(f"  [OpenAI TTS] Error: {e}")
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ── gTTS ──────────────────────────────────────────────────────────────────

def _say_gtts(text: str, lang: str = "en") -> bool:
    tmp_path = None
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, timeout=15)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tts.save(f.name)
            tmp_path = f.name
        _play_audio_file(tmp_path)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  [gTTS] Error: {e}")
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ── edge-tts (Microsoft Edge voices, fast & free) ─────────────────────────

_EDGE_TTS_VOICES: dict[str, str] = {
    "es": "es-ES-AlvaroNeural",
    "en": "en-US-GuyNeural",
    "zh": "zh-CN-YunxiNeural",
    "ja": "ja-JP-KeitaNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-KasperNeural",
    "pt": "pt-BR-AntonioNeural",
    "it": "it-IT-DiegoNeural",
    "ru": "ru-RU-DmitryNeural",
    "ko": "ko-KR-InJoonNeural",
}


def _say_edge_tts(text: str, lang: str = "es") -> bool:
    tmp_path = None
    try:
        import edge_tts
        import asyncio

        voice = _EDGE_TTS_VOICES.get(lang, _EDGE_TTS_VOICES.get(lang.split("-")[0], "en-US-GuyNeural"))
        communicate = edge_tts.Communicate(text, voice=voice)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        async def _save() -> None:
            await communicate.save(tmp_path)

        asyncio.run(_save())
        _play_audio_file(tmp_path)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  [edge-tts] Error: {e}")
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ── pyttsx3 ───────────────────────────────────────────────────────────────

def _say_pyttsx3(text: str, rate: Optional[int] = None) -> bool:
    global _pyttsx3_engine
    try:
        engine = _get_pyttsx3_engine()
        if rate:
            engine.setProperty("rate", rate)
        engine.say(text)
        engine.runAndWait()
        return True
    except (ImportError, Exception) as e:
        if not isinstance(e, ImportError):
            print(f"  [pyttsx3] Error: {e}")
        _pyttsx3_engine = None
        return False


# ── Text Cleaner ──────────────────────────────────────────────────────────

def _clean_for_tts(text: str) -> str:
    """Strip markdown, HTML, emojis, and code blocks before speaking."""
    # Remove <details>/<summary> blocks entirely
    text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL)
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove code fences (``` blocks)
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove XML-style tags like <WebSearch>
    text = re.sub(r'<\w+>.*?</\w+>', '', text, flags=re.DOTALL)
    # Remove markdown bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Remove markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove emojis
    text = re.sub(r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0001F300-\U0001FAFF]', '', text)
    # Collapse whitespace
    text = re.sub(r'\n{2,}', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


# ── ElevenLabs ────────────────────────────────────────────────────────────
# Default voice (KevRojo's cloned voice). Override via config.elevenlabs_voice_id
# or the ELEVENLABS_VOICE_ID env var, or pass voice= explicitly to say().
_ELEVENLABS_DEFAULT_VOICE = "CwhRBWXzGAHq8TQ4Fs17"
_ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"


def _elevenlabs_available() -> bool:
    """True iff the elevenlabs SDK is importable AND an API key is configured."""
    try:
        import elevenlabs  # noqa: F401
    except Exception:
        return False
    if os.environ.get("ELEVENLABS_API_KEY"):
        return True
    try:
        from config import load_config
        return bool(load_config().get("elevenlabs_api_key", ""))
    except Exception:
        return False


def _say_elevenlabs(text: str, voice: Optional[str] = None) -> bool:
    """Synthesize via ElevenLabs and play the resulting MP3.

    Reads API key from env first, config second. Voice resolution order:
    explicit arg > env var > config > module default (KevRojo's clone).
    Returns True on successful playback.
    """
    if not _elevenlabs_available():
        return False
    tmp_path: Optional[str] = None
    try:
        from elevenlabs.client import ElevenLabs

        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        voice_id = voice or os.environ.get("ELEVENLABS_VOICE_ID", "")
        model_id = os.environ.get("ELEVENLABS_MODEL_ID", "")
        if not api_key or not voice_id or not model_id:
            try:
                from config import load_config
                cfg = load_config()
                api_key = api_key or cfg.get("elevenlabs_api_key", "")
                voice_id = voice_id or cfg.get("elevenlabs_voice_id", "")
                model_id = model_id or cfg.get("elevenlabs_model_id", "")
            except Exception:
                pass
        voice_id = voice_id or _ELEVENLABS_DEFAULT_VOICE
        model_id = model_id or _ELEVENLABS_DEFAULT_MODEL
        if not api_key:
            return False

        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format="mp3_44100_128",
        )

        # `audio` is a generator of bytes — stream it into a temp .mp3 and
        # play via the shared player (interruptible with 'c').
        fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        with os.fdopen(fd, "wb") as f:
            for chunk in audio:
                if chunk:
                    f.write(chunk)
        _play_audio_file(tmp_path)
        return True
    except Exception as e:
        print(f"  [ElevenLabs TTS] Error: {e}")
        return False
    finally:
        if tmp_path:
            for _ in range(5):
                try:
                    os.unlink(tmp_path)
                    break
                except Exception:
                    time.sleep(0.2)


# ── Public Entry Point ────────────────────────────────────────────────────

def say(text: str, voice: Optional[str] = None, speed: float = 1.0, lang: str = "es", provider: Optional[str] = None) -> None:
    """Speak text using the best available TTS backend. Press 'c' to stop.

    Args:
        provider: Explicit backend to use. "auto" or None tries in priority order.
                  Supported: "pyttsx3", "edge", "gtts", "openai", "azure", "riva".
    """
    text = _clean_for_tts(text)
    if not text.strip():
        return

    with _say_lock:
        try:
            import input as _dulus_input
            _dulus_input.safe_print_notification(f"  📢 Speaking: '{text[:50]}...'  [c = stop]")
        except Exception:
            print(f"  📢 Speaking: '{text[:50]}...'  [c = stop]")

        _stop_event.clear()
        watcher = threading.Thread(target=_watch_for_cancel, daemon=True)
        watcher.start()

        try:
            # Helper to check if we should try a specific provider
            def _should_try(name: str) -> bool:
                if provider is None or provider == "auto":
                    return True
                return provider.lower() == name.lower()

            # 1. pyttsx3 — local, offline, instant (robotic SAPI5 voice)
            if _should_try("pyttsx3") and _say_pyttsx3(text):
                return
            if _stop_event.is_set():
                return

            # 2. edge-tts — Microsoft Edge voices (fast & free, needs internet)
            if _should_try("edge") and _say_edge_tts(text, lang=lang):
                return
            if _stop_event.is_set():
                return

            # 3. gTTS — cloud Spanish
            if _should_try("gtts") and _say_gtts(text, lang=lang):
                return
            if _stop_event.is_set():
                return

            # 4. ElevenLabs (premium voice cloning, needs API key)
            if _should_try("elevenlabs") and _say_elevenlabs(text, voice=voice):
                return
            if _stop_event.is_set():
                return

            # 5. OpenAI (high quality, needs key)
            if _should_try("openai") and _say_openai(text, voice=(voice or "alloy"), speed=speed):
                return
            if _stop_event.is_set():
                return

            # 5. Azure Speech Services
            if _should_try("azure") and _say_azure(text, voice=voice, lang=lang):
                return
            if _stop_event.is_set():
                return

            # 6. NVIDIA Riva (Magpie-Multilingual, cloud)
            if _should_try("riva") and _say_nvidia_riva(text, lang=lang):
                return

            # Final fallback — we intentionally do NOT print the spoken text
            # to the CLI. The "📢 Speaking: ..." notification above is sufficient.
            # This prevents accumulation of TTS notifications in the terminal.
        finally:
            _stop_event.set()  # stop watcher thread if playback ended naturally


def check_tts_availability() -> tuple[bool, str | None]:
    """Return (available, reason_if_not)."""
    try:
        import pyttsx3
        return True, "pyttsx3 (local, offline)"
    except ImportError:
        pass

    try:
        import edge_tts
        return True, "edge-tts (Microsoft Edge voices, cloud)"
    except ImportError:
        pass

    try:
        import gtts
        return True, "gTTS (cloud)"
    except ImportError:
        pass

    if _elevenlabs_available():
        return True, "ElevenLabs TTS (cloud, voice cloning)"

    if os.environ.get("OPENAI_API_KEY"):
        return True, "OpenAI TTS (cloud)"

    if _azure_tts_available():
        return True, "Azure Speech Services (cloud)"

    if _riva_tts_available():
        return True, "NVIDIA Riva Magpie-Multilingual (cloud)"

    return False, "No TTS backend installed. Try 'pip install pyttsx3', 'pip install edge-tts', 'pip install gTTS', 'pip install openai', 'pip install azure-cognitiveservices-speech', or 'pip install nvidia-riva-client'."
