"""Trackma GTK4/libadwaita frontend."""

from __future__ import annotations

import sys


def main() -> int:
    """Entry point for the GTK4 frontend."""
    from trackma.ui.gtk4.application import TrackmaApplication

    app = TrackmaApplication()
    return app.run(sys.argv)
