<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `mandel` Command-Line Interface

```text
Usage: mandel [OPTIONS] COMMAND [ARGS]...                                                                                                                 
                                                                                                                                                           
 TranZoom: `mandel` CLI generates and has utilities for Mandelbrot Set computations                                                                        
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                                                             Show version and exit.                                                            │
│ --verbose             -v                INTEGER RANGE [0<=x<=3]       Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).          │
│ --color                   --no-color                                  Force enable/disable colored output (respects NO_COLOR env var if not provided).  │
│                                                                       Defaults to having colors.                                                        │
│ --width               -w                INTEGER RANGE [16<=x<=16384]  Width of the image; 16 ≤ w ≤ 16384; default is 1024                │
│ --height              -h                INTEGER RANGE [16<=x<=16384]  Height of the image; 16 ≤ h ≤ 16384; default is 1024               │
│ --out                 -o                DIRECTORY                     The local output root directory path, ex: "~/foo/bar/"; if not given, the image   │
│                                                                       will be saved in the current working directory                                    │
│ --prefix                                TEXT                          Image save prefix; default: 'mandel' (the final file name will be                 │
│                                                                       "<prefix>[-<date>][-<hash20>].png", note the date and the hash can be turned off  │
│                                                                       with --no-date and --no-hash, respectively)                                       │
│                                                                                                                                        │
│ --date                    --no-date                                   If True, file names will include the date-time as YYYYMMDDhhmmss; if False, file  │
│                                                                       names will not include the date-time; default is True                             │
│                                                                                                                                          │
│ --hash                    --no-hash                                   If True, file names will include the hash; if False, file names will not include  │
│                                                                       the hash; default is True                                                         │
│                                                                                                                                          │
│ --threads                               INTEGER RANGE [1<=x<=16]      Number of threads to use for rendering; default is None, which means to use all   │
│                                                                       available CPU cores; will be limited to 16 threads                                │
│ --install-completion                                                  Install completion for the current shell.                                         │
│ --show-completion                                                     Show completion for the current shell, to copy it or customize the installation.  │
│ --help                                                                Show this message and exit.                                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown  Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                             │
│ gen       Generate a Mandelbrot image.                                                                                                                  │
│ read      Read a Mandelbrot image.                                                                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run mandel gen                                                                                                                                   
 1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...                                                                                                       
 ...                                                                                                                                                       
 Saved to "mandel-<date>-<hash>.png"                                                                                                                       
                                                                                                                                                           
 $ poetry run mandel -w 512 -h 512 gen " -0.74303" "0.126433" "0.01611"  # note the space because of the "-"                                               
 <saves Mandelbrot to disk with center --0.74303+0.126433j and width 0.01611>
```

## `mandel gen` Command

```text
Usage: mandel gen [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                                  
                                                                                                                                                           
 Generate a Mandelbrot image.                                                                                                                              
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; default is '-0.75'                                                         │
│   center_im      [CENTER_IM]  Imaginary part of the center point; default is '0'                                                            │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; default is '2.5'                                                      │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; default is None, i.e, the same as width                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --iter     -i                INTEGER RANGE [1000<=x<=4294967295]                   Maximum iterations (depth) to compute before determining escape;     │
│                                                                                    1000 ≤ iter ≤ 4294967295; default is None (automatic search for      │
│                                                                                    optimal iterations --- recommended)                                  │
│ --palette                      Color palette to use for rendering; default is                       │
│                                                                                    'blue-to-yellow-to-brown'; available palettes:                       │
│                                                                                    ['blue-to-yellow-to-brown', 'electric-ocean', 'lava', 'sunset']      │
│                                                                                                                       │
│ --iterm        --no-iterm                                                          If True, will output the image to iTerm2 (only use on macOS with     │
│                                                                                    iTerm2! <https://iterm2.com/documentation-images.html>); if False,   │
│                                                                                    will not output the image to iTerm2; default is False                │
│                                                                                                                                      │
│ --help                                                                             Show this message and exit.                                          │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run mandel gen                                                                                                                                   
 1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...                                                                                                       
 ...                                                                                                                                                       
 Saved to "mandel-<date>-<hash>.png"                                                                                                                       
                                                                                                                                                           
 $ poetry run mandel -w 512 -h 512 gen " -0.74303" "0.126433" "0.01611"  # note the space because of the "-"                                               
 <saves Mandelbrot to disk with center --0.74303+0.126433j and width 0.01611>
```

## `mandel markdown` Command

```text
Usage: mandel markdown [OPTIONS]                                                                                                                          
                                                                                                                                                           
 Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                                         
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Example:                                                                                                                                                  
                                                                                                                                                           
 $ poetry run mandel markdown > mandel.md                                                                                                                  
 <<saves CLI doc>>
```

## `mandel read` Command

```text
Usage: mandel read [OPTIONS] IMAGE_PATH                                                                                                                   
                                                                                                                                                           
 Read a Mandelbrot image.                                                                                                                                  
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    image_path      FILE  The local input file path, ex: "~/foo/bar/file.png"                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --iterm    --no-iterm      If True, will output the image to iTerm2 (only use on macOS with iTerm2! <https://iterm2.com/documentation-images.html>); if │
│                            False, will not output the image to iTerm2; default is False                                                                 │
│                                                                                                                                      │
│ --help                     Show this message and exit.                                                                                                  │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run mandel read /path/to/image.png                                                                                                               
 1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...                                                                                                       
 ...
```
