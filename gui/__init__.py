"""Dulus GUI package — professional desktop interface."""
from gui.main_window import DulusMainWindow
from gui.chat_widget import ChatWidget
from gui.agent_bridge import DulusBridge
from gui.sidebar import DulusSidebar
from gui.settings_dialog import SettingsDialog
from gui.tool_panel import ToolPanel
from gui.tasks_view import TasksView

__all__ = [
    "DulusMainWindow",
    "ChatWidget",
    "DulusBridge",
    "DulusSidebar",
    "SettingsDialog",
    "ToolPanel",
    "TasksView",
]
