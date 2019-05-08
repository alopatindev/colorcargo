#!/bin/env python3

'''
MIT License

Copyright (c) 2016-2019 Alexander Lopatin

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

import configparser
import os
import re
import sys
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
import traceback

import colorama
from colorama import Fore, Style

DEBUG = False
DIRPATH_SPACES = ' ' * 23  # FIXME
HASH_LENGTH = 16
BEFORE_FUNC_DELIMITER = ' - '

FILEPATH_PATTERN = ' at '
BORING_LINE_PATTERN = re.compile(r'(/rustc|(src/(libstd|libpanic_unwind|libtest))|/var/tmp/portage|/sysdeps/unix/sysv/linux)/')
PANICKED_AT_PATTERN = "' panicked at '"
TEST_RESULT_PATTERN = 'test result: '
FUNC_DELIMITER = '::'
UNKNOWN_POLL_RESULT = 101


def debug(prompt, error):
    if DEBUG:
        print(prompt, str(error), file=sys.stderr)
        traceback.print_exc()


def set_func_color(trace, line, our_project):
    result = ''
    text = trace[line].split('\n')[0]

    block_color = Fore.RESET
    func_color = Fore.CYAN + Style.NORMAL
    if our_project:
        block_color = Fore.YELLOW
        func_color = Fore.MAGENTA + Style.NORMAL

    func_pos = text.find(BEFORE_FUNC_DELIMITER)
    if func_pos >= 0:
        func_pos += len(BEFORE_FUNC_DELIMITER)
        before_func = text[:func_pos]
        func = text[func_pos:]

        hash_delimiter = FUNC_DELIMITER + 'h'
        func_hash_pos = func.rfind(hash_delimiter)

        hash_length = len(func) - (func_hash_pos + len(hash_delimiter))
        if func_hash_pos < 0 or hash_length != HASH_LENGTH:
            func_hash_pos = len(func)

        func_hash = func[func_hash_pos:]
        func = func[:func_hash_pos]

        if len(before_func) > 0:
            before_func = Style.DIM + before_func
            result += block_color + before_func

        if len(func) > 0:
            func_prefix_pos = func.rfind(FUNC_DELIMITER)
            if func_prefix_pos >= 0:
                func_prefix_pos += len(FUNC_DELIMITER)
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
        filename, file_line, column = filename_and_line_number.split(':')

        result += begin
        result += "'" + func_color + thread_name + Fore.RESET + "'"
        result += panicked_at
        result += "'" + assert_color + assert_failed + Fore.RESET + "'"
        result += ', ' + block_color + dirpath
        result += filename_color + filename
        result += file_line_color + ':' + file_line + ':' + column
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


def set_colors(trace, our_package_pattern):
    n = len(trace)
    our_project = False
    for i in range(n):
        line = trace[i]
        is_filepath = line.find(FILEPATH_PATTERN) >= 0
        if is_filepath:
            set_file_and_line_color(trace, i, our_project)
        else:
            our_project = bool(our_package_pattern is not None and our_package_pattern.match(trace[i]))
            set_func_color(trace, i, our_project)


def parse_backtrace_and_print(trace, our_package_pattern, verbose):
    try:
        set_colors(trace, our_package_pattern)
    except Exception as error:
        debug('Parsing error: ', error)
    finally:
        for text in trace:
            if verbose or BORING_LINE_PATTERN.search(text) is None:
                sys.stdout.write(text)


def find_project_config():
    config_directory = os.getcwd()
    filename = 'Cargo.toml'
    while True:
        config_path = os.path.join(config_directory, filename)
        if os.path.isfile(config_path):
            return config_path
        elif len(config_directory) <= 1:
            break
        else:
            config_directory = os.path.split(config_directory)[0]


def compile_our_package_pattern():
    config_path = find_project_config()
    if config_path is not None:
        config = configparser.ConfigParser()
        config.read(config_path)
        package_name = config['package']['name'].strip('"').replace('-', '_')
        return re.compile(r'.* - [<]{0,1}' + package_name + FUNC_DELIMITER + r'.*')


def consume(pipe, verbose):
    our_package_pattern = compile_our_package_pattern()
    found_backtrace = False
    trace = []

    while True:
        poll_result = pipe.poll()
        if poll_result is not None and poll_result != UNKNOWN_POLL_RESULT:
            break

        ch = pipe.stdout.read(1)
        if len(ch) == 0:
            break

        text = ch + pipe.stdout.readline()
        text = text.decode()

        if found_backtrace:
            trace.append(text)
            if text.find('0x0 - <unknown>') >= 0:
                found_backtrace = False
                parse_backtrace_and_print(trace, our_package_pattern, verbose)
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

    os.environ['RUST_BACKTRACE'] = 'full'
    verbose = os.getenv('COLORCARGO_VERBOSE', '') == '1'

    args = ['cargo']
    if len(argv) < 2:
        args += argv[1:]
    else:
        args += [argv[1], '--color=always'] + argv[2:]

    pipe = Popen(args=args, stdout=PIPE, stderr=STDOUT)
    try:
        thread = Thread(target=consume, args=(pipe, verbose))
        thread.start()
        thread.join()
    except KeyboardInterrupt:
        pipe.terminate()


try:
    main(sys.argv)
except Exception as error:
    debug('Parsing error: ', error)
