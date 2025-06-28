import os
import re
import subprocess
from code import InteractiveConsole
from dataclasses import dataclass
from shlex import quote
from time import time

from .environment import PipelineEnvironment, AttributedDict, AttributedDummyDict
from .helpers import empty_queued_input_data
from .progress_bar import draw_progress_bar, block_progress_bar

PERSISTENT_VARS = PVARS = AttributedDict()

# Leading red " Automatix \w > " to indicate that this shell is inside a running Automatix execution
AUTOMATIX_PROMPT = r'\[\033[0;31m\] Automatix \[\033[0m\]\\w > '

AUTOMATIX_PYTHON_BANNER = """\
Automatix Python Debugging Console

Same variables as in a python command are available, but locals() and globals() are not divided.
Exit with `exit()` or Ctrl-D.
"""
AUTOMATIX_PYTHON_EXITMSG = 'Exit Python Debugging Console.'

KEYBOARD_INTERRUPT_MESSAGE = 'Abort command by user key stroke. Exit code is set to 130.'

POSSIBLE_ANSWERS = {
    'p': 'proceed (default)',
    'T': 'start interactive terminal shell ({bash_path} -i) and return back here on exit',
    'D': 'start interactive Python debugging shell with command environment',
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


@dataclass
class Answer:
    answer: str

    @property
    def description(self):
        return POSSIBLE_ANSWERS[self.answer]


class PossibleAnswers:
    proceed = Answer(answer='p')
    terminal = Answer(answer='T')
    debug_shell = Answer(answer='D')
    variables = Answer(answer='v')
    retry = Answer(answer='r')
    reload = Answer(answer='R')
    reload_index = Answer(answer='R±X')
    skip = Answer(answer='s')
    abort = Answer(answer='a')
    abort_continue = Answer(answer='c')


PA = PossibleAnswers


class Command:
    def __init__(self, cmd: dict, index: int, pipeline: str, env: PipelineEnvironment, position: int):
        self.cmd = cmd
        self.index = index
        self.env = env
        self.pipeline = pipeline
        self.position = position

        self.bash_path = self.env.config['bash_path']

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

    def get_resolved_value(self, dummy: bool = False):
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
        variables['PVARS'] = AttributedDummyDict('PVARS', PVARS) if dummy else PVARS
        return self.value.format(**variables)

    def print_command(self):
        print()
        self.env.LOG.notice(f'({self.index}) [{self.orig_key}]: {self.get_resolved_value(dummy=True)}')

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
        empty_queued_input_data()
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
            self._ask_user(
                question='[SE] What should I do?',
                allowed_options=[PA.reload, PA.terminal, PA.debug_shell, PA.variables, PA.skip, PA.abort],
            )
            # _ask_user handles are answers but PA.retry, PA.skip, PA.proceed
            # PA.retry and PA.proceed are not in allowed options
            # PA.skip means 'skip' so we can just go on
        if self.env.config['progress_bar']:
            draw_progress_bar(self.progress_portion)

    def _execute(self, interactive: bool = False, force: bool = False):
        self.print_command()

        if not self._check_condition():
            self.env.LOG.info('Skip command, because the condition is not met.')
            return

        if self.get_type() == 'manual' or interactive:
            self.env.LOG.debug('Ask for user interaction.')

            answer = self._ask_user(
                question='[MS] Proceed?',
                allowed_options=[
                    PA.proceed,
                    PA.terminal,
                    PA.debug_shell,
                    PA.variables,
                    PA.skip,
                    PA.reload,
                    PA.reload_index,
                    PA.abort,
                ]
            )
            # _ask_user handles are answers but PA.retry, PA.skip, PA.proceed
            # PA.retry is not in allowed options
            # PA.proceed means 'proceed' so we can just go on
            if answer == PA.skip.answer or self.get_type() == 'manual':
                # no further execution is needed for manual steps
                # PA.skip means 'skip' so we skip execution and return
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
                allowed_options=[
                    PA.proceed,
                    PA.terminal,
                    PA.debug_shell,
                    PA.variables,
                    PA.retry,
                    PA.reload,
                    PA.reload_index,
                    PA.abort,
                ],
            )
            # _ask_user handles are answers but PA.retry, PA.skip, PA.proceed
            # PA.skip is not in allowed options
            # PA.proceed means 'proceed' so we can just go on
            if err_answer == PA.retry.answer:
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
        raise SyntaxError('Unknown command type')

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
            allowed_options.append(PA.abort_continue)

        options = '\n'.join([f' {k.answer}: {k.description}' for k in allowed_options])
        formatted_options = options.format(bash_path=self.bash_path)

        return self._ask_user_with_options(
            question=f'{question}\n{formatted_options}\nYour answer: \a',
            allowed_options=allowed_options,
        )

    def _ask_user_with_options(self, question: str, allowed_options: list) -> str:
        """
        Asks user and handles all answers except PA.retry, PA.skip and PA.proceed.
        Retry, skip and proceed require different handling, based on where in the code the function is called.
        """
        if self.env.config['progress_bar']:
            block_progress_bar(self.progress_portion)
        self.env.send_status('user_input_add')
        empty_queued_input_data()
        answer = input(question)
        self.env.send_status('user_input_remove')

        if answer == '':  # default
            answer = PA.proceed.answer

        if answer.startswith('R') and PA.reload_index in allowed_options and len(answer) > 1:
            try:
                raise ReloadFromFile(index=self.index + int(answer[1:]))
            except ValueError:
                pass

        if answer not in [ao.answer for ao in allowed_options]:
            self.env.LOG.warning('Invalid input. Try again.')
            return self._ask_user_with_options(question=question, allowed_options=allowed_options)

        match answer:
            case PA.terminal.answer:
                print()
                self.env.LOG.notice('Starting interactive terminal shell')
                self._run_local_command(
                    f'AUTOMATIX_SHELL=True'
                    f' {self.bash_path}'
                    f' --rcfile <(cat ~/.bashrc ; echo "PS1=\\"{AUTOMATIX_PROMPT}\\"")'
                    f' -i'
                )

                return self._ask_user_with_options(question=question, allowed_options=allowed_options)
            case PA.debug_shell.answer:
                print()
                if 'readline' not in vars():
                    import readline  # noqa F401

                pyconsole_locals = self._get_python_globals()
                pyconsole_locals.update(self._get_python_locals())

                pyconsole = InteractiveConsole(pyconsole_locals)
                pyconsole.interact(banner=AUTOMATIX_PYTHON_BANNER, exitmsg=AUTOMATIX_PYTHON_EXITMSG)

                return self._ask_user_with_options(question=question, allowed_options=allowed_options)
            case PA.variables.answer:
                self.show_and_change_variables()
                return self._ask_user_with_options(question=question, allowed_options=allowed_options)
            case PA.abort.answer:
                raise AbortException(1)
            case PA.reload.answer:
                raise ReloadFromFile(index=self.index)
            case PA.abort_continue.answer:
                raise SkipBatchItemException()
            case PA.retry.answer | PA.skip.answer | PA.proceed.answer:
                return answer
            case _:
                raise RuntimeError(
                    'This should never happen!'
                    ' Please consult the maintainer and give details about your usage.'
                    ' Most likely this is a bug, which needs to be fixed.'
                )

    def _generate_python_vars(self) -> dict:
        # For BWCommand this method is overridden
        return {
            'a_vars': self.env.vars,  # deprecated, for backwards compatibility
            'VARS': self.env.vars,
        }

    def _get_python_locals(self) -> dict:
        locale_vars = {}
        locale_vars.update(PERSISTENT_VARS)
        self.env.LOG.debug(f'locals:\n {locale_vars}')
        return locale_vars

    def _get_python_globals(self) -> dict:
        global_vars = {
            # builtins are included anyway, if not defined here
            'CONST': ConstantsWrapper(self.env.config['constants']),
            'PERSISTENT_VARS': PERSISTENT_VARS,
            'PVARS': PVARS,
            'SCRIPT_FILE_PATH': self.env.script_file_path,
            'SYSTEMS': SystemsWrapper(self.env.systems),
            'AbortException': AbortException,
            'SkipBatchItemException': SkipBatchItemException,
        }
        global_vars.update(self._generate_python_vars())
        self.env.LOG.debug(f'globals:\n {global_vars}')
        return global_vars

    def _python_action(self) -> int:
        cmd = self.get_resolved_value()

        try:
            self.env.LOG.debug(f'Run python command: {cmd}')
            if self.assignment_var:
                exec(f'VARS["{self.assignment_var}"] = {cmd}', self._get_python_globals(), self._get_python_locals())
                self.env.LOG.info(f'Variable {self.assignment_var} = {repr(self.env.vars[self.assignment_var])}')
            else:
                exec(cmd, self._get_python_globals(), self._get_python_locals())
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
        process_environment = os.environ.copy()
        process_environment['RUNNING_INSIDE_AUTOMATIX'] = '1'
        self.env.LOG.debug(f'Executing: {repr(cmd)} with environment {repr(process_environment)}')
        if self.assignment_var:
            proc = subprocess.run(
                cmd,
                env=process_environment,
                executable=self.bash_path,
                shell=True,
                stdout=subprocess.PIPE,
            )
            output = proc.stdout.decode(self.env.config["encoding"])
            self.env.vars[self.assignment_var] = assigned_value = output.rstrip('\r\n')
            hint = ' (trailing newline removed)' if (output.endswith('\n') or output.endswith('\r')) else ''
            self.env.LOG.info(f'Variable {self.assignment_var} = "{assigned_value}"{hint}')
        else:
            proc = subprocess.run(
                cmd,
                env=process_environment,
                executable=self.bash_path,
                shell=True,
            )
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

        return f'{prefix}{ssh_cmd}{quote("RUNNING_INSIDE_AUTOMATIX=1 bash -c " + quote(remote_cmd))}'

    def _remote_handle_keyboard_interrupt(self, hostname: str):
        ssh_cmd = self.env.config["ssh_cmd"].format(hostname=hostname)

        try:
            ps_pids = self.get_remote_pids(hostname=hostname)
            while ps_pids:
                self.env.LOG.notice(
                    'Remote command seems still to be running! Found PIDs: {}'.format(','.join(ps_pids))
                )
                if len(ps_pids) > 1:
                    self.env.LOG.warning(
                        'WARNING: Normally there should be at most 1 Automatix process on the system.'
                        f' We found {len(ps_pids)} !!! \n\nThis might be a sign,'
                        ' that PID determination did nasty things and returned the wrong process IDs.'
                        ' Please double check the PIDs and proceed very carefully!\n\n'
                        'If the determination is correct and you have other Automatix commands running in'
                        ' parallel or in background, be aware that the signals chosen are sent to ALL'
                        ' identified processes. This is probably not what you want!'
                    )
                self.env.send_status('user_input_add')
                empty_queued_input_data()
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

                ps_pids = self.get_remote_pids(hostname=hostname)
        except subprocess.CalledProcessError:
            self.env.LOG.warning('Could not check for remaining remote processes.')

        self.env.LOG.info('Keystroke interrupt handled.\n')

    def get_remote_pids(self, hostname) -> list:
        ps_cmd = "ps axu | grep RUNNING_INSIDE_AUTOMATIX | grep -v 'grep' | awk '{print $2}'"
        remote_ps_cmd = f'ssh {hostname} {quote(ps_cmd)} 2>&1'
        pids = subprocess.check_output(
            remote_ps_cmd,
            shell=True,
            executable=self.bash_path,
        ).decode(self.env.config["encoding"]).split()

        return pids

    def _remote_cleanup_imports(self, hostname: str):
        ssh_cmd = self.env.config["ssh_cmd"].format(hostname=hostname)
        cleanup_cmd = f'{ssh_cmd} rm -r {self.env.config["remote_tmp_dir"]}'
        self.env.LOG.debug(f'Executing: {cleanup_cmd}')
        proc = subprocess.run(cleanup_cmd, shell=True, executable=self.bash_path)
        if proc.returncode != 0:
            self.env.LOG.warning(
                'Failed to remove {tmp_dir}, exitcode: {return_code}'.format(
                    tmp_dir=self.env.config["remote_tmp_dir"],
                    return_code=proc.returncode,
                )
            )


def parse_key(key) -> tuple[str, ...]:
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
