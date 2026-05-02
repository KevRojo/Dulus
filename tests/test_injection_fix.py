
import sys
import os
# Add current directory to path so we can import providers
sys.path.append(os.getcwd())

from providers import _consolidate_web_history

def test_consolidation():
    # Scenario 1: First turn (no assistant message)
    messages = [
        {"role": "user", "content": "ls -la"}
    ]
    manifest = "[TOOL MANIFEST]"
    prompt = _consolidate_web_history(messages, manifest)
    print("Scenario 1 Prompt:\n", prompt)
    assert "[TOOL MANIFEST]" in prompt
    assert "--- [USER] ---" in prompt
    assert "ls -la" in prompt

    # Scenario 2: After a tool call
    messages = [
        {"role": "user", "content": "ls"},
        {"role": "assistant", "content": "", "tool_calls": [{"name": "Bash", "input": {"command": "ls"}}]},
        {"role": "tool", "name": "Bash", "content": "file1.txt\nfile2.txt"}
    ]
    prompt = _consolidate_web_history(messages, manifest)
    print("\nScenario 2 Prompt:\n", prompt)
    assert "--- [Tool Result: Bash] ---" in prompt
    assert "file1.txt" in prompt
    # It should NOT include the first user message if it was before the last assistant turn
    # Wait, in Scenario 2, the tool call is AFTER the assistant.
    # The last assistant message was at index 1.
    # So it should only include index 2 (the tool result).
    # This is correct because the web model already saw the user message and its own tool call.
    # It just needs the RESULT of the tool.

    # Scenario 3: Multiple tool results
    messages = [
        {"role": "user", "content": "check files"},
        {"role": "assistant", "content": "Checking...", "tool_calls": [{"id": "1", "name": "ls"}, {"id": "2", "name": "env"}]},
        {"role": "tool", "name": "ls", "content": "result 1"},
        {"role": "tool", "name": "env", "content": "result 2"}
    ]
    prompt = _consolidate_web_history(messages, manifest)
    print("\nScenario 3 Prompt:\n", prompt)
    assert "--- [Tool Result: ls] ---" in prompt
    assert "result 1" in prompt
    assert "--- [Tool Result: env] ---" in prompt
    assert "result 2" in prompt

    # Scenario 4: Background notification
    messages = [
        {"role": "assistant", "content": "Running job..."},
        {"role": "user", "content": "[Background Event Triggered]\nJob 123 finished."}
    ]
    prompt = _consolidate_web_history(messages, manifest)
    print("\nScenario 4 Prompt:\n", prompt)
    assert "--- [USER] ---" in prompt
    assert "[Background Event Triggered]" in prompt

    print("\nALL CONSOLIDATION TESTS PASSED")

if __name__ == "__main__":
    test_consolidation()
