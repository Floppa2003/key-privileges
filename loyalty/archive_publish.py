"""Publish only immutable public PDF bytes to the existing main branch.

The Sheet owns all document metadata. This writer creates no index or branch,
never deletes old copies, and has no Google or model credentials. A returned
commit is suitable for a separate, sparse archive checkout by the publisher.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re

import requests
from pdf_archive import MAX_BYTES, validated_sha

REPOSITORY = 'Floppa2003/key-privileges'
DIRECTORY = 'source-documents'
PDF_NAME = re.compile(r'[a-f0-9]{64}\.pdf')
OBJECT_SHA = re.compile(r'[a-f0-9]{40}')


class ApiError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('archive_github_http_' + str(status))


def object_sha(value):
    if not isinstance(value, str) or not OBJECT_SHA.fullmatch(value):
        raise ValueError('archive_invalid_git_object')
    return value


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def captured_files(directory):
    root = Path(directory)
    if not root.exists() and not root.is_symlink():
        return {}
    if root.is_symlink() or not root.is_dir():
        raise ValueError('archive_capture_not_directory')
    result = {}
    for path in sorted(root.iterdir()):
        if (not PDF_NAME.fullmatch(path.name) or path.is_symlink() or not path.is_file()
                or not 100 <= path.stat().st_size <= MAX_BYTES):
            raise ValueError('archive_invalid_captured_file')
        data = path.read_bytes()
        if validated_sha(data) != path.stem:
            raise ValueError('archive_captured_digest_mismatch')
        result[path.name] = data
    return result


class GitHub:
    def __init__(self, token, *, session=None):
        if not token:
            raise ValueError('archive_github_token_missing')
        self.session = session or requests.Session()
        self.headers = {'Authorization': 'Bearer ' + token,
                        'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28'}

    def request(self, method, path, **kwargs):
        try:
            response = self.session.request(method,
                'https://api.github.com/repos/' + REPOSITORY + path,
                headers=self.headers, timeout=(10, 60), allow_redirects=False, **kwargs)
        except requests.RequestException:
            # A timed-out write is ambiguous; never silently retry it.
            raise RuntimeError('archive_github_transport_failed') from None
        if response.status_code not in (200, 201):
            raise ApiError(response.status_code)
        try:
            value = response.json()
        except (ValueError, TypeError):
            raise ValueError('archive_github_invalid_json') from None
        if not isinstance(value, dict):
            raise ValueError('archive_github_invalid_response')
        return value

    def head(self):
        value = self.request('GET', '/git/ref/heads/main')
        if value.get('ref') != 'refs/heads/main' or value.get('object', {}).get('type') != 'commit':
            raise ValueError('archive_github_main_ref_mismatch')
        return object_sha(value['object']['sha'])

    def _tree_sha(self, commit):
        return object_sha(self.request('GET', '/git/commits/' + object_sha(commit))['tree']['sha'])

    def _tree(self, sha):
        result = self.request('GET', '/git/trees/' + object_sha(sha))
        if result.get('truncated') or not isinstance(result.get('tree'), list):
            raise ValueError('archive_github_incomplete_tree')
        return result['tree']

    def archive_entries(self, commit):
        root = self._tree(self._tree_sha(commit))
        found = [entry for entry in root if entry.get('path') == DIRECTORY]
        if not found:
            return {}
        if len(found) != 1 or found[0].get('type') != 'tree' or found[0].get('mode') != '040000':
            raise ValueError('archive_github_directory_type')
        rows = self._tree(found[0]['sha'])
        entries = {row['path']: {key: row[key] for key in ('type', 'mode', 'sha')} for row in rows}
        if len(entries) != len(rows):
            raise ValueError('archive_github_duplicate_tree_path')
        return entries

    def create_blob(self, data):
        result = self.request('POST', '/git/blobs', json={
            'encoding': 'base64', 'content': base64.b64encode(data).decode('ascii')})
        sha = object_sha(result['sha'])
        if sha != git_blob_sha(data):
            raise ValueError('archive_created_blob_mismatch')
        return sha

    def create_commit(self, parent, additions):
        # base_tree preserves every unrelated path and all previous PDF versions.
        tree = self.request('POST', '/git/trees', json={
            'base_tree': self._tree_sha(parent),
            'tree': [{'path': DIRECTORY + '/' + name, **entry}
                     for name, entry in sorted(additions.items())]})
        result = self.request('POST', '/git/commits', json={
            'message': 'chore: preserve public PDF originals',
            'parents': [object_sha(parent)], 'tree': object_sha(tree['sha'])})
        return object_sha(result['sha'])

    def advance(self, commit):
        # Fast-forward only. A concurrent main commit rejects our sibling commit.
        result = self.request('PATCH', '/git/refs/heads/main',
                              json={'sha': object_sha(commit), 'force': False})
        if result.get('object', {}).get('sha') != commit:
            raise ValueError('archive_updated_ref_mismatch')

    def read_blob(self, sha):
        result = self.request('GET', '/git/blobs/' + object_sha(sha))
        if result.get('encoding') != 'base64' or result.get('sha') != sha:
            raise ValueError('archive_blob_readback_contract')
        try:
            data = base64.b64decode(''.join(result['content'].split()), validate=True)
        except (ValueError, TypeError, KeyError):
            raise ValueError('archive_blob_readback_encoding') from None
        if result.get('size') != len(data) or git_blob_sha(data) != sha:
            raise ValueError('archive_blob_readback_mismatch')
        return data


def expected_entry(data):
    return {'type': 'blob', 'mode': '100644', 'sha': git_blob_sha(data)}


def verify_remote(api, commit, captured):
    entries = api.archive_entries(commit)
    for name, original in captured.items():
        expected = expected_entry(original)
        if entries.get(name) != expected:
            raise ValueError('archive_remote_copy_mismatch')
        actual = api.read_blob(expected['sha'])
        if validated_sha(actual) != name[:-4] or actual != original:
            raise ValueError('archive_remote_copy_digest_mismatch')


def publish_archive(directory, api):
    captured = captured_files(directory)  # Reject every bad input before writes.
    uploaded = {}
    added = 0
    for attempt in range(3):
        parent = api.head()
        entries = api.archive_entries(parent)
        additions = {}
        for name, data in captured.items():
            expected = expected_entry(data)
            if name in entries:
                if entries[name] != expected:
                    raise ValueError('archive_immutable_copy_mismatch')
                continue
            additions[name] = expected
        if not additions:
            break
        for name, entry in additions.items():
            if name not in uploaded:
                uploaded[name] = api.create_blob(captured[name])
            if uploaded[name] != entry['sha']:
                raise ValueError('archive_uploaded_blob_mismatch')
        commit = api.create_commit(parent, additions)
        try:
            api.advance(commit)
        except ApiError as error:
            # Retry only an explicit ref conflict with a demonstrably new head.
            if error.status not in (409, 422) or api.head() == parent:
                raise
            if attempt == 2:
                raise RuntimeError('archive_concurrent_updates_exhausted') from None
            continue
        added = len(additions)
        break
    commit = api.head()
    verify_remote(api, commit, captured)
    return {'commit_sha': commit, 'captured': len(captured),
            'added': added, 'verified': len(captured)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'):
        raise ValueError('archive_publication_only_from_owner_main')
    result = publish_archive(args.input, GitHub(os.environ.get('GH_TOKEN', '')))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('commit_sha=' + result['commit_sha'] + '\n')
    print(json.dumps({'mode': 'public_pdf_archive_readback_verified', **result}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'mode': 'public_pdf_archive_failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)
