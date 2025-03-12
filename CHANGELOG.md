# Changelog

# 2.6.1
- Fix: Reloading while using steps

# 2.6.0
- Backport changes from fork
- Adjustments due to backporting
- Refactoring: answer options in command.py
- Python action: Make `SYSTEMS` and `CONST` directly available
- Python action: Path to executed script file available as `SCRIPT_FILE_PATH`
- Python action: Automatix variables are now available as `VARS`, replacing `a_vars` (now deprecated)

# 2.5.0
- Add fine tuning for required version

# 2.4.0
- Feature: Add RUNNING_INSIDE_AUTOMATIX as environment variable for shell actions
- Feature: Python debug shell option
- Refactoring Python action
- Python action: Global variables are not persistent through commands any longer. Please use PERSISTENT_VARS.
- Python action: Global imported modules/functions/objects are not available without import any longer (re, quote, ...)
- Python action: Automatix variables are now available as `a_vars`, replacing `vars` which was shadowing the builtin `vars()` function

# 2.3.1 / 2.3.2
- Add check for proper screen version for parallel processing
- Fix: explanation URL

# 2.3.0
- Feature: Make Bash path configurable
- Feature: Overwriting configuration by environment variables also for `boolean` type.
- Refactoring: Integrate progress bar and refactor. External library is not needed anymore.

# 2.2.1
- Fix: Crash with parallel processing and Bundlewrap support enabled

# 2.2.0
- Feature: Option to change variables at runtime
- Warning for conflicting automatix package

# 2.1.0
- Logging to file for parallel processing and logging section in TIPS & TRICKS
- Overwriting configuration by environment variables for all configuration values of `string` type.

# 2.0.1
- Adjusted github workflow

# 2.0.0
- Decoupled from original repository
- Rename repo and package: automatix -> automatix_cmd
- Fix: Manual steps failed always
- Feature: Interactive shell
- Feature: Progress bar
- Feature: Parallel processing
- Removed deprecated const_, system_ and _node variables (deprecation warnings still remain as hint)

# 1.16.1
- Fixup for previous release

# 1.16.0
- Feature: add environment variable `RUNNING_INSIDE_AUTOMATIX=1`
- Fix: Manual steps always failing

# 1.15.0
- Feature: Option to invert conditions
- Feature: Catch script syntax/parsing errors and offer file reload
- Refactor command.py to reduce complexity

# 1.14.0
- Feature: Remove trailing new lines in Shell command assignments
- Feature: Possibility to change index on reload from file
- Fix: Return returncode for non-Bundlewrap remote action

# 1.13.0
- Python 3.8 is now required
- Feature: Reload from file during runtime

# 1.12.1
- Fix warning for not existing node

# 1.12.0
- Feature: select or exclude specific pipeline steps by index
- Feature: remote commands for Bundlewrap groups

# 1.11.2
- No changes, just to test auto deployment

# 1.11.1
- Fix default value for BW_REPO_PATH

# 1.11.0
- require_version to specify minimum required Automatix version for a script

# 1.10.0
- Feature PERSISTENT_VARS:
  - attribute notation and PVARS as shortcut
  - conditional use with PVARS and attribute notation

# 1.9.0
- Feature: Tab completion for bash (and other shells)
- Expand environment variables in config and script paths

# 1.8.2
- Inform user about Bundlewrap related Errors
- Fix syntax validation for Bundlewrap nodes
- Only allow listed answers and re-ask if invalid

# 1.8.1
- Make compatible with PyYAML6

# 1.8.0

- Introduce SYSTEMS, CONST and NODES as replacement for system_, const_ and _node
- Validator and warnings for deprecated syntax

# 1.7.0

- Add `hostname!` option to define non-Bundlewrap systems

# 1.6.0

- Allow Bundlewrap nodes to be defined at runtime (only fail, if undefined node is used)

# 1.5.0

- Make Bundlewrap repository avaiable in Python commands (AUTOMATIX_BW_REPO)

# 1.4.2

- Only offer c:continue in batch_mode
- Avoid multiline questions

# 1.4.0 / 1.4.1

- Introduce SkipBatchItemException
- Python: SkipBatchItemException and AbortException available
- Bugfix: Clear PERSISTENT_VARS for batch processing

# 1.3.0

- Introduce batch processing via CSV files
- Restructure internal code

# 1.2.2

- Treat empty condition_var as False

# 1.2.1

- Bug fix: Expand user for file paths

# 1.2.0

- Add FILE_ feature for variables
- Add time printing feature

# 1.1.0
- Add conditions

# 1.0.1
- Fix command-line assignment of variables

# 1.0.0

- First major release since Automatix seems to be stable
- Add PERSISTENT_VARS
- Newlines for input prompts, which simplifies automatic testing with automatix scripts

# 0.1.1

- Improve README: Add Usage Example
- Fix redundant code
- Add stack traces in error case
- Minor refactorings

# 0.1.0

- Refactor main functions
- Add documentation

# 0.0.5

- Add warning to README

# 0.0.4

- Add AUTOMATIX_SCRIPT_DIR
- Improve performance (by reducing multiple imports)

# 0.0.3

- Add bundlewrap, teamvault and custom logging support

# 0.0.2

- Add basic functionality

# 0.0.1

- Initial Development Version
