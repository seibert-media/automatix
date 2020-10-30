# automatix
Automation wrapper for bash and python commands


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

**automatix** is originally designed for internal //SEIBERT/MEDIA use.
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

Automatix requires Python &ge; 3.6.

```
pip install automatix
```

# CONFIGURATION

You can specify a path to a configuration YAML file via the
 environment variable **AUTOMATIX_CONFIG**.
Default location is "~/.automatix.cfg.yaml".

### Example: .automatix.cfg.yaml

    # Path to scripts directory
    script_dir: ~/automatix_script_files
    
    # Global constants for use in pipeline scripts
    constants:
      apt_update: 'apt-get -qy update'
      apt_upgrade: 'DEBIAN_FRONTEND=noninteractive apt-get -qy -o Dpkg::Options::=--force-confold --no-install-recommends upgrade'
      apt_full_upgrade: 'DEBIAN_FRONTEND=noninteractive apt-get -qy -o Dpkg::Options::=--force-confold --no-install-recommends full-upgrade'
    
    # Encoding
    encoding: utf-8
    
    # Path for shell imports
    import_path: '.'
    
    # SSH Command used for remote connections
    ssh_cmd: 'ssh {hostname} sudo '
    
    # Temporary directory on remote machines for shell imports
    remote_tmp_dir: 'automatix_tmp'
    
    # Logger
    logger: mylogger
    
    # Logging library (has to implement the init_logger method)
    logging_lib: mylib.logging
    
    # Bundlewrap support, bundlewrap has to be installed (default: false)
    bundlewrap: true
    
    # Teamvault / Secret support, bundlewrap-teamvault has to be installed (default: false)
    teamvault: true

# SYNOPSIS

**automatix** \[**--help**|**-h**\] \[**--systems** \[_SYSTEM1=NODENAME_ ...\]\]
                 \[**--vars** \[_VAR1=VALUE1_ ...\]\]
                 \[**--secrets** \[_SECRET1=SECRETID_ ...\]\]
                 \[**--vars-file** _VARS_FILE_PATH_ \]
                 \[**--print-overview**|**-p**\]
                 \[**--jump-to**|**-j** _JUMP_TO_\]
                 \[**--interactive**|**-i**\] \[**--force**|**-f**\] \[**--debug**|**-d**\]
                 \[**--**\] **scriptfile**


## OPTIONS

**scriptfile**
: The only required parameter for this tool to work. Use " -- " if
 needed to delimit this from argument fields. See **SCRIPTFILE**
 section for more information.

**-h**, **--help**
: View help message and exit.

**--systems** _SYSTEM1=NODENAME_
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
  types and names. You may also specify an `label` field.
  Example: `label,systems:mysystem,vars:myvar`. The automatix script will
  be processed for each row sequentially.
  
**--print-overview**, **-p**
: Just print command pipeline overview with indices then exit without
 executing the commandline. Note that the *always pipeline* will be
 executed anyway.

**--jump-to** _JUMP_TO_, **-j** _JUMP_TO_
: Jump to step with index _JUMP_TO_ instead of starting at the
 beginning. Use **-p** or the output messages to determine the
 desired step index. You can use negative numbers to start counting
 from the end.

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
    # Systems you like to refer to in pipeline (accessible via 'system_source')
    # If Bundlewrap support is activated use node names instead of hostnames.
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
      - sla=python: source_node.metadata.get('sla')
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

**systems** _(associative array)_
: Define some systems. Value has to be an valid and existing
 bundlewrap nodename.
You can refer to these systems in the command pipeline in multiple ways:

1) remote@systemname as your command action (see below)

2) via {system_systemname} which will be replaced with the value

3) via systemname_node in python actions to use the bw node object

**vars** _(associative array)_
: Define some vars. These are accessible in the command pipeline via
 {varname}. Note: Only valid Python variable names are allowed.
 You can use "*FILE_*" prefix followed by a file path to assign the file
 content to the variable.

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
 beforehand. /bin/bash will be used for execution.

3) **remote@systemname**: Remote shell command to execute. Systemname
 has to be a defined system. The command will be run via SSH (without
  pseudo-terminal allocation). It uses the standard SSH command.
  Therefore your .ssh/config should be respected.

4) **python**: Python code to execute. If bundlewrap is enabled,
 system node objects are available via systemname_node.

**ASSIGNMENT**: For **local**, **remote** and **python** action you
 can also define a variable to which the output will be assigned.
 To do this prefix the desired variablename and = before the action
 key, e.g. `myvar=python: system_node.hostname`. Be careful when
 working with multiline statements. In **python** the first line is
 likely to set the variable. All variables will be converted to
 strings when used to build commands in following steps.
 
**CONDITIONS**: You can define the command only to be executed if
 your condition variable evolves to "True" in Python. To achieve this
 write the variable name followed by a question mark at the very
 beginning like `cond?python: destroy_system()`. Be aware that all
 output from **local** or **remote** commands will lead to an
 non-empty string which evolves to "True" in Python, but empty output
 will evolve to "False".

**VALUE**: Your command. Variables will be replaced with Python
 format function. Therefore use curly brackets to refer to variables,
 systems, secrets and constants.

Constants are available via const_KEY, where KEY is the key of your
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

**AUTOMATIX_TIME**: Set this to an arbitrary value to print the times
 for the single steps and the whole script.

**ENCODING**: Specify output encoding. Default is "UTF-8".  

Additionally you can modify the environment to adjust things to your
 needs.


# TIPS & TRICKS

If you want to access variables in **python** action you defined in
preceeding command, you can use the **PERSISTENT_VARS** dictionary.
This is added to the local scope of **python** actions.
 Examples:
- To make all local variables of the actual command persistent use
 `PERSISTENT_VARS.update(locals())`.
- To delete one persistent variable named "myvar" use
 `del PERSISTENT_VARS['myvar']`
- To make variable "v2" persistent use `PERSISTENT_VARS['v2'] = v2`

You can use all variables in PERSISTENT_VARS 

An alternative is to make variables global, but in most cases using
 PERSISTENT_VARS is more clean. _**CAUTION: Choosing already existing
 (Python) variable names may lead to unexpected behaviour!!!**_ Maybe
  you want to check the source code (command.py).  
Explanation: automatix is written in Python and uses 'exec' to
 execute the command in function context. If you declare variables
 globally they remain across commands.

For **python** action there are some modules, constants and functions
 which are already imported (check command.py): e.g. 
`re, subprocess, quote(from shlex)`

To abort the current automatix and jump to the next batch item you can
 raise the `SkipBatchItemException`. For aborting the whole automatix
 process raise `AbortException`. In both cases the cleanup pipeline is
 executed. Same is the case for selecting `a`:abort or `c`:continue
 when asked (interactive or error).
 

# BEST PRACTISES

There are different ways to start scripting with **automatix**. The
 author's approach is mainly to consider the process and simply write
 down, what to do (manual steps for complex or not automated steps)
 and which commands to use.  
Then start **automatix** in interactive mode (-i) and adjust the
 single steps one by one. Replace manual steps, if suitable. Whenever
 adjustment is needed, abort, adjust and restart **automatix** with
 jump (-j) to the adjusted step.  
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

Assignments containing **null bytes** are currently not supported.

Because the **always** pipeline should not change anything, aborting
 while running this pipeline will not trigger a cleanup.

If you want to abort the **pipeline** without triggering the
 **cleanup** pipeline, use CRTL+C.

While **aborting remote functions** (via imports), automatix is not
 able to determine still running processes invoked by the function,
 because it only checks the processes for the commands (in this case
 the function name) which is called in the pipeline.
