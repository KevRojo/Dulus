"""Falcon GUI package — professional desktop interface."""
from gui.main_window import FalconMainWindow
from gui.chat_widget import ChatWidget
from gui.agent_bridge import FalconBridge
from gui.sidebar import FalconSidebar
from gui.settings_dialog import SettingsDialog
from gui.tool_panel import ToolPanel
from gui.tasks_view import TasksView

__all__ = [
    "FalconMainWindow",
    "ChatWidget",
    "FalconBridge",
    "FalconSidebar",
    "SettingsDialog",
    "ToolPanel",
    "TasksView",
]
