from argparse import Namespace

from . import get_script, collect_vars, CONFIG, cmdClass, SCRIPT_FIELDS
from .automatix import Automatix

default_args = Namespace(
    scriptfile='tests/test.yaml',
    systems=None,
    vars=None,
    secrets=None,
    print_overview=False,
    jump_to=0,
    interactive=False,
    force=False,
    debug=False,
)

script = get_script(args=default_args)

variables = collect_vars(script=script)

testauto = Automatix(
    script=script,
    variables=variables,
    config=CONFIG,
    cmd_class=cmdClass,
    script_fields=SCRIPT_FIELDS,
)

environment = testauto.env
