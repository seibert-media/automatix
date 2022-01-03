import locale
import subprocess


def _call(*args, **kwargs):
    try:
        return subprocess.check_output(*args, **kwargs).decode(locale.getpreferredencoding()).splitlines()
    except subprocess.CalledProcessError:
        return []


class ScriptFileCompleter(object):
    """
    Scriptfile completer
    """
    def __init__(self, script_path: str):
        self.script_path = script_path

    def __call__(self, prefix, **kwargs):
        completion = []
        directories = _call(["bash", "-c", f"compgen -A directory -- '{self.script_path}/{prefix}'"])
        completion += [f'{d}/' for d in directories]
        for ext in ['yaml', 'yml']:
            files = _call(["bash", "-c", f"compgen -A file -X '!*.{ext}' -- '{self.script_path}/{prefix}'"])
            completion += [f[len(self.script_path)+1:] for f in files]

        return completion
