import curses
import os
from time import time

# ANSI Codes
CODE_SAVE_CURSOR = "\033[s"
CODE_RESTORE_CURSOR = "\033[u"
CODE_CURSOR_IN_SCROLL_AREA = "\033[1A"
COLOR_FG = '\033[30m'
COLOR_BG = '\033[42m'
COLOR_BG_BLOCKED = '\033[43m'
RESTORE_FG = '\033[39m'
RESTORE_BG = '\033[49m'


class TqdmProgressBar:
    def __init__(self):
        self.start_time = 0
        self.current_nr_lines = 0
        self.progress_blocked = False
        self.rate_bar = True

    def _get_current_nr_lines(self):
        stream = os.popen('tput lines')
        output = stream.read()
        return int(output)

    def _get_current_nr_cols(self):
        stream = os.popen('tput cols')
        output = stream.read()
        return int(output)

    def _print_control_code(self, code):
        print(code, end='', flush=True)

    def _tput(self, cmd, *args):
        print(curses.tparm(curses.tigetstr("el")).decode(), end='', flush=True)

    def setup(self, rate_bar=True):
        # Enable/disable right side of progress bar with statistics
        self.rate_bar = rate_bar
        # Setup curses support (to get information about the terminal we are running in)
        curses.setupterm()

        self.current_nr_lines = self._get_current_nr_lines()
        lines = self.current_nr_lines - 1
        # Scroll down a bit to avoid visual glitch when the screen area shrinks by one row
        self._print_control_code("\n")

        # Save cursor
        self._print_control_code(CODE_SAVE_CURSOR)
        # Set scroll region (this will place the cursor in the top left)
        self._print_control_code("\033[0;" + str(lines) + "r")

        # Restore cursor but ensure its inside the scrolling area
        self._print_control_code(CODE_RESTORE_CURSOR)
        self._print_control_code(CODE_CURSOR_IN_SCROLL_AREA)

        # Start empty progress bar
        self.draw(0)

        # Setup start time
        self.start_time = time()

    def destroy(self):
        lines = self._get_current_nr_lines()
        # Save cursor
        self._print_control_code(CODE_SAVE_CURSOR)
        # Set scroll region (this will place the cursor in the top left)
        self._print_control_code("\033[0;" + str(lines) + "r")

        # Restore cursor but ensure its inside the scrolling area
        self._print_control_code(CODE_RESTORE_CURSOR)
        self._print_control_code(CODE_CURSOR_IN_SCROLL_AREA)

        # We are done so clear the scroll bar
        self._clear_progress_bar()

        # Scroll down a bit to avoid visual glitch when the screen area grows by one row
        self._print_control_code("\n\n")

    def draw(self, percentage: int | None):
        if percentage is None:
            return

        lines = self._get_current_nr_lines()

        if lines != self.current_nr_lines:
            self.setup()

        # Save cursor
        self._print_control_code(CODE_SAVE_CURSOR)

        # Move cursor position to last row
        self._print_control_code("\033[" + str(lines) + ";0f")

        # Clear progress bar
        self._tput("el")

        # Draw progress bar
        self.progress_blocked = False
        self._print_bar_text(percentage)

        # Restore cursor position
        self._print_control_code(CODE_RESTORE_CURSOR)

    def block(self, percentage: int | None):
        if percentage is None:
            return

        lines = self._get_current_nr_lines()
        # Save cursor
        self._print_control_code(CODE_SAVE_CURSOR)

        # Move cursor position to last row
        self._print_control_code("\033[" + str(lines) + ";0f")

        # Clear progress bar
        self._tput("el")

        # Draw progress bar
        self.progress_blocked = True
        self._print_bar_text(percentage)

        # Restore cursor position
        self._print_control_code(CODE_RESTORE_CURSOR)

    def _clear_progress_bar(self):
        lines = self._get_current_nr_lines()
        # Save cursor
        self._print_control_code(CODE_SAVE_CURSOR)

        # Move cursor position to last row
        self._print_control_code("\033[" + str(lines) + ";0f")

        # clear progress bar
        self._tput("el")

        # Restore cursor position
        self._print_control_code(CODE_RESTORE_CURSOR)

    def _print_bar_text(self, percentage):
        color = f"{COLOR_FG}{COLOR_BG_BLOCKED}" if self.progress_blocked else f"{COLOR_FG}{COLOR_BG}"

        cols = self._get_current_nr_cols()
        if self.rate_bar:
            # Create right side of progress bar with statistics
            r_bar = self._prepare_r_bar(percentage)
            bar_size = cols - 21 - len(r_bar)
        else:
            r_bar = ""
            bar_size = cols - 20

        # Prepare progress bar
        complete_size = round((bar_size * percentage) / 100)
        remainder_size = bar_size - complete_size
        progress_bar = f"[{color}{'#' * complete_size}{RESTORE_FG}{RESTORE_BG}{'.' * remainder_size}]"
        percentage_str = ' 100' if percentage == 100 else f"{percentage:4.1f}"

        # Print progress bar
        self._print_control_code(f" Progress {percentage_str}% {progress_bar} {r_bar}\r")

    def _prepare_r_bar(self, n):
        elapsed = time() - self.start_time
        elapsed_str = self._format_interval(elapsed)

        # Percentage/second rate (or second/percentage if slow)
        rate = n / elapsed if elapsed > 0 else 0
        inv_rate = 1 / rate if rate else None
        rate_noinv_fmt = f"{f'{rate:5.2f}' if rate else '?'}pct/s"
        rate_inv_fmt = f"{f'{inv_rate:5.2f}' if inv_rate else '?'}s/pct"
        rate_fmt = rate_inv_fmt if inv_rate and inv_rate > 1 else rate_noinv_fmt

        # Remaining time
        remaining = (100 - n) / rate if rate else 0
        remaining_str = self._format_interval(remaining) if rate else "?"

        r_bar = f"[{elapsed_str}<{remaining_str}, {rate_fmt}]"
        return r_bar

    def _format_interval(self, t):
        h_m, s = divmod(int(t), 60)
        h, m = divmod(h_m, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"
