from pathlib import Path
from typing import List

from notesdir.accessors.base import FileInfo, FileEdit, BaseAccessor, MiscAccessor
from notesdir.accessors.html import HTMLAccessor
from notesdir.accessors.markdown import MarkdownAccessor


class DelegatingAccessor(BaseAccessor):
    def accessor(self, path: Path) -> BaseAccessor:
        if path.suffix == '.md':
            return MarkdownAccessor()
        elif path.suffix == '.html':
            return HTMLAccessor()
        return MiscAccessor()

    def parse(self, path: Path) -> FileInfo:
        return self.accessor(path).parse(path)

    def _change(self, edits: List[FileEdit]) -> bool:
        return self.accessor(edits[0].path).change(edits)
