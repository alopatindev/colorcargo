#!/bin/env python2
# -*- coding: utf-8 -*-

'''
MIT License

Copyright (c) 2016 Alexander Lopatin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import colorama
from colorama import Fore, Style
import os
import re
import sys
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
import traceback

VERBOSE = False
CARGO_PATH = '/usr/bin/cargo'

DEBUG = False
DIRPATH_SPACES = ' ' * 23  # FIXME
HASH_LENGTH = 16
BEFORE_FUNC_DELIMITER = ' - '

FILEPATH_PATTERN = ' at '
BORING_LINE_PATTERN = '/buildslave/rust-buildbot/slave/'
PANICKED_AT_PATTERN = "' panicked at '"
TEST_RESULT_PATTERN = 'test result: '

current_dir = os.getcwd()
current_dir_name = os.path.split(current_dir)[1]
current_dir_abs = current_dir + os.path.sep


def debug(prompt, error):
    if DEBUG:
        print >> sys.stderr, prompt, str(error)
        traceback.print_exc()


def update_file_path(trace, i, our_project):
    try:
        if our_project and not VERBOSE:
            text = trace[i]
            begin, end = text.split(current_dir_abs)
            trace[i] = begin + end
    except ValueError as error:
        debug('Parsing error: ', error)


def set_func_color(trace, line, our_project):
    result = ''
    text = trace[line].split('\n')[0]

    block_color = Fore.RESET
    func_color = Fore.CYAN
    if our_project:
        block_color = Fore.YELLOW
        func_color = Fore.MAGENTA

    func_pos = text.find(BEFORE_FUNC_DELIMITER)
    if func_pos >= 0:
        func_pos += len(BEFORE_FUNC_DELIMITER)
        before_func = text[:func_pos]
        func = text[func_pos:]

        hash_delimiter = '::h'
        func_hash_pos = func.rfind(hash_delimiter)

        hash_length = len(func) - (func_hash_pos + len(hash_delimiter))
        if func_hash_pos < 0 or hash_length != HASH_LENGTH:
            func_hash_pos = len(func)

        func_hash = func[func_hash_pos:]
        func = func[:func_hash_pos]

        if len(before_func) > 0:
            result += block_color + before_func

        if len(func) > 0:
            func_delimiter = '::'
            func_prefix_pos = func.rfind(func_delimiter)
            if func_prefix_pos >= 0:
                func_prefix_pos += len(func_delimiter)
                func_prefix = func[:func_prefix_pos]
                func_name = func[func_prefix_pos:]
                result += func_color + func_prefix + Style.BRIGHT + func_name
            else:
                result += Style.BRIGHT + func_color + func
            result += Style.NORMAL

        if len(func_hash) > 0:
            result += func_hash
    else:
        result = block_color + text

    result += Fore.RESET + '\n'
    trace[line] = result


def set_file_and_line_color(trace, line, our_project):
    result = ''
    text = trace[line]

    try:
        block_color = Fore.RESET
        filename_color = Fore.RESET
        file_line_color = Fore.RESET

        if our_project:
            block_color = Fore.YELLOW
            filename_color = Style.BRIGHT + Fore.GREEN
            file_line_color = Fore.WHITE

        filename_and_line_pos = text.rfind('/')
        assert filename_and_line_pos >= 0
        filename_and_line_pos += 1
        filename_and_line = text[filename_and_line_pos:]

        file_line_pos = filename_and_line.rfind(':')
        assert file_line_pos >= 0
        filename = filename_and_line[:file_line_pos]
        file_line = filename_and_line[file_line_pos:]

        dirpath = text[:filename_and_line_pos]
        dirpath_pos = dirpath.find(FILEPATH_PATTERN)
        assert dirpath_pos >= 0
        dirpath = DIRPATH_SPACES + block_color + dirpath[dirpath_pos:]

        result = dirpath + filename_color + filename + \
            file_line_color + file_line
        result += Style.NORMAL + Fore.RESET
    except Exception as error:
        debug('Parsing error: ', error)
        result = text
    finally:
        trace[line] = result


def set_panicked_line_color(text):
    result = ''
    try:
        func_color = Fore.MAGENTA
        block_color = Fore.YELLOW
        assert_color = Fore.RED
        filename_color = Style.BRIGHT + Fore.GREEN
        file_line_color = Fore.WHITE

        begin, thread_name, panicked_at, assert_failed, end = text.split("'")
        full_file_name = end.split(' ')[1]
        filename_pos = full_file_name.rfind('/')
        assert filename_pos >= 0
        filename_pos += 1
        dirpath = full_file_name[:filename_pos]
        filename_and_line_number = full_file_name[filename_pos:]
        filename, file_line = filename_and_line_number.split(':')

        result += begin
        result += "'" + func_color + thread_name + Fore.RESET + "'"
        result += panicked_at
        result += "'" + assert_color + assert_failed + Fore.RESET + "'"
        result += ', ' + block_color + dirpath
        result += filename_color + filename
        result += file_line_color + ':' + file_line
        result += Style.NORMAL + Fore.RESET
    except Exception as error:
        debug('Parsing error: ', error)
        result = text
    finally:
        return result


def set_test_result_line_color(text):
    result = ''
    result += Style.BRIGHT

    color = Fore.RED
    if text.find(': ok.') >= 0:
        color = Fore.GREEN
    result += color + text
    result += Style.NORMAL + Fore.RESET

    return result


def set_colors(trace):
    n = len(trace)

    for i in range(n - 1, 0, -1):
        line = trace[i]
        if line.find(FILEPATH_PATTERN) >= 0:
            our_project = trace[i].find(current_dir_name) >= 0
            prev = i - 1

            update_file_path(trace, i, our_project)

            set_func_color(trace, prev, our_project)
            set_file_and_line_color(trace, i, our_project)

    set_func_color(trace, n - 1, False)


def parse_backtrace_and_print(trace):
    try:
        set_colors(trace)
    except Exception as error:
        debug('Parsing error: ', error)
    finally:
        for text in trace:
            if VERBOSE or BORING_LINE_PATTERN not in text:
                sys.stdout.write(text)


def consumer(pipe):
    found_backtrace = False

    trace = []

    while not pipe.poll():
        ch = pipe.stdout.read(1)

        if len(ch) == 0:
            break

        text = ch + pipe.stdout.readline()

        if found_backtrace:
            trace.append(text)
            if text.find('0x0 - <unknown>') >= 0:
                found_backtrace = False
                parse_backtrace_and_print(trace)
        elif text.find('stack backtrace:') >= 0:
            found_backtrace = True
            trace.append(text)
        else:
            if text.find(PANICKED_AT_PATTERN) >= 0:
                text = set_panicked_line_color(text)
            elif text.find(TEST_RESULT_PATTERN) == 1:
                text = set_test_result_line_color(text)
            sys.stdout.write(text)
        sys.stdout.flush()


def main(argv):
    colorama.init()

    os.environ['RUST_BACKTRACE'] = '1'

    args = [CARGO_PATH]
    if len(argv) < 2:
        args += argv[1:]
    else:
        args += [argv[1], '--color=always'] + argv[2:]

    pipe = Popen(args=args, stdout=PIPE, stderr=STDOUT)
    try:
        thread = Thread(target=consumer, args=(pipe,))
        thread.start()
        thread.join()
    except KeyboardInterrupt:
        pipe.terminate()


try:
    main(sys.argv)
except Exception as error:
    debug('Parsing error: ', error)
