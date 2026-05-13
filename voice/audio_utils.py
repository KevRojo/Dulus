"""Audio utilities for dulus voice package."""
import sys

def beep(frequency: int = 1000, duration: int = 150) -> None:
    """Trigger a system beep using ffplay (if available) or winsound/terminal bell.
    
    Using ffplay is more robust for volume mixers and cross-platform.
    """
    import subprocess
    import sys
    
    # Try ffplay first (cross-platform, respects mixer better)
    try:
        dur = duration / 1000.0
        # sine generator via lavfi filter
        cmd = [
            "ffplay", "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={dur}",
            "-autoexit", "-nodisp", "-loglevel", "quiet"
        ]
        subprocess.run(cmd, check=True, timeout=1.0)
        return
    except Exception:
        pass

    # Fallback to native methods
    if sys.platform == "win32":
        try:
            import winsound
            winsound.Beep(frequency, duration)
            return
        except Exception:
            pass

    # Cross-platform synth fallback via sounddevice (already a voice dep).
    # This is what saves WSL where ffplay is rarely installed and the
    # terminal bell is silent — synthesize a sine and push it to the
    # default output device directly.
    try:
        import numpy as np
        import sounddevice as sd
        sr = 22050
        t = np.linspace(0, duration / 1000.0, int(sr * duration / 1000.0), endpoint=False)
        tone = (0.25 * np.sin(2 * np.pi * frequency * t)).astype("float32")
        sd.play(tone, sr, blocking=True)
        return
    except Exception:
        pass

    # Last resort: terminal bell. Often silent in modern terminals but
    # at least visible as ^G in some.
    try:
        if sys.stdout.isatty():
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        pass
