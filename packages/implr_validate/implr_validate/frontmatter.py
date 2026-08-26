# scripts/implr_validate/frontmatter.py
"""Parser for the restricted YAML-frontmatter subset implr templates produce.
Standard library only. Anything outside the subset is a validation error."""
import re


class FrontmatterError(Exception):
    pass


def split_frontmatter(text):
    """Return (frontmatter_block_or_None, body)."""
    if not text.startswith("---\n") and text != "---\n":
        return None, text
    rest = text[4:]
    end = rest.find("\n---")
    if end == -1:
        raise FrontmatterError("unterminated frontmatter block")
    block = rest[:end]
    after = rest[end + 4:]
    if after.startswith("\n"):
        after = after[1:]
    return block, after


def _scalar(raw):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        return _inline_list(raw)
    if raw.startswith("{") and raw.endswith("}"):
        return _inline_object(raw)
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def _split_top(s):
    """Split on commas not inside quotes/brackets/braces."""
    parts, buf, depth, quote = [], [], 0, None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return [p.strip() for p in parts]


def _inline_list(raw):
    inner = raw[1:-1].strip()
    if inner == "":
        return []
    return [_scalar(p) for p in _split_top(inner)]


def _inline_object(raw):
    inner = raw[1:-1].strip()
    obj = {}
    for pair in _split_top(inner):
        if ":" not in pair:
            raise FrontmatterError("bad inline object: %r" % raw)
        k, v = pair.split(":", 1)
        obj[k.strip()] = _scalar(v)
    return obj


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def parse_frontmatter(text):
    block, _ = split_frontmatter(text)
    if block is None:
        raise FrontmatterError("no frontmatter block")
    lines = [ln for ln in block.split("\n") if ln.strip() != "" and not ln.lstrip().startswith("#")]
    result = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if _indent(line) != 0:
            raise FrontmatterError("unexpected indentation at top level: %r" % line)
        if ":" not in line:
            raise FrontmatterError("expected 'key:' at %r" % line)
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest != "":
            result[key] = _scalar(rest)
            i += 1
            continue
        # rest is empty: could be empty scalar, block list, or nested mapping
        j = i + 1
        children = []
        while j < len(lines) and _indent(lines[j]) >= 2:
            children.append(lines[j])
            j += 1
        if not children:
            result[key] = ""
        elif children[0].lstrip().startswith("- "):
            result[key] = _parse_block_list(children)
        else:
            result[key] = _parse_nested_mapping(children)
        i = j
    return result


def _parse_block_list(children):
    out = []
    for c in children:
        stripped = c.lstrip()
        if not stripped.startswith("- "):
            raise FrontmatterError("mixed block-list content: %r" % c)
        out.append(_scalar(stripped[2:]))
    return out


def _parse_nested_mapping(children):
    base = _indent(children[0])
    out = {}
    for c in children:
        if _indent(c) != base:
            raise FrontmatterError("only one level of nesting allowed: %r" % c)
        if ":" not in c:
            raise FrontmatterError("expected 'key:' in nested mapping: %r" % c)
        k, v = c.strip().split(":", 1)
        out[k.strip()] = _scalar(v)
    return out
