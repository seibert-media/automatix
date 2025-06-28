import curses
import pickle
import subprocess
from os.path import isfile
from time import sleep

from automatix import LOG
from automatix.helpers import FileWithLock
from automatix.parallel import Autos


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

    def add_line(self, text: str):
        self.stdscr.addstr(self.current_line, 0, text)
        self.current_line += 1

    def clear(self):
        self.stdscr.clear()
        self.current_line = 0



def handle_exit(exc: Exception | None = None) -> str:
    if exc:
        LOG.exception(exc)
        print()
        LOG.info('An unexpected error occurred. Please decide what to do:')
    else:
        LOG.info('You decided to quit the UI, but screens are most likely still running. Please decide what to do:')
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
    cw.stdscr.clear()

    cw.stdscr.addstr(0, 0, f'Automatix Status (max parallel: {autos.max_parallel})')
    cw.stdscr.addstr(1, 0, f'Working directory: {autos.tempdir}')
    cw.stdscr.addstr(2, 0, '-' * (cw.w - 1))

    cw.stdscr.addstr(3, 0, 'waiting: ')
    cw.stdscr.addstr(str(len(autos.waiting)), cw.yellow)
    cw.stdscr.addstr(', running: ')
    cw.stdscr.addstr(str(len(autos.running)), cw.cyan)
    cw.stdscr.addstr(', user input required: ')
    cw.stdscr.addstr(str(len(autos.user_input)), cw.red)
    cw.stdscr.addstr(', finished: ')
    cw.stdscr.addstr(str(len(autos.finished)), cw.green)

    cw.stdscr.addstr(4, 0, '-' * (cw.w - 1))

    cw.stdscr.addstr(6, 2, 'Waiting:             ')
    cw.stdscr.addstr(6, 22, str(sorted(autos.waiting)))
    cw.stdscr.addstr(7, 2, 'Running:             ')
    cw.stdscr.addstr(7, 22, str(sorted(autos.running)))
    cw.stdscr.addstr(8, 2, 'User input needed:   ')
    cw.stdscr.addstr(8, 22, str(sorted(autos.user_input)), cw.red)
    cw.stdscr.addstr(9, 2, 'Finished:            ')
    cw.stdscr.addstr(9, 22, str(sorted(autos.finished)))

    help_y = cw.h - 5
    cw.stdscr.addstr(help_y, 0, "-" * (cw.w - 1))
    cw.stdscr.addstr(
        help_y + 1, 2,
        'Options: [o] Overview | [n] Next Input | [X] to autoX | [mX] max parallel to X | [q] Quit'
    )
    cw.stdscr.addstr(help_y + 2, 2, f'Input: {cw.input_buffer}')

    cw.stdscr.refresh()


def process_user_input(cw: CursesWriter, autos: Autos) -> str | None:
    key = cw.stdscr.getch()
    if key == -1:  # No input
        return None

    char = chr(key)
    if key in [curses.KEY_ENTER, 10, 13]:
        answer = cw.input_buffer.lower()
        cw.input_buffer = ''

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
            subprocess.run(f'screen -r {screen_to_switch}', shell=True)
            return 'restart'

        sleep(0.2)  # Short pause to reduce CPU load


def screen_switch_loop(tempdir: str):
    while True:
        try:
            exit_reason = curses.wrapper(parallel_ui, tempdir)
        except curses.error as e:
            LOG.error(f"Curses error: {e}")
            LOG.error("Could not start the curses interface. Is the terminal compatible?")
            raise
        except (KeyboardInterrupt, Exception) as exc:
            exit_reason = handle_exit(exc=exc)

        if exit_reason != 'restart':
            break
