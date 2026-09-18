#!/usr/bin/env python3
"""Put each sentence on its own line, so the author can diff their own writing.

Only whitespace inside prose moves.  The guard permits this because the prose
stream ignores layout -- but that is exactly why this script verifies its own
output: if reflowing changed the author's words by even one character, it
writes nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prose_stream import classify, compare  # noqa: E402

#: Periods that end an abbreviation rather than a sentence.
ABBREVIATIONS = {
    "e.g.", "i.e.", "cf.", "etc.", "et", "al.", "vs.", "viz.", "approx.",
    "ca.", "resp.", "Fig.", "Figs.", "Eq.", "Eqs.", "Tab.", "Tabs.", "Sec.",
    "Secs.", "Ch.", "App.", "Ref.", "Refs.", "No.", "Nos.", "pp.", "p.",
    "Dr.", "Prof.", "Mr.", "Ms.", "Mrs.", "St.", "Inc.", "Ltd.", "Jr.",
    "min.", "max.", "std.", "dev.", "wt.", "vol.", "conc.", "temp.",
}

#: A sentence end: terminal punctuation, then space, then something that starts
#: a new sentence.  Trailing quotes and brackets stay with the sentence.
_BOUNDARY = re.compile(r"([.!?][\"')\]]*)([ \t]+)(?=[A-Z\\])")

#: What precedes the period, to test it against the abbreviation list.
_LAST_WORD = re.compile(r"(\S+)$")


def _is_sentence_end(text: str, end_of_punct: int) -> bool:
    prefix = text[:end_of_punct]
    match = _LAST_WORD.search(prefix)
    if not match:
        return False
    word = match.group(1)
    if word in ABBREVIATIONS:
        return False
    stem = word.rstrip("\"')]")
    if stem in ABBREVIATIONS:
        return False
    # Initials ("J. Smith") and numbered labels ("Fig. 3.1") are not sentence ends.
    # The numeric test needs a digit: a bare "." is the tail of a sentence that
    # ended with a macro, as in "...\cite{smith2019}. Next sentence".
    if re.fullmatch(r"[A-Z]\.", stem) or re.fullmatch(r"\d[\d.]*\.?", stem):
        return False
    return True


def reflow_text(source: str, captions_are_prose: bool = True) -> str:
    """Return `source` with one sentence per line inside author prose."""
    stream = classify(source, captions_are_prose)
    if not stream.parse_ok:
        raise ValueError("the file could not be parsed as LaTeX")

    edits: list[tuple[int, int, str]] = []
    for start, length in stream.spans:
        chunk = source[start : start + length]
        for match in _BOUNDARY.finditer(chunk):
            punct_end = match.end(1)
            if not _is_sentence_end(chunk, punct_end):
                continue
            edits.append((start + match.start(2), start + match.end(2), "\n"))

    result = source
    for begin, end, replacement in sorted(edits, reverse=True):
        result = result[:begin] + replacement + result[end:]
    return result


def reflow_file(path: Path, captions_are_prose: bool = True, write: bool = True) -> bool:
    """Reflow one file. Returns True if it changed. Refuses to alter any word."""
    original = path.read_text(encoding="utf-8")
    updated = reflow_text(original, captions_are_prose)
    if updated == original:
        return False

    verdict = compare(original, updated, captions_are_prose)
    if not verdict.allowed or classify(original, captions_are_prose).text != classify(
        updated, captions_are_prose
    ).text:
        raise AssertionError(
            f"reflow would have altered the author's text in {path}; nothing was written"
        )

    if write:
        path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args()

    changed = []
    for path in args.paths:
        try:
            if reflow_file(path, write=not args.check):
                changed.append(path)
        except (AssertionError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    for path in changed:
        print(f"{'would reflow' if args.check else 'reflowed'} {path}")
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
