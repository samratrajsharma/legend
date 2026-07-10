"""Acquire a repository (git clone or uploaded zip) and walk its files. Pure-stdlib; no
host imports, so it is unit-testable in isolation."""
from __future__ import annotations
import hashlib
import os
import subprocess
import urllib.parse
import zipfile

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
             ".idea", ".vscode", "site-packages", ".mypy_cache", ".pytest_cache", "target",
             "vendor", ".next", ".gradle"}
LANG = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
        ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript", ".go": "go",
        ".java": "java", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml", ".json": "json"}
CODE_LANGS = {"python", "javascript", "typescript", "go", "java"}
# git transports we permit (blocks ext::/file:: RCE + local-file SSRF)
ALLOWED_GIT_SCHEMES = {"http", "https", "ssh", "git"}
MAX_ARCHIVE_BYTES = 500_000_000   # uncompressed total; decompression-bomb guard


def language_of(path: str) -> str:
    return LANG.get(os.path.splitext(path)[1].lower(), "other")


def safe_git_url(url: str) -> str:
    """Validate a clone URL. Rejects argument injection (leading '-') and dangerous
    transports (ext::, file://, fd::, ...). Allows http(s)/ssh/git and scp-style git@host:path."""
    if not url or not isinstance(url, str):
        raise ValueError("a repository URL is required")
    url = url.strip()
    if url.startswith("-"):
        raise ValueError("invalid repository URL")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme:
        if parsed.scheme.lower() not in ALLOWED_GIT_SCHEMES:
            raise ValueError(f"unsupported URL scheme: {parsed.scheme}")
    elif "@" in url and ":" in url.split("@", 1)[1]:
        pass                              # scp-like ssh syntax: git@host:org/repo.git
    else:
        raise ValueError("repository URL must use https, ssh, or git")
    return url


def _redact(msg: str, url: str) -> str:
    """Strip an embedded-credential URL out of error text before it is persisted."""
    try:
        p = urllib.parse.urlparse(url)
        if p.username or p.password:
            return msg.replace(url, "<redacted-url>")
    except Exception:
        pass
    return msg


def safe_extract(zip_path: str, dest_dir: str, max_total: int = MAX_ARCHIVE_BYTES,
                 max_files: int = 20000) -> None:
    """Extract a zip defensively: skip entries that escape dest_dir (zip-slip) or are
    symlinks, and abort if the uncompressed total exceeds max_total (zip-bomb)."""
    dest_abs = os.path.abspath(dest_dir)
    total = 0
    with zipfile.ZipFile(zip_path) as z:
        for i, info in enumerate(z.infolist()):
            if i >= max_files:
                break
            target = os.path.abspath(os.path.join(dest_dir, info.filename))
            if target != dest_abs and not target.startswith(dest_abs + os.sep):
                continue                                      # escapes dest -> skip
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                continue                                      # symlink -> skip
            total += info.file_size
            if total > max_total:
                raise RuntimeError("archive too large (decompression-bomb guard)")
            z.extract(info, dest_dir)


def clone_or_extract(source: str, source_url, dest_dir: str, upload_path=None) -> str:
    """Returns the path to the working copy. `source` is 'git' or 'upload'."""
    os.makedirs(dest_dir, exist_ok=True)
    if source == "git":
        url = safe_git_url(source_url)
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0",   # never block on a credential prompt
                   GIT_ALLOW_PROTOCOL="http:https:ssh:git")
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--no-tags", "--", url, dest_dir],
            capture_output=True, text=True, timeout=900, env=env)
        if r.returncode != 0:
            raise RuntimeError("git clone failed: " + _redact(r.stderr.strip()[:400], url))
        return dest_dir
    if source == "upload":
        if not upload_path or not os.path.exists(upload_path):
            raise FileNotFoundError("uploaded archive not found")
        safe_extract(upload_path, dest_dir)
        entries = [e for e in os.listdir(dest_dir) if not e.startswith(".")]
        if len(entries) == 1 and os.path.isdir(os.path.join(dest_dir, entries[0])):
            return os.path.join(dest_dir, entries[0])   # descend into single top folder
        return dest_dir
    raise ValueError(f"unknown source: {source}")


def walk_files(root: str, max_files: int = 20000, max_bytes: int = 1_500_000):
    """Yield file records {path, abs, language, size}. Skips vendored/build dirs and huge files."""
    out = []
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ab = os.path.join(r, f)
            if os.path.islink(ab):
                continue            # don't index symlinks (could point outside the repo)
            try:
                size = os.path.getsize(ab)
            except OSError:
                continue
            if size > max_bytes:
                continue
            rel = os.path.relpath(ab, root).replace(os.sep, "/")
            out.append({"path": rel, "abs": ab, "language": language_of(rel), "size": size})
            if len(out) >= max_files:
                return out
    return out


def read_text(abs_path: str) -> str:
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
