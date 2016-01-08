#!/usr/bin/env python

import sys
import json
import time
import re
import getpass

file_fmt = '''/**
 * @file {filename}
 * @version 0.2.0
 *
 * @section License
 * Copyright (C) 2014-2016, Erik Moqvist
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * This file is part of the Simba project.
 */

/**
 * This file was generated by gen.py {major}.{minor} {date}.
 */

#include "simba.h"
#include <stdarg.h>

{sysinfo}

{fs}

{log}
'''

sysinfo_fmt = '''const FAR char sysinfo[] = "app:   {name}-{version} built {date} by {user}.\\r\\n"
                           "board: {board}\\r\\n"
                           "mcu:   {mcu}\\r\\n";
'''

fs_fmt = '''{command_externs}

{counter_externs}

{parameter_externs}

{strings}

const FAR struct fs_node_t fs_nodes[] = {{
{fs_nodes}
}};

const FAR int fs_counters[] = {{
{counters_list}
  -1
}};

const FAR int fs_parameters[] = {{
{parameters_list}
  -1
}};
'''

log_fmt = '''{argument_structures}

{write_functions}

{format_functions}

void (*log_id_to_format_fn[])(chan_t *, void *) = {{
{format_functions_array}
}};
'''

command_extern_fmt = 'extern int {callback}(int argc, const char *argv[], void *out_p, void *in_p);'
counter_extern_fmt = 'extern long long COUNTER({name});'
parameter_extern_fmt = 'extern {type} PARAMETER({name});'

strings_fmt = 'static FAR const char fs_string_{name}[] = "{value}";'

node_fmt = '''    /* index: {index} */
    {{
        .next = {next},
        .name_p = {name},
        .children = {{
            .begin = {begin},
            .end = {end},
            .len = {len}
        }},
        .parent = {parent},
        .callback = {callback}
    }},'''

list_entry_fmt = '{index},'

argument_structure_fmt = '''struct {name}_t {{
{members}
}};
'''

write_function_fmt = '''int {name}_write(char level, ...)
{{
    struct {name}_t args;
    va_list va;

    va_start(va, level);
{args}
    va_end(va);

    return (log_write(level, {identity}, &args, sizeof(args)));
}}
'''

format_function_fmt = '''void {name}_format(chan_t *chan_p, struct {name}_t *args_p)
{{
    std_fprintf(chan_p, FSTR("{fmt}")
{args}
);
}}
'''

major = 1
minor = 0

nodeindex = 0

def generate_nodes(parent, nodes, name, children, next, path):
    global nodeindex
    index = nodeindex
    nodeindex += 1
    if type(children) == type(''):
        begin = 0
        end = 0
        length = 0
        callback = children
    else:
        end = nodeindex
        length = len(children)
        callback = "NULL"
        i = 0
        for n, c in children.items():
            i = generate_nodes(index, nodes, n, c, i, path + name + "/")
        begin = i
    nodes.append((index,
                  node_fmt.format(index=index,
                                  next=next,
                                  name='fs_string_' + name,
                                  begin=begin,
                                  end=end,
                                  len=length,
                                  parent=parent,
                                  callback=callback),
                  name,
                  (path + name).replace('/__slash', '')))
    return index

def generate_fs(infiles):
    """Generate file system commands, counters and parameters.
    """
    re_command = re.compile(r'^\s*\.\.fs_command\.\. '
                            '"(?P<path>[^"]+)" '
                            '"(?P<callback>[^"]+)";\s*$', re.MULTILINE)
    re_counter = re.compile(r'^\s*\.\.fs_counter\.\. '
                            '"(?P<path>.+)" '
                            '\.\.fs_separator\.\. '
                            '"(?P<name>[^"]+)";\s*', re.MULTILINE)
    re_parameter = re.compile(r'^\s*\.\.fs_parameter\.\. '
                              '"(?P<path>[^"]+)" '
                              '"(?P<name>[^"]+)" '
                              '"(?P<type>[^"]+)";\s*$',
                              re.MULTILINE)

    # create lists of files and counters
    commands = []
    counters = []
    parameters = []
    for inf in infiles:
        file_content = open(inf).read()
        for mo in re_command.finditer(file_content):
            path = mo.group('path').replace('" "', '')
            commands.append([path, mo.group('callback')])
        for mo in re_counter.finditer(file_content):
            path = mo.group('path').replace('" "', '')
            counters.append([path, mo.group('name')])
            commands.append([path, 'fs_counter_cmd_' + mo.group('name')])
        for mo in re_parameter.finditer(file_content):
            path = mo.group('path').replace('" "', '')
            parameters.append([path,
                               mo.group('name'),
                               mo.group('type')])
            commands.append([mo.group('path'), 'fs_parameter_cmd_' + mo.group('name')])

    fs = {}
    command_externs = []

    # create a dictionary of given file system
    for command in commands:
        parts = command[0].split('/')[1:]
        name = parts[-1]
        parts = parts[0:-1]
        callback = command[1]
        fspath = fs
        for part in parts:
            if not part in fspath:
                fspath[part] = {}
            fspath = fspath[part]
        fspath[name] = callback
        command_externs.append(command_extern_fmt.format(callback=callback))

    # generate counters
    counter_externs = []
    for counter in counters:
        counter_externs.append(counter_extern_fmt.format(name=counter[1]))

    #parameters
    parameter_externs = []
    for parameter in parameters:
        parameter_externs.append(parameter_extern_fmt.format(name=parameter[1],
                                                             type=parameter[2]))

    # generate c source file
    fs_nodes = []
    generate_nodes(-1, fs_nodes, '__slash', fs, 0, "/")
    fs_nodes.sort(key=lambda n: n[0])

    # strings
    strings = [strings_fmt.format(name=name,
                                  value=name)
               for _, _, name, _ in fs_nodes
               if name != '__slash']
    strings.append(strings_fmt.format(name='__slash', value="/"))

    # remote duplicates
    strings = list(set(strings))

    # counters list
    counters_list = []
    for counter in counters:
        for node in fs_nodes:
            if counter[0] == node[3]:
                counters_list.append(list_entry_fmt.format(index=node[0]))
                break

    # parameters list
    parameters_list = []
    for parameter in parameters:
        for node in fs_nodes:
            if parameter[0] == node[3]:
                parameters_list.append(list_entry_fmt.format(index=node[0]))
                break

    return fs_fmt.format(command_externs='\n'.join(command_externs),
                         counter_externs='\n'.join(counter_externs),
                         parameter_externs='\n'.join(parameter_externs),
                         strings='\n'.join(strings),
                         fs_nodes='\n'.join(n[1] for n in fs_nodes),
                         counters_list='\n'.join(counters_list),
                         parameters_list='\n'.join(parameters_list))


def parse_format_types(fmt):
    types =[]
    for mo in re.finditer(r"(%f|%c|%d|%ld|%u|%lu)", fmt):
        if mo.group(1) == '%f':
            types.append('double')
        elif mo.group(1) == '%c':
            types.append('int')
        elif mo.group(1) == '%d':
            types.append('int')
        elif mo.group(1) == '%ld':
            types.append('long')
        elif mo.group(1) == '%u':
            types.append('unsigned int')
        elif mo.group(1) == '%lu':
            types.append('unsigned long')
    return types


def log_point_gen(identity, name, fmt):
    types = parse_format_types(fmt)

    struct_members = []
    write_args = []
    format_args = []
    for i, type in enumerate(types):
        struct_members.append('        {type} arg{number};'.format(type=type,
                                                                   number=i))
        write_args.append('    args.arg{number} = va_arg(va, {type});'.format(type=type,
                                                                              number=i))
        format_args.append('    , args_p->arg{number}'.format(number=i))

    argument_structures = argument_structure_fmt.format(name=name,
                                                        members='\n'.join(struct_members))
    write_functions = write_function_fmt.format(identity=identity,
                                                name=name,
                                                args='\n'.join(write_args))
    format_functions = format_function_fmt.format(name=name,
                                                  fmt=fmt,
                                                  args='\n'.join(format_args))

    return argument_structures, write_functions, format_functions


def generate_log(infiles):
    """Generate log identities and strings.
    """
    re_log = re.compile(r'^\s*\.\.log-begin\.\. '
                        '(?P<name>[^ ]+) '
                        '"(?P<fmt>[^"]+)" '
                        '\.\.log-end\.\.;\s*$',
                        re.MULTILINE)


    # create lists of files and counters
    log_points = []
    for inf in infiles:
        file_content = open(inf).read()
        for mo in re_log.finditer(file_content):
            log_points.append([mo.group('name'), mo.group('fmt')])

    argument_structures = []
    write_functions = []
    format_functions = []
    format_functions_array = []
    for identity, log_point in enumerate(log_points):
        name = log_point[0]
        fmt = log_point[1]

        argument_structure, write_function, format_function = log_point_gen(identity, name, fmt)
        argument_structures.append(argument_structure)
        write_functions.append(write_function)
        format_functions.append(format_function)

        format_functions_array.append("    (void (*)(chan_t *, void *)){name}_format,".format(name=name))

    return log_fmt.format(argument_structures='\n'.join(argument_structures),
                          write_functions='\n'.join(write_functions),
                          format_functions='\n'.join(format_functions),
                          format_functions_array='\n'.join(format_functions_array))


if __name__ == '__main__':
    name = sys.argv[1]
    version = sys.argv[2]
    board = sys.argv[3]
    mcu = sys.argv[4]
    outfile = sys.argv[5]
    infiles = sys.argv[6:]

    now = time.strftime("%Y-%m-%d %H:%M %Z")

    sysinfo = sysinfo_fmt.format(name=name,
                                 version=version,
                                 date=now,
                                 user=getpass.getuser(),
                                 board=board,
                                 mcu=mcu)
    fs_formatted_data = generate_fs(infiles)
    log_formatted_data = generate_log(infiles)

    fout = open(outfile, 'w').write(
        file_fmt.format(filename=outfile,
                        major=major,
                        minor=minor,
                        date=time.strftime("%Y-%m-%d %H:%M %Z"),
                        sysinfo=sysinfo,
                        fs=fs_formatted_data,
                        log=log_formatted_data))
