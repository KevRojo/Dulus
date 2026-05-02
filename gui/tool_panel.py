"""Side panel showing active tool executions."""
from __future__ import annotations

import customtkinter as ctk

THEME = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "accent": "#00BCD4",
    "text": "#eaeaea",
    "dim": "#888888",
    "tool": "#e94560",
    "success": "#4CAF50",
}

FONT_FAMILY = "Segoe UI"


class ToolPanel(ctk.CTkFrame):
    """Panel that displays running and completed tools."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=THEME["card"], corner_radius=10, **kwargs)

        self.header = ctk.CTkLabel(
            self,
            text="🔧 Tools",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=THEME["accent"],
        )
        self.header.pack(anchor="w", padx=10, pady=(10, 5))

        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent", height=300)
        self.container.pack(fill="both", expand=True, padx=5, pady=5)

        self._tools: dict[str, ctk.CTkFrame] = {}

    def add_tool(self, name: str, status: str = "running") -> None:
        if name in self._tools:
            return

        frame = ctk.CTkFrame(self.container, fg_color=THEME["bg"], corner_radius=8)
        frame.pack(fill="x", padx=5, pady=3)

        color = THEME["tool"] if status == "running" else THEME["success"]
        symbol = "⚙" if status == "running" else "✓"

        lbl = ctk.CTkLabel(
            frame,
            text=f"{symbol} {name}",
            font=(FONT_FAMILY, 11),
            text_color=color,
            anchor="w",
        )
        lbl.pack(fill="x", padx=8, pady=5)

        self._tools[name] = frame

    def update_tool(self, name: str, status: str = "done", result: str = "") -> None:
        frame = self._tools.get(name)
        if frame is None:
            return

        for child in frame.winfo_children():
            child.destroy()

        color = THEME["success"] if status == "done" else THEME["tool"]
        symbol = "✓" if status == "done" else "⚙"

        lbl = ctk.CTkLabel(
            frame,
            text=f"{symbol} {name}",
            font=(FONT_FAMILY, 11),
            text_color=color,
            anchor="w",
        )
        lbl.pack(fill="x", padx=8, pady=(5, 2))

        if result:
            preview = result[:120] + "..." if len(result) > 120 else result
            res_lbl = ctk.CTkLabel(
                frame,
                text=preview,
                font=("Consolas", 10),
                text_color=THEME["dim"],
                anchor="w",
                wraplength=180,
            )
            res_lbl.pack(fill="x", padx=8, pady=(0, 5))

    def clear_tools(self) -> None:
        for frame in self._tools.values():
            frame.destroy()
        self._tools.clear()
