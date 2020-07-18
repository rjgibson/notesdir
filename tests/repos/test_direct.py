from pathlib import Path
from notesdir.conf import DirectRepoConf
from notesdir.models import SetTitleCmd, ReplaceHrefCmd, MoveCmd, FileQuery, FileInfo, FileInfoReq, LinkInfo


def test_info_directory(fs):
    path = Path('/notes/foo/bar')
    path.mkdir(parents=True, exist_ok=True)
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert repo.info(path) == FileInfo(path)
    assert repo.info(path.parent) == FileInfo(path.parent)


def test_info_nonexistent(fs):
    path = Path('/notes/foo')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert repo.info(path) == FileInfo(path)


def test_backlinks(fs):
    fs.cwd = '/notes/foo'
    fs.create_file('/notes/foo/subject.md')
    fs.create_file('/notes/bar/baz/r1.md', contents='[1](no) [2](../../foo/subject.md)')
    fs.create_file('/notes/bar/baz/no.md', contents='[3](../../foo/bogus')
    fs.create_file('/notes/r2.md', contents='[4](foo/subject.md) [5](foo/bogus)')
    fs.create_file('/notes/foo/r3.md', contents='[6](subject.md)')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    info = repo.info(Path('subject.md'), 'backlinks')
    assert info.backlinks == [
        LinkInfo(Path('/notes/bar/baz/r1.md'), '../../foo/subject.md'),
        LinkInfo(Path('/notes/foo/r3.md'), 'subject.md'),
        LinkInfo(Path('/notes/r2.md'), 'foo/subject.md'),
    ]


def test_referrers_self(fs):
    fs.create_file('/notes/subject.md', contents='[1](subject.md)')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    info = repo.info(Path('/notes/subject.md'), 'backlinks')
    assert info.backlinks == [LinkInfo(Path('/notes/subject.md'), 'subject.md')]


def test_change(fs):
    fs.create_file('/notes/one.md', contents='[1](old)')
    fs.create_file('/notes/two.md', contents='[2](foo)')
    edits = [SetTitleCmd(Path('/notes/one.md'), 'New Title'),
             ReplaceHrefCmd(Path('/notes/one.md'), 'old', 'new'),
             MoveCmd(Path('/notes/one.md'), Path('/notes/moved.md')),
             ReplaceHrefCmd(Path('/notes/two.md'), 'foo', 'bar')]
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits)
    assert not Path('/notes/one.md').exists()
    assert Path('/notes/moved.md').read_text() == '---\ntitle: New Title\n...\n[1](new)'
    assert Path('/notes/two.md').read_text() == '[2](bar)'


def test_query(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2 #tag4')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    paths = {i.path for i in repo.query(FileQuery())}
    assert paths == {Path('/notes/one.md'), Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag1,tag4'))}
    assert paths == {Path('/notes/one.md'), Path('/notes/three.md')}
    assert not list(repo.query(FileQuery.parse('tag:bogus')))
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2,tag4'))}
    assert paths == {Path('/notes/two.md')}
    assert not list(repo.query(FileQuery.parse('-tag:tag1')))
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3 -tag:tag4'))}
    assert paths == {Path('/notes/two.md')}

    assert [i.path.name for i in repo.query('sort:filename')] == ['one.md', 'three.md', 'two.md']


def test_tag_counts(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert repo.tag_counts(FileQuery()) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert repo.tag_counts(FileQuery.parse('tag:tag3')) == {'tag1': 2, 'tag3': 2, 'tag4': 1}


def test_skip_parse(fs):
    path1 = Path('/notes/one.md')
    path2 = Path('/notes/skip.md')
    path3 = Path('/notes/moved.md')
    fs.create_file(path1, contents='I have #tags and a [link](skip.md).')
    fs.create_file(path2, contents='I #also have #tags.')
    repo = DirectRepoConf(root_paths={'/notes'}, skip_parse=lambda p: p.stem == 'skip').instantiate()
    assert repo.info(path1) == FileInfo(path1, tags={'tags'}, links=[LinkInfo(path1, 'skip.md')])
    assert (repo.info(path2, FileInfoReq.full()) == FileInfo(path2, backlinks=[LinkInfo(path1, 'skip.md')]))
    assert repo.info(path3) == FileInfo(path3)
    assert not list(repo.query(FileQuery(include_tags={'also'})))
    repo.change([ReplaceHrefCmd(path1, original='skip.md', replacement='moved.md'), MoveCmd(path2, path3)])
    assert repo.info(path1) == FileInfo(path1, tags={'tags'}, links=[LinkInfo(path1, 'moved.md')])
    assert repo.info(path2, FileInfoReq.full()) == FileInfo(path2)
    assert (repo.info(path3, FileInfoReq.full())
            == FileInfo(path3, tags={'also', 'tags'}, backlinks=[LinkInfo(path1, 'moved.md')]))
    assert list(repo.query(FileQuery(include_tags={'also'}))) == [repo.info(path3)]


def test_ignore(fs):
    path1 = Path('/notes/one.md')
    path2 = Path('/notes/.two.md')
    fs.create_file(path1, contents='I link to [two](.two.md)')
    fs.create_file(path2, contents='I link to [one](one.md)')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert list(repo.query()) == [repo.info(path1)]
    assert not repo.info(path1, FileInfoReq.full()).backlinks
    repo.conf.ignore = lambda p: False
    assert list(repo.query()) == [repo.info(path1), repo.info(path2)]
    assert repo.info(path1, FileInfoReq.full()).backlinks == [LinkInfo(path2, 'one.md')]
