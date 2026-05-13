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
        except Exception:
            pass
    else:
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except Exception:
            pass
