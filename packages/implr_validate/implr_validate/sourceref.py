"""Deterministic source-reference for tying test evidence to a code state.
Prefers git; falls back to a filesystem hash. Standard library only."""
import hashlib
import os
import subprocess


def source_ref_fallback(root, rel_paths):
    entries = []
    for rel in rel_paths:
        base = os.path.join(root, rel)
        if os.path.isfile(base):
            walk_roots = [(os.path.dirname(base), [os.path.basename(base)])]
        else:
            walk_roots = None
        if walk_roots is None:
            for dirpath, _dirs, files in os.walk(base):
                for name in sorted(files):
                    p = os.path.join(dirpath, name)
                    st = os.stat(p)
                    entries.append((os.path.relpath(p, root).replace(os.sep, "/"), st.st_size, st.st_mtime_ns))
        else:
            for dirpath, names in walk_roots:
                for name in names:
                    p = os.path.join(dirpath, name)
                    st = os.stat(p)
                    entries.append((os.path.relpath(p, root).replace(os.sep, "/"), st.st_size, st.st_mtime_ns))
    entries.sort()
    payload = "\n".join("%s|%d|%d" % e for e in entries)
    return "fb:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _git(root, args):
    return subprocess.check_output(["git"] + args, cwd=root, stderr=subprocess.DEVNULL).decode("utf-8").strip()


def source_ref(root, rel_paths):
    try:
        head = _git(root, ["rev-parse", "HEAD"])
        # tracked changes vs HEAD — includes BOTH staged and unstaged
        diff = _git(root, ["diff", "HEAD", "--"] + list(rel_paths))
        # untracked files (respecting .gitignore) — hash their contents
        others = _git(root, ["ls-files", "--others", "--exclude-standard", "--"] + list(rel_paths))
        untracked = []
        for rel in others.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            p = os.path.join(root, rel)
            try:
                with open(p, "rb") as fh:
                    content = fh.read()
            except OSError:
                content = b""
            untracked.append(rel + "\0" + hashlib.sha256(content).hexdigest())
        combined = diff + "\n--untracked--\n" + "\n".join(sorted(untracked))
        state_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:8]
        return "git:%s:%s" % (head[:12], state_hash)
    except Exception:
        return source_ref_fallback(root, rel_paths)
