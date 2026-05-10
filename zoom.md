<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `zoom` Command-Line Interface

```text
Usage: zoom [OPTIONS] COMMAND [ARGS]...                                                                                                                   
                                                                                                                                                           
 TranZoom does amazing things!                                                                                                                             
                                                                                                                                                           
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
│ --install-completion                                                 Install completion for the current shell.                                          │
│ --show-completion                                                    Show completion for the current shell, to copy it or customize the installation.   │
│ --help                                                               Show this message and exit.                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown  Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                             │
│ image     Make a Mandelbrot image.                                                                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `zoom image` Command

```text
Usage: zoom image [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                                  
                                                                                                                                                           
 Make a Mandelbrot image.                                                                                                                                  
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; default is '-0.75'                                                         │
│   center_im      [CENTER_IM]  Imaginary part of the center point; default is '0'                                                            │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; default is '2.5'                                                      │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; default is None, i.e, the same as width                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --iter     -i      INTEGER RANGE [1000<=x<=4294967295]  Maximum iterations (depth) to compute before determining escape; 1000 ≤ iter ≤ 4294967295;      │
│                                                         default is None (automatic search for optimal iterations --- recommended)                       │
│ --palette          TEXT                                 Color palette to use for rendering; default is 'blue-to-yellow-to-brown'; available palettes:   │
│                                                         ['blue-to-yellow-to-brown']                                                                     │
│                                                                                                                       │
│ --help                                                  Show this message and exit.                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Example:                                                                                                                                                  
                                                                                                                                                           
 $ poetry run zoom image                                                                                                                                   
 <saves fractal to disk with default frame>                                                                                                                
 $ poetry run zoom image " -0.3" 0 2  # note the space because of the "-"                                                                                  
 <saves fractal to disk with center -0.3+0j and width 2>
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
