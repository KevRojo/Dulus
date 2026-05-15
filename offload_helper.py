#!/usr/bin/env python3
"""
Offload Helper - Reemplazo para TmuxOffload
Funciona con las herramientas tmux que sí funcionan
"""

import subprocess
import time
import uuid
from typing import Optional, Dict, Any


class TmuxJob:
    """Representa un job ejecutado en tmux"""
    
    def __init__(self, command: str):
        self.command = command
        self.session = f"dulus_{uuid.uuid4().hex[:8]}"
        self._created = False
        self._start_time = None
        
    def start(self) -> str:
        """Inicia el job en tmux detached. Retorna session ID.

        Defense-in-depth against leaked sessions:
          1. The command line itself ends in `tmux kill-session -t <id>`
             so the session self-destructs the moment the user's command
             finishes — works even if the user's tmux config has
             `remain-on-exit on` or the shell exits weirdly.
          2. We also force `remain-on-exit off` per-session right after
             creation, which neutralises any global `set-option -g
             remain-on-exit on` the user may have in `.tmux.conf`. Belt
             AND suspenders because session leaks have bitten KevRojo
             multiple times on Windows + tmux-via-WSL setups.
        """
        # Append a self-destruct so the session terminates after the user
        # command exits — independent of tmux config quirks.
        self_destruct = f" ; tmux kill-session -t {self.session}"
        full_cmd = f"exec bash -c {repr(self.command + self_destruct)}"

        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.session, full_cmd],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"tmux error: {result.stderr}")

        # Defensive: force remain-on-exit OFF for this session in case the
        # user's global tmux config flipped the default.
        subprocess.run(
            ["tmux", "set-option", "-t", self.session, "remain-on-exit", "off"],
            capture_output=True,
        )

        self._created = True
        self._start_time = time.time()
        return self.session
    
    def is_running(self) -> bool:
        """Verifica si el job sigue corriendo"""
        if not self._created:
            return False
        result = subprocess.run(
            ["tmux", "has-session", "-t", self.session],
            capture_output=True
        )
        return result.returncode == 0
    
    def capture(self, lines: int = 1000) -> str:
        """Captura el output del job"""
        if not self._created:
            raise RuntimeError("Job no iniciado")
        
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.session, "-p", "-S", f"-{lines}"],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else ""
    
    def kill(self):
        """Mata el job y la sesión tmux"""
        if self._created:
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session],
                capture_output=True
            )
    
    def wait(self, timeout: Optional[float] = None, poll_interval: float = 0.5) -> bool:
        """
        Espera a que termine el job.
        Retorna True si terminó, False si timeout.
        """
        if not self._created:
            raise RuntimeError("Job no iniciado")
        
        start = time.time()
        while self.is_running():
            if timeout and (time.time() - start) > timeout:
                return False
            time.sleep(poll_interval)
        return True


# === API SIMPLE ===

def offload(command: str) -> str:
    """
    Ejecuta un comando en tmux detached (fire-and-forget).
    Retorna el session ID para capturar después.
    
    Uso:
        session = offload("sleep 10 && echo listo")
        # ... más tarde ...
        tmux capture-pane -t <session>:0.0 -p
    """
    job = TmuxJob(command)
    return job.start()


def offload_and_wait(command: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    """
    Ejecuta comando y espera a que termine.

    Uso:
        result = offload_and_wait("sleep 5 && date", timeout=10)
        print(result['output'])  # stdout del comando

    Note: TmuxJob.start() appends a `tmux kill-session` self-destruct to
    avoid leaked sessions on misconfigured hosts. That means the pane is
    gone the moment the command finishes — so we capture mid-flight via
    a polling sidecar instead of relying on the post-wait capture (which
    would always come back empty). We poll the pane every `poll_interval`
    seconds and keep the LAST non-empty capture as the result.
    """
    job = TmuxJob(command)
    job.start()

    poll = 0.5
    last_output = ""
    start = time.time()
    while job.is_running():
        if timeout and (time.time() - start) > timeout:
            break
        snap = job.capture()
        if snap:
            last_output = snap
        time.sleep(poll)

    # One last attempt after the session ends — usually empty because the
    # self-destruct already fired, but cheap to try.
    final = job.capture()
    if final and final.strip():
        last_output = final

    # Idempotent — session is already gone in the happy path.
    job.kill()

    return {
        'session': job.session,
        'output': last_output,
        'finished': not job.is_running(),
        'timeout_reached': bool(timeout and (time.time() - start) > timeout)
    }


def list_offloaded():
    """Lista todas las sesiones dulus activas"""
    result = subprocess.run(
        ["tmux", "list-sessions"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return []
    
    sessions = []
    for line in result.stdout.strip().split('\n'):
        if line.startswith('dulus_'):
            sessions.append(line.split(':')[0])
    return sessions


# === EJEMPLOS ===

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        print("🦅 Demo de Offload Helper")
        print("=" * 40)
        
        # Demo 1: Fire and forget
        print("\n1️⃣ Fire-and-forget:")
        session = offload("echo 'Hola desde tmux!' && sleep 2 && date")
        print(f"   Session: {session}")
        print(f"   Para ver: tmux capture-pane -t {session}:0.0 -p")
        
        time.sleep(3)
        output = subprocess.run(
            ["tmux", "capture-pane", "-t", f"{session}:0.0", "-p"],
            capture_output=True, text=True
        ).stdout
        print(f"   Output: {output.strip()[:50]}...")
        
        # Limpiar
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        
        # Demo 2: Wait mode
        print("\n2️⃣ Wait mode:")
        result = offload_and_wait("echo 'Esperando...' && sleep 2 && echo 'Listo!' && date")
        print(f"   Output: {result['output'].strip()}")
        
        # Demo 3: Listar
        print("\n3️⃣ Sesiones activas:")
        sessions = list_offloaded()
        print(f"   {len(sessions)} sesiones dulus activas")
        
        print("\n✅ Todo funcionando!")
    else:
        print("Uso: python offload_helper.py demo")
        print("\nFunciones:")
        print("  offload(cmd) -> session_id")
        print("  offload_and_wait(cmd, timeout) -> {output, session}")
        print("  list_offloaded() -> [sessions]")
