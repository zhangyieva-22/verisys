"""Offline acquisition tests: archives and remote metadata are untrusted data."""
import io
import json
from pathlib import Path
import tarfile
from urllib.error import HTTPError, URLError
import pytest
from pydantic import ValidationError
from verisys.repository.source import GitHubRepositorySource
from verisys.repository.github import (RepositoryMaterializer, RemoteLimits, IntakeError,
    extract_archive, trusted_url, TrustedRedirects, GitHubFetcher)

SHA='3d38d5ab7fa0f27bd5c28488afa354abaf2577b4'
URL='https://github.com/owner/repo'


def archive(entries):
    out=io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for name, data, kind in entries:
            item=tarfile.TarInfo(name); item.type=kind
            if kind==tarfile.REGTYPE:
                item.size=len(data);tar.addfile(item,io.BytesIO(data))
            else:
                item.linkname='outside';tar.addfile(item)
    return out.getvalue()


class FakeFetcher:
    def __init__(self, data=None):
        self.data=data or archive([('repo/app.py',b'from openai import OpenAI\nclient=OpenAI()\nclient.responses.create(input="x", timeout=2)\n',tarfile.REGTYPE)])
        self.urls=[]
    def get(self,url,**kwargs):
        self.urls.append(url)
        if 'codeload.github.com' in url:return self.data
        return json.dumps({'sha':SHA} if '/commits/' in url else {'private':False,'default_branch':'main'}).encode()


@pytest.mark.parametrize('suffix',['','.git','/','.git/'])
def test_valid_url(suffix):
    assert GitHubRepositorySource(url=URL+suffix).url==URL


@pytest.mark.parametrize('url',[
 'http://github.com/o/r','file:///o/r','ssh://github.com/o/r','git@github.com:o/r',
 'https://localhost/o/r','https://127.0.0.1/o/r','https://github.com.evil/o/r',
 'https://user:pass@github.com/o/r','https://github.com:443/o/r','https://github.com/o/r?q=x',
 'https://github.com/o/r#x','https://github.com/o/r?','https://github.com/o/r#',
 'https://github.com/o/r/tree/main','https://github.com/-o/r','https://github.com/o/..',
 'https://github.com/o/%2e%2e','https://github.com/o//r','https://github.com/o/r\n'])
def test_invalid_url(url):
    with pytest.raises(ValidationError):GitHubRepositorySource(url=url)


def test_resolved_regular_contents_cleanup_and_non_execution(tmp_path):
    fetcher=FakeFetcher(archive([('repo/app.py',b'raise RuntimeError("Never execute")\n',tarfile.REGTYPE)]))
    materializer=RepositoryMaterializer(fetcher,temp_parent=tmp_path)
    with materializer.materialize(GitHubRepositorySource(url=URL)) as repo:
        root=repo.root
        assert repo.resolved_commit_sha==SHA and repo.source.ref==SHA and repo.requested_ref=='main'
        assert (root/'app.py').read_text().startswith('raise')
    assert not root.exists() and list(tmp_path.iterdir())==[]
    assert fetcher.urls[-1].endswith('/tar.gz/'+SHA)


@pytest.mark.parametrize('name,kind',[
 ('repo/../../escaped',tarfile.REGTYPE),('/tmp/escaped',tarfile.REGTYPE),
 ('repo/a',tarfile.SYMTYPE),('repo/a',tarfile.LNKTYPE),('repo/a',tarfile.CHRTYPE),
 ('repo/a',tarfile.FIFOTYPE),('repo/a',tarfile.BLKTYPE),('repo\\a',tarfile.REGTYPE)])
def test_unsafe_archive_rejected_and_cleaned(tmp_path,name,kind):
    m=RepositoryMaterializer(FakeFetcher(archive([(name,b'x',kind)])),temp_parent=tmp_path)
    with pytest.raises(IntakeError,match='UNSAFE_ARCHIVE_CONTENT'):
        with m.materialize(GitHubRepositorySource(url=URL)):pytest.fail('Unsafe archive accepted')
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('limits',[
 RemoteLimits(max_entries=1),RemoteLimits(max_file_bytes=1),RemoteLimits(max_extracted_bytes=2),RemoteLimits(max_download_bytes=10)])
def test_archive_limits(tmp_path,limits):
    data=archive([('repo/a.py',b'xx',tarfile.REGTYPE),('repo/b.py',b'xx',tarfile.REGTYPE)])
    with pytest.raises(IntakeError,match='REPOSITORY_TOO_LARGE'):
        with RepositoryMaterializer(FakeFetcher(data),limits=limits,temp_parent=tmp_path).materialize(GitHubRepositorySource(url=URL)):pass
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('data',[b'not gzip',b'',b'\x1f\x8bgarbage'])
def test_malformed_archive(tmp_path,data):
    with pytest.raises(IntakeError,match='MALFORMED_ARCHIVE'):extract_archive(data,tmp_path,RemoteLimits())


def test_cleanup_after_consumer_failure(tmp_path):
    with pytest.raises(RuntimeError):
        with RepositoryMaterializer(FakeFetcher(),temp_parent=tmp_path).materialize(GitHubRepositorySource(url=URL)) as repo:
            root=repo.root;raise RuntimeError('consumer failure')
    assert not root.exists()


@pytest.mark.parametrize('target',['http://api.github.com/x','https://evil.example/x','https://127.0.0.1/x','https://api.github.com@evil/x'])
def test_trusted_network_boundary(target):
    with pytest.raises(IntakeError,match='UNSAFE_REMOTE_URL'):trusted_url(target)


@pytest.mark.parametrize('failure,code',[
 (TimeoutError('private'),'REMOTE_TIMEOUT'),(URLError('private'),'REMOTE_UNAVAILABLE'),
 (HTTPError(URL,429,'private',{},None),'GITHUB_RATE_LIMIT'),
 (HTTPError(URL,404,'private',{},None),'REPOSITORY_NOT_FOUND_OR_PRIVATE')])
def test_network_errors_are_sanitized(monkeypatch,failure,code):
    class Opener:
        def open(self,*a,**k):raise failure
    monkeypatch.setattr('verisys.repository.github.build_opener',lambda *a:Opener())
    with pytest.raises(IntakeError,match=code) as caught:GitHubFetcher().get('https://api.github.com/repos/o/r',max_bytes=100,timeout=1)
    assert 'private' not in str(caught.value)


def test_redirect_checked_before_fetch():
    with pytest.raises(IntakeError,match='UNSAFE_REMOTE_URL'):
        TrustedRedirects().redirect_request(None,None,302,'',{},'https://evil.example/')


def test_private_and_invalid_commit(tmp_path):
    class Private(FakeFetcher):
        def get(self,*a,**k):return b'{"private": true}'
    with pytest.raises(IntakeError,match='PRIVATE_REPOSITORY_UNSUPPORTED'):
        with RepositoryMaterializer(Private(),temp_parent=tmp_path).materialize(GitHubRepositorySource(url=URL)):pass
    with pytest.raises(IntakeError,match='INVALID_REPOSITORY_REF'):
        with RepositoryMaterializer(FakeFetcher(),temp_parent=tmp_path).materialize(GitHubRepositorySource(url=URL,ref='a'*40)):pass
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('advertised',[None,'1000'])
def test_bounded_download_with_or_without_length(monkeypatch,advertised):
    class Response:
        url='https://codeload.github.com/o/r/tar.gz/'+SHA
        headers={'Content-Length':advertised} if advertised else {}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read1(self,size):return b'x'*size
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr('verisys.repository.github.build_opener',lambda *args:Opener())
    with pytest.raises(IntakeError,match='REPOSITORY_TOO_LARGE'):
        GitHubFetcher().get(Response.url,max_bytes=10,timeout=1)


def test_download_deadline_is_not_reset_for_each_chunk(monkeypatch):
    times=iter([0,2])
    monkeypatch.setattr('verisys.repository.github.monotonic',lambda:next(times))
    class Response:
        url='https://api.github.com/repos/o/r'
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read1(self,size):pytest.fail('Exhausted deadline must not read')
    class Opener:
        def open(self,*a,**k):return Response()
    monkeypatch.setattr('verisys.repository.github.build_opener',lambda *a:Opener())
    with pytest.raises(IntakeError,match='REMOTE_TIMEOUT'):GitHubFetcher().get(Response.url,max_bytes=10,timeout=1)


def test_duplicate_archive_paths_are_rejected(tmp_path):
    data=archive([('repo/app.py',b'a',tarfile.REGTYPE),('repo/app.py',b'b',tarfile.REGTYPE)])
    with pytest.raises(IntakeError,match='UNSAFE_ARCHIVE_CONTENT'):extract_archive(data,tmp_path,RemoteLimits())


def test_corrupt_gzip_footer_is_rejected(tmp_path):
    data=archive([('repo/app.py',b'x',tarfile.REGTYPE)])
    corrupted=data[:-8]+b'12345678'
    with pytest.raises(IntakeError,match='MALFORMED_ARCHIVE'):extract_archive(corrupted,tmp_path,RemoteLimits())
