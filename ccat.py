#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" ccat.py
    ...
    -Christopher Welborn 09-26-2014
"""

import os
import sys
import docopt
import pygments
from pygments import formatters, lexers, styles

NAME = 'ccat.py'
VERSION = '0.0.1'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]
SCRIPTDIR = os.path.abspath(sys.path[0])

USAGESTR = """{versionstr}
    Usage:
        {script} -h | -v
        {script} FILE... [-b style] [-g | -l name] [-s name]
        {script} -L | -S

    Options:
        FILE                         : One or many files to print.
        -b style,--background style  : Either 'light', or 'dark'.
                                       Changes the highlight style.
        -g,--guess                   : Guess lexer by file content.
        -h,--help                    : Show this help message.
        -l name,--lexer name         : Use this language/lexer name.
        -L,--lexers                  : List all known lexer names.
        -s name,--style name         : Use this pygments style name.
        -S,--styles                  : List all known style names.
        -v,--version                 : Show version.
""".format(script=SCRIPT, versionstr=VERSIONSTR)


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd """

    if argd['--lexers']:
        return 0 if print_lexers() else 1
    elif argd['--styles']:
        return 0 if print_styles() else 1

    # Print files.
    return 0 if print_files(argd) else 1


def print_file(filename, formatter, lexername=None, guesslexer=False):
    """ Print a file's content with highlighting. """
    use_stdin = filename == '-'
    if use_stdin:
        guesslexer = True

    if (not use_stdin) and (not os.path.exists(filename)):
        print_status('File does not exist:', filename)
        return False

    lexer = None
    if not guesslexer:
        if lexername:
            try:
                lexer = lexers.get_lexer_by_name(lexername)
            except pygments.util.ClassNotFound:
                print_status('No lexer by that name:', lexername)
                return False
        else:
            try:
                lexer = lexers.get_lexer_for_filename(filename)
            except pygments.util.ClassNotFound:
                # No lexer found.
                lexer = lexers.get_lexer_by_name('text')

    try:
        if filename in ('-', '--'):
            content = sys.stdin.read()
        else:
            with open(filename, 'r') as f:
                content = f.read()
    except EnvironmentError as exio:
        print_status('Error opening file:', filename, exc=exio)
        return False

    if guesslexer:
        lexer = lexers.guess_lexer(content)

    hcontent = pygments.highlight(content, lexer, formatter)
    for i, line in enumerate(hcontent.split('\n')):
        lineno = color('{:<4}'.format(i + 1), fore='cyan')
        print('{}: {}'.format(lineno, line))

    return True


def print_files(argd):
    """ Print several files at once. """
    stylename = argd['--style'] or 'monokai'
    bgstyles = {
        'l': 'light',
        'light': 'light',
        'd': 'dark',
        'dark': 'dark',
        'none': 'dark'
    }
    bgstyle = bgstyles.get(str(argd['--background']).lower(), bgstyles['none'])

    try:
        formatter = formatters.TerminalFormatter(
            bg=bgstyle,
            linenos=True,
            style=stylename.lower())
    except pygments.util.ClassNotFound:
        print_status('Invalid style name:', stylename)
        return False

    results = []
    for filename in argd['FILE']:
        results.append(
            print_file(
                filename,
                formatter=formatter,
                lexername=argd['--lexer'],
                guesslexer=argd['--guess']))
    return all(results)


def print_lexers():
    """ Print all known lexer names. """
    print('\nLexer names:')
    for lexerid in sorted(lexers.LEXERS):
        lexername = lexers.LEXERS[lexerid]
        print('    {}'.format(lexername))
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
        if value:
            msg = ' '.join((msg, color(value, fore='red', style='bold')))
        print('\n{}'.format(msg))
        print('{}\n'.format(color(str(exc), fore='red', style='bold')))
    else:
        msg = color(msg, fore='cyan')
        if value:
            msg = ' '.join(msg, color(value, fore='blue', style='bold'))
        print(msg)


def print_styles():
    """ Prints all known pygments styles. """
    print('\nStyle names:')
    for stylename in sorted(styles.STYLE_MAP):
        print('    {}'.format(stylename))
    return True


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
            raise self.make_256error(colortype, val) from ex
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
