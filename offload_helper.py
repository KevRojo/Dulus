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
        self.session = f"falcon_{uuid.uuid4().hex[:8]}"
        self._created = False
        self._start_time = None
        
    def start(self) -> str:
        """Inicia el job en tmux detached. Retorna session ID."""
        # Usar bash -c para soportar pipes y redirects
        full_cmd = f"exec bash -c {repr(self.command)}"
        
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.session, full_cmd],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"tmux error: {result.stderr}")
        
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
    """
    job = TmuxJob(command)
    job.start()
    finished = job.wait(timeout=timeout)
    output = job.capture()
    job.kill()
    
    return {
        'session': job.session,
        'output': output,
        'finished': finished,
        'timeout_reached': not finished
    }


def list_offloaded():
    """Lista todas las sesiones falcon activas"""
    result = subprocess.run(
        ["tmux", "list-sessions"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return []
    
    sessions = []
    for line in result.stdout.strip().split('\n'):
        if line.startswith('falcon_'):
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
        print(f"   {len(sessions)} sesiones falcon activas")
        
        print("\n✅ Todo funcionando!")
    else:
        print("Uso: python offload_helper.py demo")
        print("\nFunciones:")
        print("  offload(cmd) -> session_id")
        print("  offload_and_wait(cmd, timeout) -> {output, session}")
        print("  list_offloaded() -> [sessions]")
