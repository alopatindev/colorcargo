#!/bin/env python2
# -*- coding: utf-8 -*-
#
# MIT License
# 
# Copyright (c) 2016 Alexander Lopatin
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import colorama
from colorama import Fore, Style
import os
import re
import sys
from subprocess import Popen, PIPE, STDOUT
from threading import Thread


CARGO_PATH = '/usr/bin/cargo'
current_dir = os.path.split(os.getcwd())[1]


def set_func_color(trace, line):
    func_pos = trace[line].find(' - ')
    if func_pos > 0:
        before_func = trace[line][:func_pos]
        func = trace[line][func_pos:]
        func_hash_pos = func_pos + func.find('::h')
        func_hash = ''
        if func_hash_pos > 0:
            func = trace[line][func_pos:func_hash_pos]
            func_hash = trace[line][func_hash_pos:]
        trace[line] = Fore.YELLOW + before_func + \
            Style.BRIGHT + Fore.GREEN + func + \
            Style.NORMAL + func_hash + Fore.YELLOW
    else:
        trace[line] = Fore.YELLOW + trace[line]


def set_file_and_line_color(trace, line):
    parse_ok = True

    file_and_line_pos = trace[line].rfind('/') + 1
    if file_and_line_pos > 0:
        file_and_line = trace[line][file_and_line_pos:]
        file_line_pos = file_and_line.rfind(':')
        if file_line_pos > 0:
            file_name = file_and_line[:file_line_pos]
            file_line = file_and_line[file_line_pos:]
            dirpath = trace[line][:file_and_line_pos]
        else:
            parse_ok = False
    else:
        parse_ok = False

    if parse_ok:
        trace[line] = dirpath + Style.BRIGHT + Fore.RED + \
            file_name + Fore.WHITE + file_line + Style.RESET_ALL
    else:
        trace[line] = trace[line] + Style.RESET_ALL


def set_colors(trace):
    n = len(trace)
    i = n - 1
    while i > 0:
        if trace[i].find(current_dir) != -1:
            prev = i - 1
            set_func_color(trace, prev)
            set_file_and_line_color(trace, i)
            i -= 2
        else:
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
    thread = Thread(target=consumer, args=(pipe,))
    thread.start()


main(sys.argv)
