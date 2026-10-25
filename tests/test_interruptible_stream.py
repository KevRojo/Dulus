"""Tests for agent._interruptible_stream (the Ctrl+C-safe provider pump).

An interrupted turn used to leave the producer thread blocked forever on a
full queue, holding the provider's HTTP stream open — one leaked thread and
one leaked connection per Ctrl+C.
"""
import threading

import pytest

from agent import _interruptible_stream


def _endless_stream(closed: threading.Event):
    """A provider stream that never ends on its own, like a long reply."""
    try:
        i = 0
        while True:
            i += 1
            yield i
    finally:
        closed.set()   # where a provider SDK releases its HTTP response


def test_yields_every_event_in_order():
    assert list(_interruptible_stream(iter(range(200)))) == list(range(200))


def test_producer_exception_reaches_consumer():
    def boom():
        yield 1
        raise ValueError("stream broke")

    got = []
    with pytest.raises(ValueError, match="stream broke"):
        for ev in _interruptible_stream(boom()):
            got.append(ev)
    assert got == [1]


def test_early_exit_closes_provider_stream():
    closed = threading.Event()
    pump = _interruptible_stream(_endless_stream(closed))
    for n, _ in enumerate(pump):
        if n == 3:
            break
    pump.close()
    assert closed.wait(timeout=5), "provider stream left open after consumer stopped"


def test_keyboard_interrupt_releases_producer():
    closed = threading.Event()
    pump = _interruptible_stream(_endless_stream(closed))
    next(pump)
    with pytest.raises(KeyboardInterrupt):
        pump.throw(KeyboardInterrupt)
    assert closed.wait(timeout=5), "producer still running after Ctrl+C"
