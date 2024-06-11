import os
import re
import subprocess
from shlex import quote
from time import time
from typing import Tuple

from .config import PROGRESS_BAR, progress_bar
from .environment import PipelineEnvironment


class PersistentDict(dict):
    def __getattr__(self, key: str):
        return self[key]

    def __hasattr__(self, key: str):
        return key in self

    def __setattr__(self, key: str, value):
        self[key] = value


PERSISTENT_VARS = PVARS = PersistentDict()

SHELL_EXECUTABLE = '/bin/bash'

# Leading red " Automatix \w > " to indicate that this shell is inside a running Automatix execution
AUTOMATIX_PROMPT = r'\[\033[0;31m\] Automatix \[\033[0m\]\\w > '

POSSIBLE_ANSWERS = {
    'p': 'proceed (default)',
    'T': f'start interactive terminal shell ({SHELL_EXECUTABLE} -i) and return back here on exit',
    'v': 'show and change variables',
    'r': 'retry',
    'R': 'reload from file and retry command (same index)',
    'R±X': 'same as R, but change index by X (integer)',
    's': 'skip',
    'a': 'abort',
    'c': 'abort & continue to next (CSV processing)',
    # 't' -> reserved for handling still running remote processes
    # 'k' -> reserved for handling still running remote processes
    # 'i' -> reserved for handling still running remote processes
}

KEYBOARD_INTERRUPT_MESSAGE = 'Abort command by user key stroke. Exit code is set to 130.'


class Command:
    def __init__(self, cmd: dict, index: int, pipeline: str, env: PipelineEnvironment, position: int):
        self.cmd = cmd
        self.index = index
        self.env = env
        self.pipeline = pipeline
        self.position = position

        for key, value in cmd.items():
            self.orig_key = key
            self.condition_var, self.assignment_var, self.key = parse_key(key=key)
            if isinstance(value, dict):
                # We need this workaround because the yaml lib returns a dictionary instead of a string,
                # if there is nothing but a variable in the command. Alternative is to use quotes in the script yaml.
                self.value = f'{{{next(iter(value))}}}'
            else:
                self.value = value
            break  # There should be only one entry in pipeline_cmd

    @property
    def progress_portion(self) -> int:
        own_position = self.env.command_count * (self.env.batch_index - 1) + self.position
        overall_command_count = self.env.batch_items_count * self.env.command_count
        return round(own_position / overall_command_count * 100, 1)

    def get_type(self):
        if self.key == 'local':
            return 'local'
        if self.key == 'manual':
            return 'manual'
        if self.key == 'python':
            return 'python'
        if re.search('remote@', self.key):
            return 'remote'
        raise UnknownCommandException(f'Command type {self.key} is not known.')

    def get_system(self):
        if self.get_type() == 'remote':
            return self.env.systems[re.search(r'remote@(.*)', self.key).group(1)]
        return 'localhost'

    def get_resolved_value(self):
        variables = self.env.vars.copy()
        for key, value in variables.items():
            if not isinstance(value, str):
                continue
            file_match = re.match(r'FILE_(.*)', value)
            if file_match:
                with open(os.path.expanduser(file_match.group(1))) as file:
                    variables[key] = file.read().strip()

        variables['CONST'] = ConstantsWrapper(self.env.config['constants'])
        variables['SYSTEMS'] = SystemsWrapper(self.env.systems)
        return self.value.format(**variables)

    def print_command(self):
        print()
        self.env.LOG.notice(f'({self.index}) [{self.orig_key}]: {self.get_resolved_value()}')

    def show_and_change_variables(self):
        print()
        self.env.LOG.info('Variables:')
        for key, value in self.env.vars.items():
            self.env.LOG.info(f" {key}: {value}")
        print()
        self.env.LOG.info('To change/set variable write variable + "=" followed by value.')
        self.env.LOG.info('Example: var1=xyz')
        self.env.LOG.info('Notice: You can only change 1 variable at a time. Repeat if necessary.')
        self.env.LOG.info('To not change anything just press "ENTER".')
        answer = input('\n')
        try:
            key, value = answer.split('=', maxsplit=1)
            self.env.vars[key.strip()] = value.strip()
            self.env.LOG.info(f'Variable {key.strip()} = {value.strip()}')
        except ValueError:
            if answer:
                self.env.LOG.error('Input could not be parsed.')
        self.print_command()
        print()

    def execute(self, interactive: bool = False, force: bool = False):
        try:
            self._execute(interactive=interactive, force=force)
        except (KeyError, UnknownCommandException):
            self.env.LOG.exception('Syntax or value error!')
            self.env.LOG.error('Syntax or value error! Please fix your script and reload/restart.')
            self._ask_user(question='[SE] What should I do?', allowed_options=['R', 'T', 'v', 's', 'a'])
        if PROGRESS_BAR:
            progress_bar.draw_progress_bar(self.progress_portion)

    def _execute(self, interactive: bool = False, force: bool = False):
        self.print_command()

        if not self._check_condition():
            self.env.LOG.info('Skip command, because the condition is not met.')
            return

        if self.get_type() == 'manual' or interactive:
            self.env.LOG.debug('Ask for user interaction.')

            answer = self._ask_user(question='[MS] Proceed?', allowed_options=['p', 'T', 'v', 's', 'R', 'a'])
            # answers 'a', 'c' and 'R' are handled by _ask_user, 'p' means just pass
            if answer == 's' or self.get_type() == 'manual':
                return

        steptime = time()

        return_code = self._execute_action()

        if 'AUTOMATIX_TIME' in os.environ:
            print()
            self.env.LOG.info(f'(command execution time: {round(time() - steptime)}s)')

        if return_code != 0:
            self.env.LOG.error(
                f'>> {self.env.name} << Command ({self.pipeline}:{self.index}) failed with return code {return_code}.')
            if force:
                return

            err_answer = self._ask_user(
                question='[CF] What should I do?',
                allowed_options=['p', 'T', 'v', 'r', 'R', 'a'],
            )
            # answers 'T', 'v', 'a', 'c' and 'R' are handled by _ask_user, 'p' means just pass
            if err_answer == 'r':
                return self._execute(interactive)

    def _check_condition(self) -> bool:
        if self.condition_var is None:
            return True

        if self.condition_var.endswith('!'):
            cond_var = self.condition_var[:-1]
            invert = True
        else:
            cond_var = self.condition_var
            invert = False

        if cond_var.startswith('PVARS.'):
            condition = PERSISTENT_VARS[cond_var[6:]]
        else:
            condition = self.env.vars.get(cond_var, False)

        return bool(condition) != invert

    def _execute_action(self) -> int:
        self.env.LOG.info('>')
        if self.get_type() == 'local':
            return self._local_action()
        if self.get_type() == 'python':
            return self._python_action()
        if self.get_type() == 'remote':
            return self._remote_action()

    def _ask_user(self, question: str, allowed_options: list) -> str:
        """
        User-Interactive handling of different scenarios.
        Questions should be prefixed with:
        [CF] Command Failed
        [PF] Partial command Failed (BW groups)
        [MS] Manual Step
        [RR] Remote process still Running
        [SE] Syntax Error

        :param question:
        :param allowed_options: character list of POSSIBLE_ANSWERS
        :return: answer character
        """
        if self.env.batch_mode:
            allowed_options.append('c')

        if 'R' in allowed_options:
            allowed_options.insert(allowed_options.index('R') + 1, 'R±X')

        options = '\n'.join([f' {k}: {POSSIBLE_ANSWERS[k]}' for k in allowed_options])

        return self._ask_user_with_options(
            question=f'{question}\n{options}\nYour answer: \a',
            allowed_options=allowed_options,
        )

    def _ask_user_with_options(self, question: str, allowed_options: list) -> str:
        if PROGRESS_BAR:
            progress_bar.block_progress_bar(self.progress_portion)
        self.env.send_status('user_input_add')
        answer = input(question)
        self.env.send_status('user_input_remove')

        if answer == '':  # default
            answer = 'p'

        if answer.startswith('R') and 'R' in allowed_options and len(answer) > 1:
            try:
                raise ReloadFromFile(index=self.index + int(answer[1:]))
            except ValueError:
                pass

        if answer not in allowed_options:
            self.env.LOG.warning('Invalid input. Try again.')
            return self._ask_user_with_options(question=question, allowed_options=allowed_options)

        match answer:
            case 'T':
                print()
                self.env.LOG.notice('Starting interactive terminal shell')
                self._run_local_command(
                    f'AUTOMATIX_SHELL=True'
                    f' {SHELL_EXECUTABLE}'
                    f' --rcfile <(cat ~/.bashrc ; echo "PS1=\\"{AUTOMATIX_PROMPT}\\"")'
                    f' -i'
                )
                return self._ask_user_with_options(question=question, allowed_options=allowed_options)
            case 'v':
                self.show_and_change_variables()
                return self._ask_user_with_options(question=question, allowed_options=allowed_options)
            case 'a':
                raise AbortException(1)
            case 'R':
                raise ReloadFromFile(index=self.index)
            case 'c':
                raise SkipBatchItemException()
            case _:
                return answer

    def _generate_python_vars(self):
        # For BWCommand this method is overridden
        return {'vars': self.env.vars}

    def _python_action(self) -> int:
        cmd = self.get_resolved_value()
        locale_vars = self._generate_python_vars()
        locale_vars.update(PERSISTENT_VARS)
        locale_vars.update({
            'AbortException': AbortException,
            'SkipBatchItemException': SkipBatchItemException,
        })

        self.env.LOG.debug(f'locals:\n {locale_vars}')
        try:
            self.env.LOG.debug(f'Run python command: {cmd}')
            if self.assignment_var:
                exec(f'vars["{self.assignment_var}"] = {cmd}', globals(), locale_vars)
                self.env.LOG.info(f'Variable {self.assignment_var} = {repr(self.env.vars[self.assignment_var])}')
            else:
                exec(cmd, globals(), locale_vars)
            return 0
        except (AbortException, SkipBatchItemException):
            raise
        except KeyboardInterrupt:
            self.env.LOG.info(KEYBOARD_INTERRUPT_MESSAGE)
            return 130
        except Exception as exc:
            if isinstance(exc, NameError) and not self.env.config.get('bundlewrap') and str(exc) in [
                'name \'NODES\' is not defined',
                'name \'AUTOMATIX_BW_REPO\' is not defined',
            ]:
                self.env.LOG.exception(
                    'Seems you are trying to use bundlewrap functions without having bundlewrap support enabled.'
                    ' Please check your configuration.')
                return 1
            if isinstance(exc.__context__, ReloadFromFile):
                exc.__suppress_context__ = True

            self.env.LOG.exception('Unknown error occured:')
            return 1

    def _local_action(self) -> int:
        cmd = self._build_command(path=self.env.config['import_path'])
        try:
            return self._run_local_command(cmd=cmd)
        except KeyboardInterrupt:
            self.env.LOG.info(KEYBOARD_INTERRUPT_MESSAGE)
            return 130

    def _build_command(self, path: str) -> str:
        if not self.env.imports:
            return self.get_resolved_value()
        return f'. {path}/' + f'; . {path}/'.join(self.env.imports) + '; ' + self.get_resolved_value()

    def _run_local_command(self, cmd: str) -> int:
        self.env.LOG.debug(f'Executing: {cmd}')
        if self.assignment_var:
            proc = subprocess.run(cmd, shell=True, executable=SHELL_EXECUTABLE, stdout=subprocess.PIPE)
            output = proc.stdout.decode(self.env.config["encoding"])
            self.env.vars[self.assignment_var] = assigned_value = output.rstrip('\r\n')
            hint = ' (trailing newline removed)' if (output.endswith('\n') or output.endswith('\r')) else ''
            self.env.LOG.info(f'Variable {self.assignment_var} = "{assigned_value}"{hint}')
        else:
            proc = subprocess.run(cmd, shell=True, executable=SHELL_EXECUTABLE)
        return proc.returncode

    def _remote_action(self) -> int:
        # For BWCommand this method is overridden
        return self._remote_action_on_hostname(hostname=self.get_system().replace('hostname!', ''))

    def _remote_action_on_hostname(self, hostname: str) -> int:
        try:
            exitcode = self._run_local_command(cmd=self._get_remote_command(hostname=hostname))
        except KeyboardInterrupt:
            self.env.LOG.info(KEYBOARD_INTERRUPT_MESSAGE)
            exitcode = 130
            self._remote_handle_keyboard_interrupt(hostname=hostname)

        if self.env.imports:
            self._remote_cleanup_imports(hostname=hostname)

        return exitcode

    def _get_remote_command(self, hostname: str) -> str:
        ssh_cmd = self.env.config["ssh_cmd"].format(hostname=hostname)
        remote_cmd = self.get_resolved_value()
        prefix = ''
        if self.env.imports:
            # How is this working?
            # - Create a tar archive with all imports
            # - Pipe it through SSH
            # - Create tmp dir on remote
            # - Extract tar archive there
            # - Source imports in _build_command
            prefix = f'tar -C {self.env.config["import_path"]} -cf - ' + ' '.join(self.env.imports) + ' | '
            remote_cmd = f'mkdir {self.env.config["remote_tmp_dir"]};' \
                         f' tar -C {self.env.config["remote_tmp_dir"]} -xf -;' \
                         f' {self._build_command(path=self.env.config["remote_tmp_dir"])}'

        return f'{prefix}{ssh_cmd}{quote("bash -c " + quote(remote_cmd))}'

    def _remote_handle_keyboard_interrupt(self, hostname: str) -> int:
        ssh_cmd = self.env.config["ssh_cmd"].format(hostname=hostname)

        try:
            ps_pids = self.get_remote_pids(hostname=hostname, cmd=self.get_resolved_value())
            while ps_pids:
                self.env.LOG.notice(
                    'Remote command seems still to be running! Found PIDs: {}'.format(','.join(ps_pids))
                )
                self.env.send_status('user_input_add')
                answer = input(
                    '[RR] What should I do? '
                    '(i: send SIGINT (default), t: send SIGTERM, k: send SIGKILL, p: do nothing and proceed) \n\a')
                self.env.send_status('user_input_remove')

                if answer == 'p':
                    break
                elif answer == 't':
                    signal = 'TERM'
                elif answer == 'k':
                    signal = 'KILL'
                else:
                    signal = 'INT'
                for pid in ps_pids:
                    kill_cmd = f'{ssh_cmd} kill -{signal} {pid}'
                    self.env.LOG.info(f'Kill {pid} on {hostname}')
                    subprocess.run(kill_cmd, shell=True)

                ps_pids = self.get_remote_pids(hostname=hostname, cmd=self.get_resolved_value())
        except subprocess.CalledProcessError:
            self.env.LOG.warning('Could not check for remaining remote processes.')

        self.env.LOG.info('Keystroke interrupt handled.\n')

    def get_remote_pids(self, hostname, cmd) -> []:
        ps_cmd = f"ps axu | grep {quote(cmd)} | grep -v 'grep' | awk '{{print $2}}'"
        cmd = f'ssh {hostname} {quote(ps_cmd)} 2>&1'
        pids = subprocess.check_output(
            cmd,
            shell=True,
            executable=SHELL_EXECUTABLE,
        ).decode(self.env.config["encoding"]).split()

        return pids

    def _remote_cleanup_imports(self, hostname: str):
        ssh_cmd = self.env.config["ssh_cmd"].format(hostname=hostname)
        cleanup_cmd = f'{ssh_cmd} rm -r {self.env.config["remote_tmp_dir"]}'
        self.env.LOG.debug(f'Executing: {cleanup_cmd}')
        proc = subprocess.run(cleanup_cmd, shell=True, executable=SHELL_EXECUTABLE)
        if proc.returncode != 0:
            self.env.LOG.warning(
                'Failed to remove {tmp_dir}, exitcode: {return_code}'.format(
                    tmp_dir=self.env.config["remote_tmp_dir"],
                    return_code=proc.returncode,
                )
            )


def parse_key(key) -> Tuple[str, ...]:
    """
    parses the key

    returns a list containing:
    - condition_var: if this evaluates to False, the command is not executed
    - assignment_var: name of a variable, to which the command output is assigned
    - command_type
    """

    return re.search(r'((.*)\?)?((.*)=)?(.*)', key).group(2, 4, 5)


class SystemsWrapper:
    def __init__(self, systems: dict):
        self.systems = systems

    def __getattr__(self, name):
        return self.systems[name].replace('hostname!', '')


class ConstantsWrapper:
    def __init__(self, constants: dict):
        self.constants = constants

    def __getattr__(self, name):
        return self.constants[name]


class AbortException(Exception):
    def __init__(self, return_code: int):
        self.return_code = return_code

    def __int__(self):
        return self.return_code


class SkipBatchItemException(Exception):
    pass


class UnknownCommandException(Exception):
    pass


class ReloadFromFile(Exception):
    def __init__(self, index: int):
        self.index = index

    def __int__(self):
        return self.index
