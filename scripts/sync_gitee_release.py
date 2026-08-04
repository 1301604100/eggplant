# -*- coding: utf-8 -*-
"""把当前版本的 EXE 同步为 Gitee Release（供国内检查更新兜底）。"""

from __future__ import print_function

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import time
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


def _request(method, url, data=None, headers=None, timeout=60):
    hdrs = {"User-Agent": "eggplant-pet-gitee-sync"}
    if headers:
        hdrs.update(headers)
    body = data if isinstance(data, (bytes, type(None))) else data
    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except HTTPError as exc:
        detail = b""
        try:
            detail = exc.read() or b""
        except Exception:
            pass
        text = detail.decode("utf-8", errors="replace")
        raise RuntimeError(
            "Gitee API %s %s -> HTTP %s: %s" % (method, url.split("?")[0], exc.code, text)
        ) from exc
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _with_token(url, token):
    sep = "&" if "?" in url else "?"
    return "%s%saccess_token=%s" % (url, sep, token)


def _log(msg):
    """Windows CI 默认 cp1252，避免中文路径把日志打崩。"""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("unicode_escape").decode("ascii"), flush=True)


def verify_token(token):
    """确认私人令牌可用于 API（需要 projects 权限）。"""
    data = _request("GET", _with_token("%s/user" % GITEE_API, token))
    login = (data or {}).get("login")
    if not login:
        raise RuntimeError("Gitee token invalid: /user returned %r" % (data,))
    _log("gitee: authenticated as %s" % login)
    return login


def ensure_gitee_repo_has_commit(owner, repo, token, work_dir, tag=None):
    """空仓无法建 Release：推一个占位 README 到 master，并可选推送 tag。"""
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
    if tag:
        # Release 需要 tag；已存在则覆盖指向当前 master
        subprocess.call(["git", "tag", "-d", tag], cwd=work_dir)
        subprocess.check_call(["git", "tag", "-f", tag], cwd=work_dir)
        subprocess.check_call(
            ["git", "push", "gitee", "refs/tags/%s" % tag, "--force"],
            cwd=work_dir,
        )


def find_release_by_tag(owner, repo, token, tag):
    url = _with_token(
        "%s/repos/%s/%s/releases?page=1&per_page=100" % (GITEE_API, owner, repo),
        token,
    )
    data = _request("GET", url)
    for rel in data or []:
        if rel.get("tag_name") == tag:
            return rel
    return None


def create_release(owner, repo, token, tag, name, body):
    url = _with_token("%s/repos/%s/%s/releases" % (GITEE_API, owner, repo), token)
    payload = urlencode(
        {
            "access_token": token,
            "owner": owner,
            "repo": repo,
            "tag_name": tag,
            "name": name,
            "body": body or "",
            "target_commitish": "master",
        }
    ).encode("utf-8")
    return _request(
        "POST",
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _multipart_encode(fields, file_field, filepath, filename=None):
    """组装单文件 multipart/form-data 请求体。"""
    boundary = "----EggplantBoundary%s" % uuid.uuid4().hex
    filename = filename or os.path.basename(filepath)
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
    # filename*= 提升非 ASCII 文件名兼容性
    chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
    disp = 'Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (
        file_field,
        filename.encode("ascii", "replace").decode("ascii"),
    )
    if any(ord(ch) > 127 for ch in filename):
        from urllib.parse import quote

        disp = (
            'Content-Disposition: form-data; name="%s"; filename="%s"; '
            "filename*=UTF-8''%s\r\n"
            % (
                file_field,
                filename.encode("ascii", "replace").decode("ascii"),
                quote(filename, safe=""),
            )
        )
    chunks.append(disp.encode("utf-8"))
    chunks.append(("Content-Type: %s\r\n\r\n" % ctype).encode("utf-8"))
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(chunks), "multipart/form-data; boundary=%s" % boundary


def upload_asset(owner, repo, token, release_id, filepath, retries=3, timeout=1800):
    url = _with_token(
        "%s/repos/%s/%s/releases/%s/attach_files"
        % (GITEE_API, owner, repo, release_id),
        token,
    )
    filename = os.path.basename(filepath)
    last_err = None
    for attempt in range(1, retries + 1):
        body, content_type = _multipart_encode(
            {"access_token": token},
            "file",
            filepath,
            filename=filename,
        )
        try:
            _log(
                "gitee: uploading %s (%d bytes, attempt %d/%d)"
                % (filename, len(body), attempt, retries)
            )
            return _request(
                "POST",
                url,
                data=body,
                headers={"Content-Type": content_type},
                timeout=timeout,
            )
        except (URLError, RuntimeError, TimeoutError, OSError) as exc:
            last_err = exc
            _log("gitee: upload failed: %s" % exc)
            if attempt < retries:
                time.sleep(5 * attempt)
    raise RuntimeError("upload failed after %d attempts: %s" % (retries, last_err))


def sync_release(owner, repo, token, tag, name, body, files, work_dir):
    verify_token(token)
    ensure_gitee_repo_has_commit(owner, repo, token, work_dir, tag=tag)
    rel = find_release_by_tag(owner, repo, token, tag)
    if rel is None:
        _log("gitee: creating release %s" % tag)
        rel = create_release(owner, repo, token, tag, name, body)
    else:
        _log("gitee: release exists %s id=%s" % (tag, rel.get("id")))
    release_id = rel.get("id")
    if not release_id:
        raise RuntimeError("gitee release missing id: %r" % (rel,))
    # 英文文件名优先：国内链路慢时至少保证 updater 可用资产先上去
    ordered = sorted(
        files,
        key=lambda p: 0 if os.path.basename(p) == "EggplantPet-Windows.exe" else 1,
    )
    uploaded = 0
    errors = []
    for path in ordered:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        try:
            upload_asset(owner, repo, token, release_id, path)
            uploaded += 1
        except Exception as exc:
            errors.append("%s: %s" % (os.path.basename(path), exc))
            _log("gitee: skip after errors: %s" % errors[-1])
    if uploaded == 0:
        raise RuntimeError("no assets uploaded; " + "; ".join(errors))
    if errors:
        _log("gitee: partial sync ok (%d uploaded); errors: %s" % (uploaded, errors))
    else:
        _log("gitee: sync done")


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
    token = (args.token or "").strip()
    if not token:
        print("gitee: GITEE_TOKEN missing, skip sync", file=sys.stderr)
        return 0
    os.makedirs(args.work_dir, exist_ok=True)
    try:
        sync_release(
            args.owner,
            args.repo,
            token,
            args.tag,
            args.name,
            args.body,
            args.files,
            args.work_dir,
        )
    except (HTTPError, URLError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        _log("gitee: sync failed: %s" % exc)
        msg = str(exc).lower()
        if "401" in msg or "unauthorized" in msg or "403" in msg:
            _log(
                "gitee: check GITEE_TOKEN is a personal access token "
                "with projects scope"
            )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
