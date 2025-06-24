"""Main entry point for Aetherius CLI."""

from .cli.main import app


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()