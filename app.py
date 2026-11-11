import sys

from ui.window import AgroCommish


def main():
    AgroCommish(demo="--demo" in sys.argv).mainloop()


if __name__ == "__main__":
    main()
