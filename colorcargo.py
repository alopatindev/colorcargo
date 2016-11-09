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

CARGO_PATH = '/usr/bin/cargo'
DIRPATH_SPACES = ' ' * 23  # FIXME
FILEPATH_PATTERN = ' at '
current_dir = os.path.split(os.getcwd())[1]


def set_func_color(trace, line, our_project):
    result = ''
    text = trace[line]

    block_color = Fore.RESET
    func_color = Fore.CYAN
    if our_project:
        block_color = Fore.YELLOW
        func_color = Fore.MAGENTA

    func_pos = text.find(' - ')
    if func_pos != 0:
        before_func = text[:func_pos]
        func = text[func_pos:]
        func_hash_pos = func_pos + func.rfind('::h')
        func_hash = ''
        if func_hash_pos != 0:
            func = text[func_pos:func_hash_pos]
            func_hash = text[func_hash_pos:]

        if len(before_func) != 0:
            result += block_color + before_func

        if len(func) != 0:
            func_prefix_pos = func.rfind('::')
            if func_prefix_pos != 0:
                func_prefix_pos += 2
                func_prefix = func[:func_prefix_pos]
                func_name = func[func_prefix_pos:]
                result += func_color + func_prefix + Style.BRIGHT + func_name
            else:
                result += Style.BRIGHT + func
            result += Style.NORMAL

        if len(func_hash) != 0:
            result += func_hash
    else:
        result = block_color + text

    trace[line] = result


def set_file_and_line_color(trace, line, our_project):
    result = ''
    text = trace[line]

    block_color = Fore.RESET
    filename_color = Fore.RESET
    file_line_color = Fore.RESET

    if our_project:
        block_color = Fore.YELLOW
        filename_color = Style.BRIGHT + Fore.GREEN
        file_line_color = Fore.WHITE

    parse_ok = True

    filename_and_line_pos = text.rfind('/')
    if filename_and_line_pos > 0:
        filename_and_line_pos += 1
        filename_and_line = text[filename_and_line_pos:]
        file_line_pos = filename_and_line.rfind(':')
        if file_line_pos != 0:
            filename = filename_and_line[:file_line_pos]
            file_line = filename_and_line[file_line_pos:]
            dirpath = text[:filename_and_line_pos]
            dirpath_pos = dirpath.find(FILEPATH_PATTERN)
            dirpath = DIRPATH_SPACES + block_color + dirpath[dirpath_pos:]
        else:
            parse_ok = False
    else:
        parse_ok = False

    if parse_ok:
        result = dirpath + filename_color + filename + \
            file_line_color + file_line
    else:
        result += text

    result += Style.NORMAL + Fore.RESET
    trace[line] = result


def set_colors(trace):
    n = len(trace)
    i = n - 1

    while i > 0:
        is_path = trace[i].find(FILEPATH_PATTERN)
        if is_path:
            our_project = trace[i].find(current_dir) != -1
            prev = i - 1
            set_func_color(trace, prev, our_project)
            set_file_and_line_color(trace, i, our_project)
        i -= 1


def parse_backtrace_and_print(trace):
    set_colors(trace)
    for i in trace:
        sys.stdout.write(i)


def consumer(pipe):
    found_backtrace = False

    trace = []

    while not pipe.poll():
        ch = pipe.stdout.read(1)

        if len(ch) == 0:
            break

        line = ch + pipe.stdout.readline()

        if found_backtrace:
            trace.append(line)
            if line.find('0x0 - <unknown>') != -1:
                found_backtrace = False
                parse_backtrace_and_print(trace)
        elif line.find('stack backtrace:') != -1:
            found_backtrace = True
            trace.append(line)
        else:
            sys.stdout.write(line)
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


main(sys.argv)
