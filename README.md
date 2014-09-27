ccat
====

Colorized `cat` command written in Python. It uses `pygments` to detect
the language and highlight it for the terminal. Supports all `pygments`
lexers and styles. It saves the last style you used for the next run.
You can manually specify a lexer if you don't like pygment's 'guess'.

Config is saved as **JSON** in `ccat.json`. You can configure your preferences
there to be used on each run. It saves you from typing
`ccat myfile.hs -s monokai -b light` every time.

Requirements:
-------------

* **docopt** - Handles command-line argument parsing.
* **pygments** - Syntax highlighting library for Python.


Example:
--------

I recommend you symlink this in `/usr/bin`, `~/.local/bin`, or another
directory in `$PATH`. Here are a couple basic usage examples:

```
    ccat myfile.py
    echo "import os" | ccat
```

To show some debugging info, like which lexer was used:

```
    ccat myfile -D
```


Options:
--------

```
Usage:
    ccat -h | -v
    ccat [FILE...] [-b style] [-D] [-g | -l name] [-n | -N] [-p] [-s name]
    ccat -L | -S

Options:
    FILE                         : One or many files to print.
                                   When - is given, or no FILEs are given,
                                   use stdin.
    -b style,--background style  : Either 'light', or 'dark'.
                                   Changes the highlight style.
    -D,--debug                   : Debug mode. Show more info.
    -g,--guess                   : Guess lexer by file content.
    -h,--help                    : Show this help message.
    -l name,--lexer name         : Use this language/lexer name.
    -L,--lexers                  : List all known lexer names.
    -n,--linenos                 : Print line numbers.
    -N,--nolinenos               : Don't print line numbers.
                                   Overrides config setting.
    -p,--printnames              : Print file names.
    -s name,--style name         : Use this pygments style name.
    -S,--styles                  : List all known style names.
    -v,--version                 : Show version.
```

**P.S.**: *The most useless use of `cat` ever:*

```
cat myfile.py | ccat
```
