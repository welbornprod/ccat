#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" ccat.py
    ...Automatic syntax highlighting cat-like command.
    -Christopher Welborn 09-26-2014
"""

import json
import os
import sys
import docopt
import pygments
from pygments import formatters, lexers, styles

NAME = 'CCat'
VERSION = '0.0.2'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]
SCRIPTDIR = os.path.abspath(sys.path[0])

USAGESTR = """{versionstr}
Usage:
    {script} -h | -v
    {script} [FILE...] [-b style] [-C] [-D] [-g | -l name] [-n | -N] [-p] [-s name]
    {script} -L | -S

Options:
    FILE                         : One or many files to print.
                                   When - is given, or no FILEs are given,
                                   use stdin.
    -b style,--background style  : Either 'light', or 'dark'.
                                   Changes the highlight style.
    -C,--nocolors                : Don't use colors?
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
""".format(script=SCRIPT, versionstr=VERSIONSTR)

CONFIG = os.path.join(SCRIPTDIR, 'ccat.json')
# Config options that can be saved and reloaded for later.
CONFIGOPTS = (
    'background',
    'linenos',
    'style'
)


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd """

    if argd['--lexers']:
        return 0 if print_lexers() else 1
    elif argd['--styles']:
        return 0 if print_styles() else 1

    # Print files.
    return 0 if print_files(argd) else 1


def filename_is_stdin(s):
    """ Returns True if this is an acceptable name for using stdin.
        Like None or '-'.
        Other names may be added in the future.
    """
    return (not s) or (s == '-')


def load_config(argd):
    """ Load settings from the config file, override them with cmdline options.
    """
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
        print_status('Error parsing config from:', CONFIG, exc=ex)
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
        print_debug(
            'Config loaded from: {}'.format(CONFIG),
            '\n{}'.format(json.dumps(config, indent=4, sort_keys=True)))
    return merged


def print_debug(lbl, value=None):
    """ Prints a formatted debug msg. """
    lbl = str(lbl).rjust(12)
    print_status('{}:'.format(lbl), value=value)


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
                debug       : Print extra debugging info.
                usecolor    : Use colors. This is ccat, not cat. Default: True
        """
        lexer = kwargs.get('lexer', None)
        linenos = kwargs.get('linenos', False)
        debug = kwargs.get('debug', False)
        usecolor = kwargs.get('usecolor', True)
        if not formatter:
            raise ValueError('Need a formatter to use.')

        try:
            content = fileobject.read()
        except Exception as ex:
            print_status('Unable to read the file!:', exc=ex)
            return False

        if usecolor:
            if not lexer:
                if debug:
                    print_debug('guessed', True)
                lexer = try_lexer_guess(content)

            if debug:
                print_debug('lexer', lexer.name)
            hcontent = pygments.highlight(
                content,
                lexer,
                formatter).split('\n')
            # An extra newline that 'cat' doesn't print.
            if not hcontent[-1]:
                hcontent.pop(-1)
        else:
            hcontent = content.split('\n')

        # Helps to format the line numbers. 1234 = len('1234') = .ljust(4)
        digitlen = len(str(len(hcontent)))
        # Set up the line number formatter to reduce if statements in the loop.
        if usecolor:
            formatnum = lambda ln: color(ln.ljust(digitlen), fore='cyan')
        else:
            formatnum = lambda ln: ln.ljust(digitlen)

        # Set up the line formatter also.
        if linenos:
            formatline = lambda i, l: '{}: {}'.format(formatnum(str(i)), l)
        else:
            formatline = lambda i, l: l

        # Print the lines.
        for i, line in enumerate(hcontent):
            print(formatline(i + 1, line))

        return True


def print_files(argd):
    """ Print several files at once. """
    config = load_config(argd)

    stylename = config['style'] or 'monokai'
    formatter = try_formatter(stylename, background=config['background'])
    if not formatter:
        print_status('Invalid style name:', stylename)
        print_status('Use \'ccat --styles\' to list known style names.')
        return False

    if config['debug']:
        print_debug('linenos', config['linenos'] or 'False')

    if config['nolinenos']:
        linenos = False
    else:
        linenos = config['linenos']

    def print_stdin_warn():
        if config['debug']:
            print_debug('\nUsing stdin, press CTRL + D for end of file.')

    def print_filename(s):
        """ Helper function, prints file names if --printnames is used """
        if config['printnames']:
            print('\n{}:'.format(color(s, fore='blue')))

    if not config['FILE']:
        # No file names. Use stdin.
        config['FILE'] = [None]

    # Arguments that apply to all files.
    printargs = {
        'formatter': formatter,
        'linenos': linenos,
        'debug': config['debug'],
        'usecolor': not config['nocolors']
    }

    results = []
    # Only read stdin once, but can be mixed in with other files.
    # This is set to True if stdin has been read already.
    stdin_read = False

    for filename in config['FILE']:
        usestdin = filename_is_stdin(filename)
        if config['guess']:
            printargs['lexer'] = None
        else:
            printargs['lexer'] = try_lexer(config['lexer'], filename=filename)

        if config['lexer'] and not printargs['lexer']:
            print_status('Bad lexer name:', config['lexer'])
            print_status('Use \'ccat --lexers\' to list known lexer names.')
            return False

        if usestdin:
            if stdin_read:
                if config['debug']:
                    print_status('stdin was already read, skipping.')
                continue
            print_stdin_warn()
            print_filename('stdin')
            results.append(print_file(sys.stdin, **printargs))
            stdin_read = True
        else:
            try:
                with open(filename, 'r') as fileobj:
                    print_filename(filename)
                    results.append(print_file(fileobj, **printargs))
            except EnvironmentError as ex:
                print_status('Unable to read file:', filename, exc=ex)

    return save_config(config) and all(results)


def print_lexers():
    """ Print all known lexer names. """
    print('\nLexer names:')
    fmtnames = lambda ns: '    names: {}'.format(', '.join(sorted(ns)))
    fmttypes = lambda ts: '    types: {}'.format(', '.join(sorted(ts)))
    for lexerid in sorted(lexers.LEXERS, key=lambda k: lexers.LEXERS[k][1]):
        _, propername, names, types, __ = lexers.LEXERS[lexerid]
        print('\n{}'.format(propername))
        print(fmtnames(names))
        if types:
            print(fmttypes(types))

    return True


def print_status(msg, value=None, exc=None):
    """ Prints a color-coded status message.
        Arguments:
            msg   : Standard message to print.
            value : Extra value to print, makes 'msg' the label for this value.
            exc   : An exception. If set, the msg/value is red and the
                    exception is printed in bold red.
    """

    if exc:
        msg = color(msg, fore='red')
        if value is not None:
            msg = ' '.join((msg, color(str(value), fore='red', style='bold')))
        print('\n{}'.format(msg))
        print('{}\n'.format(color(str(exc), fore='red', style='bold')))
    else:
        msg = color(msg, fore='cyan')
        if value is not None:
            msg = ' '.join((msg, color(str(value), fore='blue', style='bold')))
        print(msg)


def print_styles():
    """ Prints all known pygments styles. """
    print('\nStyle names:')
    for stylename in sorted(styles.STYLE_MAP):
        print('    {}'.format(stylename))
    return True


def save_config(config):
    """ Save the config object as json. """
    config = {k: v for k, v in config.items() if v and (k in CONFIGOPTS)}
    try:
        with open(CONFIG, 'w') as f:
            json.dump(config, f, indent=4, sort_keys=True)
    except TypeError as ex:
        print_status('Error saving config to:', CONFIG, exc=ex)
        return False
    return True


def try_formatter(stylename, background=None):
    """ Try getting a Formatter() to use,
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

    try:
        formatter = formatters.TerminalFormatter(
            bg=bgstyle,
            style=stylename.lower())
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
        self.ljust = self.wordljust
        self.rjust = self.wordrjust

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
        colorized = self.colorize(text=text, style=style, back=back, fore=fore)
        s = ''.join((
            colorized,
            self.color_code(style='reset_all'),
            self.closing))
        return s

    def make_256color(self, colortype, val):
        """ Create a 256 color code based on type ('fore' or 'back')
            out of a number (can be string).
            Raises ColorCodes.Invalid256Color() on error.
            Returns the raw color code on success.
        """
        try:
            ival = int(val)
        except (TypeError, ValueError) as ex:
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

    def wordljust(self, text=None, length=0, char=' ', **kwargs):
        """ Color a word and left justify it.
            Regular str.ljust won't work properly on a str with color codes.
            You can do colorword(s.ljust(length), fore='red') though.
            This adds the space before the color codes.
            Arguments:
                text    : text to colorize.
                length  : overall length after justification.
                char    : character to use for padding. Default: ' '

            Keyword Arguments:
                fore, back, style : same as colorizepart() and word()
        """
        text = text or ''
        spacing = char * (length - len(text))
        colored = self.colorword(text=text, **kwargs)
        return '{}{}'.format(colored, spacing)

    def wordrjust(self, text=None, length=0, char=' ', **kwargs):
        """ Color a word and right justify it.
            Regular str.rjust won't work properly on a str with color codes.
            You can do colorword(s.rjust(length), fore='red') though.
            This adds the space before the color codes.
            Arguments:
                text    : text to colorize.
                length  : overall length after justification.
                char    : character to use for padding. Default: ' '

            Keyword Arguments:
                fore, back, style : same as colorizepart() and word()
        """
        text = text or ''
        spacing = char * (length - len(text))
        colored = self.word(text=text, **kwargs)
        return '{}{}'.format(spacing, colored)

# Alias, convenience function for ColorCodes().
colorize = ColorCodes()
color = colorize.colorword


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


def _docoptextras(help, version, options, doc):
    if help and any((o.name in ('-h', '--help')) and o.value for o in options):
        print(_coloredhelp(doc).strip('\n'))
        sys.exit()
    if version and any(o.name == '--version' and o.value for o in options):
        print(color(version, 'blue'))
        sys.exit()

# Functions to override default docopt stuff
docopt.DocoptExit = _ColorDocoptExit
docopt.extras = _docoptextras

if __name__ == '__main__':
    mainret = main(docopt.docopt(USAGESTR, version=VERSIONSTR))
    sys.exit(mainret)
