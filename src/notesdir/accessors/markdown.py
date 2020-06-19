from pathlib import Path
import re
from typing import Set
import yaml
from notesdir.accessors.base import BaseAccessor, FileInfo, FileEdit


YAML_META_RE = re.compile(r'(?ms)\A---\n(.*)\n(---|\.\.\.)\s*$')
TAG_RE = re.compile(r'[\s^]#([a-zA-Z][a-zA-Z\-_0-9]*)\b')
INLINE_REF_RE = re.compile(r'\[.*\]\((\S+)\)')
REFSTYLE_REF_RE = re.compile(r'(?m)^\[.*\]:\s*(\S+)')


def extract_meta(doc) -> dict:
    match = YAML_META_RE.match(doc)
    if not match:
        return {}
    return yaml.safe_load(match.groups()[0])


def extract_tags(doc) -> Set[str]:
    return set(t.lower() for t in TAG_RE.findall(doc))


def extract_refs(doc) -> Set[str]:
    return set(INLINE_REF_RE.findall(doc) + REFSTYLE_REF_RE.findall(doc))


class MarkdownAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        text = path.read_text()
        meta = extract_meta(text)
        return FileInfo(
            path=path,
            refs=extract_refs(text),
            tags=extract_tags(text),
            title=meta.get('title')
        )

    def change(self, path: Path, edit: FileEdit):
        raise NotImplementedError()