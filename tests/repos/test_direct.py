import os.path
from pathlib import Path
from notesdir.conf import DirectRepoConf
from notesdir.models import SetTitleCmd, ReplaceHrefCmd, MoveCmd, FileQuery, FileInfo, FileInfoReq, LinkInfo


def test_info_directory(fs):
    path = Path('/notes/foo/bar')
    path.mkdir(parents=True, exist_ok=True)
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert repo.info(str(path)) == FileInfo(str(path))
    assert repo.info(str(path.parent)) == FileInfo(str(path.parent))


def test_info_nonexistent(fs):
    path = '/notes/foo'
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
    info = repo.info('subject.md', 'backlinks')
    assert info.backlinks == [
        LinkInfo('/notes/bar/baz/r1.md', '../../foo/subject.md'),
        LinkInfo('/notes/foo/r3.md', 'subject.md'),
        LinkInfo('/notes/r2.md', 'foo/subject.md'),
    ]


def test_referrers_self(fs):
    fs.create_file('/notes/subject.md', contents='[1](subject.md)')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    info = repo.info('/notes/subject.md', 'backlinks')
    assert info.backlinks == [LinkInfo('/notes/subject.md', 'subject.md')]


def test_change(fs):
    fs.create_file('/notes/one.md', contents='[1](old)')
    fs.create_file('/notes/two.md', contents='[2](foo)')
    edits = [SetTitleCmd('/notes/one.md', 'New Title'),
             ReplaceHrefCmd('/notes/one.md', 'old', 'new'),
             MoveCmd('/notes/one.md', '/notes/moved.md'),
             ReplaceHrefCmd('/notes/two.md', 'foo', 'bar')]
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits)
    assert not Path('/notes/one.md').exists()
    assert Path('/notes/moved.md').read_text() == '---\ntitle: New Title\n---\n\n[1](new)'
    assert Path('/notes/two.md').read_text() == '[2](bar)'


def test_change_directories(fs):
    paths1 = ['/notes/dir1/subdir1/one.md', '/notes/dir2/subdir2/two.md',
             '/notes/dir2/subdir3/three.md']
    nonmovingpath = '/notes/dir2/subdir3/four.md'
    for path in paths1:
        fs.create_file(path)
    fs.create_file(nonmovingpath)
    paths2 = [p.replace('/notes/', '/notes/newdir/') for p in paths1]
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    edits = [MoveCmd(paths1[i], paths2[i], create_parents=True, delete_empty_parents=True) for i in range(3)]
    repo.change(edits)
    assert [p for p in paths1 if os.path.exists(p)] == []
    assert [p for p in paths2 if os.path.exists(p)] == paths2
    assert not os.path.exists('/notes/dir1')
    assert not os.path.exists('/notes/dir2/subdir2')
    assert os.path.exists(nonmovingpath)


def test_query(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2 #tag4')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    paths = {i.path for i in repo.query(FileQuery())}
    assert paths == {'/notes/one.md', '/notes/two.md', '/notes/three.md'}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3'))}
    assert paths == {'/notes/two.md', '/notes/three.md'}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag1,tag4'))}
    assert paths == {'/notes/one.md', '/notes/three.md'}
    assert not list(repo.query(FileQuery.parse('tag:bogus')))
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2'))}
    assert paths == {'/notes/two.md', '/notes/three.md'}
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2,tag4'))}
    assert paths == {'/notes/two.md'}
    assert not list(repo.query(FileQuery.parse('-tag:tag1')))
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3 -tag:tag4'))}
    assert paths == {'/notes/two.md'}

    assert [os.path.basename(i.path) for i in repo.query('sort:filename')] == ['one.md', 'three.md', 'two.md']


def test_tag_counts(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert repo.tag_counts(FileQuery()) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert repo.tag_counts(FileQuery.parse('tag:tag3')) == {'tag1': 2, 'tag3': 2, 'tag4': 1}


def test_ignore(fs):
    path1 = '/notes/one.md'
    path2 = '/notes/.two.md'
    fs.create_file(path1, contents='I link to [two](.two.md)')
    fs.create_file(path2, contents='I link to [one](one.md)')
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    assert list(repo.query()) == [repo.info(path1)]
    assert not repo.info(path1, FileInfoReq.full()).backlinks
    assert repo.info(path2, FileInfoReq.full()).backlinks == [LinkInfo(path1, '.two.md')]
    repo.conf.ignore = lambda _1, _2: False
    assert list(repo.query()) == [repo.info(path1), repo.info(path2)]
    assert repo.info(path1, FileInfoReq.full()).backlinks == [LinkInfo(path2, 'one.md')]
    assert repo.info(path2, FileInfoReq.full()).backlinks == [LinkInfo(path1, '.two.md')]


def test_skip_parse(fs):
    path1 = '/notes/one.md'
    path2 = '/notes/one.md.resources/two.md'
    path3 = '/notes/skip.md'
    path4 = '/notes/unskip.md'
    fs.create_file(path1, contents='---\ntitle: Note One\n...\n')
    fs.create_file(path2, contents='---\ntitle: Note Two\n...\n')
    fs.create_file(path3, contents='---\ntitle: Note Skip\n...\n')
    fs.create_file(path4, contents='---\ntitle: Note No Skip\n...\n')

    def fn(parentpath, filename):
        return filename.endswith('.resources') or filename == 'skip.md'

    repo = DirectRepoConf(root_paths={'/notes'}, skip_parse=fn).instantiate()
    assert list(repo.query('sort:path')) == [
        FileInfo(path1, title='Note One'),
        FileInfo(path2),
        FileInfo(path3),
        FileInfo(path4, title='Note No Skip')
    ]
    assert repo.info(path1) == FileInfo(path1, title='Note One')
    assert repo.info(path2) == FileInfo(path2)
    assert repo.info(path3) == FileInfo(path3)
    assert repo.info(path4) == FileInfo(path4, title='Note No Skip')
