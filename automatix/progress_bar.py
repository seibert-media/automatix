import shutil
from time import time

from tqdm import tqdm


class Cursor:
    @staticmethod
    def _print(code: str):
        print(code, end='', flush=True)

    @staticmethod
    def save():
        Cursor._print("\033[s")

    @staticmethod
    def restore():
        Cursor._print("\033[u")

    @staticmethod
    def move_up(lines: int = 1):
        Cursor._print(f"\033[{lines}A")

    @staticmethod
    def move_to(row: int, col: int):
        Cursor._print(f"\033[{row};{col}f")

    @staticmethod
    def clear_line():
        Cursor._print("\033[2K")

    @staticmethod
    def set_scroll_region(top: int, bottom: int):
        # ANSI standard is 1-based.
        # Original code used 0, which most terminals treat as 1.
        Cursor._print(f"\033[{top};{bottom}r")


class TqdmProgressBar:
    def __init__(self):
        self.start_time = 0

    def setup(self):
        self.start_time = time()
        cols, lines = shutil.get_terminal_size()

        # We reserve the last line for the bar AND one empty line above it.
        # Scroll region should be from line 1 to lines-2.
        scroll_region_bottom = lines - 2

        # Scroll down a bit to avoid visual glitch when the screen area shrinks by one row
        print("\n\n", end='', flush=True)

        Cursor.save()

        # Set scroll region (this will place the cursor in the top left usually)
        # Note: Original code used 0;...r. ANSI standard is 1-based.
        # Most terminals treat 0 as 1. We stick to the original logic to be safe.
        Cursor.set_scroll_region(0, scroll_region_bottom)

        Cursor.restore()

        # Move cursor up twice because we scrolled down twice?
        # Actually, CODE_CURSOR_IN_SCROLL_AREA moves up 1 line.
        # If we are at the bottom, and region ends at lines-2...
        # Let's just restore and move up to be safe inside the region.
        Cursor.move_up()
        Cursor.move_up()

        # Draw initial empty progress bar
        self.draw(0)

    def draw(self, percentage: int | None, color: str = None):
        if percentage is None:
            return

        cols, lines = shutil.get_terminal_size()

        Cursor.save()

        # Move cursor position to last row
        Cursor.move_to(lines, 0)

        # Clear progress bar line
        Cursor.clear_line()

        # Calculate stats for tqdm
        elapsed = time() - self.start_time

        # tqdm.format_meter generates the progress bar string
        # We subtract 1 from cols to avoid accidental wrapping at the very last character
        bar_str = tqdm.format_meter(
            n=percentage,
            total=100,
            elapsed=elapsed,
            ncols=cols - 1,
            unit='pct',
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            colour=color
        )

        print(bar_str, end='', flush=True)

        # Also clear the line above the bar (the separator line) to keep it clean
        # Move cursor up one line
        Cursor.move_to(lines - 1, 0)
        Cursor.clear_line()

        Cursor.restore()

    def block(self, percentage: int | None):
        self.draw(percentage, color='yellow')

    def destroy(self):
        cols, lines = shutil.get_terminal_size()

        Cursor.save()

        # Reset scroll region (0 to lines -> full screen)
        Cursor.set_scroll_region(0, lines)

        Cursor.restore()
        Cursor.move_up()
        Cursor.move_up()

        # We are done so clear the scroll bar and the separator line
        Cursor.save()

        # Clear bar line
        Cursor.move_to(lines, 0)
        Cursor.clear_line()

        # Clear separator line
        Cursor.move_to(lines - 1, 0)
        Cursor.clear_line()

        Cursor.restore()

        # Scroll down a bit to avoid visual glitch when the screen area grows by one row
        print("\n\n\n", end='', flush=True)
