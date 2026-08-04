# -*- coding: utf-8 -*-
"""把当前版本的 EXE 同步为 Gitee Release（供国内检查更新兜底）。"""

from __future__ import print_function

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import uuid

try:
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover
    raise


GITEE_API = "https://gitee.com/api/v5"
DEFAULT_OWNER = "kary2"
DEFAULT_REPO = "eggplant-releases"


def _request(method, url, token, data=None, headers=None, timeout=60):
    hdrs = {"User-Agent": "eggplant-pet-gitee-sync"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None and not isinstance(data, bytes):
        # form or json string already encoded by caller
        body = data
    req = Request(url, data=body, headers=hdrs, method=method)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def ensure_gitee_repo_has_commit(owner, repo, token, work_dir):
    """空仓无法建 Release：推一个占位 README 到 master。"""
    remote = "https://oauth2:%s@gitee.com/%s/%s.git" % (token, owner, repo)
    git_dir = os.path.join(work_dir, ".git")
    if not os.path.isdir(git_dir):
        subprocess.check_call(["git", "init"], cwd=work_dir)
        subprocess.check_call(["git", "checkout", "-B", "master"], cwd=work_dir)
    readme = os.path.join(work_dir, "README.md")
    if not os.path.isfile(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write(
                "# eggplant-releases\n\n"
                "茄子桌宠官方 Windows 构建发布仓（无源码）。\n"
            )
        subprocess.check_call(["git", "add", "README.md"], cwd=work_dir)
        subprocess.check_call(
            [
                "git",
                "-c",
                "user.name=eggplant-ci",
                "-c",
                "user.email=ci@eggplant.local",
                "commit",
                "-m",
                "chore: bootstrap release repo",
            ],
            cwd=work_dir,
        )
    # set remote
    remotes = subprocess.check_output(
        ["git", "remote"], cwd=work_dir, universal_newlines=True
    ).split()
    if "gitee" in remotes:
        subprocess.check_call(
            ["git", "remote", "set-url", "gitee", remote], cwd=work_dir
        )
    else:
        subprocess.check_call(["git", "remote", "add", "gitee", remote], cwd=work_dir)
    subprocess.check_call(
        ["git", "push", "-u", "gitee", "HEAD:master", "--force"],
        cwd=work_dir,
    )


def find_release_by_tag(owner, repo, token, tag):
    url = "%s/repos/%s/%s/releases?access_token=%s&page=1&per_page=100" % (
        GITEE_API,
        owner,
        repo,
        token,
    )
    data = _request("GET", url, token)
    for rel in data or []:
        if rel.get("tag_name") == tag:
            return rel
    return None


def create_release(owner, repo, token, tag, name, body):
    url = "%s/repos/%s/%s/releases" % (GITEE_API, owner, repo)
    payload = urlencode(
        {
            "access_token": token,
            "tag_name": tag,
            "name": name,
            "body": body or "",
            "target_commitish": "master",
        }
    ).encode("utf-8")
    return _request(
        "POST",
        url,
        token,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _multipart_encode(fields, file_field, filepath):
    """组装单文件 multipart/form-data 请求体。"""
    boundary = "----EggplantBoundary%s" % uuid.uuid4().hex
    filename = os.path.basename(filepath)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(filepath, "rb") as f:
        file_bytes = f.read()

    chunks = []
    for key, value in fields.items():
        chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
        chunks.append(
            ('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode("utf-8")
        )
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
    chunks.append(
        (
            'Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
            % (file_field, filename)
        ).encode("utf-8")
    )
    chunks.append(("Content-Type: %s\r\n\r\n" % ctype).encode("utf-8"))
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(chunks), "multipart/form-data; boundary=%s" % boundary


def upload_asset(owner, repo, token, release_id, filepath):
    url = "%s/repos/%s/%s/releases/%s/attach_files" % (
        GITEE_API,
        owner,
        repo,
        release_id,
    )
    body, content_type = _multipart_encode(
        {"access_token": token},
        "file",
        filepath,
    )
    return _request(
        "POST",
        url,
        token,
        data=body,
        headers={"Content-Type": content_type},
        timeout=300,
    )


def sync_release(owner, repo, token, tag, name, body, files, work_dir):
    ensure_gitee_repo_has_commit(owner, repo, token, work_dir)
    rel = find_release_by_tag(owner, repo, token, tag)
    if rel is None:
        print("gitee: creating release", tag)
        rel = create_release(owner, repo, token, tag, name, body)
    else:
        print("gitee: release exists", tag, "id=", rel.get("id"))
    release_id = rel.get("id")
    if not release_id:
        raise RuntimeError("gitee release missing id: %r" % (rel,))
    for path in files:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        print("gitee: uploading", path)
        upload_asset(owner, repo, token, release_id, path)
    print("gitee: sync done")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--token", default=os.environ.get("GITEE_TOKEN", ""))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--file", action="append", dest="files", required=True)
    parser.add_argument(
        "--work-dir",
        default=os.environ.get("GITEE_SYNC_WORKDIR", ".gitee-release-work"),
    )
    args = parser.parse_args(argv)
    if not args.token:
        print("gitee: GITEE_TOKEN missing, skip sync", file=sys.stderr)
        return 0
    os.makedirs(args.work_dir, exist_ok=True)
    try:
        sync_release(
            args.owner,
            args.repo,
            args.token,
            args.tag,
            args.name,
            args.body,
            args.files,
            args.work_dir,
        )
    except (HTTPError, URLError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("gitee: sync failed:", repr(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
