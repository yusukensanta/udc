"""Normalize ADR structure: tail section order, numbering, Related ADRs, and §{Title} placeholders.

Usage: normalize_adrs.py [repo-root] [--check]

Without --check the files are rewritten. With --check nothing is written and the
exit status is 1 if a file would change. The operation is idempotent.

Adding or moving a section changes the numbers of the sections after it. To keep
cross-references correct, write a reference as `§{Section title}` (or
`ADR-0013 §{Section title}`); this tool replaces it with the current number.
"""

from __future__ import annotations

import pathlib
import re
import sys

TAIL = (
    "Trade-offs and consequences",
    "Validation plan",
    "Ownership boundary",
    "Revisit conditions",
    "References",
)
HEADING = re.compile(r"^(#{2,3}) (?:\d+(?:\.\d+)*\.?\s+)?(.+?)\s*$")
ADR_ID = re.compile(r"ADR-(\d{4})")
PLACEHOLDER = re.compile(r"(?:ADR-(\d{4}) )?§\{([^}]+)\}")


CODE_SPAN = re.compile(r"(`[^`\n]*`)")


class NormalizeError(Exception):
    """A document cannot be normalized without a human decision."""


def sub_outside_code(pattern: re.Pattern[str], replace, text: str) -> str:
    """Apply a substitution everywhere except inside code spans and fenced code blocks."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
        elif fenced:
            out.append(line)
        else:
            parts = CODE_SPAN.split(line)
            parts[::2] = [pattern.sub(replace, part) for part in parts[::2]]
            out.append("".join(parts))
    return "\n".join(out)


def parse(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split into (preamble lines, [(section title, body lines)]). Code fences are respected."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        match = None if fenced else HEADING.match(line)
        if match and match.group(1) == "##":
            current = (match.group(2), [])
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current[1].append(line)
    return preamble, sections


def strip_blank(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def build(name: str, text: str, titles: dict[str, tuple[str, str]]) -> tuple[str, dict[str, str]]:
    """Return the normalized text of one ADR and its {section title: number} index."""
    own = ADR_ID.search(name).group(1)
    preamble, sections = parse(text)
    sections = [(title, body) for title, body in sections if title != "Related ADRs"]
    names = [title for title, _ in sections]
    duplicates = sorted({title for title in names if names.count(title) > 1})
    if duplicates:
        raise NormalizeError(f"{name}: duplicate sections {duplicates}")
    head = [s for s in sections if s[0] not in TAIL]
    tail = [s for wanted in TAIL for s in sections if s[0] == wanted]
    ordered = head + tail

    out = [*strip_blank(preamble), ""]
    index: dict[str, str] = {}
    for number, (title, body) in enumerate(ordered, 1):
        index[title] = str(number)
        out += [f"## {number}. {title}", ""]
        sub, fenced = 0, False
        for line in strip_blank(body):
            if line.startswith("```"):
                fenced = not fenced
            match = None if fenced else HEADING.match(line)
            if match and match.group(1) == "###":
                sub += 1
                index[match.group(2)] = f"{number}.{sub}"
                line = f"### {number}.{sub} {match.group(2)}"
            out.append(line)
        out.append("")

    mentioned = sorted({num for num in ADR_ID.findall("\n".join(out)) if num != own})
    if mentioned:
        out += [f"## {len(ordered) + 1}. Related ADRs", ""]
        for num in mentioned:
            if num not in titles:
                raise NormalizeError(f"{name}: refers to ADR-{num}, which does not exist")
            file_name, title = titles[num]
            out.append(f"- [ADR-{num}: {title}]({file_name})")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n", index


def normalize(root: pathlib.Path) -> dict[pathlib.Path, str]:
    """Compute the normalized content of every file that would change."""
    adr_dir = root / "docs" / "adr"
    files = sorted(adr_dir.glob("ADR-*.md"))
    originals = {path: path.read_text(encoding="utf-8") for path in files}
    titles: dict[str, tuple[str, str]] = {}
    for path, text in originals.items():
        first = text.splitlines()[0] if text else ""
        match = re.match(r"# ADR-(\d{4}): (.+)$", first)
        if not match:
            raise NormalizeError(
                f"{path.name}: first line must be '# ADR-NNNN: Title', got {first!r}"
            )
        titles[match.group(1)] = (path.name, match.group(2))

    built: dict[pathlib.Path, str] = {}
    indexes: dict[str, dict[str, str]] = {}
    for path, text in originals.items():
        num = ADR_ID.search(path.name).group(1)
        built[path], indexes[num] = build(path.name, text, titles)

    def resolver(own: str | None):
        def replace(match: re.Match[str]) -> str:
            num, title = match.group(1) or own, match.group(2)
            if num is None or title not in indexes.get(num, {}):
                raise NormalizeError(f"unresolved placeholder: ADR-{num} §{{{title}}}")
            prefix = f"ADR-{match.group(1)} " if match.group(1) else ""
            return f"{prefix}§{indexes[num][title]}"

        return replace

    changed: dict[pathlib.Path, str] = {}
    for path, text in built.items():
        new = sub_outside_code(PLACEHOLDER, resolver(ADR_ID.search(path.name).group(1)), text)
        if new != originals[path]:
            changed[path] = new
    for extra in (root / "README.md", root / "CONTRIBUTING.md", root / "docs" / "PRD.md"):
        if not extra.exists():
            continue
        text = extra.read_text(encoding="utf-8")
        new = sub_outside_code(PLACEHOLDER, resolver(None), text)
        if new != text:
            changed[extra] = new
    return changed


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    positional = [a for a in args if not a.startswith("--")]
    root = pathlib.Path(positional[0] if positional else ".").resolve()
    try:
        changed = normalize(root)
    except NormalizeError as error:
        print(f"error: {error}")
        return 2
    if check_only:
        for path in changed:
            print(f"would change: {path.relative_to(root)}")
        if changed:
            print("run tools/docs/normalize_adrs.py to fix")
            return 1
        print("ADRs are normalized")
        return 0
    for path, text in changed.items():
        path.write_text(text, encoding="utf-8")
        print(f"normalized {path.relative_to(root)}")
    print(f"{len(changed)} file(s) changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
