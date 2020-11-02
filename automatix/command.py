import os
import re
import subprocess
import traceback

from shlex import quote
from time import time
from typing import Tuple

from .environment import PipelineEnvironment

PERSISTENT_VARS = {}


class Command:
    def __init__(self, pipeline_cmd: dict, index: int, env: PipelineEnvironment):
        self.pipeline_cmd = pipeline_cmd
        self.index = index
        self.env = env

        for key, value in pipeline_cmd.items():
            self.orig_key = key
            self.condition_var, self.assignment_var, self.key = parse_key(key=key)
            if isinstance(value, dict):
                # We need this workaround because the yaml lib returns a dictionary instead of a string,
                # if there is nothing but a variable in the command. Alternative is to use quotes in the script yaml.
                self.value = f'{{{next(iter(value))}}}'
            else:
                self.value = value
            break  # There should be only one entry in pipeline_cmd

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

        for key, value in self.env.config['constants'].items():
            variables[f'const_{key}'] = value
        return self.value.format(**variables)

    def execute(self, interactive: bool = False, force: bool = False):
        self.env.LOG.notice(f'\n({self.index}) [{self.orig_key}]: {self.get_resolved_value()}')
        return_code = 0

        if self.condition_var is not None and not bool(self.env.vars.get(self.condition_var, False)):
            self.env.LOG.info(f'Skip command, because condition variable "{self.condition_var}" evolves to False')
            return

        if self.get_type() == 'manual' or interactive:
            self.env.LOG.debug('Ask for user interaction.')

            options = 'p: proceed (default), s: skip, a: abort'
            if self.env.batch_mode:
                options += ', c: abort & continue to next (CSV processing)'

            answer = input(f'[MS] Proceed? ({options})')
            if answer == 's':
                return
            if answer == 'a':
                raise AbortException(1)
            if self.env.batch_mode and answer == 'c':
                raise SkipBatchItemException()

        steptime = time()

        if self.get_type() == 'local':
            return_code = self._local_action()
        if self.get_type() == 'python':
            return_code = self._python_action()
        if self.get_type() == 'remote':
            return_code = self._remote_action()

        if 'AUTOMATIX_TIME' in os.environ:
            self.env.LOG.info(f'(command execution time: {round(time() - steptime)}s)')

        if return_code != 0:
            self.env.LOG.error(f'>> {self.env.name} << Command ({self.index}) failed with return code {return_code}.')
            if force:
                return

            err_options = 'p: proceed (default), r: retry, a: abort'
            if self.env.batch_mode:
                err_options += ', c: abort & continue to next (CSV processing)'

            err_answer = input(f'[CF] What should I do? ({err_options})')
            if err_answer == 'r':
                return self.execute(interactive)
            if err_answer == 'a':
                raise AbortException(return_code)
            if self.env.batch_mode and err_answer == 'c':
                raise SkipBatchItemException()

    def _local_action(self) -> int:
        cmd = self._build_command(path=self.env.config['import_path'])
        try:
            return self._run_local_command(cmd=cmd)
        except KeyboardInterrupt:
            self.env.LOG.info('Abort command by user key stroke. Exit code is set to 130.')
            return 130

    def _generate_python_vars(self):
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
                self.env.LOG.info(f'Variable {self.assignment_var} = {self.env.vars[self.assignment_var]}')
            else:
                exec(cmd, globals(), locale_vars)
            return 0
        except (AbortException, SkipBatchItemException):
            raise
        except KeyboardInterrupt:
            self.env.LOG.info('Abort command by user key stroke. Exit code is set to 130.')
            return 130
        except Exception:
            self.env.LOG.error(traceback.format_exc())
            return 1

    def _get_remote_hostname(self):
        return self.get_system()

    def _remote_action(self) -> int:
        hostname = self._get_remote_hostname()

        ssh_cmd = self.env.config["ssh_cmd"].format(hostname=hostname)
        remote_cmd = self.get_resolved_value()
        prefix = ''
        if self.env.imports:
            prefix = f'tar -C {self.env.config["import_path"]} -cf - ' + ' '.join(self.env.imports) + ' | '
            remote_cmd = f'mkdir {self.env.config["remote_tmp_dir"]};' \
                         f' tar -C {self.env.config["remote_tmp_dir"]} -xf -;' \
                         f' {self._build_command(path=self.env.config["remote_tmp_dir"])}'

        cmd = f'{prefix}{ssh_cmd}{quote("bash -c " + quote(remote_cmd))}'

        try:
            exitcode = self._run_local_command(cmd=cmd)
        except KeyboardInterrupt:
            self.env.LOG.info('Abort command by user key stroke. Exit code is set to 130.')
            exitcode = 130

            try:
                ps_pids = self.get_remote_pids(hostname=hostname, cmd=self.get_resolved_value())
                while ps_pids:
                    self.env.LOG.notice(
                        'Remote command seems still to be running! Found PIDs: {}'.format(','.join(ps_pids))
                    )
                    answer = input(
                        '[RR] What should I do? '
                        '(i: send SIGINT (default), t: send SIGTERM, k: send SIGKILL, p: do nothing and proceed) \n')

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

        if self.env.imports:
            cleanup_cmd = f'{ssh_cmd} rm -r {self.env.config["remote_tmp_dir"]}'
            self.env.LOG.debug(f'Executing: {cleanup_cmd}')
            proc = subprocess.run(cleanup_cmd, shell=True, executable='/bin/bash')
            if proc.returncode != 0:
                self.env.LOG.warning(
                    'Failed to remove {tmp_dir}, exitcode: {return_code}'.format(
                        tmp_dir=self.env.config["remote_tmp_dir"],
                        return_code=proc.returncode,
                    )
                )

        return exitcode

    def _build_command(self, path: str) -> str:
        if not self.env.imports:
            return self.get_resolved_value()
        return f'. {path}/' + f'; . {path}/'.join(self.env.imports) + '; ' + self.get_resolved_value()

    def _run_local_command(self, cmd: str) -> int:
        self.env.LOG.debug(f'Executing: {cmd}')
        if self.assignment_var:
            proc = subprocess.run(cmd, shell=True, executable='/bin/bash', stdout=subprocess.PIPE)
            output = proc.stdout.decode(self.env.config["encoding"])
            self.env.vars[self.assignment_var] = output
            self.env.LOG.info(f'Variable {self.assignment_var} = {output}')
        else:
            proc = subprocess.run(cmd, shell=True, executable='/bin/bash')
        return proc.returncode

    def get_remote_pids(self, hostname, cmd) -> []:
        ps_cmd = f"ps axu | grep {quote(cmd)} | grep -v 'grep' | awk '{{print $2}}'"
        cmd = f'ssh {hostname} {quote(ps_cmd)} 2>&1'
        pids = subprocess.check_output(
            cmd,
            shell=True,
            executable='/bin/bash'
        ).decode(self.env.config["encoding"]).split()

        return pids


def parse_key(key) -> Tuple[str, ...]:
    """
    parses the key

    returns a list containing:
    - condition_var: if this evolves to False, the command is not executed
    - assignment_var: name of a variable, to which the command output is assigned
    - command_type
    """

    return re.search(r'((.*)\?)?((.*)=)?(.*)', key).group(2, 4, 5)


class AbortException(Exception):
    def __init__(self, return_code: int):
        self.return_code = return_code

    def __int__(self):
        return self.return_code


class SkipBatchItemException(Exception):
    pass


class UnknownCommandException(Exception):
    pass
