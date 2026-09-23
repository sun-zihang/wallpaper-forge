from core.version import __version__


def main() -> None:
    from gui.main_window import run

    run(__version__)


if __name__ == "__main__":
    main()
