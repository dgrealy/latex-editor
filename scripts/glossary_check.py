#!/usr/bin/env python3
"""Find acronyms the document uses but never defines, and definitions it no longer uses.

Acronyms are detected in the author's prose stream, so a citation key, a file
path or a macro name can never be mistaken for one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import session_state  # noqa: E402
from prose_stream import classify  # noqa: E402

#: Two or more capitals, optionally with digits: DNA, CO2, PDE, MRI, XRD.
_ACRONYM = re.compile(r"\b([A-Z]{2,}[0-9]*(?:s)?)\b")
_NEWACRONYM = re.compile(r"\\newacronym\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}\s*\{([^}]*)\}")
_GLOSSARY_ENTRY = re.compile(r"\\newglossaryentry\s*\{([^}]*)\}")
_NOMENCLATURE = re.compile(r"\\nomenclature\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_GLS_USE = re.compile(r"\\(?:gls|Gls|glspl|Glspl|acrshort|acrlong|acrfull|ac[slf]?)\s*\{([^}]*)\}")

#: Capitalised words that are not acronyms in a scientific manuscript.
IGNORE = {"I", "A", "AND", "OR", "THE", "II", "III", "IV", "VI", "VII", "VIII", "IX"}


def survey(cfg) -> dict:
    used: dict[str, str] = {}
    gls_keys: set[str] = set()

    for path in session_state.author_tex_files(cfg):
        text = path.read_text(encoding="utf-8", errors="replace")
        where = path.relative_to(cfg.root).as_posix()
        stream = classify(text, cfg.captions_are_prose)
        for token in stream.prose:
            for acronym in _ACRONYM.findall(token.text):
                if acronym in IGNORE or acronym.rstrip("s") in IGNORE:
                    continue
                used.setdefault(acronym, f"{where}:{token.line}")
        gls_keys.update(_GLS_USE.findall(text))

    defined: dict[str, str] = {}
    symbols: set[str] = set()
    for path in sorted(cfg.root.rglob("*.tex")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for key, short in _NEWACRONYM.findall(text):
            defined[short.strip()] = key.strip()
        for key in _GLOSSARY_ENTRY.findall(text):
            defined.setdefault(key.strip(), key.strip())
        symbols.update(entry.strip() for entry in _NOMENCLATURE.findall(text))

    undefined = {name: where for name, where in used.items() if name.rstrip("s") not in
                 {short.rstrip("s") for short in defined}}
    unused = sorted(short for short in defined if short not in used and defined[short] not in gls_keys)

    return {
        "undefined_acronyms": dict(sorted(undefined.items())),
        "unused_definitions": unused,
        "defined_count": len(defined),
        "nomenclature_symbols": sorted(symbols),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = config_module.load()
    if cfg is None:
        print("Not a latex-editor project (no .latex-editor.yml found).", file=sys.stderr)
        return 2

    result = survey(cfg)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()
        return 0

    if result["undefined_acronyms"]:
        print("Acronyms used but not defined:")
        for name, where in result["undefined_acronyms"].items():
            print(f"  {name:<10} first used at {where}")
    if result["unused_definitions"]:
        print("Defined but never used: " + ", ".join(result["unused_definitions"]))
    if not result["undefined_acronyms"] and not result["unused_definitions"]:
        print(f"All {result['defined_count']} acronym definitions are used and nothing is undefined.")
    print(f"{len(result['nomenclature_symbols'])} nomenclature entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
