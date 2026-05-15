#!/usr/bin/env bash
# Dulus one-liner installer.
#
#   curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
#
# Flags (pass them after `bash -s --`):
#   --dry-run       Print every command that would run, change nothing.
#   --no-deps       Skip system dependency install (just pip install dulus).
#   --pre           Install latest pre-release from PyPI.
#   --uv            Use uv for the python install (auto-detected if present).
#   --pip           Force plain pip even if uv/pipx are available.
#   --pipx          Use pipx (isolated venv).
#   --profile=NAME  full | standard | basic | custom   (default: ask interactively)
#
# Example: dry run, no interaction
#   curl -fsSL ... | bash -s -- --dry-run
#
# Example: install full profile non-interactively
#   curl -fsSL ... | bash -s -- --profile=full --pipx
#
# This script is idempotent — re-running it on a working install upgrades
# Dulus to the latest version and leaves system deps alone.

set -euo pipefail

# ── colors (only if stdout is a TTY) ─────────────────────────────────────────
if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
    RED=$(tput setaf 1); GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3); BLUE=$(tput setaf 4); CYAN=$(tput setaf 6)
else
    BOLD=""; DIM=""; RESET=""
    RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""
fi

say()   { printf "%s%s%s\n"      "${CYAN}"   "$*" "${RESET}"; }
ok()    { printf "%s✓%s %s\n"    "${GREEN}"  "${RESET}" "$*"; }
warn()  { printf "%s!%s %s\n"    "${YELLOW}" "${RESET}" "$*"; }
err()   { printf "%s✗%s %s\n"    "${RED}"    "${RESET}" "$*" >&2; }
header(){ printf "\n%s%s%s\n%s%s%s\n"  "${BOLD}${CYAN}" "$*" "${RESET}" "${DIM}" "─────────────────────────────────────────────" "${RESET}"; }

# ── flags ────────────────────────────────────────────────────────────────────
DRY_RUN=0
NO_DEPS=0
PRE=0
INSTALLER=""        # auto | pip | pipx | uv
PROFILE=""          # full | standard | basic | custom (empty = ask)
for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN=1 ;;
        --no-deps)  NO_DEPS=1 ;;
        --pre)      PRE=1 ;;
        --uv)       INSTALLER="uv" ;;
        --pip)      INSTALLER="pip" ;;
        --pipx)     INSTALLER="pipx" ;;
        --profile=*) PROFILE="${arg#--profile=}" ;;
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) warn "Unknown flag: $arg (ignoring)" ;;
    esac
done

run() {
    # Single shim for the dry-run mode. Echoes the command; runs it only if
    # not --dry-run.
    printf "%s$%s %s\n" "${DIM}" "${RESET}" "$*"
    if [ "$DRY_RUN" -eq 0 ]; then
        eval "$@"
    fi
}

# ── banner ───────────────────────────────────────────────────────────────────
cat <<'BANNER'

  ▲ DULUS — installer
  Multi-provider AI CLI · The bird, not the rocket 🦅

BANNER

[ "$DRY_RUN" -eq 1 ] && warn "Dry run mode — nothing will actually be installed."

# ═══════════════════════════════════════════════════════════════════════════
# 1. ENVIRONMENT DETECTION (always runs first, regardless of profile)
# ═══════════════════════════════════════════════════════════════════════════
header "1. Detecting your environment"

UNAME_S=$(uname -s 2>/dev/null || echo "Unknown")
UNAME_R=$(uname -r 2>/dev/null || echo "")
DISTRO=""
DISTRO_VER=""
IS_WSL=0
IS_WSLG=0
IS_MAC=0
IS_LINUX=0
IS_TERMUX=0
IS_GITBASH=0

case "$UNAME_S" in
    Linux*)
        IS_LINUX=1
        if [ -r /etc/os-release ]; then
            DISTRO=$(. /etc/os-release && echo "${ID:-linux}")
            DISTRO_VER=$(. /etc/os-release && echo "${VERSION_ID:-}")
        fi
        if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
            IS_WSL=1
            # WSLg present means a working /mnt/wslg pulse socket
            [ -S /mnt/wslg/PulseServer ] && IS_WSLG=1
            printf "  %sOS:%s WSL  (%s%s)\n" "${BOLD}" "${RESET}" "$DISTRO" "${DISTRO_VER:+ $DISTRO_VER}"
            if [ "$IS_WSLG" -eq 1 ]; then
                printf "  %sWSLg:%s available — /voice will work via PulseAudio bridge\n" "${BOLD}" "${RESET}"
            else
                printf "  %sWSLg:%s ${YELLOW}missing${RESET} — run \`wsl --update\` from PowerShell for /voice support\n" "${BOLD}" "${RESET}"
            fi
        elif [ -n "${PREFIX:-}" ] && echo "${PREFIX}" | grep -q "com.termux"; then
            IS_TERMUX=1
            printf "  %sOS:%s Termux (Android)\n" "${BOLD}" "${RESET}"
        else
            printf "  %sOS:%s Linux  (%s%s)\n" "${BOLD}" "${RESET}" "$DISTRO" "${DISTRO_VER:+ $DISTRO_VER}"
        fi ;;
    Darwin*)
        IS_MAC=1
        DISTRO="macos"
        DISTRO_VER=$(sw_vers -productVersion 2>/dev/null || echo "")
        printf "  %sOS:%s macOS %s\n" "${BOLD}" "${RESET}" "$DISTRO_VER" ;;
    MINGW*|CYGWIN*|MSYS*)
        IS_GITBASH=1
        DISTRO="windows"
        printf "  %sOS:%s Windows (Git Bash / MSYS)\n" "${BOLD}" "${RESET}"
        warn "For native Windows, prefer install.ps1 — this shell can't sudo apt."
        ;;
    *)
        printf "  %sOS:%s %s ${YELLOW}(unknown)${RESET}\n" "${BOLD}" "${RESET}" "$UNAME_S" ;;
esac

# Package manager
PKG=""
PKG_INSTALL=""
PKG_UPDATE=""
PKG_QUERY=""   # how to check if a single pkg is installed

if [ "$IS_TERMUX" -eq 1 ]; then
    PKG="pkg"; PKG_INSTALL="pkg install -y"; PKG_UPDATE="pkg update -y"
    PKG_QUERY='pkg list-installed 2>/dev/null | grep -q "^${P}/"'
elif command -v apt-get >/dev/null 2>&1; then
    PKG="apt"; PKG_INSTALL="sudo apt-get install -y"; PKG_UPDATE="sudo apt-get update"
    PKG_QUERY='dpkg -s "$P" >/dev/null 2>&1'
elif command -v dnf >/dev/null 2>&1; then
    PKG="dnf"; PKG_INSTALL="sudo dnf install -y"; PKG_UPDATE="sudo dnf check-update || true"
    PKG_QUERY='rpm -q "$P" >/dev/null 2>&1'
elif command -v pacman >/dev/null 2>&1; then
    PKG="pacman"; PKG_INSTALL="sudo pacman -S --noconfirm"; PKG_UPDATE="sudo pacman -Sy"
    PKG_QUERY='pacman -Q "$P" >/dev/null 2>&1'
elif command -v brew >/dev/null 2>&1; then
    PKG="brew"; PKG_INSTALL="brew install"; PKG_UPDATE="brew update"
    PKG_QUERY='brew list "$P" >/dev/null 2>&1'
elif command -v zypper >/dev/null 2>&1; then
    PKG="zypper"; PKG_INSTALL="sudo zypper install -y"; PKG_UPDATE="sudo zypper refresh"
    PKG_QUERY='rpm -q "$P" >/dev/null 2>&1'
fi

if [ -n "$PKG" ]; then
    printf "  %sPkg mgr:%s %s\n" "${BOLD}" "${RESET}" "$PKG"
else
    printf "  %sPkg mgr:%s ${YELLOW}none detected${RESET} — system deps will need manual install\n" "${BOLD}" "${RESET}"
fi

# Python
PY_BIN=""
PY_VER=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        v=$("$candidate" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "0.0")
        major=${v%%.*}
        minor=${v##*.}
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PY_BIN="$candidate"
            PY_VER="$v"
            break
        fi
    fi
done

if [ -z "$PY_BIN" ]; then
    err "No Python 3.11+ found on PATH."
    case "$PKG" in
        apt)    say "  Install with: sudo apt install python3.11 python3.11-venv python3.11-dev" ;;
        brew)   say "  Install with: brew install python@3.12" ;;
        pkg)    say "  Install with: pkg install python" ;;
        dnf)    say "  Install with: sudo dnf install python3.12 python3.12-devel" ;;
        pacman) say "  Install with: sudo pacman -S python" ;;
    esac
    # Bonus diagnostic — Python might actually BE installed but missing from
    # PATH. That's the #1 fresh-WSL / fresh-Windows pain point. Try the
    # well-known interpreter locations and tell the user where it lives.
    HINT=""
    for guess in /usr/local/bin/python3 /opt/python*/bin/python3 \
                 "$HOME/.pyenv/shims/python3" \
                 "$HOME/AppData/Local/Programs/Python/Python313/python.exe" \
                 "$HOME/AppData/Local/Programs/Python/Python312/python.exe" \
                 "$HOME/AppData/Local/Programs/Python/Python311/python.exe" \
                 "/c/Program Files/Python313/python.exe" \
                 "/c/Program Files/Python312/python.exe" \
                 "/c/Program Files/Python311/python.exe" ; do
        if [ -x "$guess" ]; then
            HINT="$guess"
            break
        fi
    done
    if [ -n "$HINT" ]; then
        echo
        warn "Found a Python at: $HINT"
        warn "It's installed but not on PATH. Add this line to ~/.bashrc / ~/.zshrc:"
        echo "    export PATH=\"$(dirname "$HINT"):\$PATH\""
        echo "Then open a new shell and re-run me."
    fi
    exit 1
fi
printf "  %sPython:%s %s (%s)\n" "${BOLD}" "${RESET}" "$PY_BIN" "$PY_VER"

# Warn if the installer puts dulus somewhere that's NOT on PATH yet
# (very common on fresh WSL when ~/.local/bin or %APPDATA%\Python\Scripts
# isn't in PATH out of the box).
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *)
        if [ -d "$HOME/.local/bin" ]; then
            warn "Heads up: $HOME/.local/bin is NOT on your PATH."
            warn "After install you may need to run:"
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
        fi
        ;;
esac

# Python installer.
#
# IMPORTANT: For Dulus we DEFAULT TO pip (--user) instead of uv/pipx.
# Reason: Dulus loads plugins at runtime that import arbitrary packages
# (pandas via yfinance, tomli via sherlock, etc.). uv tool and pipx
# put Dulus inside a private venv — plugins then can't find packages
# that the user `pip install`s into their main env. pip --user shares
# the user-site env with the rest of their tools, so plugins Just Work.
#
# We still offer uv/pipx for power users who know the trade-off; if
# either is present and the user is on a TTY, we ask. Non-interactive
# (curl|bash) always falls back to pip --user.
if [ -z "$INSTALLER" ]; then
    HAVE_UV=0;   command -v uv   >/dev/null 2>&1 && HAVE_UV=1
    HAVE_PIPX=0; command -v pipx >/dev/null 2>&1 && HAVE_PIPX=1
    if [ "$HAVE_UV" -eq 1 ] || [ "$HAVE_PIPX" -eq 1 ]; then
        if [ -t 0 ]; then
            echo
            say "How would you like to install Dulus?"
            printf "  ${BOLD}1)${RESET} pip --user   (recommended — plugins share your Python env, no surprises)\n"
            if [ "$HAVE_UV" -eq 1 ]; then
                printf "  ${BOLD}2)${RESET} uv tool      (isolated venv — clean, but plugins like yfinance/sherlock can't see deps you pip-install yourself)\n"
            fi
            if [ "$HAVE_PIPX" -eq 1 ]; then
                printf "  ${BOLD}3)${RESET} pipx         (isolated venv — same trade-off as uv)\n"
            fi
            printf "\n%sPick 1-3 [default: 1]> %s" "${BOLD}" "${RESET}"
            read -r _inst_choice
            case "${_inst_choice:-1}" in
                1) INSTALLER="pip" ;;
                2) INSTALLER="uv" ;;
                3) INSTALLER="pipx" ;;
                *) INSTALLER="pip" ;;
            esac
        else
            # Non-interactive (curl|bash) — pick the safe default.
            INSTALLER="pip"
        fi
    else
        INSTALLER="pip"
    fi
fi
printf "  %sInstaller:%s %s\n" "${BOLD}" "${RESET}" "$INSTALLER"

# Tmux / audio probe
HAVE_TMUX=0; command -v tmux >/dev/null 2>&1 && HAVE_TMUX=1
HAVE_PULSE=0; command -v pulseaudio >/dev/null 2>&1 && HAVE_PULSE=1
[ "$HAVE_TMUX" -eq 1 ] && printf "  %sTmux:%s installed\n" "${BOLD}" "${RESET}"
[ "$HAVE_PULSE" -eq 1 ] && printf "  %sPulse:%s installed\n" "${BOLD}" "${RESET}"

# ═══════════════════════════════════════════════════════════════════════════
# 2. PROFILE PICKER
# ═══════════════════════════════════════════════════════════════════════════
header "2. Pick an install profile"

cat <<EOF

  ${BOLD}1) full${RESET}      — everything. Voice (Whisper+PortAudio), browser tools (Playwright),
                MemPalace semantic memory, GUI (tkinter), tmux, WSL audio bridge.
                Heaviest install. ~1.5 GB. Best for daily-driver setups.

  ${BOLD}2) standard${RESET}  — REPL + webchat + tmux daemon + Telegram bridge.
                Skips voice, GUI, browser automation, semantic memory.
                ~300 MB. The "I just want to chat" sweet spot.

  ${BOLD}3) basic${RESET}     — bare \`pip install dulus\`. No system deps installed.
                ~150 MB. For servers / Docker / minimal sandboxes.

  ${BOLD}4) custom${RESET}    — toggle each feature one by one.

EOF

if [ -n "$PROFILE" ]; then
    ok "Profile preselected: $PROFILE"
elif [ ! -t 0 ]; then
    warn "Non-interactive shell (curl|bash) — defaulting to ${BOLD}full${RESET}.\n"
    warn "Pass --profile=standard|basic to override on next run."
    PROFILE="full"
else
    printf "%sPick 1-4 [default: 1]> %s" "${BOLD}" "${RESET}"
    read -r choice
    choice=${choice:-1}
    case "$choice" in
        1|full)     PROFILE="full" ;;
        2|standard) PROFILE="standard" ;;
        3|basic)    PROFILE="basic" ;;
        4|custom)   PROFILE="custom" ;;
        *) err "Invalid choice — aborting."; exit 1 ;;
    esac
fi

# Profile → feature flags
WANT_VOICE=0
WANT_GUI=0
WANT_TMUX=0
WANT_WEBBRIDGE=0
WANT_MEMPALACE=0

case "$PROFILE" in
    full)
        WANT_VOICE=1; WANT_GUI=1; WANT_TMUX=1; WANT_WEBBRIDGE=1; WANT_MEMPALACE=1 ;;
    standard)
        WANT_TMUX=1 ;;
    basic)
        : ;;  # nothing
    custom)
        ask() {
            local q="$1"; local default="$2"
            printf "  %s [Y/n]: " "$q"
            read -r r
            r=${r:-$default}
            case "$r" in [Yy]*) return 0 ;; *) return 1 ;; esac
        }
        ask "Voice input (Whisper + PortAudio)?" Y && WANT_VOICE=1
        ask "Desktop GUI (tkinter)?" N && WANT_GUI=1
        ask "Tmux for /bg start daemon?" Y && WANT_TMUX=1
        ask "Browser automation (Playwright)?" N && WANT_WEBBRIDGE=1
        ask "Semantic memory (MemPalace)?" Y && WANT_MEMPALACE=1
        ;;
esac
ok "Profile: ${BOLD}$PROFILE${RESET}"

# ═══════════════════════════════════════════════════════════════════════════
# 3. COMPUTE NEEDED SYSTEM PACKAGES
# ═══════════════════════════════════════════════════════════════════════════
declare -a NEEDED_PKGS=()

pkg_missing() {
    local P="$1"
    [ -z "$PKG_QUERY" ] && return 0  # no query method → assume missing
    eval "$PKG_QUERY" && return 1 || return 0
}

if [ "$NO_DEPS" -eq 0 ] && [ -n "$PKG" ]; then
    case "$PKG" in
    apt)
        # Voice: input (PortAudio + ALSA for recording) + output (ffmpeg for
        # TTS playback — Dulus shells out to ffplay/mpv when the TTS provider
        # returns an mp3, otherwise you get "no player found").
        if [ "$WANT_VOICE" -eq 1 ]; then
            for p in libportaudio2 portaudio19-dev libasound2-dev ffmpeg; do
                pkg_missing "$p" && NEEDED_PKGS+=("$p")
            done
            # WSL: pulseaudio bridge for audio devices
            if [ "$IS_WSL" -eq 1 ]; then
                for p in pulseaudio pulseaudio-utils alsa-utils libasound2-plugins libpulse0; do
                    pkg_missing "$p" && NEEDED_PKGS+=("$p")
                done
            fi
        fi
        # GUI: tkinter ships separate on Debian/Ubuntu
        if [ "$WANT_GUI" -eq 1 ]; then
            pkg_missing python3-tk && NEEDED_PKGS+=("python3-tk")
        fi
        # Tmux
        if [ "$WANT_TMUX" -eq 1 ]; then
            pkg_missing tmux && NEEDED_PKGS+=("tmux")
        fi
        # Playwright system deps are handled by `playwright install --with-deps`,
        # not apt directly — we skip them here.
        ;;
    brew)
        if [ "$WANT_VOICE" -eq 1 ]; then
            pkg_missing portaudio && NEEDED_PKGS+=("portaudio")
            pkg_missing ffmpeg    && NEEDED_PKGS+=("ffmpeg")
        fi
        [ "$WANT_GUI"   -eq 1 ] && { pkg_missing python-tk && NEEDED_PKGS+=("python-tk"); }
        [ "$WANT_TMUX"  -eq 1 ] && { pkg_missing tmux      && NEEDED_PKGS+=("tmux"); }
        ;;
    pkg)
        # Termux. Voice support is iffy on Android — best-effort.
        [ "$WANT_TMUX"  -eq 1 ] && { pkg_missing tmux && NEEDED_PKGS+=("tmux"); }
        if [ "$WANT_VOICE" -eq 1 ]; then
            pkg_missing python-numpy && NEEDED_PKGS+=("python-numpy")
            pkg_missing ffmpeg       && NEEDED_PKGS+=("ffmpeg")
        fi
        ;;
    dnf)
        if [ "$WANT_VOICE" -eq 1 ]; then
            pkg_missing portaudio-devel && NEEDED_PKGS+=("portaudio-devel")
            pkg_missing alsa-lib-devel  && NEEDED_PKGS+=("alsa-lib-devel")
            pkg_missing ffmpeg          && NEEDED_PKGS+=("ffmpeg")
        fi
        [ "$WANT_GUI"   -eq 1 ] && { pkg_missing python3-tkinter && NEEDED_PKGS+=("python3-tkinter"); }
        [ "$WANT_TMUX"  -eq 1 ] && { pkg_missing tmux            && NEEDED_PKGS+=("tmux"); }
        ;;
    pacman)
        if [ "$WANT_VOICE" -eq 1 ]; then
            pkg_missing portaudio && NEEDED_PKGS+=("portaudio")
            pkg_missing ffmpeg    && NEEDED_PKGS+=("ffmpeg")
        fi
        [ "$WANT_GUI"   -eq 1 ] && { pkg_missing tk        && NEEDED_PKGS+=("tk"); }
        [ "$WANT_TMUX"  -eq 1 ] && { pkg_missing tmux      && NEEDED_PKGS+=("tmux"); }
        ;;
    zypper)
        if [ "$WANT_VOICE" -eq 1 ]; then
            pkg_missing portaudio-devel && NEEDED_PKGS+=("portaudio-devel")
            pkg_missing alsa-devel      && NEEDED_PKGS+=("alsa-devel")
            pkg_missing ffmpeg          && NEEDED_PKGS+=("ffmpeg")
        fi
        [ "$WANT_GUI"   -eq 1 ] && { pkg_missing python3-tk && NEEDED_PKGS+=("python3-tk"); }
        [ "$WANT_TMUX"  -eq 1 ] && { pkg_missing tmux       && NEEDED_PKGS+=("tmux"); }
        ;;
    esac
fi

# ═══════════════════════════════════════════════════════════════════════════
# 4. ASK USER HOW TO INSTALL SYSTEM PACKAGES
# ═══════════════════════════════════════════════════════════════════════════
if [ "${#NEEDED_PKGS[@]}" -gt 0 ]; then
    header "3. System dependencies"
    say "Missing for profile '${PROFILE}':"
    for p in "${NEEDED_PKGS[@]}"; do
        printf "  • %s\n" "$p"
    done
    echo
    printf "  ${BOLD}1)${RESET} Auto-install now (sudo password prompt)\n"
    printf "  ${BOLD}2)${RESET} Show me the command, I'll run it manually\n"
    printf "  ${BOLD}3)${RESET} Skip — proceed with pip install only\n"

    if [ ! -t 0 ]; then
        warn "Non-interactive shell — showing command only (run it yourself):"
        printf "\n  %s\n\n" "$PKG_INSTALL ${NEEDED_PKGS[*]}"
        say "Re-run me from an interactive terminal for auto-install:"
        say "  bash <(curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh)"
        choice=2
    else
        printf "\n%sPick 1-3 [default: 1]> %s" "${BOLD}" "${RESET}"
        read -r choice
        choice=${choice:-1}
    fi

    case "$choice" in
        1)
            header "Installing system packages"
            [ -n "$PKG_UPDATE" ] && run "$PKG_UPDATE"
            run "$PKG_INSTALL ${NEEDED_PKGS[*]}"
            ok "System dependencies installed."
            ;;
        2)
            header "Manual install"
            say "Run this in another terminal, then come back and re-run me:"
            printf "\n  %s\n\n" "$PKG_INSTALL ${NEEDED_PKGS[*]}"
            exit 0
            ;;
        3)
            warn "Skipping system deps. Some features in profile '$PROFILE' won't work until installed manually."
            ;;
        *)  err "Invalid choice — aborting."; exit 1 ;;
    esac
else
    if [ "$NO_DEPS" -eq 0 ]; then
        ok "All system packages for profile '$PROFILE' are already present."
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 5. WSL AUDIO CONFIG (~/.asoundrc) — only if voice profile + WSL + WSLg
# ═══════════════════════════════════════════════════════════════════════════
if [ "$WANT_VOICE" -eq 1 ] && [ "$IS_WSL" -eq 1 ] && [ "$IS_WSLG" -eq 1 ]; then
    if [ ! -f "$HOME/.asoundrc" ] || ! grep -q "wslg/PulseServer" "$HOME/.asoundrc" 2>/dev/null; then
        header "4. WSL audio bridge"
        say "Writing ~/.asoundrc so ALSA routes through the WSLg PulseAudio socket."
        if [ "$DRY_RUN" -eq 0 ]; then
            cat > "$HOME/.asoundrc" <<'EOF'
# Route ALSA through the WSLg PulseAudio bridge (auto-written by dulus installer).
# This is what makes Kali / minimal WSL distros find your Windows mic.
pcm.!default {
    type pulse
    server unix:/mnt/wslg/PulseServer
}
ctl.!default {
    type pulse
    server unix:/mnt/wslg/PulseServer
}
EOF
        else
            printf "%s$%s cat > ~/.asoundrc <<EOF ... EOF (writes 7 lines)\n" "${DIM}" "${RESET}"
        fi
        ok "~/.asoundrc configured for WSLg audio."
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 6. PIP EXTRAS — translate profile into the right `dulus[extras]` spec
# ═══════════════════════════════════════════════════════════════════════════
declare -a EXTRAS=()
[ "$WANT_VOICE"     -eq 1 ] && EXTRAS+=("voice")
[ "$WANT_WEBBRIDGE" -eq 1 ] && EXTRAS+=("webbridge")
[ "$WANT_MEMPALACE" -eq 1 ] && EXTRAS+=("memory")

if [ "${#EXTRAS[@]}" -gt 0 ]; then
    EXTRAS_SPEC="dulus[$(IFS=,; echo "${EXTRAS[*]}")]"
else
    EXTRAS_SPEC="dulus"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 7. INSTALL DULUS
# ═══════════════════════════════════════════════════════════════════════════
header "5. Installing Dulus"

PRE_FLAG=""
[ "$PRE" -eq 1 ] && PRE_FLAG="--pre"

case "$INSTALLER" in
    uv)
        ok "Using uv (isolated venv — note: runtime plugins won't see deps installed outside this env)"
        # uv tool install SKIPS if already installed. Detect that and upgrade
        # instead so re-runs of the installer actually pull the latest Dulus.
        if uv tool list 2>/dev/null | grep -q "^dulus "; then
            run "uv tool upgrade dulus"
        else
            run "uv tool install '$EXTRAS_SPEC' $PRE_FLAG --python $PY_BIN"
        fi
        ;;
    pipx)
        ok "Using pipx (isolated venv — same note as uv)"
        if [ "${#EXTRAS[@]}" -gt 0 ]; then
            run "pipx install 'dulus[$(IFS=,; echo "${EXTRAS[*]}")]' $PRE_FLAG --python $PY_BIN --force"
        else
            run "pipx install dulus $PRE_FLAG --python $PY_BIN --force"
        fi
        ;;
    pip)
        ok "Using pip --user (recommended — plugins share your Python env)"
        # Detect modern pip with PEP 668 + Termux quirks
        BREAK=""
        if [ "$IS_TERMUX" -eq 1 ] || "$PY_BIN" -m pip install --help 2>&1 | grep -q "break-system-packages"; then
            BREAK="--break-system-packages"
        fi
        # --user puts dulus in ~/.local/bin (Linux/macOS) or %APPDATA%\Python\
        # (Windows) where any plugin's `pip install pandas` lands too. If
        # running inside an active venv, --user is rejected — strip it then.
        USER_FLAG="--user"
        if [ -n "${VIRTUAL_ENV:-}" ]; then
            USER_FLAG=""
            ok "Detected active venv: $VIRTUAL_ENV — installing into it instead of --user"
        fi
        run "$PY_BIN -m pip install --upgrade $PRE_FLAG $BREAK $USER_FLAG '$EXTRAS_SPEC'"
        ;;
esac

# Playwright browser binaries — only if webbridge was requested
if [ "$WANT_WEBBRIDGE" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    if command -v playwright >/dev/null 2>&1; then
        run "playwright install chromium --with-deps || playwright install chromium"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 8. VERIFY
# ═══════════════════════════════════════════════════════════════════════════
header "6. Verifying"

DULUS_BIN=""
for cand in \
    "$HOME/.local/bin/dulus" \
    "$HOME/.cargo/bin/dulus" \
    "$HOME/.uv/tools/dulus/bin/dulus" \
    "$(command -v dulus 2>/dev/null || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then
        DULUS_BIN="$cand"
        break
    fi
done

if [ -z "$DULUS_BIN" ]; then
    warn "dulus binary not found on PATH yet — open a new terminal."
    warn "If pipx/uv was used, run: pipx ensurepath  (or  uv tool update-shell)"
else
    if [ "$DRY_RUN" -eq 0 ]; then
        VER=$("$DULUS_BIN" --version 2>/dev/null | head -1 | awk '{print $NF}' || echo "?")
        ok "Installed: $DULUS_BIN ($VER)"
    else
        ok "(dry-run) would verify: $DULUS_BIN --version"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 9. NEXT STEPS
# ═══════════════════════════════════════════════════════════════════════════
header "✓ All set"
cat <<EOF

  Get going:
    ${BOLD}dulus${RESET}                    open the REPL
    ${BOLD}dulus --help${RESET}             list flags
    ${BOLD}dulus -c "help"${RESET}          list every slash command
    ${BOLD}dulus -c "bg start"${RESET}      run headless daemon in tmux + webchat

  First-run picks:
    • Pick a model with ${BOLD}/model${RESET} (NVIDIA tier is free — 14 frontier models)
    • Set your soul with ${BOLD}/soul${RESET} (English / Spanish / your own)
    • ${BOLD}/help${RESET} inside the REPL shows everything

  Trouble?
    ${BOLD}dulus -c "doctor"${RESET}        run the full health check

  Profile installed:  ${BOLD}$PROFILE${RESET}
  Re-install / switch profile any time:
    ${DIM}curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash${RESET}

  Docs · github.com/KevRojo/Dulus
  X    · @KevRojox
  PyPI · pypi.org/project/dulus
                                          ${CYAN}🦅 Lo visible no necesita espejuelo.${RESET}

EOF
