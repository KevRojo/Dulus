"""
Context Integration Module for Falcon
Integrates MemPalace context loading into Falcon's conversation flow
"""

import json
import os
from typing import Dict, Any, List

class ContextManager:
    def __init__(self):
        self.context_items: List[Dict[str, Any]] = []
        self.is_loaded = False
    
    def load_context(self) -> Dict[str, Any]:
        """Load context from MemPalace and store it for use during the conversation."""
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
            
            # Get recent items for context (limit to 10)
            results = collection.get(
                limit=10,
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
            
            self.context_items = context_items
            self.is_loaded = True
            
            return {
                "status": "success",
                "items_loaded": len(context_items),
                "message": f"Loaded {len(context_items)} context items"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to load context"
            }
    
    def get_context_summary(self) -> str:
        """Get a summary of loaded context for display."""
        if not self.is_loaded:
            return "Context not yet loaded."
        
        if not self.context_items:
            return "No context items found."
        
        summary = ["Recent Context Summary:"]
        for i, item in enumerate(self.context_items[:3]):  # Show first 3 items
            content = item.get("content", "")[:150] + "..." if len(item.get("content", "")) > 150 else item.get("content", "")
            wing = item.get("wing", "unknown")
            room = item.get("room", "general")
            summary.append(f"  [{wing}/{room}] {content}")
        
        if len(self.context_items) > 3:
            summary.append(f"  ... and {len(self.context_items) - 3} more items")
        
        return "\n".join(summary)
    
    def search_context(self, query: str) -> List[Dict[str, Any]]:
        """Search through loaded context for relevant items."""
        if not self.is_loaded or not self.context_items:
            return []
        
        # Simple keyword search in content
        relevant_items = []
        query_lower = query.lower()
        
        for item in self.context_items:
            content = item.get("content", "").lower()
            if query_lower in content:
                relevant_items.append(item)
        
        return relevant_items

# Global context manager instance
context_manager = ContextManager()

def initialize_conversation_context() -> Dict[str, Any]:
    """Initialize context at the start of a conversation."""
    return context_manager.load_context()

def get_current_context_summary() -> str:
    """Get current context summary for display."""
    return context_manager.get_context_summary()

def search_current_context(query: str) -> List[Dict[str, Any]]:
    """Search current context for relevant information."""
    return context_manager.search_context(query)

# Auto-initialize context when module is imported
init_result = initialize_conversation_context()