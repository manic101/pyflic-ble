"""Regression tests for the real Flic Twist button-event packet format.

The packets below were captured from a physical Flic Twist while pressing
it over a live session (session MAC already stripped by the client). Each
notification is::

    opcode 0x09 + event_count (u32 LE) + event slots of 7 bytes each

where each 7-byte slot is a 48-bit timestamp (1/32768 s ticks) followed by
a flags byte (bits 0-3 event type, bit 4 was_queued, bit 5
was_queued_last). The previous parser assumed 8-byte slots with a trailing
mode-index byte, so ``len(event_bytes) // 8`` was 0 for the real format
and every press silently decoded to zero events.
"""

import pytest

from pyflic_ble.const import (
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_UP,
    PushTwistMode,
)
from pyflic_ble.handlers.twist import TwistProtocolHandler
from pyflic_ble.protocol import TwistButtonEventNotification

# A real short press (DOWN -> UP -> CLICK) followed by a real
# 2 s hold (DOWN -> HOLD -> UP), captured 2026-11-04. Hex includes opcode.
_REAL_PACKETS = [
    ("09550000004858b09a000001", EVENT_TYPE_DOWN),
    ("09570000002282b09a000004", EVENT_TYPE_UP),  # release, second-flag set
    ("09580000004898b09a000002", EVENT_TYPE_CLICK),
    ("0959000000d126b29a000001", EVENT_TYPE_DOWN),
    ("095a000000e566b29a000003", EVENT_TYPE_HOLD),
    ("095b000000030cb39a000000", EVENT_TYPE_UP),
]


@pytest.mark.parametrize(("hexdata", "expected"), _REAL_PACKETS)
def test_real_twist_button_packet_decodes(hexdata: str, expected: str) -> None:
    """A real 7-byte Twist button event decodes to the mapped HA event."""
    handler = TwistProtocolHandler(PushTwistMode.DEFAULT)

    events, _, _ = handler.handle_notification(bytes.fromhex(hexdata))

    assert [event.event_type for event in events] == [expected]


def test_notification_parses_seven_byte_slots() -> None:
    """The notification yields one event per 7-byte slot."""
    notification = TwistButtonEventNotification.from_bytes(
        bytes.fromhex("550000004858b09a000001")
    )

    assert notification.event_count == 85
    assert len(notification.events) == 1
    event = notification.events[0]
    assert event.event_type == 1  # DOWN
    assert event.was_queued is False  # live press, not a queued replay
    assert event.was_queued_last is False
    assert event.twist_mode_index == 0


def test_short_press_and_hold_sequence_decodes() -> None:
    """The full captured press sequence decodes in order."""
    handler = TwistProtocolHandler(PushTwistMode.DEFAULT)

    decoded: list[str] = []
    for hexdata, _expected in _REAL_PACKETS:
        events, _, _ = handler.handle_notification(bytes.fromhex(hexdata))
        decoded.extend(event.event_type for event in events)

    assert decoded == [expected for _, expected in _REAL_PACKETS]