# vim: set ts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can Headeristribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
import os, re
import argparse

class FxcTool(object):
    def __init__(self):
        super(FxcTool, self).__init__()
        self.output_files = []
        self.output_nodes = []

    def evaluate(self, cmd):
        for shader in cmd.data.shaders:
            self.evaluate_shader(cmd, shader)

        argv = [
            'python',
            __file__,
            '--prefix',
            cmd.data.output,
        ]
        if cmd.data.namespace:
            argv += ['--namespace', cmd.data.namespace]
        if cmd.data.listDefineName:
            argv += ['--list-define-name', cmd.data.listDefineName]

        argv += self.output_files

        _, (cxx_file,
            h_file) = cmd.context.AddCommand(inputs = [__file__],
                                             argv = argv,
                                             outputs = [
                                                 '{0}-bytecode.cxx'.format(cmd.data.output),
                                                 '{0}-include.h'.format(cmd.data.output),
                                             ],
                                             folder = cmd.localFolderNode)

        cmd.sources += [cmd.CustomSource(source = cxx_file, weak_deps = self.output_nodes)]
        cmd.sourcedeps += [h_file]

    def evaluate_shader(self, cmd, shader):
        source = shader['source']
        var_prefix = shader['variable']
        profile = shader['profile']
        entrypoint = shader.get('entry', 'main')

        output_file = '{0}.{1}.{2}.h'.format(cmd.NameForObjectFile(source), var_prefix, entrypoint)

        sourceFile = cmd.ComputeSourcePath(source)

        argv = [
            'fxc',
            '/T',
            profile,
            '/E',
            entrypoint,
            '/Fh',
            output_file,
            '/Vn',
            '{0}_Bytes_Impl'.format(var_prefix),
            '/Vi',
            '/nologo',
            sourceFile,
        ]
        outputs = [output_file]
        folder = cmd.localFolderNode

        _, (output_node,) = cmd.context.AddCommand(inputs = [sourceFile],
                                                   argv = argv,
                                                   outputs = [output_file],
                                                   folder = cmd.localFolderNode,
                                                   dep_type = 'fxc')

        self.output_files += [output_file]
        self.output_nodes += [output_node]

class FxcJob(object):
    def __init__(self, output, namespace):
        super(FxcJob, self).__init__()
        self.tool = FxcTool()
        self.output = output
        self.shaders = []
        self.namespace = namespace
        self.listDefineName = None

def fxc_helper_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', type = str, required = True, help = 'Prefix for prefix files')
    parser.add_argument('--namespace', type = str, help = 'Optional fully-qualified namespace')
    parser.add_argument('--list-define-name',
                        type = str,
                        help = 'Optional name for shader list define')
    parser.add_argument('sources', type = str, nargs = '+', help = 'Source list')

    args = parser.parse_args()

    bytecode_fp = open('{0}-bytecode.cxx'.format(args.prefix), 'w')
    include_fp = open('{0}-include.h'.format(args.prefix), 'w')

    header = '// Auto-generated by {0}\n'.format(__file__)
    bytecode_fp.write(header)
    include_fp.write(header)

    bytecode_fp.write("#define WIN32_LEAN_AND_MEAN\n")
    bytecode_fp.write("#include <stddef.h>\n")
    bytecode_fp.write("#include <stdint.h>\n")
    bytecode_fp.write("#include <Windows.h>\n")
    bytecode_fp.write('\n')

    include_fp.write("#pragma once\n")
    include_fp.write("#include <stddef.h>\n")
    include_fp.write("#include <stdint.h>\n")
    include_fp.write('\n')

    fqns = args.namespace.split('::') if args.namespace else []
    if fqns:
        for part in fqns:
            bytecode_fp.write('namespace {0} {{\n'.format(part))
            include_fp.write('namespace {0} {{\n'.format(part))
        bytecode_fp.write('\n')
        include_fp.write('\n')

    var_prefixes = []

    for source_file in args.sources:
        m = re.match(r'([^.]+)\.([^.]+)\.([^.]+)\.h', source_file)
        var_prefix = m.group(2)
        if m is None:
            raise Exception('Sources must be in objname.varprefix.entrypoint.h form')

        bytecode_line = """#include "{0}"
extern const uint8_t* {1}_Bytes = {1}_Bytes_Impl;
extern const size_t {1}_Length = sizeof({1}_Bytes_Impl);
""".format(source_file, var_prefix)
        bytecode_fp.write(bytecode_line)

        include_fp.write("""extern const uint8_t* {0}_Bytes;
extern const size_t {0}_Length;
""".format(var_prefix))

        var_prefixes.append(var_prefix)

    bytecode_fp.write('\n')
    include_fp.write('\n')

    if args.list_define_name:
        include_fp.write('#define {0}(_) \\\n'.format(args.list_define_name))
        for var_prefix in var_prefixes:
            include_fp.write('  _({0}) \\\n'.format(var_prefix))
        include_fp.write('  // terminator\n')
        include_fp.write('\n')

    for part in fqns:
        bytecode_fp.write('}} // namespace {0}\n'.format(part))
        include_fp.write('}} // namespace {0}\n'.format(part))

    bytecode_fp.close()
    include_fp.close()

if __name__ == '__main__':
    fxc_helper_tool()
