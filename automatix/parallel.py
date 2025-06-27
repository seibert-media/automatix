import argparse
import curses
import os
import pickle
import subprocess
import sys
from dataclasses import dataclass, field
from os import listdir, unlink
from os.path import isfile
from pathlib import Path
from time import sleep, strftime, gmtime

from .automatix import Automatix
from .colors import yellow, green, red, cyan
from .command import AbortException
from .config import LOG, init_logger, CONFIG
from .progress_bar import setup_scroll_area, destroy_scroll_area

STATUS_TEMPLATE = 'waiting: {w}, running: {r}, user input required: {u}, finished: {f}'


@dataclass
class Autos:
    status_file: str
    time_id: int
    count: int
    tempdir: str

    max_parallel: int = 2
    waiting: list = field(default_factory=list)
    running: set = field(default_factory=set)
    user_input: set = field(default_factory=set)
    finished: set = field(default_factory=set)


class FileWithLock:
    def __init__(self, file_path: str, method: str):
        self.file_path = file_path
        self.method = method
        self.file_obj = None

    def __enter__(self):
        get_lock(self.file_path)
        self.file_obj = open(self.file_path, self.method)
        return self.file_obj

    def __exit__(self, type, value, traceback):
        self.file_obj.close()
        release_lock(self.file_path)


def get_lock(file_path: str):
    while True:
        try:
            os.mkdir(f'{file_path}.lock')
        except FileExistsError:
            sleep(1)
            continue
        break


def release_lock(file_path: str):
    os.rmdir(f'{file_path}.lock')


def get_logfile_dir(time_id: int, scriptfile: str) -> str:
    human_readable_time = strftime('%Y-%m-%d_%H-%M-%S_UTC', gmtime(time_id))
    return f'{CONFIG.get("logfile_dir")}/{human_readable_time}__{Path(scriptfile).stem}'


def get_files(tempdir: str) -> set:
    return {f for f in listdir(tempdir) if isfile(f'{tempdir}/{f}') and f.startswith('auto')}


def print_status(autos: Autos):
    print(STATUS_TEMPLATE.format(
        w=yellow(len(autos.waiting)),
        r=cyan(len(autos.running)),
        u=red(len(autos.user_input)),
        f=green(f'{len(autos.finished)}/{autos.count}'),
    ))


def check_for_status_change(autos: Autos, status_file: str):
    with FileWithLock(status_file, 'r+') as sf:
        for line in sf:
            if not line:
                continue
            LOG.debug(f'Line: {line}')
            auto_file, status = line.strip().split(':')
            LOG.debug(f'Got {auto_file}:{status}')
            match status:
                case 'max_parallel':
                    # In this case we misuse the "auto_file" part as number
                    # for how many parallel screens are allowed.
                    autos.max_parallel = int(auto_file)
                    LOG.info(f'Now process max {auto_file} screens parallel')
                case 'user_input_remove':
                    autos.user_input.remove(auto_file)
                case 'user_input_add':
                    autos.user_input.add(auto_file)
                    LOG.info(f'{auto_file} is waiting for user input')
                case 'finished':
                    autos.running.remove(auto_file)
                    autos.finished.add(auto_file)
                    LOG.info(f'{auto_file} finished')
                case _:
                    LOG.warning(f'[{auto_file}] Unrecognized status "{status}"\n')
        sf.truncate(0)


def run_manage_loop(tempdir: str, time_id: int):
    status_file = f'{tempdir}/{time_id}_overview'
    auto_files = sorted(get_files(tempdir))
    autos = Autos(status_file=status_file, time_id=time_id, count=len(auto_files), waiting=auto_files, tempdir=tempdir)
    with open(f'{tempdir}/{next(iter(auto_files))}', 'rb') as f:
        scriptfile = pickle.load(f).env.cmd_args.scriptfile

    LOG.info(f'Found {autos.count} files to process. Screens name are like "{time_id}_autoX"')
    LOG.info('To switch screens detach from this screen via "<ctrl>+a d".')
    LOG.info('To scroll back in history press "<ctrl>+a Esc" to enable "copy mode". Switch back with "Esc".')
    LOG.info('You can modify this behaviour by screen configuration options (`~/.screenrc`).')

    open(status_file, 'a').close()
    try:
        while len(autos.finished) < autos.count:
            if len(autos.running) < autos.max_parallel and autos.waiting:
                auto_file = autos.waiting.pop(0)
                autos.running.add(auto_file)
                LOG.info(f'Starting new screen at {time_id}_{auto_file}')
                subprocess.run(
                    f'screen -d -m -S {time_id}_{auto_file}'
                    f' -L -Logfile {get_logfile_dir(time_id=time_id, scriptfile=scriptfile)}/{auto_file}.log'
                    f' automatix-from-file {tempdir} {time_id} {auto_file}',
                    # for debugging replace line above with:
                    # f' bash -c "automatix-from-file {tempdir} {time_id} {auto_file} || bash"',
                    shell=True,
                )

            check_for_status_change(autos=autos, status_file=status_file)

            print_status(autos=autos)

            # Write status to file for screen switch loop
            with FileWithLock(f'{tempdir}/autos', 'wb') as f:
                pickle.dump(obj=autos, file=f)

            sleep(1)

        LOG.info(f'All parallel screen reported finished ({len(autos.finished)}/{autos.count}).')
    except Exception as exc:
        LOG.exception(exc)
        sleep(60)  # For debugging
    finally:
        with open(f'{tempdir}/{time_id}_finished', 'w') as fifo:
            fifo.write('finished')


def run_manager():
    parser = argparse.ArgumentParser(
        description='Automatix manager for parallel processing (called by the automatix main programm)',
        epilog='Explanations and README at https://github.com/vanadinit/automatix',
    )
    parser.add_argument('tempdir')
    parser.add_argument('time_id')
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='activate debug log level',
    )
    args = parser.parse_args()

    init_logger(name=CONFIG['logger'], debug=args.debug)
    run_manage_loop(tempdir=args.tempdir, time_id=int(args.time_id))


def run_auto(tempdir: str, time_id: int, auto_file: str):
    auto_path = f'{tempdir}/{auto_file}'

    def send_status(status: str):
        with FileWithLock(f'{tempdir}/{time_id}_overview', 'a') as sf:
            sf.write(f'{auto_file}:{status}\n')

    with open(auto_path, 'rb') as f:
        auto: Automatix = pickle.load(file=f)
    auto.set_command_count()
    auto.env.attach_logger()
    auto.env.reinit_logger()
    auto.env.send_status = send_status

    try:
        auto.run()
    except AbortException as exc:
        sys.exit(int(exc))
    except KeyboardInterrupt:
        print()
        LOG.warning('Aborted by user. Exiting.')
        sys.exit(130)
    finally:
        send_status('finished')
        unlink(auto_path)


def run_auto_from_file():
    parser = argparse.ArgumentParser(
        description='Automatix from file for parallel processing (called by the automatix-manager)',
        epilog='Explanations and README at https://github.com/vanadinit/automatix',
    )
    parser.add_argument('tempdir')
    parser.add_argument('time_id')
    parser.add_argument('auto_file')
    args = parser.parse_args()

    try:
        if CONFIG['progress_bar']:
            setup_scroll_area()

        run_auto(tempdir=args.tempdir, time_id=args.time_id, auto_file=args.auto_file)
    finally:
        if CONFIG['progress_bar']:
            destroy_scroll_area()


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

    # Wait until the first status file exists
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
                pass
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
