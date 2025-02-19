# ============================================================================
# FILE: file.py
# AUTHOR: Felipe Morales <hel.sheep at gmail.com>
#         Shougo Matsushita <Shougo.Matsu at gmail.com>
# License: MIT license
# ============================================================================

from pathlib import Path
from pynvim import Nvim
import re
import typing

from deoplete.base.source import Base
from deoplete.util import expand, exists_path, UserContext, Candidates


class Source(Base):

    def __init__(self, vim: Nvim) -> None:
        super().__init__(vim)

        self.name = 'file'
        self.mark = '[F]'
        self.min_pattern_length = 0
        self.rank = 150
        self.events: typing.List[str] = ['InsertEnter']
        self.vars = {
            'enable_buffer_path': True,
            'enable_slash_completion': False,
            'force_completion_length': -1,
        }

        self._isfname = ''

    def on_event(self, context: UserContext) -> None:
        self._isfname = self.vim.call(
            'deoplete#util#vimoption2python_not',
            self.vim.options['isfname'])

    def get_complete_position(self, context: UserContext) -> int:
        pos = int(context['input'].rfind('/'))
        force_completion_length = int(
            self.get_var('force_completion_length'))
        if pos < 0 and force_completion_length >= 0:
            fmt = '[a-zA-Z0-9.-]{{{}}}$'.format(force_completion_length)
            m = re.search(fmt, context['input'])
            if m:
                return m.start()
        return pos if pos < 0 else pos + 1

    def gather_candidates(self, context: UserContext) -> Candidates:
        if not self._isfname:
            self.on_event(context)

        input_str = (context['input']
                     if context['input'].rfind('/') >= 0
                     else './')

        # Note: context['bufpath'] will be empty if not exists file
        bufname = context['bufname']
        bufpath = (bufname if Path(bufname).is_absolute()
                   else str(Path(context['cwd']).joinpath(bufname)))
        buftype = self.vim.call('getbufvar', '%', '&buftype')
        if 'nofile' in buftype:
            bufpath = ''

        p = self._longest_path_that_exists(context, input_str, bufpath)
        slash_completion = bool(self.get_var('enable_slash_completion'))
        if not p or re.search('//+$', p) or (
                p == '/' and not slash_completion):
            return []

        complete_str = self._substitute_path(context, expand(p) + '/', bufpath)
        if not Path(complete_str).is_dir():
            return []
        hidden = context['complete_str'].find('.') == 0
        contents: typing.List[typing.Any] = [[], []]
        try:
            for item in sorted([str(x.name) for x
                                in Path(complete_str).iterdir()],
                               key=str.lower):
                if not hidden and item[0] == '.':
                    continue
                contents[not Path(complete_str + item).is_dir()].append(item)
        except PermissionError:
            pass

        dirs, files = contents
        return [{'word': x, 'abbr': x + '/'} for x in dirs
                ] + [{'word': x} for x in files]

    def _longest_path_that_exists(self, context: UserContext,
                                  input_str: str, bufpath: str) -> str:
        input_str = re.sub(r'[^/]*$', '', input_str)
        data = re.split(r'((?:%s+|(?:(?<![\w\s/\.])(?:~|\.{1,2})?/)+))' %
                        self._isfname, input_str)
        data = [''.join(data[i:]) for i in range(len(data))]
        existing_paths = sorted(filter(
            lambda x: exists_path(self._substitute_path(
                context, x, bufpath)), data))
        return existing_paths[-1] if existing_paths else ''

    def _substitute_path(self, context: UserContext,
                         path: str, bufpath: str) -> str:
        m = re.match(r'(\.{1,2})/+', path)
        if not m:
            return expand(path)

        if self.get_var('enable_buffer_path') and bufpath:
            base = str(Path(bufpath).parent)
        else:
            base = context['cwd']

        if m.group(1) == '..':
            base = str(Path(base).parent)
        return str(Path(base).joinpath(path[len(m.group(0)):])) + '/'
