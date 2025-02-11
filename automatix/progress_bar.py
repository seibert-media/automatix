# Most of the code in this file is copied from or inspired by
# https://github.com/pollev/python_progress_bar/blob/master/python_progress_bar/progress_bar.py

import curses
import os

from time import time

# Usage:
# setup_scroll_area()              <- create empty progress bar
# draw_progress_bar(10)            <- advance progress bar
# draw_progress_bar(40)            <- advance progress bar
# block_progress_bar(45)           <- turns the progress bar yellow to indicate some action is requested from the user
# draw_progress_bar(90)            <- advance progress bar
# destroy_scroll_area()            <- remove progress bar


# Constants
CODE_SAVE_CURSOR = "\033[s"
CODE_RESTORE_CURSOR = "\033[u"
CODE_CURSOR_IN_SCROLL_AREA = "\033[1A"
COLOR_FG = '\033[30m'
COLOR_BG = '\033[42m'
COLOR_BG_BLOCKED = '\033[43m'
RESTORE_FG = '\033[39m'
RESTORE_BG = '\033[49m'


class ProgressStatus:
    progress_blocked = False
    current_nr_lines = 0
    start_time = 0
    rate_bar = True


def get_current_nr_lines():
    stream = os.popen('tput lines')
    output = stream.read()
    return int(output)


def get_current_nr_cols():
    stream = os.popen('tput cols')
    output = stream.read()
    return int(output)


def setup_scroll_area(rate_bar=True):
    # Enable/disable right side of progress bar with statistics
    ProgressStatus.rate_bar = rate_bar
    # Setup curses support (to get information about the terminal we are running in)
    curses.setupterm()

    ProgressStatus.current_nr_lines = get_current_nr_lines()
    lines = ProgressStatus.current_nr_lines - 1
    # Scroll down a bit to avoid visual glitch when the screen area shrinks by one row
    __print_control_code("\n")

    # Save cursor
    __print_control_code(CODE_SAVE_CURSOR)
    # Set scroll region (this will place the cursor in the top left)
    __print_control_code("\033[0;" + str(lines) + "r")

    # Restore cursor but ensure its inside the scrolling area
    __print_control_code(CODE_RESTORE_CURSOR)
    __print_control_code(CODE_CURSOR_IN_SCROLL_AREA)

    # Start empty progress bar
    draw_progress_bar(0)

    # Setup start time
    ProgressStatus.start_time = time()


def destroy_scroll_area():
    lines = get_current_nr_lines()
    # Save cursor
    __print_control_code(CODE_SAVE_CURSOR)
    # Set scroll region (this will place the cursor in the top left)
    __print_control_code("\033[0;" + str(lines) + "r")

    # Restore cursor but ensure its inside the scrolling area
    __print_control_code(CODE_RESTORE_CURSOR)
    __print_control_code(CODE_CURSOR_IN_SCROLL_AREA)

    # We are done so clear the scroll bar
    __clear_progress_bar()

    # Scroll down a bit to avoid visual glitch when the screen area grows by one row
    __print_control_code("\n\n")


def draw_progress_bar(percentage):
    lines = get_current_nr_lines()

    if lines != ProgressStatus.current_nr_lines:
        setup_scroll_area()

    # Save cursor
    __print_control_code(CODE_SAVE_CURSOR)

    # Move cursor position to last row
    __print_control_code("\033[" + str(lines) + ";0f")

    # Clear progress bar
    __tput("el")

    # Draw progress bar
    ProgressStatus.progress_blocked = False
    __print_bar_text(percentage)

    # Restore cursor position
    __print_control_code(CODE_RESTORE_CURSOR)


def block_progress_bar(percentage):
    lines = get_current_nr_lines()
    # Save cursor
    __print_control_code(CODE_SAVE_CURSOR)

    # Move cursor position to last row
    __print_control_code("\033[" + str(lines) + ";0f")

    # Clear progress bar
    __tput("el")

    # Draw progress bar
    ProgressStatus.progress_blocked = True
    __print_bar_text(percentage)

    # Restore cursor position
    __print_control_code(CODE_RESTORE_CURSOR)


def __clear_progress_bar():
    lines = get_current_nr_lines()
    # Save cursor
    __print_control_code(CODE_SAVE_CURSOR)

    # Move cursor position to last row
    __print_control_code("\033[" + str(lines) + ";0f")

    # clear progress bar
    __tput("el")

    # Restore cursor position
    __print_control_code(CODE_RESTORE_CURSOR)


def __print_bar_text(percentage):
    color = f"{COLOR_FG}{COLOR_BG_BLOCKED}" if ProgressStatus.progress_blocked else f"{COLOR_FG}{COLOR_BG}"

    cols = get_current_nr_cols()
    if ProgressStatus.rate_bar:
        # Create right side of progress bar with statistics
        r_bar = __prepare_r_bar(percentage)
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
    __print_control_code(f" Progress {percentage_str}% {progress_bar} {r_bar}\r")


def __prepare_r_bar(n):
    elapsed = time() - ProgressStatus.start_time
    elapsed_str = __format_interval(elapsed)

    # Percentage/second rate (or second/percentage if slow)
    rate = n / elapsed
    inv_rate = 1 / rate if rate else None
    rate_noinv_fmt = f"{f'{rate:5.2f}' if rate else '?'}pct/s"
    rate_inv_fmt = f"{f'{inv_rate:5.2f}' if inv_rate else '?'}s/pct"
    rate_fmt = rate_inv_fmt if inv_rate and inv_rate > 1 else rate_noinv_fmt

    # Remaining time
    remaining = (100 - n) / rate if rate else 0
    remaining_str = __format_interval(remaining) if rate else "?"

    r_bar = f"[{elapsed_str}<{remaining_str}, {rate_fmt}]"
    return r_bar


def __format_interval(t):
    h_m, s = divmod(int(t), 60)
    h, m = divmod(h_m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


def __tput(cmd, *args):
    print(curses.tparm(curses.tigetstr("el")).decode(), end='')
    # print(curses.tparm(curses.tigetstr("el")).decode())


def __print_control_code(code):
    print(code, end='')
