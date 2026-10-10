"""The Jubako desktop window (GTK4 + Libadwaita)."""

__all__ = ["main"]


def main(argv=None):
    from .app import main as _main

    return _main(argv)
