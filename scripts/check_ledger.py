#!/usr/bin/env python3
"""Check the insights ledger: its columns, verdicts, reversal conditions and keys.

Standard library only, Python 3.11+. Run after every ledger edit: python3 scripts/check_ledger.py [ledger.md]
Exit 0 clean, 1 a broken row (each named by line and rule), 2 misuse.
"""
import sys
from pathlib import Path

COLUMNS = ("Key", "Ask", "Pass", "Verdict", "Revisit", "Source")
VERDICTS = ("LANDED", "OPEN", "DEFER", "NO-GO")
NEEDS_REVISIT = ("DEFER", "NO-GO")
KEY_PREFIX = "insight:"
DEFAULT = Path(__file__).resolve().parent.parent / "ledger" / "insights-ledger.md"


def cells(line: str) -> list[str]:
    body = line.strip().removeprefix("|").removesuffix("|").replace("\\|", "\x00")
    return [cell.strip().replace("\x00", "|") for cell in body.split("|")]


def empty(cell: str) -> bool:
    return cell in ("", "—", "-")


def tables(text: str) -> list[list[tuple[int, str]]]:
    """Each run of consecutive table lines, as (line number, line) pairs."""
    found, run = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("|"):
            run.append((number, line))
        elif run:
            found, run = found + [run], []
    return found + [run] if run else found


def check(text: str) -> tuple[int, list[str]] | None:
    """(rows checked, problems) for the first table with Key and Verdict columns, or None if there is none."""
    for table in tables(text):
        header = cells(table[0][1])
        if "Key" not in header or "Verdict" not in header:
            continue
        # Order matters too: the triage command's closed-door sweep reads Verdict and Revisit by position.
        if header != list(COLUMNS):
            return 0, [f"line {table[0][0]}: the columns are {header}, and must be {list(COLUMNS)} in that order"]
        problems, first_seen = [], {}
        for number, line in table[2:]:
            row = cells(line)
            if len(row) != len(header):
                problems.append(f"line {number}: {len(row)} cells, the header has {len(header)}")
                continue
            row = dict(zip(header, row))
            key, verdict = row["Key"].strip("`"), row["Verdict"].strip("*")
            if not key.startswith(KEY_PREFIX):
                problems.append(f"line {number}: the key {key!r} must start with {KEY_PREFIX!r}")
            if key in first_seen:
                problems.append(f"line {number}: the key {key!r} repeats line {first_seen[key]}; one row per ask")
            first_seen.setdefault(key, number)
            if verdict not in VERDICTS:
                problems.append(f"line {number}: the verdict {verdict!r} is not one of {', '.join(VERDICTS)}")
            if verdict in NEEDS_REVISIT and empty(row["Revisit"]):
                problems.append(f"line {number}: a {verdict} row must name the fact that would reverse it in Revisit")
            if verdict == "LANDED" and empty(row["Source"]):
                problems.append(f"line {number}: a LANDED row must cite the commit that shipped it in Source")
        return len(table) - 2, problems
    return None


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[1]) if len(argv) == 2 else DEFAULT
    if not path.is_file():
        print(f"No ledger at {path}.", file=sys.stderr)
        return 2
    result = check(path.read_text(encoding="utf-8"))
    if result is None:
        print(f"{path} has no table with Key and Verdict columns.", file=sys.stderr)
        return 2
    rows, problems = result
    for problem in problems:
        print(f"{path}: {problem}")
    print(f"{'BROKEN' if problems else 'OK'}: {rows} rows, {len(problems)} problem(s) in {path}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
