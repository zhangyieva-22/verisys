"""Intake contracts, separate from architecture facts and discovery state."""
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit
from pydantic import Field, ConfigDict, field_validator
from verisys.models.base import DomainModel

SHA_PATTERN = r"^[0-9a-f]{40}$"


class LocalRepositorySource(DomainModel):
    model_config = ConfigDict(frozen=True)
    type: Literal['local'] = 'local'
    path: str = Field(min_length=1, max_length=4096, strict=True)


class GitHubRepositorySource(DomainModel):
    model_config = ConfigDict(frozen=True)
    type: Literal['github'] = 'github'
    url: str = Field(min_length=1, max_length=512, strict=True)
    ref: str | None = Field(default=None, min_length=1, max_length=256, strict=True)

    @field_validator('url')
    @classmethod
    def canonical_url(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.query or parsed.fragment
                or '?' in value or '#' in value or re.search(r'\s', value)):
            raise ValueError('Use an HTTPS public GitHub repository URL')
        match = re.fullmatch(r'/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]{1,100})/?', parsed.path)
        if not match:
            raise ValueError('Use a GitHub owner/repository URL')
        owner, repo = match.groups()
        repo = repo.removesuffix('.git')
        if not repo or repo in {'.', '..'} or '--' in owner or owner.endswith('-'):
            raise ValueError('Invalid GitHub owner or repository')
        return f'https://github.com/{owner}/{repo}'

    @field_validator('ref')
    @classmethod
    def safe_ref(cls, value):
        if value is not None and (not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]{0,255}', value)
                                  or '..' in value or value.endswith('/') or '//' in value):
            raise ValueError('Invalid repository ref')
        return value

    @property
    def owner_repo(self):
        return self.url.removeprefix('https://github.com/')


RepositorySource = Annotated[LocalRepositorySource | GitHubRepositorySource, Field(discriminator='type')]
