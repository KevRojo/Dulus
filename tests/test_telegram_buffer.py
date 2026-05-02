import sys
import os
sys.path.append(os.getcwd())

import input as falcon_input
from common import sanitize_text

def test_telegram_buffer_pruning():
    """Test that old Telegram messages are pruned from output buffer."""
    # Simulate multiple Telegram messages accumulating
    falcon_input._output_buffer.clear()
    falcon_input.append_output("  📩 Telegram: Hello 1")
    falcon_input.append_output("Some model output")
    falcon_input.append_output("  📩 Telegram: Hello 2")
    falcon_input.append_output("More model output")
    falcon_input.append_output("  📩 Telegram: Hello 3")
    
    # Before pruning: 5 lines
    assert len(falcon_input._output_buffer) == 5
    
    # Simulate read_line_split pruning (keep only last Telegram)
    # NOTE: we match on ASCII suffix because emojis get corrupted on Windows
    _tg_markers = (" Telegram:", " Transcribed:")
    _tg_idx = [i for i, ln in enumerate(falcon_input._output_buffer) if any(m in ln for m in _tg_markers)]
    if len(_tg_idx) > 1:
        _drop = set(_tg_idx[:-1])
        falcon_input._output_buffer[:] = [ln for i, ln in enumerate(falcon_input._output_buffer) if i not in _drop]
    
    # After pruning: 3 lines (Hello 1 and 2 removed, keep Hello 3)
    assert len(falcon_input._output_buffer) == 3
    assert "Hello 3" in falcon_input._output_buffer[-1]
    assert "Some model output" in falcon_input._output_buffer[0]
    assert "More model output" in falcon_input._output_buffer[1]
    
    print("Telegram buffer pruning test PASSED")


def test_sanitize_text():
    """Test that sanitize_text removes surrogates but keeps valid text/emojis."""
    # Normal text
    assert sanitize_text("hello") == "hello"
    
    # Valid emoji (real UTF-8, not surrogates)
    assert sanitize_text("hello 📩 world") == "hello 📩 world"
    
    # Real surrogates (U+D800-U+DFFF) must be stripped
    text_with_surrogates = "hello \ud83d\udcec world"
    result = sanitize_text(text_with_surrogates)
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in result)
    
    # Must not raise when JSON-serialised
    import json
    json.dumps({"text": result})
    
    print("sanitize_text test PASSED")


if __name__ == "__main__":
    test_telegram_buffer_pruning()
    test_sanitize_text()
