<!-- cspell:disable -->
<!-- auto-generated; DO NOT EDIT! see base.GenerateTyperHelpMarkdown() -->

# `zoom` Command-Line Interface

```text
Usage: zoom [OPTIONS] COMMAND [ARGS]...                                                                                                                   
                                                                                                                                                           
 TranZoom will do things!                                                                                                                                  
                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                                                                 Show version and exit.                                                        │
│ --verbose             -v                INTEGER RANGE [0<=x<=3]           Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).      │
│ --color                   --no-color                                      Force enable/disable colored output (respects NO_COLOR env var if not         │
│                                                                           provided). Defaults to having colors.                                         │
│ --out                 -o                DIRECTORY                         The local output root directory path, ex: "~/foo/bar/"; if not given, the     │
│                                                                           image will be saved in the current working directory                          │
│ --prefix                                TEXT                              Image save prefix; default: 'mandel' (the final file name will be             │
│                                                                           "<prefix>[-<date>][-<hash20>].png", note the date and the hash can be turned  │
│                                                                           off with --no-date and --no-hash, respectively)                               │
│                                                                                                                                        │
│ --date                    --no-date                                       If True, file names will include the date-time as YYYYMMDDhhmmss; if False,   │
│                                                                           file names will not include the date-time; default is True                    │
│                                                                                                                                          │
│ --hash                    --no-hash                                       If True, file names will include the hash; if False, file names will not      │
│                                                                           include the hash; default is True                                             │
│                                                                                                                                          │
│ --threads                               INTEGER RANGE [1<=x<=16]          Number of threads to use for rendering; default is None, which means to use   │
│                                                                           all available CPU cores; will be limited to 16 threads                        │
│ --model               -m                TEXT                              LLM model to load and use: the model must be compatible with the              │
│                                                                           llama.cpp/LMStudio client libraries; will NOT get the model for you, so make  │
│                                                                           sure you either have it available in your LMStudio or the model files are     │
│                                                                           under the specified models root path (`-r/--root` option); should be a string │
│                                                                           you would use with `lms get <THIS>` or `https://huggingface.co/<THIS>`;       │
│                                                                           default: 'qwen3-8b@Q8_0', a good general-purpose text (non-vision) model      │
│                                                                                                                                 │
│ --tokens              -t                INTEGER RANGE [2<=x<=200]         Speculative Decoding: controls how many tokens the model should generate in   │
│                                                                           advance during auto-tagging; if you do not define this flag then speculative  │
│                                                                           decoding will be disabled; usually this is a small value, like 4 or 8, and it │
│                                                                           can improve the speed of processing by allowing the model to generate tokens  │
│                                                                           in parallel; default: None (disabled)                                         │
│ --seed                -s                INTEGER RANGE [2<=x<=2147483647]  A seed value for the random number generator used to load the models into     │
│                                                                           memory; providing a seed ensures reproducibility of the results; default:     │
│                                                                           None (randomized seed)                                                        │
│ --context                               INTEGER RANGE [16<=x<=16777216]   Maximum number of tokens to use as context for the model; default: 32768      │
│                                                                           tokens                                                                        │
│                                                                                                                                         │
│ --temperature         -x                FLOAT RANGE [0.0<=x<=2.0]         Temperature controls how random token selection is during generation; [0 or   │
│                                                                           near 0]: most deterministic, focused, repetitive, best for extraction /       │
│                                                                           structured output / coding / tool use; [0.2-0.5]: still stable, but less      │
│                                                                           rigid; [0.7-1.0]: more natural and varied; [>1.0]: often more creative, but   │
│                                                                           also more errors, drift, and nonsense; default: 0.150 (a good value for       │
│                                                                           structured output and tool use)                                               │
│                                                                                                                                          │
│ --gpu                 -g                FLOAT RANGE [0.1<=x<=1.0]         GPU ratio to use, a value between 0.1 (10%) and 1.0 (100%) that indicates the │
│                                                                           percentage of GPU resources to allocate to AI; default: 0.80                  │
│                                                                                                                                           │
│ --gpu-layers                            INTEGER RANGE [-1<=x<=128]        Number of layers offloaded to GPU; default: -1 (which means "as many as       │
│                                                                           possible")                                                                    │
│                                                                                                                                            │
│ --fp16                    --no-fp16                                       Use FP16 precision for the auto-tagger model? This can reduce memory usage    │
│                                                                           and potentially increase speed, but may slightly affect the accuracy of the   │
│                                                                           tagging results default: False (do not use FP16, use full precision)          │
│                                                                                                                                       │
│ --mmap                    --no-mmap                                       Use memory-mapped file loading (if supported)? default: True (use mmap)       │
│                                                                                                                                          │
│ --flash                   --no-flash                                      Enable flash attention (if supported)? default: True (use flash)              │
│                                                                                                                                         │
│ --kv-cache                              INTEGER RANGE [4<=x<=128]         GGML type for KV-cache keys/values (if supported): determines the precision   │
│                                                                           level used to store keys/values; default: None (store according to original   │
│                                                                           precision in model)                                                           │
│ --timeout                               FLOAT RANGE [0.0<=x<=86400.0]     Timeout, in seconds, for AI calls; zero, or <1s, means no timeout (infinite); │
│                                                                           default: 300.0 seconds                                                        │
│                                                                                                                                         │
│ --install-completion                                                      Install completion for the current shell.                                     │
│ --show-completion                                                         Show completion for the current shell, to copy it or customize the            │
│                                                                           installation.                                                                 │
│ --help                                                                    Show this message and exit.                                                   │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ markdown  Emit Markdown docs for the CLI (see README.md section "Versioning and releases").                                                             │
│ ai        Use AI to search for an interest point.                                                                                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## `zoom ai` Command

```text
Usage: zoom ai [OPTIONS] [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]                                                                                     
                                                                                                                                                           
 Use AI to search for an interest point.                                                                                                                   
                                                                                                                                                           
╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   center_re      [CENTER_RE]  Real part of the center point; default is '-0.75'                                                         │
│   center_im      [CENTER_IM]  Imaginary part of the center point; default is '0'                                                            │
│   f_width        [F_WIDTH]    Width of the frame in the real plane; default is '2.5'                                                      │
│   f_height       [F_HEIGHT]   Height of the frame in the imaginary plane; default is None, i.e, the same as width                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --max-steps  -n                INTEGER RANGE   Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C); default is 0     │
│                                                      (unlimited, run forever)                                                                           │
│                                                                                                                                             │
│ --iterm          --no-iterm                          If True, will output the image to iTerm2 (only use on macOS with iTerm2!                           │
│                                                      <https://iterm2.com/documentation-images.html>); if False, will not output the image to iTerm2;    │
│                                                      default is False                                                                                   │
│                                                                                                                                      │
│ --help                                               Show this message and exit.                                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                                                                                           
 Examples:                                                                                                                                                 
                                                                                                                                                           
 $ poetry run zoom -m "qwen3-vl-32b-instruct@q8_0" ai                                                                                                      
 <start with full set and zoom in using model Qwen 32>                                                                                                     
                                                                                                                                                           
 $ poetry run zoom -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 ai " -0.7436499" "0.13188204" "0.00073801" --iterm -n 10                                         
 <zoom in using model Qwen 32 with higher temperature 0.7, start from "Seahorse Tail", print iTerm2 images, stop after 10 steps>
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
