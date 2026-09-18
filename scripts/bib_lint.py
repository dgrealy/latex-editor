#!/usr/bin/env python3
"""Check a BibTeX file for the mistakes that survive to a submitted manuscript.

Missing required fields, page ranges typed with a hyphen, titles whose acronyms
will be lowercased by the style, duplicate entries, and -- importantly -- entries
whose metadata was never verified against a source.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = {
    "article": ["author", "title", "journal", "year"],
    "book": ["author", "title", "publisher", "year"],
    "inbook": ["author", "title", "publisher", "year"],
    "incollection": ["author", "title", "booktitle", "publisher", "year"],
    "inproceedings": ["author", "title", "booktitle", "year"],
    "conference": ["author", "title", "booktitle", "year"],
    "phdthesis": ["author", "title", "school", "year"],
    "mastersthesis": ["author", "title", "school", "year"],
    "techreport": ["author", "title", "institution", "year"],
    "misc": ["title"],
    "unpublished": ["author", "title", "note"],
}

#: article entries really ought to carry these too, even though BibTeX
#: does not insist.
RECOMMENDED = {"article": ["volume", "pages", "doi"]}

_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", re.DOTALL)
_FIELD = re.compile(r"(\w+)\s*=\s*(\{.*?\}|\"[^\"]*\"|[^,\n]+)\s*,?", re.DOTALL)
_KEY_SCHEME = re.compile(r"^[a-z][a-z-]*\d{4}[a-z0-9]*$")
_ACRONYM = re.compile(r"(?<![{\\])\b([A-Z]{2,})\b(?![}])")


def _balanced(value: str) -> str:
    value = value.strip()
    if value.startswith("{") and value.endswith("}"):
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def parse(text: str) -> list[dict]:
    entries = []
    for match in _ENTRY.finditer(text):
        kind, key, body = match.group(1).lower(), match.group(2), match.group(3)
        fields = {
            name.lower(): _balanced(value)
            for name, value in _FIELD.findall(body)
        }
        entries.append(
            {
                "type": kind,
                "key": key,
                "fields": fields,
                "raw": match.group(0),
                "line": text.count("\n", 0, match.start()) + 1,
            }
        )
    return entries


def lint(text: str, provenance: dict | None = None) -> list[dict]:
    provenance = provenance or {}
    findings: list[dict] = []
    seen_keys: dict[str, int] = {}
    seen_titles: dict[str, str] = {}

    def add(entry, severity, message):
        findings.append(
            {"key": entry["key"], "line": entry["line"], "severity": severity, "message": message}
        )

    for entry in parse(text):
        key, fields = entry["key"], entry["fields"]

        if key in seen_keys:
            add(entry, "error", f"duplicate key, already defined at line {seen_keys[key]}")
        seen_keys[key] = entry["line"]

        title = fields.get("title", "").strip().lower()
        if title:
            if title in seen_titles and seen_titles[title] != key:
                add(entry, "warning", f"same title as entry {seen_titles[title]}")
            seen_titles.setdefault(title, key)

        for field in REQUIRED.get(entry["type"], []):
            if not fields.get(field):
                add(entry, "error", f"missing required field '{field}' for @{entry['type']}")
        for field in RECOMMENDED.get(entry["type"], []):
            if not fields.get(field):
                add(entry, "warning", f"no '{field}'")

        pages = fields.get("pages", "")
        if pages and "--" not in pages and re.search(r"\d\s*-\s*\d", pages):
            add(entry, "warning", "page range uses a single hyphen; BibTeX wants --")

        raw_title = fields.get("title", "")
        for acronym in set(_ACRONYM.findall(raw_title)):
            add(entry, "warning", f"acronym '{acronym}' in the title is not brace-protected")

        if not _KEY_SCHEME.match(key):
            add(entry, "info", "key does not follow the authoryear scheme, e.g. smith2019")

        record = provenance.get(key)
        if record is None:
            add(entry, "warning", "no provenance record: metadata has not been verified")
        elif not record.get("verified"):
            source = record.get("source", "an unverified source")
            add(entry, "error", f"metadata from {source} was never verified against the publisher")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bib", type=Path)
    parser.add_argument("--provenance", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    provenance = {}
    if args.provenance and args.provenance.is_file():
        provenance = json.loads(args.provenance.read_text(encoding="utf-8"))

    findings = lint(args.bib.read_text(encoding="utf-8", errors="replace"), provenance)

    if args.json:
        json.dump(findings, sys.stdout, indent=2)
        print()
    else:
        for item in findings:
            print(f"{item['severity']:8} {args.bib}:{item['line']}  {item['key']}: {item['message']}")
        if not findings:
            print(f"{args.bib}: all entries look well formed.")
    return 1 if any(f["severity"] == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
