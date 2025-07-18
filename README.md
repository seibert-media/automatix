# automatix
Automation wrapper for bash and python commands. Extended Features version.


# DESCRIPTION

**automatix** is a wrapper for scripted sysadmin tasks. It offers
 some useful functionality for easier scripting and having full
 control over the automated process.

The idea of **automatix** is to write down all the commands you would
 normally type to your commandline or python console into a YAML file.
 Then use **automatix** to execute these commands. 

There are different modes for **automatix** to work. Without any
 parameters automatix will try to execute the specified command
 pipeline from the script file until an error occurs or the pipeline
 is done. The interactive mode (**-i**) asks for every single
 commandline step whether to execute, skip or abort.
 Forced mode (**-f**) will also proceed if errors occur.

**automatix** was originally designed for internal Seibert Group use.
 It comes therefore with bundlewrap and teamvault support as well as
 the possibility to use your own logging library.

## Warning:

Beware that this tool cannot substitute the system administrators
 brain and it needs a responsible handling, since you can do
 (and destroy) almost everything with it.

**Automatix** evaluates YAML files and executes defined commands as
 shell or python commands. There is no check for harmful commands.
 Be aware that this can cause critical damage to your system.

Please use the interactive mode and doublecheck commands before
 executing. Usage of automatix is at your own risk!


# INSTALLATION

Automatix requires Python &ge; 3.10.

```
pip install automatix
```

NOTICE: original `automatix` and `automatix_cmd` share the
same main entrypoint. To avoid overwriting and confusion,
you should have only installed **ONE** of them!

# CONFIGURATION

You can specify a path to a configuration YAML file via the
 environment variable **AUTOMATIX_CONFIG**.
Default location is "~/.automatix.cfg.yaml".
All (string) configuration values can be overwritten by the
 corresponding upper case environment variables preceeded
 by 'AUTOMATIX_', e.g. _AUTOMATIX_ENCODING_.

### Example: .automatix.cfg.yaml

    # Path to scripts directory
    script_dir: '~/automatix_script_files'
    
    # Global constants for use in pipeline scripts
    constants:
      apt_update: 'apt-get -qy update'
      apt_upgrade: 'DEBIAN_FRONTEND=noninteractive apt-get -qy -o Dpkg::Options::=--force-confold --no-install-recommends upgrade'
      apt_full_upgrade: 'DEBIAN_FRONTEND=noninteractive apt-get -qy -o Dpkg::Options::=--force-confold --no-install-recommends full-upgrade'
    
    # Encoding
    encoding: 'utf-8'
    
    # Path for shell imports
    import_path: '.'

    # Path to local bash (default: /bin/bash)
    bash_path: '/bin/bash'
    
    # SSH Command used for remote connections
    ssh_cmd: 'ssh {hostname} sudo '
    
    # Temporary directory on remote machines for shell imports
    remote_tmp_dir: 'automatix_tmp'
    
    # Logger
    logger: 'mylogger'
    
    # Logging library (has to implement the init_logger method)
    logging_lib: 'mylib.logging'

    # Logfile directory for parallel processing (ONLY for parallel processing!)
    logfile_dir: 'automatix_logs'
    
    # Bundlewrap support, bundlewrap has to be installed (default: false)
    bundlewrap: true
    
    # Teamvault / Secret support, bundlewrap-teamvault has to be installed (default: false)
    teamvault: true

    # Activate progress bar, python_progress_bar has to be installed (default: false)
    progress_bar: true

    # Startup script, which is triggered on every start of Automatix.
    # The whole Automatix call with all arguments is passed through as arguments.
    startup_script: '/some/path/bin/automatix_startup.sh'

# SYNOPSIS

**automatix**
      \[**--help**|**-h**\]
      \[**--systems** \[_SYSTEM1=ADDRESS_OR_NODENAME_ ...\]\]
      \[**--vars** \[_VAR1=VALUE1_ ...\]\]
      \[**--secrets** \[_SECRET1=SECRETID_ ...\]\]
      \[**--vars-file** _VARS_FILE_PATH_ \]
      \[**--print-overview**|**-p**\]
      \[**--jump-to**|**-j** _JUMP_TO_\]
      \[**--steps**|**-s** _STEPS_\]
      \[**--interactive**|**-i**\]
      \[**--force**|**-f**\]
      \[**--debug**|**-d**\]
      \[**--**\] **scriptfile**


## OPTIONS

**scriptfile**
: The only required parameter for this tool to work. Use " -- " if
 needed to delimit this from argument fields. See **SCRIPTFILE**
 section for more information.  

**-h**, **--help**
: View help message and exit.  

**--systems** _SYSTEM1=ADDRESS_OR_NODENAME_
: Use this to set systems without adding them to the
  scriptfile or to overwrite them. You can specify multiple
  systems like: --systems v1=string1 v2=string2 v3=string3  
  
**--vars** _VAR1=VALUE1_
: Use this to set vars without adding them to the scriptfile
  or to overwrite them. You can specify multiple vars
  like: --vars v1=string1 v2=string2 v3=string3  
  
**--secrets** _SECRET1=SECRETID_
: Use this to set secrets without adding them to the
  scriptfile or to overwrite them. You can specify multiple
  secrets like: --secrets v1=string1 v2=string2 v3=string3 *(only if
  teamvault is enabled)*  
  
**--vars-file** _VARS_FILE_PATH_
: Use this to specify a CSV file from where **automatix** reads
  systems, variables and secrets. First row must contain the field
  types and names. You may also specify an `label` and `group` field.
  
  The `label` field can be to achieve a better overview and which row
  is currently executed. It is used, when printing error messages or
  as status line in screens for parallel processing. Without label
  the row number is displayed.

  The `group` field is only relevant for parallel processing. Row of
  the same group are grouped together in a single screen and processed
  sequentially there. Different groups are processed parallel.
  Rows without specified group are run each in a parallel screen.
  These rows are processed after the groups.

  Example header: `label,group,systems:mysystem,vars:myvar`.
  
**--parallel**
: Run CSV file entries parallel in screen sessions; only valid with --vars-file.
  GNU screen has to be installed. See EXTRAS section below.

**--print-overview**, **-p**
: Just print command pipeline overview with indices then exit without
 executing the commandline. Note that the *always pipeline* will be
 executed anyway.  

**--jump-to** _JUMP_TO_, **-j** _JUMP_TO_
: Jump to step with index _JUMP_TO_ instead of starting at the
 beginning. Use this option without argument to get an interactive selection.
 You can also use negative numbers to start counting from the end.  

**--steps** _STEPS_, **-s** _STEPS_
: Only execute these steps (comma-separated indices) or exclude steps
 by prepending the comma-separated list with "e".
 Examples: `-s 1,3,7`, `-s e2`, `-s e0,5,7,2`  

**--interactive**, **-i**
: Confirm actions before executing.  
  
**--force**, **-f**
: Try always to proceed (except manual steps), even if errors occur
 (no retries).  

**--debug**, **-d**
: Activate debug log level.  


### EXAMPLE: Usage

    automatix -i --systems source=sourcesystem.com target=targetsystem.org -- scriptfile.yaml


## SCRIPTFILE

The **scriptfile** describes your automated process. Therefore it
 contains information about systems, variables, secrets and the
 command pipeline.

You can provide a path to your **scriptfile** or place your
 scriptfile in the predefined directory (see **CONFIGURATION**
 section, _script_dir_). The path has precedence over the predefined
 directory, if the file exists at both locations.

The **scriptfile** has to contain valid YAML.

### EXAMPLE: scriptfile
    
    name: Migration Server XY
    # Systems you like to refer to in pipeline (accessible via 'SYSTEMS.source')
    # If Bundlewrap support is activated use node names instead of hostnames or add preceeding 'hostname!'.
    require_version: '1.5.0'
    systems:
      source: sourcesystem.com
      target: targetsystem.org
    # Custom vars to use in pipeline
    vars:
      version: 1.2.3
      domain: 'bla.mein-test-system'
    # Teamvault Secrets, if activated (left: like vars, right: SECRETID_FIELD, FIELD=username|password|file)
    secrets:
      web_user: v6GQag_username
      web_pw: v6GQag_password
    # Imports for functions you like to use (path may be modified in configuration)
    imports:
      - myfunctions.sh
    # like command pipeline but will be exectuted always beforehand
    always:
      - python: |
          import mylib as nc
          PERSISTENT_VARS.update(locals())
    pipeline:
      - remote@target: systemctl stop server
      - remote@source: zfs snapshot -r tank@before-migration
      - manual: Please trigger preparing tasks via webinterface
      - myvar=local: curl -L -vvv -k https://{domain}/
      - local: echo "1.1.1.1 {domain}" >> /etc/hosts
      - sla=python: NODES.source.metadata.get('sla')
      - python: |
            sla = '{sla}'
            if sla == 'gold':
                print('Wow that\'s pretty cool. You have SLA Gold.')
            else:
                print('Oh. Running out of money? SLA Gold is worth it. You should check your wallet.')
            PERSISTENT_VARS['sla'] = sla
      - cond=python: sla == 'gold'
      - cond?local: echo "This command is only executed if sla is gold."
    cleanup:
      - local: rm temp_files


### FIELDS

**name** _(string)_
: Just a name for the process. Does not do anything.

**require_version** _(string)_
: The required Automatix version for this script to run. Similar to the
 [Python version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/#version-specifiers).
 Multiple conditions can be separated by comma. Allowed operators are: "==","!=",">=" (default),"<=",">","<","~="

**systems** _(associative array)_
: Define some systems. Value has to be a valid SSH destination like an
 IP address or hostname. If Bundlewrap support is enabled, it has to
 be a valid and existing Bundlewrap node or group name, or you can 
 precede your IP or hostname with `hostname!` to define a
 non-Bundlewrap system.
You can refer to these systems in the command pipeline in multiple ways:

1) remote@systemname as your command action (see below)

2) via {SYSTEMS.systemname} which will be replaced with the value

3) via SYSTEMS.systemname in python actions which contains the value

4) via NODES.systemname in python actions to use the Bundlewrap node
   object (Bundlewrap nodes only, no groups)

**vars** _(associative array)_
: Define some vars. These are accessible in the command pipeline via
 {varname}. Note: Only valid Python variable names are allowed.
 You can use "*FILE_*" prefix followed by a file path to assign the file
 content to the variable, e.g. `myvar: FILE_/path/to/file`.
 In python actions you can access these variables directly via `VARS.varname`.

**secrets** _(associative array)_
: Define teamvault secrets. Value has to be in this format:
 _SECRETID_FIELD_. _FIELD_ must be one of username, password or file.
 The resolved secret values are accessible in command line via
 {secretname}. *(only if teamvault is enabled)*

**imports** _(list)_
: Listed shell files (see **CONFIGURATION** section, _import_path_)
 will be sourced before every local or remote command execution.
 For remote commands, these files are transferred via tar and ssh to
 your home directory on the remote system beforehand and deleted
 afterwards. This is meant to define some functions you may need.

**always**, **cleanup** _(list of associative arrays)_
: See **ALWAYS / CLEANUP PIPELINE** section.

**pipeline** _(list of associative arrays)_
: See **PIPELINE** section.

### PIPELINE

Here you define the commands automatix shall execute.

**KEY**: One of these possible command actions:

1) **manual**: Some manual instruction for the user. The user has to
 confirm, that automatix may proceed.

2) **local**: Local shell command to execute. Imports will be sourced
 beforehand. The Bash specified in `bash_path` (default: /bin/bash) will
 be used for execution. The environment is inherited with additional
 **RUNNING_INSIDE_AUTOMATIX** set to 1.

3) **remote@systemname**: Remote shell command to execute. Systemname
 has to be a defined system. The command will be run via SSH (without
  pseudo-terminal allocation). It uses the standard SSH command.
  Therefore your .ssh/config should be respected.
 If systemname is a Bundlewrap group, the remote command will be
  executed sequentially for every node.

4) **python**: Python code to execute.
   * `PERSISTENT_VARS`, `PVARS`, `SkipBatchItemException`, `AbortException`
     are available, see corresponding sections in **TIPS & TRICKS** 
   * Notice that the variable `VARS` (deprecated `a_vars`) contains
     the Automatix variables as a dictionary. `VARS` supports also
     the attribute notation like `VARS.myvariable`. You can use it 
     to access or change the variables directly.
   * The path to the executed script file is available as `SCRIPT_FILE_PATH`.
   * You can refer to systems and constants via `SYSTEMS.systemname`
     and `CONST.constantname`.
   * If bundlewrap is enabled, the Bundlewrap repository object is
     available via `AUTOMATIX_BW_REPO` and system node objects are
     available via `NODES.systemname` (replace "systemname").
     Use `AUTOMATIX_BW_REPO.reload()` to reinitialize the Bundlewrap 
     repository from the file system. This can be useful for using
     newly created nodes (e.g. remote commands).  
   

**ASSIGNMENT**: For **local**, **remote** and **python** action you
 can also define a variable to which the output will be assigned.
 To do this prefix the desired variablename and = before the action
 key, e.g. `myvar=python: NODES.system.hostname`. Be careful when
 working with multiline statements. In **python** the first line is
 likely to set the variable. All variables will be converted to
 strings when used to build commands in following steps.
 
**CONDITIONS**: You can define the command only to be executed if
 your condition variable evaluates to "True" in Python. To achieve
 this write the variable name followed by a question mark at the very
 beginning like `cond?python: destroy_system()`. Be aware that all
 output from **local** or **remote** commands will lead to a non-empty
 string which evaluates to "True" in Python, but empty output will
 evaluate to "False". Use `!?` instead of `?` to invert the condition.

**VALUE**: Your command. Variables will be replaced with Python
 format function. Therefore, use curly brackets to refer to variables,
 systems, secrets and constants.

Constants are available via CONST.KEY, where KEY is the key of your
 constants in your **CONFIGURATION** file. There you can define some
 widely used constants.

In most cases its a good idea to define your command in quotes to
 avoid parsing errors, but it is not always necessary. Another way is
 to use '|' to indicate a _literal scalar block_. There you can even
 define whole program structures for python (see example).

#### Escaping in Pipeline

Because automatix uses Python's format() function:  
`{` -> `{{`  
`}` ->  `}}`  

Standard YAML escapes (see also https://yaml.org/spec/1.2/spec.html):  
`'` -> `''`  
`"` -> `\"`  
`\ ` -> `\\`  
`:` -> Please use quotes (double or single).


### ALWAYS / CLEANUP PIPELINE

Same usage as the 'normal' command pipeline, but will be executed
 every time at start of automatix (**always**) or at the end
 (**cleanup**) even if aborted (a). The commands are executed without
 --interactive flag, independend of the specified parameters.

Intended use case for **always**: python imports or informations that
 are needed afterwards and do not change anything on systems.
 You want to have these available even if using --jump|-j feature.

Intended use case for **cleanup**: Remove temporary files or artifacts.


## ENVIRONMENT

**AUTOMATIX_CONFIG**: Specify the path to the configuration file.
 Default is "~/.automatix.cfg.yaml".  

**AUTOMATIX_**_config-variable-in-upper-case_: Set or overwrite the 
 corresponding configuration value. See **CONFIGURATION** section.
 Works only for string and boolean values!
 String values (case-insensitive 'true' or 'false') are converted
 to `True` or `False` in Python, if the fields expects a boolean.
 **All other values (int, float, dict, list, ...) are ignored!**

**AUTOMATIX_TIME**: Set this to an arbitrary value to print the times
 for the single steps and the whole script, e.g. `AUTOMATIX_TIME=true`.


# TIPS & TRICKS

### YAML Syntax

For multiline commands and variables YAML offers different possibilities
 to write multiline strings. A look at https://yaml-multiline.info/ might
 be helpful.  

### PERSISTENT_VARS

If you want to access variables in **python** action you defined in
preceeding command, you can use the **PERSISTENT_VARS** dictionary
(shortcut: **PVARS**).
This is added to the local scope of **python** actions and the
dictonary keys are also available as attributes.
 Examples:
- To make all local variables of the actual command persistent use
 `PERSISTENT_VARS.update(locals())`.
- To delete one persistent variable named "myvar" use
 `del PERSISTENT_VARS['myvar']`
- To make variable "v2" persistent use `PERSISTENT_VARS['v2'] = v2`
  or `PERSISTENT_VARS.v2 = v2`
- Use the shortcut like `PVARS.v2 = v2`

You can use variables in PERSISTENT_VARS also as condition by
using the shortcut and the attribute notation:
    
      - python: PVARS.cond = some_function()
      - PVARS.cond?local: echo 'This is only printed if "some_function" evaluates to "True"'
      - PVARS.cond!?local: echo 'And this is printed if "some_function" evaluates to "False"'

Since version 2.4.0 making variables global does not work any longer!

### Abort and Skip Exceptions

To abort the current automatix and jump to the next batch item you can
 raise the `SkipBatchItemException`. For aborting the whole automatix
 process raise `AbortException(return_code: int)`. In both cases the
 cleanup pipeline is executed. Same is the case for selecting
 `a`:abort or `c`:continue when asked (interactive or error).

### Logging / Saving the output

**automatix** offers no own capability to log the output to a log file or
 save it otherwise.  

If you have _GNU screen_ installed, you may start a screen session with
 `-L` and optional `-Logfile LOGFILE` in which you start **automatix**.
 (This is how it works with "parallel processing", see **EXTRAS** section.)

A different approach is to use `tee`, e.g. `automatix [script file + options] 2>&1 | tee auto.log`.
 Different to the screen approach this seems not to capture your input.

# BEST PRACTISES

There are different ways to start scripting with **automatix**. The
 author's approach is mainly to consider the process and simply write
 down, what to do (manual steps for complex or not automated steps)
 and which commands to use.  
Then start **automatix** in interactive mode (-i) and adjust the
 single steps one by one. Replace manual steps, if suitable. Whenever
 adjustment is needed, abort, adjust and restart **automatix** with
 jump (-j) to the adjusted step.  
From **automatix** 1.13.0 on you can use the reload scriptfile feature
 instead. When asked for options (either because a command failed or
 you are in interactive mode) you can use **-R** to reload the
 scriptfile. If lines in the scriptfile have changed, or you need to
 repeat steps, you can use R+/-$number to reload and adjust the
 restart point (available since **automatix** 1.14.0). NOTICE: If using
 vars-file, this reloads the script ONLY the active CSV row!

Repeat this procedure to automate more and more and increase quality,
 whenever you feel like it.

Consider to put often used paths or code sequences in automatix
 variables for better readability.  
Do the same with variable content like URLs, to make it possible to
 overwrite it by command line options. Where ever possible prefer to
 use functions to determine already available information, such as BW
 metadata, instead of defining things explicitly. This will make
 things easier when using the script with different systems /
 parameters.

Preferred way of using **automatix** is to put often used and complex
 algorithms in shell functions or python libraries (shelllib/pylib)
 and import them. Advantage of this approach is that you can use your
 implemented functions multiple times and build up a toolbox of nice
 functionality over time.


# NOTES

**Manual steps** will always cause automatix to stop and wait for
 user input.

Be careful with **assignments** containing line breaks (echo, ...).
 Using the variables may lead to unexpected behaviour or errors.
 From version 1.14.0 on trailing new lines in **assignments**
 of Shell commands (_local_, _remote@_) are removed.

Assignments containing **null bytes** are currently not supported.

Because the **always** pipeline should not change anything, aborting
 while running this pipeline will not trigger a cleanup.

If you want to abort the **pipeline** without triggering the
 **cleanup** pipeline, use CRTL+C.

While **aborting remote functions** (via imports), automatix is not
 able to determine still running processes invoked by the function,
 because it only checks the processes for the commands (in this case
 the function name) which is called in the pipeline.

User input questions are of following categories:
- [MS] **M**anual **S**tep
- [CF] **C**ommand **F**ailed
- [PF] **P**artial command **F**ailed (BW groups)
- [RR] **R**emote process still **R**unning
- [SE] **S**yntax **E**rror

The terminal (T) answer starts an interactive Bash-Shell.
 Therefore .bashrc is executed, but the command prompt (PS1) is
 replaced to indicate, that we are still in an automatix process.
 

# EXTRAS

## Parallel processing
Requirement: GNU screen installed and accessible via `screen` command in bash.

This **automatix** version has the option to process multiple **automatix** instances at a time.
 This is achieved by starting multiple [GNU screen](https://www.gnu.org/software/screen/) sessions.
 Please make yourself comfortable with the screen controls before using this feature to avoid getting lost.

The main programm stays in a loop while attaching to the screen sessions and you will come back to it
 if you detach a screen session. The **automatix-manager** runs in its own screen session and is
 responsible for starting the automatix screens and status updates.

By default the programm starts with 2 parallel automatix instances. Use the main programm loop controls
 to change the number of allowed parallel sessions (pressing 'm' followed by your desired number).

If you force the programm to terminate (e.g. keyboard interrupt, process kill, ...),
 check for still running screen processes via `screen -list`. They are independent and may continue
 running. Cleanup manually, if necessary.

The screens write their output to log files in the specified **logfile_dir** (see **CONFIGURATION** section).
 These logfiles contain the escape sequences that are used to provide the colored output an the terminal.
 You can use a pager that supports interpreting these sequences like the terminal to have a similar
 experience (`more` or `less -r` worked for me).

## Bash completion (experimental)
Automatix supports bash completion for parameters and the script directory via [argcomplete](https://github.com/kislyuk/argcomplete).

Therefor follow the installation instructions for argcomplete, which is at the current time

    pip install argcomplete

and either global activation via executing

    activate-global-python-argcomplete

or activation for automatix (e.g. in `.bashrc`)

    eval "$(register-python-argcomplete automatix)"

Automatix will recognize the installed module and offer the completion automatically.

## Progress bar (experimental)
You can activate an "apt-like" progress bar based on the amount of commands
 by setting the configuration option `progress_bar` to `True` (config file or environment).

The status on the right displays `[elapsed time<remaining time, rate]`,
 where rate is percentage/second if fast and second/percentage if slow.

Note, that using commands that heavily modify the terminal behaviour/output
 (such as `top`, `watch`, `glances`, ...), may lead to a unreadable
 or undesirable output. It might be a better idea to encourage the user
 to open a separate terminal and type these commands there.

Using automatix itself as command should work, but may lead to confusing
 output as well. Note, that the progress bar will be overwritten by the
 new automatix instance for the duration of the automatix command.
