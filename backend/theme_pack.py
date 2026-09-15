"""Theme pack shim (ex-gui) — thin wrapper over backend.themes."""
from __future__ import annotations

def list_themes() -> dict:
    from backend.themes import THEMES
    return {name: f"{t['accent']} accent, {t['bg']} bg" for name, t in THEMES.items()}

def generate_css_variables(theme_name: str) -> str:
    from backend.themes import THEMES
    t = THEMES.get(theme_name)
    if not t:
        return ""
    css = ":root{\n"
    css += f"  --bg:{t['bg']};\n"
    css += f"  --bg2:{t['card']};\n"
    css += f"  --bg3:{t.get('code_bg', t['card'])};\n"
    css += f"  --ink:{t['text']};\n"
    css += f"  --dim:{t['dim']};\n"
    css += f"  --dim2:{t['border']};\n"
    css += f"  --accent:{t['accent']};\n"
    css += f"  --accent2:{t.get('accent_hover', t['accent'])};\n"
    css += f"  --green:{t.get('success', '#4caf50')};\n"
    css += f"  --red:{t.get('error', '#ff6b6b')};\n"
    css += f"  --yellow:{t.get('warning', '#FFC107')};\n"
    css += f"  --blue:{t['accent']};\n"
    css += "}\n"
    return css
