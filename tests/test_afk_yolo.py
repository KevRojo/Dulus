"""Tests for AFK Mode and YOLO Mode."""
import sys
from pathlib import Path

# Ensure project root is on path for dulus.* imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from dulus_tools.afk_mode import AFKMode
from dulus_tools.yolo_mode import YOLOMode


# ── AFK Mode Tests ───────────────────────────────────────────────────────────


class TestAFKMode:
    """Test suite for AFKMode."""

    def test_default_state_is_disabled(self):
        """AFK mode should be disabled by default."""
        afk = AFKMode()
        assert afk.enabled is False

    def test_enable_sets_state(self):
        """enable() should set the state to True."""
        afk = AFKMode()
        afk.enable()
        assert afk.enabled is True

    def test_disable_sets_state(self):
        """disable() should set the state to False."""
        afk = AFKMode()
        afk.enable()
        afk.disable()
        assert afk.enabled is False

    def test_toggle_returns_new_state(self):
        """toggle() should return the new state."""
        afk = AFKMode()
        result = afk.toggle()
        assert result is True
        assert afk.enabled is True

    def test_toggle_twice_returns_false(self):
        """Toggling twice should return False."""
        afk = AFKMode()
        afk.toggle()
        result = afk.toggle()
        assert result is False
        assert afk.enabled is False

    def test_repr_shows_state(self):
        """__repr__ should include the enabled state."""
        afk = AFKMode()
        assert "enabled=False" in repr(afk)
        afk.enable()
        assert "enabled=True" in repr(afk)

    def test_dataclass_field_is_hidden(self):
        """The _enabled field should not appear in repr from dataclass."""
        afk = AFKMode()
        # The field has repr=False, so it shouldn't show _enabled directly
        r = repr(afk)
        assert "_enabled" not in r

    def test_multiple_instances_are_independent(self):
        """Different instances should have independent state."""
        afk1 = AFKMode()
        afk2 = AFKMode()
        afk1.enable()
        assert afk1.enabled is True
        assert afk2.enabled is False


# ── YOLO Mode Tests ──────────────────────────────────────────────────────────


class TestYOLOMode:
    """Test suite for YOLOMode."""

    def test_default_state_is_disabled(self):
        """YOLO mode should be disabled by default."""
        yolo = YOLOMode()
        assert yolo.enabled is False

    def test_enable_sets_state(self):
        """enable() should set the state to True."""
        yolo = YOLOMode()
        yolo.enable()
        assert yolo.enabled is True

    def test_disable_sets_state(self):
        """disable() should set the state to False."""
        yolo = YOLOMode()
        yolo.enable()
        yolo.disable()
        assert yolo.enabled is False

    def test_toggle_returns_new_state(self):
        """toggle() should return the new state."""
        yolo = YOLOMode()
        result = yolo.toggle()
        assert result is True
        assert yolo.enabled is True

    def test_toggle_twice_returns_false(self):
        """Toggling twice should return False."""
        yolo = YOLOMode()
        yolo.toggle()
        result = yolo.toggle()
        assert result is False
        assert yolo.enabled is False

    def test_repr_shows_state(self):
        """__repr__ should include the enabled state."""
        yolo = YOLOMode()
        assert "enabled=False" in repr(yolo)
        yolo.enable()
        assert "enabled=True" in repr(yolo)

    def test_dataclass_field_is_hidden(self):
        """The _enabled field should not appear in repr from dataclass."""
        yolo = YOLOMode()
        r = repr(yolo)
        assert "_enabled" not in r

    def test_multiple_instances_are_independent(self):
        """Different instances should have independent state."""
        yolo1 = YOLOMode()
        yolo2 = YOLOMode()
        yolo1.enable()
        assert yolo1.enabled is True
        assert yolo2.enabled is False


# ── Cross-Feature Tests ──────────────────────────────────────────────────────


class TestAFKYOLOIndependence:
    """Test that AFK and YOLO modes are independent."""

    def test_modes_are_independent(self):
        """AFK and YOLO can be enabled/disabled independently."""
        afk = AFKMode()
        yolo = YOLOMode()

        # Both off by default
        assert afk.enabled is False
        assert yolo.enabled is False

        # Enable AFK only
        afk.enable()
        assert afk.enabled is True
        assert yolo.enabled is False

        # Enable YOLO too
        yolo.enable()
        assert afk.enabled is True
        assert yolo.enabled is True

        # Disable AFK, YOLO stays on
        afk.disable()
        assert afk.enabled is False
        assert yolo.enabled is True

    def test_all_combinations(self):
        """Test all four combinations of AFK/YOLO states."""
        for afk_state in [False, True]:
            for yolo_state in [False, True]:
                afk = AFKMode()
                yolo = YOLOMode()
                if afk_state:
                    afk.enable()
                if yolo_state:
                    yolo.enable()
                assert afk.enabled is afk_state
                assert yolo.enabled is yolo_state
