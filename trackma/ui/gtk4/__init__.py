"""Trackma GTK4/libadwaita frontend."""

from __future__ import annotations

import logging
import sys


def main() -> int:
    """Entry point for the GTK4 frontend."""
    import os

    if os.environ.get("TRACKMA_DEBUG"):
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")

    from trackma.ui.gtk4.application import TrackmaApplication

    app = TrackmaApplication()
    return app.run(sys.argv)
