<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `zoom` Command-Line Interface

```text
Usage: zoom [OPTIONS] COMMAND [ARGS]...                                                                                                                   
                                                                                                                                                           
 TranZoom does amazing things!                                                                                                                             
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                                                           Show version and exit.                                                              │
│ --verbose             -v                INTEGER RANGE [0<=x<=3]     Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).            │
│ --color                   --no-color                                Force enable/disable colored output (respects NO_COLOR env var if not provided).    │
│                                                                     Defaults to having colors.                                                          │
│ --width               -w                INTEGER RANGE [4<=x<=8192]  Width of the image; 4 ≤ w ≤ 8192; default is 1024                    │
│ --height              -h                INTEGER RANGE [4<=x<=8192]  Height of the image; 4 ≤ h ≤ 8192; default is 1024                   │
│ --install-completion                                                Install completion for the current shell.                                           │
│ --show-completion                                                   Show completion for the current shell, to copy it or customize the installation.    │
│ --help                                                              Show this message and exit.                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown  Emit Markdown docs for the CLI (see README.md section "Creating a New Version").                                                              │
│ image     Make a Mandelbrot image.                                                                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `zoom image` Command

```text
Usage: zoom image [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                                  
                                                                                                                                                           
 Make a Mandelbrot image.                                                                                                                                  
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; default is "-0.6"                                                           │
│   center_im      [CENTER_IM]  Imaginary part of the center point; default is "0"                                                            │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; default is "3"                                                          │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; default is None, i.e, the same as width                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `zoom markdown` Command

```text
Usage: zoom markdown [OPTIONS]                                                                                                                            
                                                                                                                                                           
 Emit Markdown docs for the CLI (see README.md section "Creating a New Version").                                                                          
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Example:                                                                                                                                                  
                                                                                                                                                           
 $ poetry run zoom markdown > zoom.md                                                                                                                      
 <<saves CLI doc>>
```
