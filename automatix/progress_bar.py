import curses
import shutil
from time import time
from tqdm import tqdm

# ANSI Codes
CODE_SAVE_CURSOR = "\033[s"
CODE_RESTORE_CURSOR = "\033[u"
CODE_CURSOR_IN_SCROLL_AREA = "\033[1A"


def _print_control_code(code):
    print(code, end='', flush=True)


class TqdmProgressBar:
    def __init__(self):
        self.start_time = 0

    def setup(self):
        # Setup curses support (to get information about the terminal we are running in)
        # This was in the original code and might be necessary for some terminals
        try:
            curses.setupterm()
        except Exception:
            pass

        # Setup start time for ETA calculation
        self.start_time = time()

        # Get terminal size
        cols, lines = shutil.get_terminal_size()

        # We reserve the last line for the bar AND one empty line above it.
        # Scroll region should be from line 1 to lines-2.
        scroll_region_bottom = lines - 2

        # Scroll down a bit to avoid visual glitch when the screen area shrinks by one row
        _print_control_code("\n\n")

        # Save cursor
        _print_control_code(CODE_SAVE_CURSOR)

        # Set scroll region (this will place the cursor in the top left usually)
        # ANSI: ESC [ {top} ; {bottom} r
        # Note: Original code used 0;...r. ANSI standard is 1-based. 
        # Most terminals treat 0 as 1. We stick to the original logic to be safe.
        _print_control_code(f"\033[0;{scroll_region_bottom}r")

        # Restore cursor but ensure its inside the scrolling area
        _print_control_code(CODE_RESTORE_CURSOR)
        # Move cursor up twice because we scrolled down twice? 
        # Actually, CODE_CURSOR_IN_SCROLL_AREA moves up 1 line.
        # If we are at the bottom, and region ends at lines-2...
        # Let's just restore and move up to be safe inside the region.
        _print_control_code(CODE_CURSOR_IN_SCROLL_AREA)
        _print_control_code(CODE_CURSOR_IN_SCROLL_AREA)

        # Draw initial empty progress bar
        self.draw(0)

    def draw(self, percentage: int | None, color: str = None):
        if percentage is None:
            return

        cols, lines = shutil.get_terminal_size()

        # Save cursor
        _print_control_code(CODE_SAVE_CURSOR)

        # Move cursor position to last row
        _print_control_code(f"\033[{lines};0f")

        # Clear progress bar line
        _print_control_code("\033[2K")

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
        _print_control_code(f"\033[{lines-1};0f")
        _print_control_code("\033[2K")
        
        # Draw a separator line? Or just empty?
        # Let's draw a thin separator line using unicode box drawing characters if you like?
        # Or just keep it empty. Empty is cleaner.
        # print("─" * (cols-1), end='', flush=True) 

        # Restore cursor position
        _print_control_code(CODE_RESTORE_CURSOR)

    def block(self, percentage: int | None):
        self.draw(percentage, color='yellow')

    def destroy(self):
        cols, lines = shutil.get_terminal_size()

        # Save cursor
        _print_control_code(CODE_SAVE_CURSOR)

        # Reset scroll region (0 to lines -> full screen)
        _print_control_code(f"\033[0;{lines}r")

        # Restore cursor
        _print_control_code(CODE_RESTORE_CURSOR)
        _print_control_code(CODE_CURSOR_IN_SCROLL_AREA)
        _print_control_code(CODE_CURSOR_IN_SCROLL_AREA)

        # We are done so clear the scroll bar and the separator line
        _print_control_code(CODE_SAVE_CURSOR)
        
        # Clear bar line
        _print_control_code(f"\033[{lines};0f")
        _print_control_code("\033[2K")
        
        # Clear separator line
        _print_control_code(f"\033[{lines-1};0f")
        _print_control_code("\033[2K")
        
        _print_control_code(CODE_RESTORE_CURSOR)

        # Scroll down a bit to avoid visual glitch when the screen area grows by one row
        _print_control_code("\n\n\n")
