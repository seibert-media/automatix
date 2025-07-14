import locale
import os
import subprocess
from argparse import Action, Namespace

from argcomplete import warn

from .helpers import read_yaml


def _call(*args, **kwargs):
    try:
        return subprocess.check_output(*args, **kwargs).decode(locale.getpreferredencoding()).splitlines()
    except subprocess.CalledProcessError:
        return []


class ScriptFileCompleter:
    """
    Scriptfile completer
    """

    def __init__(self, script_dir: str):
        self.script_dir = script_dir

    def __call__(self, prefix: str, **kwargs):
        completion = []
        try:
            completion.extend(self.find_dirs_and_files(root_path='.', prefix=prefix))
            completion.extend(self.find_dirs_and_files(root_path=self.script_dir, prefix=prefix))
        except Exception as exc:
            warn(f'Shell completion failed: {repr(exc)}')
        return completion

    def find_dirs_and_files(self, root_path: str, prefix: str) -> list:
        completion = []
        pre_len = len(root_path) + 1
        directories = _call(["bash", "-c", f"compgen -A directory -- '{root_path}/{prefix}'"])
        completion += [f'{d[pre_len:]}/' for d in directories]
        for ext in ['yaml', 'yml']:
            files = _call(["bash", "-c", f"compgen -A file -X '!*.{ext}' -- '{root_path}/{prefix}'"])
            completion += [f[pre_len:] for f in files]
        return completion


class ScriptFieldCompleter:
    def __init__(self, script_dir: str):
        self.script_dir = script_dir

    def __call__(self, action: Action, parsed_args: Namespace, **kwargs):
        try:
            if parsed_args.scriptfile is None:
                return []

            s_file = parsed_args.scriptfile
            if not os.path.isfile(parsed_args.scriptfile):
                s_file = f'{self.script_dir}/{parsed_args.scriptfile}'

            script = read_yaml(s_file)
            completion = [f'{key}=' for key in script.get(action.dest, {}).keys()]

            return completion
        except Exception as exc:
            warn(f'Shell completion failed: {repr(exc)}')
            return []
