<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `zoom` Command-Line Interface

```text
Usage: zoom [OPTIONS] COMMAND [ARGS]...                                                                                                                   
                                                                                                                                                           
 TranZoom will do things!                                                                                                                                  
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                                                            Show version and exit.                                                             │
│ --verbose             -v                INTEGER RANGE [0<=x<=3]      Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).           │
│ --color                   --no-color                                 Force enable/disable colored output (respects NO_COLOR env var if not provided).   │
│                                                                      Defaults to having colors.                                                         │
│ --width               -w                INTEGER RANGE [16<=x<=8192]  Width of the image; 16 ≤ w ≤ 8192; default is 1024                  │
│ --height              -h                INTEGER RANGE [16<=x<=8192]  Height of the image; 16 ≤ h ≤ 8192; default is 1024                 │
│ --out                 -o                DIRECTORY                    The local output root directory path, ex: "~/foo/bar/"; if not given, the image    │
│                                                                      will be saved in the current working directory                                     │
│ --prefix                                TEXT                         Image save prefix; default: 'mandel' (the final file name will be                  │
│                                                                      "<prefix>[-<date>][-<hash20>].png", note the date and the hash can be turned off   │
│                                                                      with --no-date and --no-hash, respectively)                                        │
│                                                                                                                                        │
│ --date                    --no-date                                  If True, file names will include the date-time as YYYYMMDDhhmmss; if False, file   │
│                                                                      names will not include the date-time; default is True                              │
│                                                                                                                                          │
│ --hash                    --no-hash                                  If True, file names will include the hash; if False, file names will not include   │
│                                                                      the hash; default is True                                                          │
│                                                                                                                                          │
│ --threads                               INTEGER RANGE [1<=x<=12]     Number of threads to use for rendering; default is None, which means to use all    │
│                                                                      available CPU cores; will be limited to 12 threads                                 │
│ --install-completion                                                 Install completion for the current shell.                                          │
│ --show-completion                                                    Show completion for the current shell, to copy it or customize the installation.   │
│ --help                                                               Show this message and exit.                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown  Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `zoom markdown` Command

```text
Usage: zoom markdown [OPTIONS]                                                                                                                            
                                                                                                                                                           
 Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                                         
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Example:                                                                                                                                                  
                                                                                                                                                           
 $ poetry run zoom markdown > zoom.md                                                                                                                      
 <<saves CLI doc>>
```
