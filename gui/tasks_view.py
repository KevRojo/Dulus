"""Falcon Tasks View — professional Kanban-style task board v2.

Reads tasks from .falcon-context/tasks.json and displays them in a
three-column layout: Pending | In Progress | Completed.

v2 improvements:
- Filter by owner (agent) and phase (week)
- Priority badges (CRITICAL/HIGH/MEDIUM/LOW)
- Agent color coding
- Auto-refresh via file polling
- Phase grouping separators
- Owner summary stats
"""
from __future__ import annotations

import json
import datetime
import os
import threading
from pathlib import Path
from typing import Dict, List, Callable

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    import tkinter as ctk
    HAS_CTK = False

from gui.themes import get_theme

# ── Theme constants ───────────────────────────────────────────────────────────
BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
ACCENT_COLOR = "#00BCD4"
ACCENT_HOVER = "#00acc1"
MAGENTA_ACCENT = "#e91e63"
TEXT_COLOR = "#eaeaea"
TEXT_DIM = "#a0a0a0"
BORDER_COLOR = "#2a2a4a"
SUCCESS_COLOR = "#4caf50"
WARNING_COLOR = "#FFC107"
ERROR_COLOR = "#F44336"
PENDING_COLOR = "#FF9800"

# ── Agent colors ──────────────────────────────────────────────────────────────
AGENT_COLORS: Dict[str, str] = {
    "kimi-code": "#00BCD4",
    "kimi-code2": "#e91e63",
    "kimi-code3": "#4caf50",
    "": "#9E9E9E",
}

# ── Priority colors ───────────────────────────────────────────────────────────
PRIORITY_COLORS: Dict[str, str] = {
    "CRITICAL": "#F44336",
    "HIGH": "#FF5722",
    "MEDIUM": "#FF9800",
    "LOW": "#9E9E9E",
}

FONT_FAMILY = "Segoe UI"
FONT_NORMAL = (FONT_FAMILY, 12)
FONT_BOLD = (FONT_FAMILY, 12, "bold")
FONT_SMALL = (FONT_FAMILY, 10)
FONT_TITLE = (FONT_FAMILY, 16, "bold")

TASKS_PATH = Path(__file__).parent.parent / ".falcon-context" / "tasks.json"
POLL_MS = 5000  # 5 seconds


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso)
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return iso


class TaskCard(ctk.CTkFrame if HAS_CTK else ctk.Frame):
    """A single task card widget with priority, agent color, and phase."""

    def __init__(self, master, task: dict, **kwargs):
        fg = kwargs.pop("fg_color", CARD_COLOR)
        super().__init__(master, fg_color=fg, corner_radius=12, border_width=1,
                         border_color=BORDER_COLOR, **kwargs)
        self.task = task
        self._expanded = False
        self._build()

    def _build(self) -> None:
        t = self.task
        status = t.get("status", "pending")
        subject = t.get("subject", "Sin titulo")
        description = t.get("description", "")
        owner = t.get("owner", "")
        blocked_by = t.get("blocked_by", [])
        task_id = t.get("id", "?")
        updated = _fmt_date(t.get("updated_at", ""))
        metadata = t.get("metadata", {})
        phase = metadata.get("phase", "")
        priority = metadata.get("priority", "")

        agent_color = AGENT_COLORS.get(owner, AGENT_COLORS[""])

        # ── Top accent bar (agent color) ─────────────────────────────────────
        accent_bar = ctk.CTkFrame(self, fg_color=agent_color, height=3, corner_radius=0)
        accent_bar.pack(fill="x", padx=0, pady=0)
        accent_bar.pack_propagate(False)

        # ── Header row ───────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))

        id_lbl = ctk.CTkLabel(
            header, text=f"#{task_id}", font=FONT_SMALL, text_color=TEXT_DIM,
        )
        id_lbl.pack(side="left")

        # Priority badge
        if priority and priority in PRIORITY_COLORS:
            pri_frame = ctk.CTkFrame(
                header, fg_color=PRIORITY_COLORS[priority] + "30",
                corner_radius=4, height=18,
            )
            pri_frame.pack(side="right", padx=(4, 0))
            pri_frame.pack_propagate(False)
            ctk.CTkLabel(
                pri_frame, text=priority[:3], font=(FONT_FAMILY, 8, "bold"),
                text_color=PRIORITY_COLORS[priority], width=32,
            ).pack(padx=2)

        # Phase mini-badge
        if phase:
            short_phase = phase.replace("Semana ", "W").replace(":", "")
            ph_frame = ctk.CTkFrame(
                header, fg_color=BORDER_COLOR, corner_radius=4, height=18,
            )
            ph_frame.pack(side="right", padx=(4, 0))
            ph_frame.pack_propagate(False)
            ctk.CTkLabel(
                ph_frame, text=short_phase, font=(FONT_FAMILY, 8),
                text_color=TEXT_DIM, width=60,
            ).pack(padx=2)

        # ── Title ────────────────────────────────────────────────────────────
        title_lbl = ctk.CTkLabel(
            self, text=subject, font=FONT_BOLD, text_color=TEXT_COLOR,
            wraplength=280, justify="left",
        )
        title_lbl.pack(anchor="w", padx=12, pady=(2, 4))

        # ── Short description ────────────────────────────────────────────────
        short_desc = (description[:120] + "...") if len(description) > 120 else description
        self.desc_lbl = ctk.CTkLabel(
            self, text=short_desc, font=FONT_SMALL, text_color=TEXT_DIM,
            wraplength=280, justify="left",
        )
        self.desc_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        # ── Expand button ────────────────────────────────────────────────────
        if len(description) > 120:
            self.expand_btn = ctk.CTkButton(
                self, text="Ver mas", font=FONT_SMALL, fg_color="transparent",
                hover_color=BORDER_COLOR, text_color=ACCENT_COLOR, height=24, width=80,
                command=self._toggle_expand,
            )
            self.expand_btn.pack(anchor="w", padx=12, pady=(0, 4))
            self.full_desc = description

        # ── Metadata row ─────────────────────────────────────────────────────
        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(4, 10))

        if owner:
            ctk.CTkLabel(
                meta, text=f"@{owner}", font=FONT_SMALL,
                text_color=agent_color,
            ).pack(side="left")

        ctk.CTkLabel(
            meta, text=f"{updated}", font=FONT_SMALL, text_color=TEXT_DIM,
        ).pack(side="right")

        # ── Blocked by badge ─────────────────────────────────────────────────
        if blocked_by:
            block_frame = ctk.CTkFrame(self, fg_color="#3e1a24", corner_radius=6)
            block_frame.pack(fill="x", padx=12, pady=(0, 10))
            ctk.CTkLabel(
                block_frame,
                text=f"Bloqueada por: {', '.join(f'#{b}' for b in blocked_by)}",
                font=FONT_SMALL, text_color=ERROR_COLOR,
            ).pack(padx=8, pady=4)

    def _toggle_expand(self) -> None:
        if self._expanded:
            short = (self.full_desc[:120] + "...") if len(self.full_desc) > 120 else self.full_desc
            self.desc_lbl.configure(text=short)
            self.expand_btn.configure(text="Ver mas")
            self._expanded = False
        else:
            self.desc_lbl.configure(text=self.full_desc)
            self.expand_btn.configure(text="Ver menos")
            self._expanded = True


class TasksView(ctk.CTkFrame if HAS_CTK else ctk.Frame):
    """Professional Kanban task board for Falcon with filters and auto-refresh."""

    def __init__(self, master, tasks_file: Path | str | None = None, **kwargs):
        super().__init__(master, fg_color=BG_COLOR, corner_radius=0, **kwargs)
        self.tasks_file = Path(tasks_file) if tasks_file else TASKS_PATH
        self._columns: Dict[str, ctk.CTkScrollableFrame] = {}
        self._count_labels: Dict[str, ctk.CTkLabel] = {}
        self._column_headers: Dict[str, ctk.CTkFrame] = {}
        self._column_containers: Dict[str, ctk.CTkFrame] = {}
        self._column_title_labels: Dict[str, ctk.CTkLabel] = {}
        self._owner_filter: str = ""
        self._phase_filter: str = ""
        self._last_mtime: float = 0.0
        self._poll_after_id: str | None = None
        self._build_ui()
        self.refresh()
        self._start_polling()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Top toolbar ──────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        toolbar.grid_propagate(False)

        title = ctk.CTkLabel(
            toolbar, text="Falcon Task Board", font=(FONT_FAMILY, 20, "bold"),
            text_color=ACCENT_COLOR,
        )
        title.pack(side="left")

        # Owner filter
        self.owner_var = ctk.StringVar(value="Todos")
        owner_opts = ["Todos", "kimi-code", "kimi-code2", "kimi-code3", "Sin owner"]
        self._owner_menu = ctk.CTkOptionMenu(
            toolbar, values=owner_opts, variable=self.owner_var,
            font=FONT_SMALL, dropdown_font=FONT_SMALL,
            fg_color=CARD_COLOR, button_color=BORDER_COLOR,
            button_hover_color=ACCENT_HOVER, text_color=TEXT_COLOR,
            width=120, height=30, command=lambda _: self.refresh(),
        )
        self._owner_menu.pack(side="right", padx=(8, 0))
        ctk.CTkLabel(toolbar, text="Agente:", font=FONT_SMALL, text_color=TEXT_DIM).pack(side="right")

        # Phase filter
        self.phase_var = ctk.StringVar(value="Todas")
        phase_opts = [
            "Todas", "Semana 1: Fundamentos", "Semana 2: Entry Points",
            "Semana 3: Plataforma", "Semana 4: Ecosistema", "Legacy",
        ]
        self._phase_menu = ctk.CTkOptionMenu(
            toolbar, values=phase_opts, variable=self.phase_var,
            font=FONT_SMALL, dropdown_font=FONT_SMALL,
            fg_color=CARD_COLOR, button_color=BORDER_COLOR,
            button_hover_color=ACCENT_HOVER, text_color=TEXT_COLOR,
            width=160, height=30, command=lambda _: self.refresh(),
        )
        self._phase_menu.pack(side="right", padx=(8, 0))
        ctk.CTkLabel(toolbar, text="Fase:", font=FONT_SMALL, text_color=TEXT_DIM).pack(side="right")

        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            toolbar, text="Refrescar", font=FONT_BOLD,
            fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER,
            text_color=BG_COLOR, corner_radius=10, height=34,
            command=self.refresh,
        )
        self.refresh_btn.pack(side="right", padx=(16, 0))

        # ── Agent summary bar ────────────────────────────────────────────────
        summary = ctk.CTkFrame(self, fg_color="transparent", height=30)
        summary.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        summary.grid_propagate(False)

        self._agent_labels: Dict[str, ctk.CTkLabel] = {}
        for agent, color in AGENT_COLORS.items():
            if not agent:
                continue
            lbl = ctk.CTkLabel(
                summary, text=f"@{agent}: 0", font=FONT_SMALL,
                text_color=color,
            )
            lbl.pack(side="left", padx=(0, 16))
            self._agent_labels[agent] = lbl

        self._total_label = ctk.CTkLabel(
            summary, text="Total: 0", font=FONT_SMALL, text_color=TEXT_DIM,
        )
        self._total_label.pack(side="right")

        # ── Columns container ────────────────────────────────────────────────
        cols_frame = ctk.CTkFrame(self, fg_color="transparent")
        cols_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        cols_frame.grid_columnconfigure(0, weight=1)
        cols_frame.grid_columnconfigure(1, weight=1)
        cols_frame.grid_columnconfigure(2, weight=1)
        cols_frame.grid_rowconfigure(0, weight=1)

        self._columns_container = cols_frame
        self._create_column(cols_frame, 0, "Pendiente", PENDING_COLOR, "pending")
        self._create_column(cols_frame, 1, "En Progreso", ACCENT_COLOR, "in_progress")
        self._create_column(cols_frame, 2, "Completadas", SUCCESS_COLOR, "completed")

    def _create_column(self, parent, col: int, title: str, color: str, status_key: str) -> None:
        container = ctk.CTkFrame(parent, fg_color=BG_COLOR, corner_radius=0)
        container.grid(row=0, column=col, sticky="nsew", padx=8, pady=0)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)
        self._column_containers[status_key] = container

        hdr = ctk.CTkFrame(container, fg_color=CARD_COLOR, corner_radius=10, height=40)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        hdr.grid_propagate(False)
        self._column_headers[status_key] = hdr

        title_lbl = ctk.CTkLabel(
            hdr, text=title, font=FONT_BOLD, text_color=color,
        )
        title_lbl.pack(side="left", padx=12, pady=4)
        self._column_title_labels[status_key] = title_lbl

        count_lbl = ctk.CTkLabel(
            hdr, text="0", font=FONT_BOLD, text_color=TEXT_DIM,
        )
        count_lbl.pack(side="right", padx=12, pady=4)
        self._count_labels[status_key] = count_lbl

        scroll = ctk.CTkScrollableFrame(
            container, fg_color="transparent", corner_radius=0,
            scrollbar_fg_color=BORDER_COLOR,
            scrollbar_button_color=ACCENT_COLOR,
            scrollbar_button_hover_color=ACCENT_HOVER,
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        self._columns[status_key] = scroll

    def _load_tasks(self) -> List[dict]:
        try:
            data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
            return data.get("tasks", [])
        except Exception:
            return []

    def _matches_filters(self, task: dict) -> bool:
        owner = task.get("owner", "")
        metadata = task.get("metadata", {})
        phase = metadata.get("phase", "")

        owner_filter = self.owner_var.get()
        if owner_filter == "Sin owner":
            if owner:
                return False
        elif owner_filter != "Todos" and owner != owner_filter:
            return False

        phase_filter = self.phase_var.get()
        if phase_filter != "Todas":
            if phase_filter == "Legacy":
                if phase:
                    return False
            elif phase != phase_filter:
                return False

        return True

    def refresh(self) -> None:
        # Clear columns
        for scroll in self._columns.values():
            for widget in scroll.winfo_children():
                widget.destroy()

        tasks = self._load_tasks()
        counts: Dict[str, int] = {"pending": 0, "in_progress": 0, "completed": 0, "cancelled": 0}
        agent_counts: Dict[str, int] = {"kimi-code": 0, "kimi-code2": 0, "kimi-code3": 0}

        # Filter and sort
        filtered = [t for t in tasks if self._matches_filters(t)]
        status_order = {"in_progress": 0, "pending": 1, "completed": 2, "cancelled": 3}
        filtered.sort(key=lambda t: status_order.get(t.get("status", ""), 99))

        for task in filtered:
            status = task.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1

            owner = task.get("owner", "")
            if owner in agent_counts:
                agent_counts[owner] += 1

            col_key = status if status in self._columns else "pending"
            scroll = self._columns.get(col_key)
            if scroll is None:
                continue

            card = TaskCard(scroll, task)
            card.pack(fill="x", pady=(0, 10), padx=2)

        # Update column counters
        for key, lbl in self._count_labels.items():
            lbl.configure(text=str(counts.get(key, 0)))

        # Update agent summary
        for agent, lbl in self._agent_labels.items():
            lbl.configure(text=f"@{agent}: {agent_counts.get(agent, 0)}")

        total = len(filtered)
        done = counts.get("completed", 0)
        pct = int((done / total) * 100) if total else 0
        self._total_label.configure(text=f"Total: {total} | {pct}% done")
        self.refresh_btn.configure(text="Refrescar")

        # Update last mtime
        try:
            self._last_mtime = self.tasks_file.stat().st_mtime
        except Exception:
            pass

    def _check_file_changed(self) -> None:
        try:
            mtime = self.tasks_file.stat().st_mtime
            if mtime != self._last_mtime:
                self.refresh()
        except Exception:
            pass
        self._poll_after_id = self.after(POLL_MS, self._check_file_changed)

    def _start_polling(self) -> None:
        self._check_file_changed()

    def apply_theme(self) -> None:
        """Re-apply current theme colors to persistent widgets."""
        t = get_theme()
        global BG_COLOR, CARD_COLOR, ACCENT_COLOR, ACCENT_HOVER, TEXT_COLOR, TEXT_DIM, BORDER_COLOR
        BG_COLOR = t["bg"]
        CARD_COLOR = t["card"]
        ACCENT_COLOR = t["accent"]
        ACCENT_HOVER = t["accent_hover"]
        TEXT_COLOR = t["text"]
        TEXT_DIM = t["dim"]
        BORDER_COLOR = t["border"]

        self.configure(fg_color=t["bg"])
        self.refresh_btn.configure(
            fg_color=t["accent"], hover_color=t["accent_hover"], text_color=t["bg"]
        )
        self._owner_menu.configure(
            fg_color=t["card"], button_color=t["border"],
            button_hover_color=t["accent_hover"], text_color=t["text"],
        )
        self._phase_menu.configure(
            fg_color=t["card"], button_color=t["border"],
            button_hover_color=t["accent_hover"], text_color=t["text"],
        )
        self._total_label.configure(text_color=t["dim"])
        for lbl in self._agent_labels.values():
            # agent colors are fixed; only dim text updates
            pass
        for lbl in self._count_labels.values():
            lbl.configure(text_color=t["dim"])
        # Column headers & containers
        for key, hdr in self._column_headers.items():
            hdr.configure(fg_color=t["card"])
        for key, container in self._column_containers.items():
            container.configure(fg_color=t["bg"])
        for key, lbl in self._column_title_labels.items():
            # preserve original status color but update if needed
            pass
        # Column scrollbars
        for scroll in self._columns.values():
            scroll.configure(
                fg_color="transparent",
                scrollbar_fg_color=t["border"],
                scrollbar_button_color=t["accent"],
                scrollbar_button_hover_color=t["accent_hover"],
            )
        self.refresh()

    def destroy(self) -> None:
        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
        super().destroy()


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Falcon Tasks v2")
    root.geometry("1200x750")
    root.configure(fg_color=BG_COLOR)
    tv = TasksView(root)
    tv.pack(fill="both", expand=True)
    root.mainloop()
