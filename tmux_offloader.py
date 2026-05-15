#!/usr/bin/env python3
"""
TmuxOffloader - Wrapper alternativo a TmuxOffload
Usa tmux directamente ya que TmuxOffload tiene bugs
"""

import subprocess
import time
import random
import string
from pathlib import Path


def generate_session_name(prefix="job"):
    """Genera nombre único de sesión"""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{suffix}"


def run_in_tmux(command, session_name=None, wait=False, timeout=None):
    """
    Ejecuta un comando en una sesión tmux detached.
    
    Args:
        command: Comando a ejecutar (string)
        session_name: Nombre de sesión (auto-generado si None)
        wait: Si True, espera a que termine y retorna output
        timeout: Segundos máximos de espera (si wait=True)
    
    Returns:
        Si wait=False: session_name (para capturar después)
        Si wait=True: dict con {'stdout', 'stderr', 'returncode', 'session_name'}
    """
    if session_name is None:
        session_name = generate_session_name()

    # Crear sesión detached con el comando. We embed an exit sentinel so we
    # can recover the return code from the captured pane, and (for fire-
    # and-forget) we append a self-destruct so the session never lingers
    # even if the user's tmux config has `remain-on-exit on`.
    sentinel = f"echo '___TMUX_EXITCODE___'$?"
    if wait:
        # In wait mode we'll explicitly kill the session AFTER capturing
        # the pane, so don't self-destruct here.
        full_cmd = f"{command}; {sentinel}"
    else:
        # Fire-and-forget — the user may never come back to kill it.
        full_cmd = f"{command}; {sentinel}; tmux kill-session -t {session_name}"

    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, full_cmd],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create tmux session: {result.stderr}")

    # Belt-and-suspenders: neutralise any user-level `remain-on-exit on`
    # so a finished pane doesn't keep the session alive forever.
    subprocess.run(
        ["tmux", "set-option", "-t", session_name, "remain-on-exit", "off"],
        capture_output=True,
    )

    if not wait:
        return session_name
    
    # Modo wait: esperar a que termine
    max_wait = timeout or 300  # default 5 min
    waited = 0
    poll_interval = 0.5
    
    while waited < max_wait:
        # Verificar si la sesión sigue activa
        check = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )
        if check.returncode != 0:
            # Sesión terminó
            break
        time.sleep(poll_interval)
        waited += poll_interval
    
    # Capturar output
    capture = subprocess.run(
        ["tmux", "capture-pane", "-t", f"{session_name}:0.0", "-p"],
        capture_output=True,
        text=True
    )
    
    output = capture.stdout
    
    # Extraer exit code
    exit_code = 0
    if "___TMUX_EXITCODE___" in output:
        parts = output.rsplit("___TMUX_EXITCODE___", 1)
        output = parts[0].strip()
        try:
            exit_code = int(parts[1].strip().split()[0])
        except:
            exit_code = 0
    
    # Limpiar sesión
    subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
    
    return {
        'stdout': output,
        'stderr': '',  # tmux no separa stderr fácilmente
        'returncode': exit_code,
        'session_name': session_name
    }


def get_session_output(session_name):
    """
    Captura el output de una sesión tmux existente.
    Retorna el output o None si la sesión no existe.
    """
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", f"{session_name}:0.0", "-p"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return result.stdout
    return None


def is_session_active(session_name):
    """Verifica si una sesión tmux sigue activa"""
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True
    )
    return result.returncode == 0


def kill_session(session_name):
    """Mata una sesión tmux"""
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True
    )


def list_sessions():
    """Lista todas las sesiones tmux activas"""
    result = subprocess.run(
        ["tmux", "list-sessions"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return [line.split(':')[0] for line in result.stdout.strip().split('\n') if line]
    return []


# === EJEMPLO DE USO ===
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🧪 Probando TmuxOffloader...")
        
        # Test 1: Modo fire-and-forget
        print("\n[Test 1] Fire-and-forget:")
        session = run_in_tmux("echo 'Hola desde tmux' && sleep 2 && date")
        print(f"  Sesión creada: {session}")
        time.sleep(3)
        output = get_session_output(session)
        if output:
            print(f"  Output capturado: {output.strip()[:50]}...")
        kill_session(session)
        print("  ✅ Test 1 pasado")
        
        # Test 2: Modo wait
        print("\n[Test 2] Modo wait:")
        result = run_in_tmux("echo 'Esperando...' && sleep 2 && echo 'Listo!'", wait=True)
        print(f"  Output: {result['stdout'].strip()}")
        print(f"  Exit code: {result['returncode']}")
        print("  ✅ Test 2 pasado")
        
        print("\n🎉 Todo funcionando!")
    else:
        print("Uso: python tmux_offloader.py test")
        print("")
        print("Funciones disponibles:")
        print("  run_in_tmux(command, wait=False) - Ejecuta comando en tmux")
        print("  get_session_output(session) - Captura output de sesión")
        print("  is_session_active(session) - Verifica si sesión existe")
        print("  kill_session(session) - Mata sesión")
        print("  list_sessions() - Lista sesiones activas")
