"""Keep the test suite away from the developer's real ~/.dulus.

config.py resolves its directory once, at import, from $DULUS_CONFIG_DIR or
~/.dulus, and several modules write under ``Path.home() / ".dulus"`` directly.
Without this, running pytest rewrote the real config.json (test_voice saves
voice_lang through cmd_voice) and left scratch files next to it. This runs
before any test module is imported, so every import-time path lands here.
"""
import atexit
import os
import shutil
import tempfile

_SANDBOX = tempfile.mkdtemp(prefix="dulus-tests-")
atexit.register(shutil.rmtree, _SANDBOX, ignore_errors=True)

os.environ["HOME"] = _SANDBOX            # POSIX Path.home()
os.environ["USERPROFILE"] = _SANDBOX     # Windows Path.home()
os.environ["DULUS_CONFIG_DIR"] = os.path.join(_SANDBOX, ".dulus")
os.environ["DULUS_HOME"] = os.path.join(_SANDBOX, ".dulus")
