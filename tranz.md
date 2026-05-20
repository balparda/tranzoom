<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `tranz` Command-Line Interface

```text
Usage: tranz [OPTIONS] COMMAND [ARGS]...                                                                                                                  
                                                                                                                                                           
 TranZoom: Fractal (Mandelbrot/Julia) image and zoom generator, with LLM-powered features                                                                  
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                                                                                       Show version and exit.                                  │
│ --verbose             -v                INTEGER RANGE [0<=x<=3]                                 Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO,         │
│                                                                                                 -vvv=DEBUG).                                            │
│                                                                                                                                             │
│ --color                   --no-color                                                            Force enable/disable colored output (respects NO_COLOR  │
│                                                                                                 env var if not provided). Defaults to having colors.    │
│ --out                 -o                DIRECTORY                                               The local output root directory path, ex: "~/foo/bar/"; │
│                                                                                                 if not given, the image will be saved in the current    │
│                                                                                                 working directory                                       │
│ --prefix                                TEXT                                                    Image save prefix; default: None, meaning use "mandel"  │
│                                                                                                 for Mandelbrot and "julia" for Julia (the final file    │
│                                                                                                 name will be "<prefix>[-<date>][-<hash20>].png", note   │
│                                                                                                 the date and the hash can be turned off with --no-date  │
│                                                                                                 and --no-hash, respectively)                            │
│ --date                    --no-date                                                             If True, file names will include the date-time as       │
│                                                                                                 YYYYMMDDhhmmss; if False, file names will not include   │
│                                                                                                 the date-time; default is True                          │
│                                                                                                                                          │
│ --hash                    --no-hash                                                             If True, file names will include the hash; if False,    │
│                                                                                                 file names will not include the hash; default is True   │
│                                                                                                                                          │
│ --palette                                                                    'blue-to-yellow-to-brown'; available palettes:          │
│                                                                                                 ['blue-to-yellow-to-brown', 'electric-ocean',           │
│                                                                                                 'grayscale', 'lava', 'rgrayscale', 'sunset']            │
│                                                                                                                       │
│ --set-palette                                                                points; default is 'rgrayscale'; available palettes:    │
│                                                                                                 ['blue-to-yellow-to-brown', 'electric-ocean',           │
│                                                                                                 'grayscale', 'lava', 'rgrayscale', 'sunset']            │
│                                                                                                                                    │
│ --set                                                                  Which algorithm to use for coloring the interior Set    │
│                                                                                                 points, either None, or one of 'min', 'max', 'angle',   │
│                                                                                                 'imaginary'; default is None, do not color the Set      │
│                                                                                                 points (i.e., they will be black)                       │
│ --threads                               INTEGER RANGE [1<=x<=16]                                Number of threads to use for rendering; default is      │
│                                                                                                 None, which means to use all available CPU cores; will  │
│                                                                                                 be limited to 16 threads                                │
│ --model               -m                TEXT                                                    LLM vision model to load and use: the model must be     │
│                                                                                                 compatible with the LMStudio client libraries and must  │
│                                                                                                 support vision; will NOT get the model for you, so make │
│                                                                                                 sure you either have it available in your LMStudio;     │
│                                                                                                 should be a string you would use with `lms get <THIS>`  │
│                                                                                                 or `https://huggingface.co/<THIS>`; default:            │
│                                                                                                 'qwen3-vl-32b-instruct@q8_0', a good general-purpose    │
│                                                                                                 vision model                                            │
│                                                                                                                    │
│ --tokens              -t                INTEGER RANGE [2<=x<=200]                               Speculative Decoding: controls how many tokens the      │
│                                                                                                 model should generate in advance during auto-tagging;   │
│                                                                                                 if you do not define this flag then speculative         │
│                                                                                                 decoding will be disabled; usually this is a small      │
│                                                                                                 value, like 4 or 8, and it can improve the speed of     │
│                                                                                                 processing by allowing the model to generate tokens in  │
│                                                                                                 parallel; default: None (disabled)                      │
│ --seed                -s                INTEGER RANGE [2<=x<=2147483647]                        A seed value for the random number generator used to    │
│                                                                                                 load the models into memory; providing a seed ensures   │
│                                                                                                 reproducibility of the results; default: None           │
│                                                                                                 (randomized seed)                                       │
│ --context                               INTEGER RANGE [16<=x<=16777216]                         Maximum number of tokens to use as context for the      │
│                                                                                                 model; default: 32768 tokens                            │
│                                                                                                                                         │
│ --temperature         -x                FLOAT RANGE [0.0<=x<=2.0]                               Temperature controls how random token selection is      │
│                                                                                                 during generation; [0 or near 0]: most deterministic,   │
│                                                                                                 focused, repetitive, best for extraction / structured   │
│                                                                                                 output / coding / tool use; [0.2-0.5]: still stable,    │
│                                                                                                 but less rigid; [0.7-1.0]: more natural and varied;     │
│                                                                                                 [>1.0]: often more creative, but also more errors,      │
│                                                                                                 drift, and nonsense; default: 0.150 (a good value for   │
│                                                                                                 structured output and tool use)                         │
│                                                                                                                                          │
│ --gpu                 -g                FLOAT RANGE [0.1<=x<=1.0]                               GPU ratio to use, a value between 0.1 (10%) and 1.0     │
│                                                                                                 (100%) that indicates the percentage of GPU resources   │
│                                                                                                 to allocate to AI; default: 0.80                        │
│                                                                                                                                           │
│ --gpu-layers                            INTEGER RANGE [-1<=x<=128]                              Number of layers offloaded to GPU; default: -1 (which   │
│                                                                                                 means "as many as possible")                            │
│                                                                                                                                            │
│ --fp16                    --no-fp16                                                             Use FP16 precision for the auto-tagger model? This can  │
│                                                                                                 reduce memory usage and potentially increase speed, but │
│                                                                                                 may slightly affect the accuracy of the tagging results │
│                                                                                                 default: False (do not use FP16, use full precision)    │
│                                                                                                                                       │
│ --mmap                    --no-mmap                                                             Use memory-mapped file loading (if supported)? default: │
│                                                                                                 True (use mmap)                                         │
│                                                                                                                                          │
│ --flash                   --no-flash                                                            Enable flash attention (if supported)? default: True    │
│                                                                                                 (use flash)                                             │
│                                                                                                                                         │
│ --kv-cache                              INTEGER RANGE [4<=x<=128]                               GGML type for KV-cache keys/values (if supported):      │
│                                                                                                 determines the precision level used to store            │
│                                                                                                 keys/values; default: None (store according to original │
│                                                                                                 precision in model)                                     │
│ --timeout                               FLOAT RANGE [0.0<=x<=86400.0]                           Timeout, in seconds, for AI calls; zero, or <1s, means  │
│                                                                                                 no timeout (infinite); default: 300.0 seconds           │
│                                                                                                                                         │
│ --iterm                   --no-iterm                                                            If True, will output the image to iTerm2 (only use on   │
│                                                                                                 macOS with iTerm2!                                      │
│                                                                                                 <https://iterm2.com/documentation-images.html>); if     │
│                                                                                                 False, will not output the image to iTerm2; default is  │
│                                                                                                 False                                                   │
│                                                                                                                                      │
│ --install-completion                                                                            Install completion for the current shell.               │
│ --show-completion                                                                               Show completion for the current shell, to copy it or    │
│                                                                                                 customize the installation.                             │
│ --help                                                                                          Show this message and exit.                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown  Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                             │
│ image     Examples:                                                                                                                                     │
│ zoom      Examples:                                                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 # --- Mandelbrot Image Generation ---                                                                                                                     
 poetry run tranz image mandel                                                                                                                             
 poetry run tranz image -w 512 -h 512 mandel " -0.74303" "0.126433" "0.01611"  # note the space because of the "-"                                         
                                                                                                                                                           
 # --- Julia Set Image Generation ---                                                                                                                      
 poetry run tranz image julia                                                                                                                              
 poetry run tranz -s 1024 image julia "13667/50000" "371/50000" " -313420497/429687500" "0.6567" "0.00544" "0.004"                                         
 poetry run tranz image julia "/path/to/julia_point_image.png" "" "/path/to/frame_image.png"                                                               
                                                                                                                                                           
 # --- TranZoom Fractal Image Data Reading / Visualization ---                                                                                             
 poetry run tranz image read /path/to/image.png                                                                                                            
                                                                                                                                                           
 # --- LLM-Guided Fractal Zoom ---                                                                                                                         
 poetry run tranz zoom ai                                                                                                                                  
 poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 zoom -n 10 ai " -0.7436499" "0.13188204" "0.00073801"                                             
 poetry run tranz --iterm zoom ai "/path/to/image.png"                                                                                                     
 poetry run tranz --iterm zoom -s 700 --fractal julia ai                                                                                                   
                                                                                                                                                           
 # --- Human/Manual-Guided Fractal Zoom ---                                                                                                                
 poetry run tranz --iterm zoom manual " -0.74303" "0.126433" "0.01611"                                                                                     
 poetry run tranz zoom manual "/path/to/image.png"                                                                                                         
 poetry run tranz --iterm zoom -s 700 --fractal julia manual                                                                                               
                                                                                                                                                           
 # --- Markdown Help ---                                                                                                                                   
 poetry run tranz markdown > tranz.md
```

## `tranz image` Command

```text
Usage: tranz image [OPTIONS] COMMAND [ARGS]...                                                                                                            
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 # --- Mandelbrot Set Image Generation ---                                                                                                                 
 poetry run tranz image mandel                                                                                                                             
 poetry run tranz image -w 512 -h 512 mandel " -0.74303" "0.126433" "0.01611"  # note the space because of the "-"                                         
                                                                                                                                                           
 # --- Julia Set Image Generation ---                                                                                                                      
 poetry run tranz image julia                                                                                                                              
 poetry run tranz -s 1024 image julia "13667/50000" "371/50000" " -313420497/429687500" "0.6567" "0.00544" "0.004"                                         
 poetry run tranz image julia "/path/to/julia_point_image.png" "" "/path/to/frame_image.png"                                                               
                                                                                                                                                           
 # --- TranZoom Fractal Image Data Reading / Visualization ---                                                                                             
 poetry run tranz image read /path/to/image.png                                                                                                            
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --width       -w      INTEGER RANGE [16<=x<=16384]         Width of the image; 16 ≤ w ≤ 16384; default is 1024                           │
│ --height      -h      INTEGER RANGE [16<=x<=16384]         Height of the image; 16 ≤ h ≤ 16384; default is 1024                          │
│ --size        -s      INTEGER RANGE [16<=x<=16384]         Size of the image: *overrides* both `-w/--width` and `-h/--height` by determining the max    │
│                                                            pixel length of the final image, which will be proportional to the given frame, i.e., the    │
│                                                            final dimensions will be scaled accordingly and, given a size S, will be either (S, x), (x,  │
│                                                            S) or (S, S), where x < S, and will make the final image ratio/proportion be the same as the │
│                                                            frame; 16 ≤ S ≤ 16384; default is None, i.e., follow the explicit `-w/--width` and           │
│                                                            `-h/--height` options                                                                        │
│ --iter        -i      INTEGER RANGE [1000<=x<=2147483647]  Maximum iterations (depth) to compute before determining escape; 1000 ≤ iter ≤ 2147483647;   │
│                                                            default is None (automatic search for optimal iterations --- recommended)                    │
│ --mark                TEXT                                 A point formatted as "(re, im)" to add a crosshair overlay, `re` and `im` multi-precision;   │
│                                                            this can be a float (ex: "(0.34, -0.56)") or a fraction of ints (rational numbers, ex:       │
│                                                            "(123/451, 789/1011)") or any combination of these, and the numbers will be fed directly to  │
│                                                            multi-precision arithmetic so no precision is lost; default is None, i.e., do not mark       │
│                                                            overlay on the image                                                                         │
│ --mark-color          TEXT                                 Color of the crosshair overlay; default is "red"; available colors: 'black', 'blue', 'cyan', │
│                                                            'green', 'magenta', 'red', 'white', 'yellow'                                                 │
│                                                                                                                                           │
│ --mark-width          INTEGER RANGE [1<=x<=50]             Width of the crosshair overlay; 1 ≤ w ≤ 50; default is 1                         │
│ --help                                                     Show this message and exit.                                                                  │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ mandel  Generate a Mandelbrot image.                                                                                                                    │
│ julia   Generate a Julia image.                                                                                                                         │
│ read    Read a TranZoom fractal image.                                                                                                                  │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### `tranz image julia` Sub-Command

```text
Usage: tranz image julia [OPTIONS] [POINT_RE] [POINT_IM] [CENTER_RE] [CENTER_IM]                                                                          
                          [F_WIDTH] [F_HEIGHT]                                                                                                             
                                                                                                                                                           
 Generate a Julia image.                                                                                                                                   
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   point_re       [POINT_RE]   Real part of the Julia Set constant; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:         │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; ALTERNATIVELY: you  │
│                               can use this to input an existing PNG image path, and it will read the Julia Set constant from the given image's metadata │
│                               frame *CENTER* (overriding/ignoring the imaginary parameter part!); default is '0.27334'                                  │
│                                                                                                                                       │
│   point_im       [POINT_IM]   Imaginary part of the Julia Set constant; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:    │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is          │
│                               '0.00742'                                                                                                                 │
│                                                                                                                                       │
│   center_re      [CENTER_RE]  Real part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451")    │
│                               and the number will be fed directly to multi-precision arithmetic so no precision is lost; ALTERNATIVELY: you can use     │
│                               this to input an existing PNG image path, and it will read the frame from the given image's metadata (overriding/ignoring │
│                               the other CLI frame parameters!); default is '0'                                                                          │
│                                                                                                                                             │
│   center_im      [CENTER_IM]  Imaginary part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:          │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '0'      │
│                                                                                                                                             │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:        │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '1.8'    │
│                                                                                                                                           │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:  │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '2.2'    │
│                                                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run tranz image julia                                                                                                                            
 1024x1024 Julia in frame [(0, 0) ± (9/5, 11/5) @ (13667/50000, 371/50000)] ...                                                                            
 ...                                                                                                                                                       
 Saved to "julia-<date>-<hash>.png"                                                                                                                        
                                                                                                                                                           
 $ poetry run tranz -s 1024 image julia "13667/50000" "371/50000" " -313420497/429687500" "0.6567" "0.00544" "0.004"                                       
 <saves 1024px Julia to disk with center -313420497/429687500+0.6567j and width 0.6567 by 0.004>                                                           
                                                                                                                                                           
 $ poetry run tranz image julia "/path/to/julia_point_image.png" "" "/path/to/frame_image.png"                                                             
 <gets the same frame used in "frame_image.png" and saves a new image using "julia_point_image.png" Julia point>
```

### `tranz image mandel` Sub-Command

```text
Usage: tranz image mandel [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                          
                                                                                                                                                           
 Generate a Mandelbrot image.                                                                                                                              
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451")    │
│                               and the number will be fed directly to multi-precision arithmetic so no precision is lost; ALTERNATIVELY: you can use     │
│                               this to input an existing PNG image path, and it will read the frame from the given image's metadata (overriding/ignoring │
│                               the other CLI frame parameters!); default is '-0.75'                                                                      │
│                                                                                                                                         │
│   center_im      [CENTER_IM]  Imaginary part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:          │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '0'      │
│                                                                                                                                             │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:        │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '2.5'    │
│                                                                                                                                           │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:  │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is None,    │
│                               i.e, the same as width                                                                                                    │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run tranz image mandel                                                                                                                           
 1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...                                                                                                       
 ...                                                                                                                                                       
 Saved to "mandel-<date>-<hash>.png"                                                                                                                       
                                                                                                                                                           
 $ poetry run tranz image -w 512 -h 512 mandel " -0.74303" "0.126433" "0.01611"  # note the space because of the "-"                                       
 <saves Mandelbrot to disk with center -0.74303+0.126433j and width 0.01611>                                                                               
                                                                                                                                                           
 $ poetry run tranz image mandel "/path/to/image.png"                                                                                                      
 <gets the same frame used in "/path/to/image.png" and saves a new image of it to disk>
```

### `tranz image read` Sub-Command

```text
Usage: tranz image read [OPTIONS] IMAGE_PATH                                                                                                              
                                                                                                                                                           
 Read a TranZoom fractal image.                                                                                                                            
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    image_path      FILE  The local input file path, ex: "~/foo/bar/file.png"                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run tranz image read /path/to/image.png                                                                                                          
 1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...                                                                                                       
 ...
```

## `tranz markdown` Command

```text
Usage: tranz markdown [OPTIONS]                                                                                                                           
                                                                                                                                                           
 Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                                         
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Example:                                                                                                                                                  
                                                                                                                                                           
 $ poetry run tranz markdown > tranz.md                                                                                                                    
 <<saves CLI doc>>
```

## `tranz zoom` Command

```text
Usage: tranz zoom [OPTIONS] COMMAND [ARGS]...                                                                                                             
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 # --- LLM-Guided Fractal Zoom ---                                                                                                                         
 poetry run tranz zoom ai                                                                                                                                  
 poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 zoom -n 10 ai " -0.7436499" "0.13188204" "0.00073801"                                             
 poetry run tranz --iterm zoom ai "/path/to/image.png"                                                                                                     
 poetry run tranz --iterm zoom -s 700 --fractal julia ai                                                                                                   
                                                                                                                                                           
 # --- Human/Manual-Guided Fractal Zoom ---                                                                                                                
 poetry run tranz --iterm zoom manual " -0.74303" "0.126433" "0.01611"                                                                                     
 poetry run tranz zoom manual "/path/to/image.png"                                                                                                         
 poetry run tranz --iterm zoom -s 700 --fractal julia manual                                                                                               
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --fractal    -f                  Fractal type to generate; possible values: 'mandelbrot', 'julia'; default: 'mandelbrot'              │
│                                                                                                                                    │
│ --width      -w      INTEGER RANGE [16<=x<=16384]  Width of the image; 16 ≤ w ≤ 16384; default is 512                                     │
│ --height     -h      INTEGER RANGE [16<=x<=16384]  Height of the image; 16 ≤ h ≤ 16384; default is 512                                    │
│ --size       -s      INTEGER RANGE [16<=x<=16384]  Size of the image: *overrides* both `-w/--width` and `-h/--height` by determining the max pixel      │
│                                                    length of the final image, which will be proportional to the given frame, i.e., the final dimensions │
│                                                    will be scaled accordingly and, given a size S, will be either (S, x), (x, S) or (S, S), where x <   │
│                                                    S, and will make the final image ratio/proportion be the same as the frame; 16 ≤ S ≤ 16384; default  │
│                                                    is None, i.e., follow the explicit `-w/--width` and `-h/--height` options                            │
│ --max-steps  -n      INTEGER RANGE           Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C); default is 0       │
│                                                    (unlimited, run forever)                                                                             │
│                                                                                                                                             │
│ --julia-re           TEXT                          Real part of the Julia Set constant; this can be a float (ex: "0.34") or a fraction of ints          │
│                                                    (rational number, ex: "123/451") and the number will be fed directly to multi-precision arithmetic   │
│                                                    so no precision is lost; ALTERNATIVELY: you can use this to input an existing PNG image path, and it │
│                                                    will read the Julia Set constant from the given image's metadata frame *CENTER* (overriding/ignoring │
│                                                    the imaginary parameter part!); default is '0.27334'                                                 │
│                                                                                                                                       │
│ --julia-im           TEXT                          Imaginary part of the Julia Set constant; this can be a float (ex: "0.34") or a fraction of ints     │
│                                                    (rational number, ex: "123/451") and the number will be fed directly to multi-precision arithmetic   │
│                                                    so no precision is lost; default is '0.00742'                                                        │
│                                                                                                                                       │
│ --help                                             Show this message and exit.                                                                          │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ ai      Use AI to search for an interest point.                                                                                                         │
│ manual  Manually navigate a Mandelbrot zoom search (no AI).                                                                                             │
│ auto    Create a GIF/MP4 zoom fractal animation.                                                                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### `tranz zoom ai` Sub-Command

```text
Usage: tranz zoom ai [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                               
                                                                                                                                                           
 Use AI to search for an interest point.                                                                                                                   
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451")    │
│                               and the number will be fed directly to multi-precision arithmetic so no precision is lost; ALTERNATIVELY: you can use     │
│                               this to input an existing PNG image path, and it will read the frame from the given image's metadata (overriding/ignoring │
│                               the other CLI frame parameters!); default is '-0.75'                                                                      │
│                                                                                                                                         │
│   center_im      [CENTER_IM]  Imaginary part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:          │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '0'      │
│                                                                                                                                             │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:        │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '2.5'    │
│                                                                                                                                           │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:  │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is None,    │
│                               i.e, the same as width                                                                                                    │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --query   -q                 TEXT                      Query to be added to the default prompt; default is None, no additional query                    │
│ --reason      --no-reason                              If True, LLM sector evaluations will include an extra `reason` field for the AI output, which is │
│                                                        great for debugging and understanding the LLM, but is much slower on the LLM; if False, the      │
│                                                        field will not be included, which is faster; default is False                                    │
│                                                                                                                                     │
│ --memory                     INTEGER RANGE [0<=x<=30]  Maximum number of iterations the LLM will remember; 0 ≤ m ≤ 30; 0 (zero) means no memory, every  │
│                                                        AI call is independent; default is 5                                                             │
│                                                                                                                                             │
│ --help                                                 Show this message and exit.                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run tranz zoom ai                                                                                                                                
 <start with full set and zoom in using model Qwen 32>                                                                                                     
                                                                                                                                                           
 $ poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 zoom -n 10 ai " -0.7436499" "0.13188204" "0.00073801"                                           
 <zoom in using model Qwen 32 with higher temperature 0.7, start from "Seahorse Tail", stop after 10 steps>                                                
                                                                                                                                                           
 $ poetry run tranz --iterm zoom ai "/path/to/image.png"                                                                                                   
 <gets the same frame used in "/path/to/image.png" and starts zoom there, print iTerm2 images>                                                             
                                                                                                                                                           
 $ poetry run tranz --iterm zoom -s 700 --fractal julia ai                                                                                                 
 <start with full default Julia Set and AI zoom with 700px size, print iTerm2 images>
```

### `tranz zoom auto` Sub-Command

```text
Usage: tranz zoom auto [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                             
                        [DEST_MAGNIFICATION_10]                                                                                                            
                                                                                                                                                           
 Create a GIF/MP4 zoom fractal animation.                                                                                                                  
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re                  [CENTER_RE]              Real part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational   │
│                                                       number, ex: "123/451") and the number will be fed directly to multi-precision arithmetic so no    │
│                                                       precision is lost; ALTERNATIVELY: you can use this to input an existing PNG image path, and it    │
│                                                       will read the frame from the given image's metadata (overriding/ignoring the other CLI frame      │
│                                                       parameters!); default is '-0.75'                                                                  │
│                                                                                                                                         │
│   center_im                  [CENTER_IM]              Imaginary part of the center point; this can be a float (ex: "0.34") or a fraction of ints        │
│                                                       (rational number, ex: "123/451") and the number will be fed directly to multi-precision           │
│                                                       arithmetic so no precision is lost; default is '0'                                                │
│                                                                                                                                             │
│   f_width                    [F_WIDTH]                Width of the frame in the real plane; this can be a float (ex: "0.34") or a fraction of ints      │
│                                                       (rational number, ex: "123/451") and the number will be fed directly to multi-precision           │
│                                                       arithmetic so no precision is lost; default is '2.5'                                              │
│                                                                                                                                           │
│   f_height                   [F_HEIGHT]               Height of the frame in the imaginary plane; this can be a float (ex: "0.34") or a fraction of     │
│                                                       ints (rational number, ex: "123/451") and the number will be fed directly to multi-precision      │
│                                                       arithmetic so no precision is lost; default is None, i.e, the same as width                       │
│   dest_magnification_10      [DEST_MAGNIFICATION_10]  Magnification magnitude to go through in the animation zoom; ATTENTION!! this is exponential      │
│                                                       10**mag, so a value of 2.0 means 10**2 = 100x zoom; default is 1.00, i.e., 10.00x zoom            │
│                                                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --anim                                                             Type of animation to produce; possible values: 'gif', 'mp4'; default is     │
│                                                                             "gif"                                                                       │
│                                                                                                                                           │
│ --duration                             FLOAT RANGE [0.1<=x<=45000.0]        GIF/video duration, in seconds; 0.1 ≤ d ≤ 45000.0 or None; pick 2 out of    │
│                                                                             `--duration`, `--frames` and `--fps`, and the third will be computed;       │
│                                                                             default is None                                                             │
│ --frames                               INTEGER RANGE [3<=x<=100000]         Number of frames in GIF/video; 3 ≤ fr ≤ 100000 or None; pick 2 out of       │
│                                                                             `--duration`, `--frames` and `--fps`, and the third will be computed;       │
│                                                                             default is None                                                             │
│ --fps                                  FLOAT RANGE [0.1<=x<=30.0]           Frames per second (FPS) for the GIF/video; 0.1 ≤ fps ≤ 30.0 or None; pick 2 │
│                                                                             out of `--duration`, `--frames` and `--fps`, and the third will be          │
│                                                                             computed; default is None                                                   │
│ --loop                                 INTEGER RANGE [0<=x<=1000]           Number of loops for the GIF (NOT MP4!); 0 ≤ loop ≤ 1000; default is 0; zero │
│                                                                             (0) means infinite loops                                                    │
│                                                                                                                                             │
│ --iter         -i                      INTEGER RANGE [1000<=x<=2147483647]  Maximum iterations (depth) to compute before determining escape; 1000 ≤     │
│                                                                             iter ≤ 2147483647; default is None (automatic search for optimal iterations │
│                                                                             --- recommended)                                                            │
│ --mark                                 TEXT                                 A point formatted as "(re, im)" to add a crosshair overlay, `re` and `im`   │
│                                                                             multi-precision; this can be a float (ex: "(0.34, -0.56)") or a fraction of │
│                                                                             ints (rational numbers, ex: "(123/451, 789/1011)") or any combination of    │
│                                                                             these, and the numbers will be fed directly to multi-precision arithmetic   │
│                                                                             so no precision is lost; default is None, i.e., do not mark overlay on the  │
│                                                                             image                                                                       │
│ --mark-color                           TEXT                                 Color of the crosshair overlay; default is "red"; available colors:         │
│                                                                             'black', 'blue', 'cyan', 'green', 'magenta', 'red', 'white', 'yellow'       │
│                                                                                                                                           │
│ --mark-width                           INTEGER RANGE [1<=x<=50]             Width of the crosshair overlay; 1 ≤ w ≤ 50; default is 1        │
│ --save-frames      --no-save-frames                                         If True, will save the intermediate frames of the animation; if False,      │
│                                                                             intermediate frames will not be saved; default is False                     │
│                                                                                                                                │
│ --help                                                                      Show this message and exit.                                                 │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run tranz zoom auto
```

### `tranz zoom manual` Sub-Command

```text
Usage: tranz zoom manual [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                           
                                                                                                                                                           
 Manually navigate a Mandelbrot zoom search (no AI).                                                                                                       
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451")    │
│                               and the number will be fed directly to multi-precision arithmetic so no precision is lost; ALTERNATIVELY: you can use     │
│                               this to input an existing PNG image path, and it will read the frame from the given image's metadata (overriding/ignoring │
│                               the other CLI frame parameters!); default is '-0.75'                                                                      │
│                                                                                                                                         │
│   center_im      [CENTER_IM]  Imaginary part of the center point; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:          │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '0'      │
│                                                                                                                                             │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:        │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is '2.5'    │
│                                                                                                                                           │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; this can be a float (ex: "0.34") or a fraction of ints (rational number, ex:  │
│                               "123/451") and the number will be fed directly to multi-precision arithmetic so no precision is lost; default is None,    │
│                               i.e, the same as width                                                                                                    │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run tranz zoom manual                                                                                                                            
 <start with full set and zoom in manually>                                                                                                                
                                                                                                                                                           
 $ poetry run tranz --iterm zoom manual " -0.7436499" "0.13188204" "0.00073801"                                                                            
 <zoom in manually, start from "Seahorse Tail", print iTerm2 images>                                                                                       
                                                                                                                                                           
 $ poetry run tranz zoom manual "/path/to/image.png"                                                                                                       
 <gets the same frame used in "/path/to/image.png" and starts zoom there>                                                                                  
                                                                                                                                                           
 $ poetry run tranz --iterm zoom -s 700 --fractal julia manual                                                                                             
 <start with full default Julia Set and manual zoom with 700px size, print iTerm2 images>
```
