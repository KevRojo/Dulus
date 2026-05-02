"""
Startup Context Loader for Falcon
This module automatically loads MemPalace context when Falcon starts
"""

import context_integration

def load_startup_context():
    """Load context at Falcon startup and display summary."""
    print("Loading MemPalace context...")
    
    # Initialize context
    result = context_integration.initialize_conversation_context()
    
    if result["status"] == "success":
        print(f"Context loaded successfully: {result['message']}")
        print("\\nContext Summary:")
        print(context_integration.get_current_context_summary())
    else:
        print(f"Context loading failed: {result['message']}")
        print(f"Error: {result['error']}")

# Auto-execute when imported
if __name__ != "__main__":  # When imported as module
    load_startup_context()
else:  # When run directly
    load_startup_context()