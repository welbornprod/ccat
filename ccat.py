#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" ccat.py
    ...Automatic syntax highlighting cat-like command.
    -Christopher Welborn 09-26-2014
"""
from __future__ import print_function
import json
import os
import sys
import docopt
import pygments
from pygments import formatters, lexers, styles

NAME = 'ColorCat'
VERSION = '0.4.0'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]
SCRIPTDIR = os.path.abspath(sys.path[0])

# Beyond 80 chars, I know.
USAGESTR = """{versionstr}
Usage:
    {script} -h | -v
    {script} [FILE...] [-b style] [-f name] [-g | -l name] [-s name]
         [-c | -C] [-D] [-n | -N] [-p] [--nosave]
    {script} -F | -L | -S

Options:
    FILE                         : One or many files to print.
                                   When - is given, or no FILEs are given,
                                   use stdin.
    -b style,--background style  : Either 'light', or 'dark'.
                                   Changes the highlight style.
    -c,--colors                  : Force colors, even when piping output.
    -C,--nocolors                : Don't use colors?
    -D,--debug                   : Debug mode. Show more info.
    -f name,--format name        : Format for output.
                                   Default: terminal
    -F,--formatters              : List all available formatters.
    -g,--guess                   : Guess lexer by file content.
    -h,--help                    : Show this help message.
    -l name,--lexer name         : Use this language/lexer name.
    -L,--lexers                  : List all known lexer names.
    -n,--linenos                 : Print line numbers.
    -N,--nolinenos               : Don't print line numbers.
                                   Overrides config setting.
    --nosave                     : Don't save options in config file.
    -p,--printnames              : Print file names.
    -s name,--style name         : Use this pygments style name.
    -S,--styles                  : List all known style names.
    -v,--version                 : Show version.
""".format(script=SCRIPT, versionstr=VERSIONSTR)

CONFIG = os.path.join(SCRIPTDIR, 'ccat.json')
# Config options that can be saved and reloaded for later.
CONFIGOPTS = (
    'background',
    'format',
    'linenos',
    'style'
)
NON_JSON_KEYS = {'formatfilename', 'printargs'}

# Known terminal-friendly formatters.
FORMATTERS = {
    'terminal': {
        'class': formatters.TerminalFormatter,
    },
    '256': {
        'class': formatters.Terminal256Formatter,
    },
    'html': {
        'class': formatters.HtmlFormatter,
        'default_args': {'full': True},
    }
}

DEBUG = False


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd """
    if argd['--lexers']:
        return 0 if print_lexers() else 1
    elif argd['--styles']:
        return 0 if print_styles() else 1
    elif argd['--formatters']:
        return 0 if print_formatters() else 1
    # Print files.
    config = parse_printer_config(argd)
    if argd['--nosave']:
        return 0 if print_files(config) else 1
    return 0 if (print_files(config) and save_config(config)) else 1


def filename_is_stdin(s):
    """ Returns True if this is an acceptable name for using stdin.
        Like None or '-'.
        Other names may be added in the future.
    """
    return (not s) or (s == '-')


def get_line_formatter(maxnum, linenos=True):
    """ Return a function to format a single line of output,
        with optional line numbers.
        Arguments:
            maxnum   : Largest line number encountered (len(lines)).
            linenos  : Whether to include line numbers.
    """
    if linenos:
        # Helps to format the line numbers. 1234 = len('1234') = .zfill(4)
        width = len(str(maxnum))

        def formatline(i, l):
            """ Line formatter, with line numbers. """
            return '{}: {}'.format(color(str(i).zfill(width), fore='cyan'), l)
        return formatline

    def formatline(i, l):
        """ Plain line formatter, no line numbers. """
        return l
    return formatline


def handle_file(filename, config):
    """ Use `print_file` to print a single file, and print any errors.
        A valid config object must be passed, given from parse_printer_config.
    """
    try:
        with open(filename, 'r') as f:
            if config['printnames']:
                print(config['formatfilename'](filename))
            if config['nocolors']:
                # Colors have been disabled, there is no reason to
                # use pygments at this point.
                return pipe_file(f, **config['printargs'])

            return print_file(f, **config['printargs'])
    except EnvironmentError as ex:
        print_status('Unable to read file:', filename, exc=ex)
    return False


def handle_stdin(config):
    """ Use `print_file` to handle stdin input, and print any errors.
        A valid config object must be passed, given from parse_printer_config.
    """
    if handle_stdin.handled:
        if config['debug']:
            print_status('stdin was already read, skipping.')
        return False

    if config['stdin_tty'] and config['stdout_tty']:
        print_status('\nUsing stdin, press CTRL + D for end of file.')

    if config['printnames']:
        print(config['formatfilename']('stdin'))
    handle_stdin.handled = True

    if config['nocolors']:
        # No colors, no pygments.
        return pipe_file(sys.stdin, **config['printargs'])
    return print_file(sys.stdin, **config['printargs'])


# Only read stdin once, but can be mixed in with other files.
# This is set to True if stdin has been read already.
handle_stdin.handled = False


def load_config(argd):
    """ Load settings from the config file, override them with cmdline options.
    """
    global DEBUG
    cmdline = {k.lstrip('-'): v for k, v in argd.items()}
    if not os.path.exists(CONFIG):
        return cmdline

    # Load config as json.
    try:
        with open(CONFIG, 'r') as f:
            config = json.load(f)
    except EnvironmentError as ex:
        print_status('Error loading config from:', CONFIG, exc=ex)
        return cmdline
    except ValueError as exparse:
        print_status('Error parsing config from:', CONFIG, exc=exparse)
        return cmdline

    # Merge the dicts.
    merged = cmdline.copy()
    for k, v in config.items():
        if k not in CONFIGOPTS:
            continue
        if v and not merged[k]:
            merged[k] = v
    # Signal that the config was loaded from file.
    if argd['--debug']:
        DEBUG = True
        print_debug(
            'Config loaded from: {}'.format(CONFIG),
            config)
    return merged


def parse_printer_config(argd):
    """ Parse user args into usable objects for `print_files` and `print_file`.
        Returns None on error.
        On success returns a dict of:
            {
                'background' : Name of background style.
                'debug'      : Whether to print debug info.
                'FILE'       : List of file names to print, where a None name
                               means to use stdin.
                'format'     : Name of formatter.
                'nocolors'   : Whether to pipe output without pygments.
                'stdin_tty'  : Whether stdin is a tty.
                'stdout_tty' : Whether stdout is a tty.
                'style'      : Style name for formatter.
                'printargs'  : Arguments for `print_file`:
                    {
                        'debug'    : Whether to print debug info.
                        'formatter': A pygments Formatter().
                        'linenos'  : Whether to print line numbers.
                    }
            }
    """
    config = load_config(argd)
    config['stdout_tty'] = sys.stdout.isatty()
    config['stdin_tty'] = sys.stdin.isatty()

    stylename = config['style'] or 'monokai'
    userformatter = config['format'] or 'terminal'
    if userformatter not in FORMATTERS:
        print_status('Bad formatter name:', userformatter)
        return None
    # Html requires a default arg, an init arg, and piping is okay.
    ishtml = formatted_pipe = (userformatter == 'html')
    if ishtml:
        # Formatter linenos, must be used with html instead of ccat linenos.
        fmtargs = {'linenos': not config['nolinenos']}
    else:
        fmtargs = {}

    formatter = try_formatter(
        userformatter,
        stylename,
        background=config['background'],
        args=fmtargs
    )
    if not formatter:
        print_status('Invalid style name:', stylename)
        print_status('Use \'ccat --styles\' to list known style names.')
        return None

    # Disable colors when piping output, unless the formatter will still work.
    if not (config['stdout_tty'] or formatted_pipe):
        # Html output is fine to pipe, or forced --colors.
        config['nocolors'] = not config['colors']

    if config['debug']:
        print_debug('linenos', config['linenos'] or 'False')

    # Disable ccat linenos automatically when piping output or for html.
    linenos = False if (config['nolinenos'] or ishtml) else config['linenos']

    if not config['FILE']:
        # No file names. Use stdin.
        config['FILE'] = [None]

    if config['nocolors']:
        config['formatfilename'] = '\n{}:'.format
    else:
        config['formatfilename'] = (
            lambda s: '\n{}:'.format(color(s, fore='blue')))

    # Arguments that apply to all files.
    config['printargs'] = {
        'formatter': formatter,
        'linenos': linenos,
        'debug': config['debug'],
    }
    if DEBUG:
        print_debug(
            'Final printer config',
            {k: v for k, v in config.items() if k not in NON_JSON_KEYS})
    return config


def pipe_file(fileobject, **kwargs):
    """ Just print the file to stdout. No formatting or anything.
        Arguments:
            fileobject  : An open fd to read from.

        Keyword Arguments:
            linenos     : Whether to print line numbers.
    """
    if not kwargs.get('linenos', False):
        # Straight piping.
        return pipe_file_simple(fileobject)
    return pipe_file_linenos(fileobject)


def pipe_file_linenos(fileobject):
    """ Straight file -> stdout pipine, with line numbers. """
    print_debug('Piping file with line numbers...')
    try:
        lines = fileobject.readlines()
    except Exception as ex:
        print_stderr('Unable to read the file: {}\n{}'.format(
            fileobject.name,
            ex))
        return False

    width = len(str(len(lines)))
    for i, line in enumerate(lines):
        print('{}: {}'.format(str(i).zfill(width), line), end='')

    return True


def pipe_file_simple(fileobject):
    """ Straight file -> stdout piping. No frills/customization. """
    print_debug('Piping file...')
    try:
        sys.stdout.buffer.write(fileobject.buffer.read())
    except EnvironmentError as ex:
        print_stderr('Unable to read the file: {}\n{}'.format(
            fileobject.name,
            ex))
        return False
    return True


def print_debug(lbl, value=None):
    """ Prints a formatted debug msg. """
    if DEBUG:
        if value:
            lbl = str(lbl).rjust(12)
            print_status('{}:'.format(lbl), value=value)
        else:
            print_status(str(lbl))


def print_file(fileobject, formatter, **kwargs):
    """ Print a file's content with highlighting.
        Arguments:
            fileobject  : An open fd to read from.
            lexer       : A Pygments Lexer(), pre-initialized.
                          If None, then guess the lexer based on content.
            formatter   : A Pygments Formatter(), pre-initialized.
                          (saves from creating a formatter on each file)
        Keyword Arguments:
            linenos     : Print line numbers.
    """
    lexer = kwargs.get('lexer', None)
    linenos = kwargs.get('linenos', False)

    if not formatter:
        raise ValueError('Need a formatter to use.')

    try:
        content = fileobject.read()
    except Exception as ex:
        print_status('Unable to read the file!:', exc=ex)
        return False

    if not lexer:
        print_debug('guessed', True)
        # try_lexer_guess() will fall back to 'text' lexer.
        lexer = try_lexer_guess(content)

    print_debug('lexer', lexer.name)
    hilitelines = pygments.highlight(
        content,
        lexer,
        formatter).splitlines()
    # An extra newline that 'cat' doesn't print.
    if not hilitelines[-1]:
        hilitelines.pop(-1)

    # Fix line number style for certain formatter styles.
    if isinstance(formatter, formatters.HtmlFormatter):
        # FIXME: Hack linenos style to match the main style.
        hilitelines.append(
            '<style>td.linenos { background-color: transparent; }</style>')

    # Set up the line formatter also.
    formatline = get_line_formatter(len(hilitelines), linenos=linenos)

    # Print the lines.
    for i, line in enumerate(hilitelines):
        print(formatline(i + 1, line))

    return True


def print_files(config):
    """ Print several files at once. Parses user string args into usable
        objects for `print_file` (Lexer(), Formatter()).
        Decides whether to disable all lexing (just piping input/output).
        Returns True for success, or False for errors (which are printed).
        Arguments:
            argd  : A docopt arg dict from the command line.
    """
    if not config:
        # Any user arg errors have been printed, just return.
        return False

    results = []
    for filename in config['FILE']:
        try:
            filename = filename.strip()
        except AttributeError:
            # Filename is None.
            pass
        if not set_lexer(filename, config):
            return False
        if filename_is_stdin(filename):
            results.append(handle_stdin(config))
        else:
            results.append(handle_file(filename, config))

    return all(results)


def print_formatters():
    """ Print all known formatters. """
    # These are terminal-friendly formatters, there are many others.
    print('\nAvailable formatters:')
    print('    {}'.format('\n    '.join(FORMATTERS)))
    return True


def print_lexers():
    """ Print all known lexer names. """
    print('\nLexer names:')

    def fmtlabel(lbl, ns):
        """ Format a label/list-items pair. """
        return '    {}: {}'.format(lbl, ', '.join(sorted(ns)))

    for lexerid in sorted(lexers.LEXERS, key=lambda k: lexers.LEXERS[k][1]):
        _, propername, names, types, __ = lexers.LEXERS[lexerid]
        print('\n{}'.format(propername))
        print(fmtlabel('names', names))
        if types:
            print(fmtlabel('types', types))

    return True


def print_status(msg, value=None, exc=None):
    """ Prints a color-coded status message.
        Arguments:
            msg   : Standard message to print.
            value : Extra value to print.
                    This makes 'msg' the label for this value.
            exc   : An exception. If set, the msg/value is red and the
                    exception is printed in bold red.
    """
    if sys.stdout.isatty():
        f = sys.stdout
    elif sys.stderr.isatty():
        f = sys.stderr
    else:
        # Nothing to print to,
        # status messages aren't important enough to be piped to file.
        return None

    if exc:
        # An error message, coming from an Exception.
        msg = color(msg, fore='red')
        if value is not None:
            msg = ' '.join((msg, color(str(value), fore='red', style='bold')))
        print('\n{}'.format(msg), file=sys.stderr)
        print('{}\n'.format(
            color(str(exc), fore='red', style='bold')),
            file=sys.stderr)
    else:
        # A normal msg, printed to the first available terminal.
        msg = color(msg, fore='cyan')

        if isinstance(value, (list, tuple, dict)):
            msg = ' '.join((
                msg,
                '\n{}'.format(
                    color(
                        json.dumps(value, indent=4, sort_keys=True),
                        fore='blue')
                )
            ))
        elif value:
            msg = ' '.join((
                msg,
                color(str(value), fore='blue', style='bold')
            ))
        print(msg, file=f)


def print_stderr(*args, **kwargs):
    """ A print that uses sys.stderr instead of stdout. No formatting. """
    if kwargs.get('file', None) is None:
        kwargs['file'] = sys.stderr
    print(*args, **kwargs)


def print_styles():
    """ Prints all known pygments styles. """
    print('\nStyle names:')
    for stylename in sorted(styles.STYLE_MAP):
        print('    {}'.format(stylename))
    return True


def save_config(config):
    """ Save the config object as json. """
    if DEBUG:
        debugconfig = {
            k: v for k, v in config.items()
            if k not in NON_JSON_KEYS
        }
        print_debug('Checking', value=debugconfig)
    config = {k: v for k, v in config.items() if v and (k in CONFIGOPTS)}
    if DEBUG:
        debugconfig = {
            k: v for k, v in config.items()
            if k not in NON_JSON_KEYS
        }
        print_debug('Valid config', value=debugconfig)
    if not config:
        print_debug('No config to save.')
        return False
    print_debug('Saving config', value=config)
    try:
        with open(CONFIG, 'w') as f:
            json.dump(config, f, indent=4, sort_keys=True)
    except TypeError as ex:
        print_stderr('Error saving config to:', CONFIG, exc=ex)
        return False
    return True


def set_lexer(filename, config):
    """ Set the printargs Lexer() for an individual file.
        A valid config object must be passed, given from parse_printer_config.
        Returns True on success, or False on fatal error.
    """
    if config['guess']:
        # Forced guess from the user.
        # print_file() will try to guess the lexer from the content.
        config['printargs']['lexer'] = None
        return True

    if config['lexer']:
        # Transform the user's lexer name into a real Lexer().
        # Filename may be stdin (None, or '-', or anything falsey).
        config['printargs']['lexer'] = try_lexer(
            config['lexer'],
            filename=filename)
        if config['printargs']['lexer']:
            return True

        # Lexer name was not transformed into a real Lexer().
        print_status('Bad lexer name:', config['lexer'])
        print_status('Use \'ccat --lexers\' to list known lexer names.')
        return False
    # No lexer name was given, guess it.
    config['printargs']['lexer'] = None
    return True


def try_formatter(formattername, stylename, background=None, args=None):
    """ Try getting a Formatter() to use with a style and optional bg style.
        Arguments:
            stylename  : A valid pygments style name.
            background : 'light' or 'dark'. Defaults to 'dark'
    """
    bgstyles = {
        'l': 'light',
        'light': 'light',
        'd': 'dark',
        'dark': 'dark',
        'none': 'dark'
    }
    bgstyle = bgstyles.get(str(background).lower(), bgstyles['none'])
    # Any passed-in formatter args.
    formatterargs = args.copy() if args else {}
    # Custom style arguments.
    formatterargs.update({
        'bg': bgstyle,
        'style': stylename.lower()
    })
    # Default formatter-based arguments.
    formatterargs.update(FORMATTERS[formattername].get('default_args', {}))
    formattername = formattername or 'terminal'
    formattercls = FORMATTERS[formattername]['class']

    print_debug('Formatter args for {}'.format(formattername), formatterargs)
    try:
        formatter = formattercls(**formatterargs)
    except pygments.util.ClassNotFound:
        return None
    return formatter


def try_lexer_guess(content):
    """ Try getting a pygments lexer by content.
        If it can't be guessed, return the default 'text' lexer.
    """
    try:
        lexer = lexers.guess_lexer(content)
    except pygments.util.ClassNotFound:
        return lexers.get_lexer_by_name('text')
    return lexer


def try_lexer(name, filename=None):
    """ Try getting a pygments lexer by name.
        None is returned if no lexer can be found by that name,
        unless 'filename' is given. If 'filename' is given the lexer
        is guessed by file name.
        Ultimately returns None on failure.
    """
    if not name:
        if filename_is_stdin(filename):
            # No lexer or file name.
            return None
        try:
            lexer = lexers.get_lexer_for_filename(filename)
        except pygments.util.ClassNotFound:
            return None
        # Retrieved by file name only.
        return lexer

    try:
        lexer = lexers.get_lexer_by_name(name)
    except pygments.util.ClassNotFound:
        if filename_is_stdin(filename):
            # No lexer found.
            return None
        try:
            lexer = lexers.get_lexer_for_filename(filename)
        except pygments.util.ClassNotFound:
            return None
        # Retrieved by falling back to file name.
        return lexer
    # Successful lexer by name.
    return lexer


class ColorCodes(object):
    # FIXME: The 'Colr' library may be used in the future, it provides several
    #        more options when working with colored output on linux.
    #        (this class was the starting point for Colr. Much has changed.)
    """ This class colorizes text for an ansi terminal.
        Inspired by Colorama (though very different)
    """
    class Invalid256Color(ValueError):
        pass

    def __init__(self):
        # Names and corresponding code number
        namemap = (
            ('black', 0),
            ('red', 1),
            ('green', 2),
            ('yellow', 3),
            ('blue', 4),
            ('magenta', 5),
            ('cyan', 6),
            ('white', 7)
        )
        self.codes = {'fore': {}, 'back': {}, 'style': {}}
        # Set codes for forecolors (30-37) and backcolors (40-47)
        for name, number in namemap:
            self.codes['fore'][name] = str(30 + number)
            self.codes['back'][name] = str(40 + number)
            lightname = 'light{}'.format(name)
            self.codes['fore'][lightname] = str(90 + number)
            self.codes['back'][lightname] = str(100 + number)

        # Set reset codes for fore/back.
        self.codes['fore']['reset'] = '39'
        self.codes['back']['reset'] = '49'

        # Map of code -> style name/alias.
        stylemap = (
            ('0', ['r', 'reset', 'reset_all']),
            ('1', ['b', 'bright', 'bold']),
            ('2', ['d', 'dim']),
            ('3', ['i', 'italic']),
            ('4', ['u', 'underline', 'underlined']),
            ('5', ['f', 'flash']),
            ('7', ['h', 'highlight', 'hilight', 'hilite', 'reverse']),
            ('22', ['n', 'normal', 'none'])
        )
        # Set style codes.
        for code, names in stylemap:
            for alias in names:
                self.codes['style'][alias] = code

        # Format string for full color code.
        self.codeformat = '\033[{}m'
        self.codefmt = lambda s: self.codeformat.format(s)
        self.closing = '\033[m'
        # Extended (256 color codes)
        self.extforeformat = '\033[38;5;{}m'
        self.extforefmt = lambda s: self.extforeformat.format(s)
        self.extbackformat = '\033[48;5;{}m'
        self.extbackfmt = lambda s: self.extbackformat.format(s)

        # Shortcuts to most used functions.
        self.word = self.colorword

    def color_code(self, fore=None, back=None, style=None):
        """ Return the code for this style/color
        """

        codes = []
        userstyles = {'style': style, 'back': back, 'fore': fore}
        for stype in userstyles:
            style = userstyles[stype].lower() if userstyles[stype] else None
            # Get code number for this style.
            code = self.codes[stype].get(style, None)
            if code:
                # Reset codes come first (or they will override other styles)
                codes.append(code)

        return self.codefmt(';'.join(codes))

    def color256(self, text=None, fore=None, back=None, style=None):
        """ Return a colored word using the extended 256 colors.
        """
        text = text or ''
        codes = []
        if style is not None:
            userstyle = self.codes['style'].get(style, None)
            if userstyle:
                codes.append(self.codefmt(userstyle))
        if back is not None:
            codes.append(self.make_256color('back', back))
        if fore is not None:
            codes.append(self.make_256color('fore', fore))

        codes.extend([
            text,
            self.codes['style']['reset_all'],
            self.closing
        ])
        return ''.join(codes)

    def colorize(self, text=None, fore=None, back=None, style=None):
        """ Return text colorized.
            fore,back,style  : Name of fore or back color, or style name.
        """
        text = text or ''

        return ''.join((
            self.color_code(style=style, back=back, fore=fore),
            text,
            self.closing))

    def colorword(self, text=None, fore=None, back=None, style=None):
        """ Same as colorize, but adds a style->reset_all after it. """
        text = text or ''
        colorized = self.colorize(
            text=text,
            style=style,
            back=back,
            fore=fore
        )
        s = ''.join((
            colorized,
            self.color_code(style='reset_all'),
            self.closing
        ))
        return s

    def make_256color(self, colortype, val):
        """ Create a 256 color code based on type ('fore' or 'back')
            out of a number (can be string).
            Raises ColorCodes.Invalid256Color() on error.
            Returns the raw color code on success.
        """
        try:
            ival = int(val)
        except (TypeError, ValueError):
            # Python 2 doesn't like 'raise e2 from e1'
            raise self.make_256error(colortype, val)
        else:
            if (ival < 0) or (ival > 255):
                raise self.make_256error(colortype, val)
        if colortype == 'fore':
            return self.extforefmt(str(ival))
        elif colortype == 'back':
            return self.extbackfmt(str(ival))

        # Should not make it here. Developer error.
        errmsg = 'Invalid colortype: {}'.format(colortype)
        raise ColorCodes.Invalid256Color(errmsg)

    def make_256error(self, colortype, val):
        """ Create a new "invalid 256 color number" error based on
            'fore' or 'back'.
            Returns the error, does not raise it.
        """
        errmsg = ' '.join((
            'Invalid number for {}: {}'.format(colortype, val),
            'Must be in range 0-255'))
        return ColorCodes.Invalid256Color(errmsg)


# Alias, convenience function for ColorCodes().
color = ColorCodes().colorword


class _ColorDocoptExit(SystemExit):

    """ Custom DocoptExit class, colorizes the help text. """

    usage = ''

    def __init__(self, message=''):
        usagestr = '{}\n{}'.format(message,
                                   _coloredhelp(self.usage)).strip()
        SystemExit.__init__(self, usagestr)


def _coloredhelp(s):
    """ Colorize the usage string for docopt
        (ColorDocoptExit, docoptextras)
    """
    newlines = []
    bigindent = (' ' * 16)
    for line in s.split('\n'):
        if line.strip('\n').strip().strip(':') in ('Usage', 'Options'):
            # label
            line = color(line, style='bold')
        elif (':' in line) and (not line.startswith(bigindent)):
            # opt,desc line. colorize it.
            lineparts = line.split(':')
            opt = lineparts[0]
            vals = [lineparts[1]] if len(lineparts) == 2 else lineparts[1:]

            # colorize opt
            if ',' in opt:
                opts = opt.split(',')
            else:
                opts = [opt]
            optstr = ','.join([color(o, 'blue') for o in opts])

            # colorize desc
            valstr = ':'.join(color(val, 'green') for val in vals)
            line = ':'.join([optstr, valstr])
        elif line.startswith(bigindent):
            # continued desc string..
            # Make any 'Default:Value' parts look the same as the opt,desc.

            line = ':'.join(color(s, 'green') for s in line.split(':'))
        elif (not line.startswith('    ')):
            # header line.
            line = color(line, 'red', style='bold')
        else:
            # everything else, usage mainly.
            # When copy/pasting this code, filename/scriptname is just the
            # script or filename that is displayed in Usage.
            line = line.replace(SCRIPT, color(SCRIPT, 'green'))

        newlines.append(line)
    return '\n'.join(newlines)


def _docoptextras(help_, version, options, doc):
    help_arg = any((o.name in ('-h', '--help')) and o.value for o in options)
    if help_ and help_arg:
        print(_coloredhelp(doc).strip('\n'))
        sys.exit()
    if version and any((o.name == '--version') and o.value for o in options):
        print(color(version, 'blue'))
        sys.exit()


# Functions to override default docopt stuff
docopt.DocoptExit = _ColorDocoptExit
docopt.extras = _docoptextras

if __name__ == '__main__':
    mainret = main(docopt.docopt(USAGESTR, version=VERSIONSTR))
    sys.exit(mainret)
