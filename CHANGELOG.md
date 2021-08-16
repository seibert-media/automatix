# Changelog

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
