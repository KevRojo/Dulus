# syntax=docker/dockerfile:1.6
#
# Dulus — multi-provider AI CLI runtime image.
#
# Build:
#   docker build -t kevrojo/dulus:latest .
#
# Run (interactive REPL):
#   docker run -it --rm \
#       -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
#       -v dulus-memory:/root/.dulus \
#       kevrojo/dulus
#
# Run (daemon mode with webchat exposed on host :5050 — shifted off 5000 so
# a native Dulus install on the host can keep its default ports):
#   docker run -d --name dulus \
#       -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
#       -v dulus-memory:/root/.dulus \
#       -p 5050:5000 -p 5152:5151 \
#       kevrojo/dulus dulus --daemon
#
# Pull a published image:
#   docker pull ghcr.io/kevrojo/dulus:latest

# ─── Stage 1: builder ────────────────────────────────────────────────────────
# We resolve the wheel from PyPI in a throw-away builder so the final image
# only ships the installed package (no pip cache, no build deps).
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build

# Install build deps only when present. Keeping this minimal so the layer is
# small; if the user wants the [voice]/[memory]/[webbridge] extras they can
# pass --build-arg DULUS_EXTRAS="voice,memory".
ARG DULUS_VERSION=
ARG DULUS_EXTRAS=

# Use the published wheel by default. To build from local source instead,
# pass --build-arg DULUS_SOURCE=local and ensure the repo is in the context.
ARG DULUS_SOURCE=pypi
COPY pyproject.toml ./pyproject-local.toml

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends git build-essential; \
    if [ "$DULUS_SOURCE" = "local" ]; then \
        echo "Building Dulus from local source (context)"; \
    else \
        pkg="dulus${DULUS_VERSION:+==$DULUS_VERSION}"; \
        if [ -n "$DULUS_EXTRAS" ]; then pkg="dulus[$DULUS_EXTRAS]${DULUS_VERSION:+==$DULUS_VERSION}"; fi; \
        echo "Installing $pkg from PyPI"; \
        pip install --prefix=/install "$pkg"; \
    fi; \
    rm -rf /var/lib/apt/lists/*

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    DULUS_IN_DOCKER=1

# Minimal runtime deps:
#   tmux  — needed for `dulus /bg start` (background daemon launcher)
#   git   — many plugin install flows shell out to git
#   curl  — handy for in-container smoke tests
#   ca-certificates — for HTTPS to API providers
#   tini  — proper PID 1 for clean signal handling
# Build with --build-arg WITH_VOICE=1 if you plan to use [voice] (Whisper,
# sounddevice). It pulls libportaudio2 + ALSA dev headers so the sounddevice
# wheel can find PortAudio at runtime — without these you hit
# `OSError: PortAudio library not found` on first /voice call.
ARG WITH_VOICE=0

# Build with --build-arg WITH_GUI=1 to bundle tkinter for the desktop GUI
# (`dulus-gui` / customtkinter). Not needed for the REPL or the webchat
# HTTP server thanks to lazy GUI imports in 0.2.76+. Default off so the
# slim image stays slim.
ARG WITH_GUI=0

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        tmux git curl ca-certificates tini; \
    if [ "$WITH_VOICE" = "1" ]; then \
        apt-get install -y --no-install-recommends \
            libportaudio2 portaudio19-dev libasound2-dev; \
    fi; \
    if [ "$WITH_GUI" = "1" ]; then \
        apt-get install -y --no-install-recommends python3-tk; \
    fi; \
    rm -rf /var/lib/apt/lists/*

# Bring the installed Dulus from the builder.
COPY --from=builder /install /usr/local

# Memory + config volume. Mount this so soul.md, MemPalace, plugins, and
# session checkpoints survive container restarts.
VOLUME ["/root/.dulus"]
WORKDIR /root

# Expose:
#   5000  WebChat HTTP (browser UI)
#   5151  IPC port used by `/bg` daemon and external integrations
EXPOSE 5000 5151

# Use tini so Ctrl-C in `docker run -it` actually kills the REPL.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["dulus"]
