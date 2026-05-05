"""Dulus — Backend + Smart Context + Plugins + Personas + MemPalace."""
__version__ = "0.2.0"

# Public API exports
from backend.context import build_context, build_smart_context, get_compact_context
from backend.tasks import create_task, load_tasks, update_task
from backend.personas import (
    get_active_persona,
    get_all_personas,
    get_persona,
    get_personas_for_context,
    set_active_persona,
    create_persona,
    update_persona,
    delete_persona,
)
from backend.mempalace_bridge import (
    load_cache,
    refresh_cache,
    get_memories,
    get_mempalace_compact_text,
    get_mempalace_context_block,
)
from backend.compressor import compress, compress_compact_context, summarize_memory
from backend.plugins import load_all_plugins, get_plugin_info, create_example_plugin
from backend.marketplace import load_registry, get_stats
__all__ = [
    "__version__",
    # Context
    "build_context",
    "build_smart_context",
    "get_compact_context",
    # Tasks
    "create_task",
    "load_tasks",
    "update_task",
    # Personas
    "get_active_persona",
    "get_all_personas",
    "get_persona",
    "get_personas_for_context",
    "set_active_persona",
    "create_persona",
    "update_persona",
    "delete_persona",
    # MemPalace
    "load_cache",
    "refresh_cache",
    "get_memories",
    "get_mempalace_compact_text",
    "get_mempalace_context_block",
    # Compressor
    "compress",
    "compress_compact_context",
    "summarize_memory",
    # Plugins
    "load_all_plugins",
    "get_plugin_info",
    "create_example_plugin",
    # Marketplace
    "load_registry",
    "get_stats",
]
