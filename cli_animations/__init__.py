"""CLI animations for Dulus — drop-in terminal visuals.

Works as:
  * installed package:  ``from cli_animations import print_banner, spinner``
  * local folder:       ``python demo.py`` (uses the local package path)

Cross-platform (macOS / Linux / Windows). Zero third-party deps.
"""
from __future__ import annotations

from .ansi import (
    C,
    GLYPH,
    animations_enabled,
    clr,
    gradient_text,
    pad,
    render_track,
    rgb,
    supports_color,
)
from .banners import (
    BANNERS,
    CIGUA_PALMERA,
    DULUS_BANNER,
    GOD_MODE_BANNER,
    WAVE_DIVIDER,
    box,
    load_ascii_asset,
    print_banner,
    print_box,
    type_banner,
)
from .effects import (
    animate_glitch,
    animate_wave,
    glitch_text,
    matrix_rain,
    pulse_line,
    print_creator_signature,
    typewriter,
    wave_text,
)
from .effort_slider import (
    EFFORT_LEVELS,
    EffortConfig,
    effort_ramp_animation,
    render_effort_bar,
    render_effort_slider,
    select_effort,
)
from .progress import (
    animate_progress_demo,
    indeterminate_bar,
    progress_bar,
    render_bar,
    render_segmented,
    render_steps,
)
from .spinners import (
    CLAUDE_FRAMES,
    CLAUDE_PHRASES,
    DULUS_PHRASES,
    SPINNERS,
    animate_spinner,
    spin_once,
    spinner,
)
from .status import (
    animate_thinking,
    pipeline_status,
    status_bar,
    thinking_line,
    toast,
    tool_status,
)

__version__ = "1.2.1"
__all__ = [
    # ansi
    "C",
    "GLYPH",
    "animations_enabled",
    "clr",
    "gradient_text",
    "pad",
    "render_track",
    "rgb",
    "supports_color",
    # banners
    "BANNERS",
    "CIGUA_PALMERA",
    "DULUS_BANNER",
    "GOD_MODE_BANNER",
    "WAVE_DIVIDER",
    "box",
    "load_ascii_asset",
    "print_banner",
    "print_box",
    "type_banner",
    # effort
    "EFFORT_LEVELS",
    "EffortConfig",
    "effort_ramp_animation",
    "render_effort_bar",
    "render_effort_slider",
    "select_effort",
    # effects
    "animate_glitch",
    "animate_wave",
    "glitch_text",
    "matrix_rain",
    "pulse_line",
    "print_creator_signature",
    "typewriter",
    "wave_text",
    # progress
    "animate_progress_demo",
    "indeterminate_bar",
    "progress_bar",
    "render_bar",
    "render_segmented",
    "render_steps",
    # spinners
    "CLAUDE_FRAMES",
    "CLAUDE_PHRASES",
    "DULUS_PHRASES",
    "SPINNERS",
    "animate_spinner",
    "spin_once",
    "spinner",
    # status
    "animate_thinking",
    "pipeline_status",
    "status_bar",
    "thinking_line",
    "toast",
    "tool_status",
    # meta
    "__version__",
]
