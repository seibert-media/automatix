import curses
import pickle
import subprocess
from os.path import isfile
from textwrap import wrap
from time import sleep

from .config import LOG
from .helpers import FileWithLock
from .parallel import Autos


class CursesWriter:
    def __init__(self, stdscr: curses.window):
        self.stdscr = stdscr

        # Terminal setup
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(True)  # Make getch() non-blocking

        # Initialize colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_YELLOW, -1)  # -1 for default background
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_GREEN, -1)

        self.yellow = curses.color_pair(1)
        self.cyan = curses.color_pair(2)
        self.red = curses.color_pair(3)
        self.green = curses.color_pair(4)

        self.h, self.w = stdscr.getmaxyx()

        self.input_buffer = ''
        self.current_line = 0

    def add_text(self, text: str, start: int = 0, attr: int | None = None, append_line: bool = False):
        if append_line:
            self.current_line, x = self.stdscr.getyx()
            start = start if start else x + 1

        available_width = self.w - start - 1
        if available_width <= 0:  # Not enough space to print anything
            # Move to the next line anyway to avoid infinite loops on tiny screens
            self.add_empty_line()
            return

        wrapped_lines = wrap(text, width=available_width)

        # If the original text was empty, textwrap returns an empty list.
        # Ensure we "print" an empty line to advance the cursor.
        if not wrapped_lines:
            wrapped_lines.append('')

        for line in wrapped_lines:
            if attr is not None:
                self.stdscr.addstr(self.current_line, start, line, attr)
            else:
                self.stdscr.addstr(self.current_line, start, line)
            self.current_line += 1

    def add_empty_line(self):
        self.current_line += 1
        self.stdscr.move(self.current_line, 0)

    def clear(self):
        self.stdscr.clear()
        self.current_line = 0


def handle_exit(exc: Exception) -> str:
    if isinstance(exc, KeyboardInterrupt):
        LOG.error('You decided to quit the UI, but screens are most likely still running. Please decide what to do:')
    else:
        LOG.exception(exc)
        print()
        LOG.error('An unexpected error occurred. Please decide what to do:')
    match input(
        'Press "q" and Enter to quit.'
        ' This will cause this programm to terminate.'
        ' Check "screen -list" afterwards for still running screens.\n'
        ' Press something else to restart the UI, where you can switch to the different screens.\n'
    ):
        case 'q':
            raise SystemExit(130)
        case _:
            return 'restart'


def draw_status(cw: CursesWriter, autos: Autos):
    cw.clear()

    cw.add_text(f'Automatix Status (max parallel: {autos.max_parallel})')
    cw.add_text('-' * (cw.w - 2))

    cw.add_text('waiting: ')
    cw.add_text(str(len(autos.waiting)), attr=cw.yellow, append_line=True)
    cw.add_text(', running: ', append_line=True)
    cw.add_text(str(len(autos.running)), attr=cw.cyan, append_line=True)
    cw.add_text(', user input required: ', append_line=True)
    cw.add_text(str(len(autos.user_input)), attr=cw.red, append_line=True)
    cw.add_text(', finished: ', append_line=True)
    cw.add_text(f'{len(autos.finished)}/{autos.count}', attr=cw.green, append_line=True)

    cw.add_text('-' * (cw.w - 2))
    cw.add_empty_line()

    cw.add_text('Waiting:             ', start=2)
    cw.add_text(', '.join(autos.waiting), start=22, append_line=True)
    cw.add_text('Running:             ', start=2)
    cw.add_text(', '.join(autos.running), start=22, append_line=True)
    cw.add_text('User input needed: ', attr=cw.red, start=2)
    cw.add_text(', '.join(autos.user_input), attr=cw.red, start=22, append_line=True)
    cw.add_text('Finished:            ', start=2)
    cw.add_text(', '.join(autos.finished), start=22, append_line=True)

    cw.current_line = cw.h - 6
    cw.add_text(f'Working directory: {autos.tempdir}')
    cw.add_text("-" * (cw.w - 1))
    cw.add_text(
        'Options: [o] Overview | [n] Next Input | [X] to autoX | [mX] max parallel to X | [q] Quit',
        start=2,
    )
    cw.add_text(f'Input: {cw.input_buffer}', start=2)

    cw.stdscr.refresh()


def handle_answer(answer: str, autos: Autos) -> str | None:
    if answer == 'q':
        raise KeyboardInterrupt('Quit UI by user')
    elif answer == 'o':
        return f'{autos.time_id}_overview'
    elif answer == 'n' and autos.user_input:
        return f'{autos.time_id}_{next(iter(autos.user_input))}'
    elif answer.startswith('m'):
        try:
            max_parallel = int(answer[1:])
            with FileWithLock(autos.status_file, 'a') as sf:
                sf.write(f'{max_parallel}:max_parallel\n')
        except (ValueError, IndexError):
            pass  # Ignore invalid input
    else:
        try:
            number = int(answer)
            return f'{autos.time_id}_auto{str(number).rjust(len(str(autos.count)), "0")}'
        except ValueError:
            pass  # Ignore invalid input


def process_user_input(cw: CursesWriter, autos: Autos) -> str | None:
    key = cw.stdscr.getch()
    if key == -1:  # No input
        return None

    char = chr(key)
    if key in [curses.KEY_ENTER, 10, 13]:
        answer = cw.input_buffer.lower()
        cw.input_buffer = ''

        if new_screen := handle_answer(answer=answer, autos=autos):
            return new_screen
    elif key in [curses.KEY_BACKSPACE, 127]:
        cw.input_buffer = cw.input_buffer[:-1]
    elif char.isalnum():
        cw.input_buffer += char


def parallel_ui(stdscr: curses.window, tempdir: str):
    cw = CursesWriter(stdscr=stdscr)

    # Wait until the status file exists
    while not isfile(f'{tempdir}/autos'):
        stdscr.clear()
        stdscr.addstr(0, 0, 'Waiting for the manager process to start...')
        stdscr.refresh()
        sleep(0.5)

    while True:
        # 1. Load data
        with FileWithLock(f'{tempdir}/autos', 'rb') as f:
            autos = pickle.load(file=f)

        # 2. Draw status
        draw_status(cw=cw, autos=autos)

        # 3. Check if all processes have finished
        if len(autos.running) + len(autos.waiting) + len(autos.user_input) == 0:
            cw.stdscr.addstr(cw.h - 1, 2, 'All processes have finished. Press "q" to exit.', cw.green)
            cw.stdscr.refresh()
            # Wait until the user presses 'q'
            cw.stdscr.nodelay(False)
            while cw.stdscr.getch() not in [ord('q'), ord('Q')]:
                sleep(0.1)
            return 'quit'

        # 4. Process user input
        screen_to_switch = process_user_input(cw=cw, autos=autos)
        if screen_to_switch:
            # Important: End curses before an external program takes control of the terminal
            curses.endwin()
            print(f"Switching to screen '{screen_to_switch}'... (Return with <ctrl>+a d)")
            subprocess.run(['screen', '-r', screen_to_switch])
            return 'restart'

        sleep(0.2)  # Short pause to reduce CPU load


def screen_switch_loop(tempdir: str):
    while True:
        try:
            exit_reason = curses.wrapper(parallel_ui, tempdir)
        except curses.error as exc:
            LOG.error(f"Curses error: {exc}")
            LOG.error("Could not start the curses interface. Is the terminal compatible?")
            exit_reason = handle_exit(exc=exc)
        except (KeyboardInterrupt, Exception) as exc:
            exit_reason = handle_exit(exc=exc)

        if exit_reason != 'restart':
            break
