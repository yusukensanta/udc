"""Consistency checks for the UDC documentation set.

Usage: check_docs.py [repo-root] [--list-refs]

Exit status is 1 if any check fails. The checks cover what a reader cannot
verify by eye across 19 ADRs: that every ADR carries the required header
fields and sections, that cross-references resolve, and that terms owned by
one document (states, error categories, validation levels, roadmap phases)
are used consistently everywhere else.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys
from dataclasses import dataclass, field

HEADER_FIELDS = ("Status", "Date", "Decision owners", "Scope")
STATUSES = ("Accepted", "Proposed", "Superseded", "Deprecated", "Rejected")
REQUIRED_SECTIONS = (
    "Context",
    "Decision drivers",
    "Options considered",
    "Rationale",
    "Trade-offs and consequences",
    "Validation plan",
    "Ownership boundary",
    "Revisit conditions",
    "Related ADRs",
)
DECISION_TITLES = frozenset({"Decision", "Decisions", "Proposed decision"})
TAIL_ORDER = (
    "Trade-offs and consequences",
    "Validation plan",
    "Ownership boundary",
    "Revisit conditions",
    "References",
    "Related ADRs",
)
VALIDATION_LEVELS = range(1, 6)

# Wording that earlier revisions replaced. A match means an old term came back.
RETIRED = {
    r"publication workflow": "use 'publication step' or the ADR-0017 protocol",
    r"Job Coordinator": "undefined component",
    r"Job Manifest\b(?! and State)": "use lower-case 'job manifest'",
    r"config file, then documented environment": "old precedence order",
    r"Checksums / hashes": "old L4 definition",
    r"Terminal in MVP": "replaced by execution generations",
    r"generic Publisher|generic file publisher": "use 'Generic Publisher'",
    r"visibility[- ]commit": "use 'publication mode'",
    r"Any format\. Any cloud": "retired tagline",
    r"interoperability platform": "retired positioning",
}

ADR_REF = re.compile(r"(?:ADR-(\d{4}) )?§(\d+(?:\.\d+)?)")
PRD_REF_INTERNAL = re.compile(r"(?<!ADR-\d{4} )§(\d+(?:\.\d+)?)")
PRD_REF_EXTERNAL = re.compile(r"PRD §(\d+(?:\.\d+)?)")
REQUIREMENT_ID = re.compile(r"\b(N?FR-\d{2})\b")
STATE_TOKEN = re.compile(r"\b[A-Z]+(?:_[A-Z]+)*\b(?!\.md)")
ERROR_CATEGORY_USE = re.compile(r"\b[Aa]n? ([A-Z][a-z]+(?: / [a-z]+)?) error\b")


def slug(heading: str) -> str:
    """GitHub-style anchor for a heading."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def headings(text: str) -> list[tuple[int, str]]:
    """(level, title) for every heading outside code fences."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        match = None if fenced else re.match(r"^(#{1,6}) (.+?)\s*$", line)
        if match:
            out.append((len(match.group(1)), match.group(2)))
    return out


def without_code(text: str) -> str:
    """The text with code spans and fenced code blocks removed."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            out.append(re.sub(r"`[^`\n]*`", "", line))
    return "\n".join(out)


def table_rows(section: str) -> list[list[str]]:
    """Data rows of every Markdown table in the text, as stripped cells."""
    rows = []
    for line in section.splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s:|-]+\|?$", line):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


@dataclass
class Adr:
    path: pathlib.Path
    text: str
    num: str = field(init=False)
    header: str = field(init=False)
    h2: list[str] = field(init=False)
    bodies: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        self.num = re.search(r"ADR-(\d{4})", self.path.name).group(1)
        self.header = self.text.split("\n## ", 1)[0]
        self.h2 = [title for level, title in headings(self.text) if level == 2]
        self.bodies = {}
        current, fenced = None, False
        for line in self.text.splitlines():
            if line.startswith("```"):
                fenced = not fenced
            match = None if fenced else re.match(r"^## (?:\d+\. )?(.+?)\s*$", line)
            if match:
                current = match.group(1)
                self.bodies[current] = ""
            elif current is not None:
                self.bodies[current] += line + "\n"

    @property
    def titles(self) -> list[str]:
        """Second-level titles without their numbers."""
        return [re.sub(r"^\d+\. ", "", title) for title in self.h2]

    @property
    def sections(self) -> dict[str, str]:
        """Section number -> title, for correctly numbered headings."""
        out: dict[str, str] = {}
        for level, title in headings(self.text):
            pattern = r"(\d+)\. (.+)$" if level == 2 else r"(\d+\.\d+) (.+)$"
            match = re.match(pattern, title) if level in (2, 3) else None
            if match:
                out[match.group(1)] = match.group(2)
        return out

    def field(self, name: str) -> str | None:
        match = re.search(rf"^- \*\*{re.escape(name)}:\*\*[ \t]*(.*)$", self.header, re.M)
        return match.group(1).strip() if match else None


@dataclass
class DocSet:
    root: pathlib.Path
    texts: dict[pathlib.Path, str]
    adrs: dict[str, Adr]

    @property
    def prd_path(self) -> pathlib.Path:
        return self.root / "docs" / "PRD.md"

    @property
    def prd(self) -> str:
        return self.texts.get(self.prd_path, "")

    def rel(self, path: pathlib.Path) -> str:
        return str(path.relative_to(self.root))


def load(root: pathlib.Path) -> DocSet:
    root = root.resolve()
    adr_dir = root / "docs" / "adr"
    adr_files = sorted(adr_dir.glob("ADR-*.md"))
    others = [root / "README.md", root / "CONTRIBUTING.md", root / "docs" / "PRD.md"]
    paths = [p for p in others if p.exists()] + adr_files
    texts = {p: p.read_text(encoding="utf-8") for p in paths}
    adrs = {}
    for path in adr_files:
        adr = Adr(path, texts[path])
        adrs[adr.num] = adr
    return DocSet(root, texts, adrs)


# --- checks: each returns a list of problems ---------------------------------


def check_links(docs: DocSet) -> list[str]:
    """Relative links and their anchors resolve."""
    errors = []
    anchors = {p: {slug(h) for _, h in headings(t)} for p, t in docs.texts.items()}
    for path, text in docs.texts.items():
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, fragment = target.partition("#")
            dest = (path.parent / file_part).resolve() if file_part else path
            if not dest.exists():
                errors.append(f"{docs.rel(path)}: broken link {target}")
            elif fragment and dest in anchors and fragment not in anchors[dest]:
                errors.append(f"{docs.rel(path)}: broken anchor {target}")
    return errors


def check_headers(docs: DocSet) -> list[str]:
    """Every ADR has a well-formed title and the four header fields with usable values."""
    errors = []
    for adr in docs.adrs.values():
        name = adr.path.name
        first = adr.text.splitlines()[0] if adr.text else ""
        title = re.match(r"# ADR-(\d{4}): \S", first)
        if not title:
            errors.append(f"{name}: first line must be '# ADR-NNNN: Title'")
        elif title.group(1) != adr.num:
            errors.append(f"{name}: title number {title.group(1)} differs from the file name")
        for name_ in HEADER_FIELDS:
            value = adr.field(name_)
            if value is None:
                errors.append(f"{name}: header missing {name_}")
            elif not value:
                errors.append(f"{name}: header field {name_} is empty")
        status = adr.field("Status")
        if status and not status.startswith(STATUSES):
            errors.append(f"{name}: unknown status {status!r}")
        date = adr.field("Date")
        if date:
            try:
                datetime.date.fromisoformat(date)
            except ValueError:
                errors.append(f"{name}: Date {date!r} is not YYYY-MM-DD")
        if "**Priority:**" in adr.text:
            errors.append(f"{name}: ADRs carry no Priority header")
    return errors


def check_structure(docs: DocSet) -> list[str]:
    """Sections are numbered in order, required ones exist once, and none is empty."""
    errors = []
    for adr in docs.adrs.values():
        name = adr.path.name
        for position, heading in enumerate(adr.h2, 1):
            match = re.match(r"(\d+)\. .+$", heading)
            if not match or int(match.group(1)) != position:
                errors.append(f"{name}: section {position} misnumbered: {heading!r}")
        major, minor = 0, 0
        for level, heading in headings(adr.text):
            if level == 2:
                major, minor = major + 1, 0
            elif level == 3:
                minor += 1
                match = re.match(r"(\d+)\.(\d+) .+$", heading)
                if not match or (int(match.group(1)), int(match.group(2))) != (major, minor):
                    errors.append(f"{name}: subsection misnumbered: {heading!r}")
        titles = adr.titles
        for required in REQUIRED_SECTIONS:
            if titles.count(required) != 1:
                errors.append(
                    f"{name}: expected exactly one {required!r} section, "
                    f"found {titles.count(required)}"
                )
        if not DECISION_TITLES & set(titles):
            errors.append(f"{name}: no decision section")
        tail = [t for t in titles if t in TAIL_ORDER]
        if (
            tail != [t for t in TAIL_ORDER if t in tail]
            or titles[len(titles) - len(tail) :] != tail
        ):
            errors.append(f"{name}: tail sections out of order: {tail}")
        for title, body in adr.bodies.items():
            if not body.strip():
                errors.append(f"{name}: section {title!r} is empty")
        options = adr.bodies.get("Options considered", "")
        subsections = len(re.findall(r"^### ", options, re.M))
        if len(table_rows(options)) - 1 < 2 and subsections < 2:
            errors.append(f"{name}: 'Options considered' needs at least two options")
    return errors


def check_ownership_boundary(docs: DocSet) -> list[str]:
    """The ownership boundary says what is owned and names an owner for what is not."""
    errors = []
    for adr in docs.adrs.values():
        body = adr.bodies.get("Ownership boundary")
        if body is None:
            continue
        if "**Owns:**" not in body:
            errors.append(f"{adr.path.name}: ownership boundary has no '**Owns:**'")
        if "**Does not own:**" not in body:
            errors.append(f"{adr.path.name}: ownership boundary has no '**Does not own:**'")
            continue
        for line in body.split("**Does not own:**", 1)[1].splitlines():
            if line.startswith("- ") and not re.search(r"ADR-\d{4}|PRD", line):
                errors.append(f"{adr.path.name}: 'Does not own' item names no owner: {line[:60]!r}")
    return errors


def check_related_adrs(docs: DocSet) -> list[str]:
    """Related ADRs lists exactly the ADRs the body mentions."""
    errors = []
    for adr in docs.adrs.values():
        body, _, related = adr.text.rpartition("Related ADRs")
        mentioned = set(re.findall(r"ADR-(\d{4})", body)) - {adr.num}
        linked = set(re.findall(r"\[ADR-(\d{4}):", related))
        if mentioned != linked:
            errors.append(
                f"{adr.path.name}: Related ADRs mismatch, missing {sorted(mentioned - linked)}, "
                f"extra {sorted(linked - mentioned)}"
            )
        for num in sorted(mentioned | linked):
            if num not in docs.adrs:
                errors.append(f"{adr.path.name}: refers to ADR-{num}, which does not exist")
    return errors


def adr_section_refs(docs: DocSet) -> list[tuple[pathlib.Path, str, str, str | None]]:
    """Every ADR section reference: (file, ADR number, section number, resolved title or None)."""
    out = []
    for path, text in docs.texts.items():
        own = re.search(r"ADR-(\d{4})", path.name)
        for match in ADR_REF.finditer(text):
            num = match.group(1) or (own.group(1) if own else None)
            before = text[max(0, match.start() - 4) : match.start()]
            if num is None or (not match.group(1) and "PRD" in before):
                continue  # a reference into the PRD
            if path == docs.prd_path and not match.group(1):
                continue
            adr = docs.adrs.get(num)
            title = adr.sections.get(match.group(2)) if adr else None
            out.append((path, num, match.group(2), title))
    return out


def check_section_refs(docs: DocSet) -> list[str]:
    """Every 'ADR-NNNN §x.y' and every bare '§x.y' inside an ADR resolves."""
    errors = [
        f"{docs.rel(path)}: unresolved reference ADR-{num} §{section}"
        for path, num, section, title in adr_section_refs(docs)
        if title is None
    ]
    if any("§{" in without_code(text) for text in docs.texts.values()):
        errors.append("unresolved §{...} placeholder remains; run normalize_adrs.py")
    return errors


def check_prd_refs(docs: DocSet) -> list[str]:
    """References into the PRD (section numbers and requirement ids) resolve."""
    numbers = set(re.findall(r"^#{2,3} (\d+(?:\.\d+)?)\.? ", docs.prd, re.M))
    requirement_ids = set(re.findall(r"^### (N?FR-\d{2}):", docs.prd, re.M))
    errors = []
    for path, text in docs.texts.items():
        pattern = PRD_REF_INTERNAL if path == docs.prd_path else PRD_REF_EXTERNAL
        for section in pattern.findall(text):
            if section not in numbers:
                errors.append(f"{docs.rel(path)}: unresolved reference PRD §{section}")
        for requirement in REQUIREMENT_ID.findall(text):
            if requirement not in requirement_ids:
                errors.append(f"{docs.rel(path)}: unknown requirement {requirement}")
    return sorted(set(errors))


def check_status_table(docs: DocSet) -> list[str]:
    """The PRD status table agrees with each ADR header."""
    errors = []
    for num, adr in docs.adrs.items():
        status = adr.field("Status") or ""
        row = re.search(rf"\| \[ADR-{num}\]\([^)]+\) \| [^|]+ \| ([^|]+) \|", docs.prd)
        if not row:
            errors.append(f"PRD status table: no row for ADR-{num}")
        elif not row.group(1).strip().startswith(status.split(" ")[0] or "?"):
            errors.append(
                f"PRD status table: ADR-{num} is {row.group(1).strip()!r}, header says {status!r}"
            )
    return errors


def _ownership_rows(text: str, header: str) -> list[tuple[str, ...]] | None:
    if header not in text:
        return None
    block = text[text.index(header) :].split("\n\n")[0]
    return [tuple(cell.strip() for cell in line.split("|")[1:4]) for line in block.splitlines()[2:]]


def check_adr_0001_maps(docs: DocSet) -> list[str]:
    """ADR-0001 has a scope-map row for every ADR, and the PRD repeats its ownership table."""
    adr1 = docs.adrs.get("0001")
    if adr1 is None:
        return ["ADR-0001 is missing; it holds the scope map and the ownership table"]
    errors = [
        f"ADR-0001 scope map: no row for {num}"
        for num in docs.adrs
        if not re.search(rf"^\| {num} \|", adr1.text, re.M)
    ]
    mine = _ownership_rows(adr1.text, "| Concern | Owns | Must not own |")
    theirs = _ownership_rows(docs.prd, "| Concern | Owns | Does not own |")
    if mine is None or theirs is None:
        errors.append("ownership table not found in ADR-0001 or in the PRD")
    elif mine != theirs:
        errors.append("PRD ownership table differs from ADR-0001")
    return errors


def defined_states(docs: DocSet) -> set[str]:
    """State names defined by the state tables of ADR-0013."""
    adr = docs.adrs.get("0013")
    body = adr.bodies.get("State machines and legal transitions", "") if adr else ""
    states: set[str] = set()
    for row in table_rows(body):
        for cell in row[:2]:
            states.update(re.findall(r"\b[A-Z]+(?:_[A-Z]+)*\b", cell))
    return {s for s in states if len(s) > 3}


def error_categories(docs: DocSet) -> set[str]:
    """Error category names defined by the category table of ADR-0008."""
    adr = docs.adrs.get("0008")
    body = adr.bodies.get("Error categories", "") if adr else ""
    return {row[0] for row in table_rows(body)[1:]}


def roadmap_phases(docs: DocSet) -> set[int]:
    return {int(n) for n in re.findall(r"^\| Phase (\d+) \|", docs.prd, re.M)}


def check_vocabulary(docs: DocSet) -> list[str]:
    """Terms owned by one document are used with the values that document defines."""
    errors = []
    states = defined_states(docs)
    categories = error_categories(docs)
    phases = roadmap_phases(docs)
    last_phase = max(phases) if phases else None
    for path, text in docs.texts.items():
        where = docs.rel(path)
        for token in set(STATE_TOKEN.findall(text)):
            looks_like_state = "_" in token or (len(token) > 5 and token.endswith(("ING", "ED")))
            if states and looks_like_state and token not in states:
                errors.append(f"{where}: state {token} is not defined in ADR-0013")
        for level in set(re.findall(r"\bL(\d+)\b", text)):
            if int(level) not in VALIDATION_LEVELS:
                errors.append(f"{where}: validation level L{level} does not exist (ADR-0006)")
        for category in set(ERROR_CATEGORY_USE.findall(text)):
            if categories and category not in categories:
                errors.append(f"{where}: error category {category!r} is not defined in ADR-0008")
        if last_phase is None:
            continue
        for phase in set(re.findall(r"\bPhases? (\d+)\b", text)):
            if int(phase) not in phases:
                errors.append(f"{where}: Phase {phase} is not in the PRD roadmap")
        for upper in set(re.findall(r"\bPhase 0–(\d+)", text)):
            if int(upper) != last_phase:
                errors.append(f"{where}: 'Phase 0–{upper}' but the roadmap ends at {last_phase}")
    return sorted(errors)


def check_retired_terms(docs: DocSet) -> list[str]:
    errors = []
    for path, text in docs.texts.items():
        for pattern, why in RETIRED.items():
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{docs.rel(path)}:{line}: retired wording {match.group(0)!r} ({why})"
                )
    return errors


def check_readme_range(docs: DocSet) -> list[str]:
    """The README states the ADR range that actually exists."""
    readme = docs.texts.get(docs.root / "README.md", "")
    stated = re.search(r"ADR-0001 to ADR-(\d{4})", readme)
    if not docs.adrs or not stated:
        return []
    last = max(docs.adrs)
    if stated.group(1) != last:
        return [f"README.md: says 'ADR-0001 to ADR-{stated.group(1)}' but the last ADR is {last}"]
    return []


CHECKS = (
    check_links,
    check_headers,
    check_structure,
    check_ownership_boundary,
    check_related_adrs,
    check_section_refs,
    check_prd_refs,
    check_status_table,
    check_adr_0001_maps,
    check_vocabulary,
    check_retired_terms,
    check_readme_range,
)


def run(root: pathlib.Path) -> list[str]:
    docs = load(root)
    errors: list[str] = []
    for check in CHECKS:
        errors.extend(check(docs))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    list_refs = "--list-refs" in args
    positional = [a for a in args if not a.startswith("--")]
    root = pathlib.Path(positional[0] if positional else ".")
    docs = load(root)
    if list_refs:
        print("Section references:")
        for path, num, section, title in adr_section_refs(docs):
            print(f"  {path.name}: ADR-{num} §{section} -> {title}")
        print()
    errors = run(root)
    if errors:
        print(f"{len(errors)} problem(s):")
        for error in errors:
            print("  -", error)
        return 1
    print(f"all checks passed across {len(docs.texts)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
