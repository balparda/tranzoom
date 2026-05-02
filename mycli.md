<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `mycli` Command-Line Interface

```text
Usage: mycli [OPTIONS] COMMAND [ARGS]...                                                                                                                  
                                                                                                                                                           
 MyCLI does amazing things!                                                                                                                                
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                                                        Show version and exit.                                                                 │
│ --verbose             -v                INTEGER RANGE [0<=x<=3]  Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).               │
│ --color                   --no-color                             Force enable/disable colored output (respects NO_COLOR env var if not provided).       │
│                                                                  Defaults to having colors.                                                             │
│ --foo                 -f                INTEGER                  Some integer option.                                                    │
│ --bar                 -b                TEXT                     Some string option.                                              │
│ --install-completion                                             Install completion for the current shell.                                              │
│ --show-completion                                                Show completion for the current shell, to copy it or customize the installation.       │
│ --help                                                           Show this message and exit.                                                            │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown    Emit Markdown docs for the CLI (see README.md section "Creating a New Version").                                                            │
│ configpath  Print the config file path.                                                                                                                 │
│ hello       Say hello.                                                                                                                                  │
│ random      Random utilities.                                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `mycli configpath` Command

```text
Usage: mycli configpath [OPTIONS]                                                                                                                         
                                                                                                                                                           
 Print the config file path.                                                                                                                               
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `mycli hello` Command

```text
Usage: mycli hello [OPTIONS] [NAME]                                                                                                                       
                                                                                                                                                           
 Say hello.                                                                                                                                                
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   name      [NAME]                                                                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `mycli markdown` Command

```text
Usage: mycli markdown [OPTIONS]                                                                                                                           
                                                                                                                                                           
 Emit Markdown docs for the CLI (see README.md section "Creating a New Version").                                                                          
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Example:                                                                                                                                                  
                                                                                                                                                           
 $ poetry run mycli markdown > mycli.md                                                                                                                    
 <<saves CLI doc>>
```

## `mycli random` Command

```text
Usage: mycli random [OPTIONS] COMMAND [ARGS]...                                                                                                           
                                                                                                                                                           
 Random utilities.                                                                                                                                         
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ num  Generate a random integer.                                                                                                                         │
│ str  Generate a random string.                                                                                                                          │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### `mycli random num` Sub-Command

```text
Usage: mycli random num [OPTIONS]                                                                                                                         
                                                                                                                                                           
 Generate a random integer.                                                                                                                                
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --min         INTEGER  Minimum value (inclusive).                                                                                           │
│ --max         INTEGER  Maximum value (inclusive).                                                                                         │
│ --help                 Show this message and exit.                                                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### `mycli random str` Sub-Command

```text
Usage: mycli random str [OPTIONS]                                                                                                                         
                                                                                                                                                           
 Generate a random string.                                                                                                                                 
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --length    -n      INTEGER RANGE   String length.                                                                                   │
│ --alphabet          TEXT                  Custom alphabet to sample from (defaults to ).                                                                │
│ --help                                    Show this message and exit.                                                                                   │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
