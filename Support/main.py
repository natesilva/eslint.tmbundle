#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ESLint validation plugin for TextMate
"""

from __future__ import print_function
import os
import sys
import time
import subprocess
import validator
from ashes import AshesEnv

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_PATH = 'tm-file://' + os.environ['TM_BUNDLE_SUPPORT']
ASHES_ENV = AshesEnv([os.path.join(THIS_DIR, 'templates')])

def validate():
    """
    Run ESLint validation using settings from the current TextMate
    environment. Return a list of issues.
    """

    eslint_command = os.environ.get('TM_JAVASCRIPT_ESLINT_ESLINT', 'eslint')
    the_validator = validator.Validator(eslint_command)

    filename = os.environ.get('TM_FILEPATH', None)
    input_is_html = not os.environ['TM_SCOPE'].startswith('source.js')
    line_offset = int(os.environ.get('TM_INPUT_START_LINE', 1)) - 1
    cwd = os.environ.get('TM_DIRECTORY', None)
    if not cwd:
        cwd = os.environ.get('TM_PROJECT_DIRECTORY', None)

    try:
        issues = the_validator.run(
            filename=filename,
            input_is_html=input_is_html,
            line_offset=line_offset,
            cwd=cwd
        )
    except validator.ValidateError as err:
        context = {
            'BASE_PATH': BASE_PATH,
            'timestamp': time.strftime('%c'),
            'errorMessage': err.message,
        }
        if err.path:
            context['searchPath'] = err.path
            html = ASHES_ENV.render('error_eslint_path.html', context)
        else:
            html = ASHES_ENV.render('error_eslint_other.html', context)
        print(html)
        sys.exit()

    return issues

def full_report():
    """ Run ESLint and output an HTML report. """

    issues = validate()

    context = {
        'BASE_PATH': BASE_PATH,
        'issues': issues,
        'targetFilename': '(current unsaved file)',
        'targetUrl': 'txmt://open?line=1&amp;column=0'
    }

    if 'TM_FILEPATH' in os.environ:
        context['targetFilename'] = os.path.basename(os.environ['TM_FILEPATH'])
        context['targetUrl'] = 'txmt://open?url=file://%s' % os.environ['TM_FILEPATH']

    error_count = 0
    warning_count = 0

    for issue in issues:
        if issue['isError']:
            error_count += 1
        if issue['isWarning']:
            warning_count += 1

    context['hasErrorsOrWarnings'] = error_count + warning_count > 0

    if error_count == 1:
        context['errorCountString'] = '1 error'
    elif error_count:
        context['errorCountString'] = '%s errors' % error_count

    if warning_count == 1:
        context['warningCountString'] = '1 warning'
    elif warning_count:
        context['warningCountString'] = '%s warnings' % warning_count

    html = ASHES_ENV.render('report.html', context)
    print(html)


def quiet():
    """ Run ESLint and display a summary of the results as a tooltip. """

    issues = validate()
    update_gutter_marks(issues)

    error_count = 0
    warning_count = 0

    for issue in issues:
        if issue['isError']:
            error_count += 1
        if issue['isWarning']:
            warning_count += 1

    parts = []
    if error_count:
        parts.append('{0} error{1}'.format(error_count, 's' if error_count > 1 else ''))
    if warning_count > 0:
        parts.append('{0} warning{1}'.format(warning_count, 's' if warning_count > 1 else ''))
    result = ', '.join(parts)
    if result:
        result += '\r\rPress Shift-Ctrl-V to view the full report.'
    print(result)


def update_gutter_marks(issues):
    """
    Update the gutter marks in TextMate that indicate an issue on a
    particular line.
    """
    mate = os.environ['TM_MATE']
    file_path = os.environ['TM_FILEPATH']

    marks = []

    for item in issues:
        msg = item['reason']
        if 'shortname' in item:
            msg += ' ({0})'.format(item['shortname'])
        pos = '{0}:{1}'.format(item['line'], item['character'])
        marks.append((msg, pos))

    subprocess.call([mate, '--clear-mark=warning', file_path])

    for mark in marks:
        subprocess.call(
            [
                mate,
                '--set-mark=warning:[ESLint] {0}'.format(mark[0]),
                '--line={0}'.format(mark[1]),
                file_path
            ]
        )


def fix():
    """ Run the eslint --fix command against the current file. """
    if 'TM_FILEPATH' not in os.environ:
        # ignore if file is not saved
        return

    if not os.environ['TM_SCOPE'].startswith('source.js'):
        # refuse to run against HTML-embedded JavaScript
        return

    eslint_command = os.environ.get('TM_JAVASCRIPT_ESLINT_ESLINT', 'eslint')
    the_validator = validator.Validator(eslint_command)
    filename = os.environ['TM_FILEPATH']
    cwd = os.environ.get('TM_DIRECTORY', None)
    if not cwd:
        cwd = os.environ.get('TM_PROJECT_DIRECTORY', None)

    the_validator.fix(filename, cwd)

    mate = os.environ['TM_MATE']
    subprocess.call([mate, '--clear-mark=warning', filename])


if __name__ == '__main__':
    if '--html' in sys.argv:
        full_report()
    elif '--fix' in sys.argv:
        fix()
    else:
        quiet()