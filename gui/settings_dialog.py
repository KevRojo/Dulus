"""Settings popup for Falcon GUI."""
from __future__ import annotations

import os
from typing import Optional

import customtkinter as ctk

from config import save_config
from gui.themes import list_themes, set_theme

THEME = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "accent": "#00BCD4",
    "accent_hover": "#00acc1",
    "text": "#eaeaea",
    "dim": "#888888",
    "border": "#2a2a4a",
}

FONT_FAMILY = "Segoe UI"


def _build_model_list() -> list[str]:
    """Build list of provider/model strings from PROVIDERS registry."""
    try:
        from providers import PROVIDERS
        models: list[str] = []
        for pname, pmeta in PROVIDERS.items():
            for m in pmeta.get("models", []):
                models.append(f"{pname}/{m}")
        return sorted(models) if models else ["kimi/kimi-k2.5"]
    except Exception:
        return [
            "kimi/kimi-k2.5",
            "openai/gpt-4o",
            "anthropic/claude-3-5-sonnet",
            "deepseek/deepseek-chat",
            "ollama/llama3.3",
        ]


class SettingsDialog(ctk.CTkToplevel):
    """Floating settings window."""

    def __init__(self, master, config: dict) -> None:
        super().__init__(master)
        self.config = config
        self.title("Settings")
        self.geometry("480x520")
        self.configure(fg_color=THEME["bg"])
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        # Header
        ctk.CTkLabel(
            self,
            text="⚙ Settings",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=THEME["accent"],
        ).pack(pady=(20, 15))

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", width=440)
        scroll.pack(fill="both", expand=True, padx=20, pady=5)

        # Model
        ctk.CTkLabel(scroll, text="Model", font=(FONT_FAMILY, 12, "bold"), text_color=THEME["text"]).pack(anchor="w", pady=(10, 2))
        self.model_var = ctk.StringVar(value=config.get("model", "kimi/kimi-k2.5"))
        models = _build_model_list()
        ctk.CTkOptionMenu(scroll, values=models, variable=self.model_var, fg_color=THEME["card"]).pack(fill="x", pady=2)

        # Thinking
        ctk.CTkLabel(scroll, text="Thinking Level", font=(FONT_FAMILY, 12, "bold"), text_color=THEME["text"]).pack(anchor="w", pady=(15, 2))
        think_val = {0: "off", 1: "min", 2: "med", 3: "max", 4: "raw"}.get(config.get("thinking", 0), "off")
        self.think_var = ctk.StringVar(value=think_val)
        ctk.CTkOptionMenu(scroll, values=["off", "min", "med", "max", "raw"], variable=self.think_var, fg_color=THEME["card"]).pack(fill="x", pady=2)

        # Verbose
        ctk.CTkLabel(scroll, text="Verbose Mode", font=(FONT_FAMILY, 12, "bold"), text_color=THEME["text"]).pack(anchor="w", pady=(15, 2))
        self.verbose_var = ctk.BooleanVar(value=config.get("verbose", False))
        ctk.CTkSwitch(scroll, text="Enable verbose output", variable=self.verbose_var, progress_color=THEME["accent"]).pack(anchor="w", pady=2)

        # Appearance mode
        ctk.CTkLabel(scroll, text="Appearance", font=(FONT_FAMILY, 12, "bold"), text_color=THEME["text"]).pack(anchor="w", pady=(15, 2))
        self.appearance_var = ctk.StringVar(value=config.get("appearance", "Dark"))
        ctk.CTkOptionMenu(scroll, values=["Dark", "Light", "System"], variable=self.appearance_var, fg_color=THEME["card"]).pack(fill="x", pady=2)

        # Color theme
        ctk.CTkLabel(scroll, text="Color Theme", font=(FONT_FAMILY, 12, "bold"), text_color=THEME["text"]).pack(anchor="w", pady=(15, 2))
        self.theme_var = ctk.StringVar(value=config.get("theme", "midnight"))
        ctk.CTkOptionMenu(scroll, values=list_themes(), variable=self.theme_var, fg_color=THEME["card"]).pack(fill="x", pady=2)

        # API Key (masked)
        ctk.CTkLabel(scroll, text="API Key (active provider)", font=(FONT_FAMILY, 12, "bold"), text_color=THEME["text"]).pack(anchor="w", pady=(15, 2))
        self.api_var = ctk.StringVar()
        ctk.CTkEntry(scroll, textvariable=self.api_var, show="●", fg_color=THEME["card"], text_color=THEME["text"]).pack(fill="x", pady=2)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color=THEME["border"],
            hover_color="red",
            command=self.destroy,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Save",
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            command=self._save,
        ).pack(side="right", padx=5)

    def _save(self) -> None:
        self.config["model"] = self.model_var.get()
        think_map = {"off": 0, "min": 1, "med": 2, "max": 3, "raw": 4}
        self.config["thinking"] = think_map.get(self.think_var.get(), 0)
        self.config["verbose"] = self.verbose_var.get()
        self.config["appearance"] = self.appearance_var.get()
        self.config["theme"] = self.theme_var.get()
        ctk.set_appearance_mode(self.appearance_var.get())
        # Notify parent to apply color theme
        if hasattr(self.master, "apply_theme"):
            self.master.apply_theme(self.theme_var.get())
        key = self.api_var.get().strip()
        if key:
            pname = self.config.get("model", "").split("/")[0]
            if pname:
                self.config[f"{pname}_api_key"] = key
        try:
            save_config(self.config)
        except Exception:
            pass
        self.destroy()
