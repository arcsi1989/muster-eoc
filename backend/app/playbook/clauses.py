"""The playbook's clauses, parsed from docs/playbook.md (ID, section, title, text)."""

import re
from dataclasses import dataclass
from pathlib import Path

SECTION = re.compile(r"^## (\d+)\. (.+)$")
CLAUSE = re.compile(r"^\*\*(P-\d+\.\d+) (.+?)\*\*\s*(.*)$")


@dataclass(frozen=True)
class Clause:
    id: str
    section: str
    title: str  # the bold lead-in, without its trailing full stop
    text: str


def parse_clauses(playbook_path: Path) -> list[Clause]:
    clauses = []
    section = ""
    for line in playbook_path.read_text().splitlines():
        if heading := SECTION.match(line):
            section = f"{heading.group(1)}. {heading.group(2)}"
        elif clause := CLAUSE.match(line):
            clause_id, title, text = clause.groups()
            clauses.append(Clause(clause_id, section, title.rstrip("."), text.strip()))
    return clauses
