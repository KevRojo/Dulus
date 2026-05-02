"""
Auto Context Loader for Falcon
Automatically loads relevant context from MemPalace at the start of each conversation
"""

import json
import sys
import os
from typing import Dict, Any

def load_initial_context() -> Dict[str, Any]:
    """Load initial context from MemPalace for the conversation."""
    try:
        # Import the mempalace directly
        from mempalace.palace import get_collection
        
        # Get palace path from default location
        palace_path = os.path.expanduser("~/.mempalace/palace")
        
        if not os.path.exists(palace_path):
            return {
                "status": "error",
                "error": "Palace path not found",
                "message": f"Palace path {palace_path} does not exist"
            }
            
        collection = get_collection(palace_path)
        
        # Get recent items for context (limit to 15)
        results = collection.get(
            limit=15,
            include=["documents", "metadatas"]
        )
        
        context_items = []
        if results and 'documents' in results:
            for i, doc in enumerate(results['documents']):
                item = {
                    "content": doc[:300] + "..." if len(doc) > 300 else doc
                }
                if 'metadatas' in results and i < len(results['metadatas']):
                    meta = results['metadatas'][i]
                    if meta:
                        item.update({k: v for k, v in meta.items() 
                                   if k in ['wing', 'room', 'timestamp']})
                context_items.append(item)
        
        return {
            "status": "success",
            "context_items": context_items,
            "message": f"Loaded {len(context_items)} context items from MemPalace"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to load context from MemPalace"
        }

def format_context_for_display(context_result: Dict[str, Any]) -> str:
    """Format the context data for display to the user."""
    if context_result["status"] == "error":
        return f"Context loading failed: {context_result['message']} - {context_result['error']}"
    
    items = context_result["context_items"]
    if not items:
        return "No previous context found in memory."
    
    formatted = ["MemPalace Context Loaded:"]
    for item in items[:5]:  # Show first 5 items
        content_preview = item.get("content", "")[:100] + "..." if len(item.get("content", "")) > 100 else item.get("content", "")
        wing = item.get("wing", "unknown")
        room = item.get("room", "general")
        formatted.append(f"  * [{wing}/{room}] {content_preview}")
    
    if len(items) > 5:
        formatted.append(f"  ... and {len(items) - 5} more items")
    
    return "\\n".join(formatted)  # Escape newlines for compatibility

# Auto-execute on import
if __name__ == "__main__":
    context = load_initial_context()
    # Use sys.stdout.write to avoid encoding issues
    sys.stdout.write(format_context_for_display(context))