import json
from pathlib import Path

from freezegun import freeze_time

from notesdir.models import SetTitleCmd, ReplaceRefCmd, MoveCmd, FileQuery
from notesdir.repos.direct import DirectRepo


def test_referrers(fs):
    fs.cwd = '/notes/foo'
    fs.create_file('/notes/foo/subject.md')
    fs.create_file('/notes/bar/baz/r1.md', contents='[1](no) [2](../../foo/subject.md)')
    fs.create_file('/notes/bar/baz/no.md', contents='[3](../../foo/bogus')
    fs.create_file('/notes/r2.md', contents='[4](foo/subject.md) [5](foo/bogus)')
    fs.create_file('/notes/foo/r3.md', contents='[6](subject.md)')
    repo = DirectRepo({'roots': ['/notes']})
    expected = {Path(p) for p in {'/notes/bar/baz/r1.md', '/notes/r2.md', '/notes/foo/r3.md'}}
    assert repo.referrers(Path('subject.md')) == expected


def test_referrers_self(fs):
    fs.create_file('/notes/subject.md', contents='[1](subject.md)')
    repo = DirectRepo({'roots': ['/notes']})
    expected = {Path('/notes/subject.md')}
    assert repo.referrers(Path('/notes/subject.md')) == expected


def test_change(fs):
    fs.create_file('/notes/one.md', contents='[1](old)')
    fs.create_file('/notes/two.md', contents='[2](foo)')
    edits = [SetTitleCmd(Path('/notes/one.md'), 'New Title'),
             ReplaceRefCmd(Path('/notes/one.md'), 'old', 'new'),
             MoveCmd(Path('/notes/one.md'), Path('/notes/moved.md')),
             ReplaceRefCmd(Path('/notes/two.md'), 'foo', 'bar')]
    repo = DirectRepo({'roots': ['/notes']})
    repo.change(edits)
    assert not Path('/notes/one.md').exists()
    assert Path('/notes/moved.md').read_text() == '---\ntitle: New Title\n...\n[1](new)'
    assert Path('/notes/two.md').read_text() == '[2](bar)'


@freeze_time('2020-02-03T04:05:06-0800')
def test_log_edits(fs):
    doc1 = 'I have [a link](doc2.md).'
    doc2 = bytes([0xfe, 0xfe, 0xff, 0xff])
    fs.create_file('doc1.md', contents=doc1)
    fs.create_file('doc2.bin', contents=doc2)
    edits = [
        ReplaceRefCmd(Path('doc1.md'), 'doc2.md', 'garbage.md'),
        MoveCmd(Path('doc2.bin'), Path('new-doc2.bin')),
    ]
    repo = DirectRepo({'roots': ['/notes'], 'edit_log_path': 'edits'})
    repo.change(edits)
    log = Path('edits').read_text().splitlines()
    assert len(log) == 2
    entry1 = json.loads(log[0])
    # FIXME these dates should have time zone indicators!
    assert entry1 == {
        'datetime': '2020-02-03T12:05:06',
        'path': 'doc1.md',
        'edits': [{
            'class': 'ReplaceRefCmd',
            'original': 'doc2.md',
            'replacement': 'garbage.md',
        }],
        'prior_text': 'I have [a link](doc2.md).'
    }
    entry2 = json.loads(log[1])
    assert entry2 == {
        'datetime': '2020-02-03T12:05:06',
        'path': 'doc2.bin',
        'edits': [{
            'class': 'MoveCmd',
            'dest': 'new-doc2.bin',
        }],
        'prior_base64': '/v7//w=='
    }


def test_paths_and_filters(fs):
    fs.create_file('/foo/one.md')
    fs.create_file('/foo/one.bin')
    fs.create_file('/foo/two.md')
    fs.create_file('/bar/one.md')
    fs.create_file('/bar/three.md')
    fs.create_file('/bar/three2.md')
    repo = DirectRepo({'roots': ['/foo', '/bar'], 'filters': [r'\/.{5}\.md']})
    assert set(repo._paths()) == {
        Path('/foo/one.md'),
        Path('/foo/one.bin'),
        Path('/foo/two.md'),
        Path('/bar/one.md'),
        Path('/bar/three2.md')
    }


def test_query(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2 #tag4')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = DirectRepo({'roots': ['/notes']})
    paths = {i.path for i in repo.query(FileQuery())}
    assert paths == {Path('/notes/one.md'), Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag1,tag4'))}
    assert paths == {Path('/notes/one.md'), Path('/notes/three.md')}
    assert not repo.query(FileQuery.parse('tag:bogus'))
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2,tag4'))}
    assert paths == {Path('/notes/two.md')}
    assert not repo.query(FileQuery.parse('-tag:tag1'))
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3 -tag:tag4'))}
    assert paths == {Path('/notes/two.md')}


def test_tag_counts(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = DirectRepo({'roots': ['/notes']})
    assert repo.tag_counts(FileQuery()) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert repo.tag_counts(FileQuery.parse('tag:tag3')) == {'tag1': 2, 'tag3': 2, 'tag4': 1}