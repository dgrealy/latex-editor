"""Extract the author-owned prose token stream from LaTeX source.

This is the primitive the whole prose guard rests on.  Given a .tex file it
returns the ordered list of words that belong to the *author* -- running text,
section headings, captions -- while skipping everything Claude is allowed to
write: math, float bodies, citation and reference arguments, comments and the
preamble.

Two files whose prose streams are identical say exactly the same thing to a
reader, however differently they are laid out.  That makes the stream a precise
test for "did this edit change the author's words?".
"""

from __future__ import annotations

import re
from typing import Iterable, NamedTuple

try:
    from pylatexenc.latexwalker import (
        LatexCharsNode,
        LatexCommentNode,
        LatexEnvironmentNode,
        LatexGroupNode,
        LatexMacroNode,
        LatexMathNode,
        LatexSpecialsNode,
        LatexWalker,
        get_default_latex_context_db,
    )
    from pylatexenc.macrospec import MacroSpec
except ImportError as exc:  # pragma: no cover - environment problem, not logic
    # Say what is missing and how to fix it. A stack trace here tells the author
    # nothing they can act on, and this tool asks Claude to do better than that.
    raise ImportError(
        "latex-editor needs pylatexenc to read LaTeX. Install it with:\n"
        "    pip install pylatexenc\n"
        "Inside the dev container it is already present; on a bare host it is not."
    ) from exc

# --------------------------------------------------------------------------
# Classification tables
# --------------------------------------------------------------------------

#: Environments Claude owns outright.  Their bodies never contribute prose --
#: only a \caption inside them does.
CLAUDE_ENVS = {
    # maths
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "flalign", "flalign*",
    "eqnarray", "eqnarray*", "split", "cases", "dcases", "array",
    "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
    "smallmatrix", "displaymath", "math", "IEEEeqnarray", "subequations",
    # floats and their contents
    "table", "table*", "tabular", "tabular*", "tabularx", "tabulary",
    "longtable", "longtabu", "threeparttable", "booktabs", "subtable",
    "figure", "figure*", "subfigure", "subfloat", "wrapfigure", "SCfigure",
    # algorithms
    "algorithm", "algorithm*", "algorithmic", "algorithmique", "algorithm2e",
    "lstlisting", "verbatim", "Verbatim", "minted", "listing", "semiverbatim",
    # graphics
    "tikzpicture", "pgfpicture", "axis", "semilogxaxis", "semilogyaxis",
    "loglogaxis", "groupplot", "circuitikz", "forest", "adjustbox",
}

#: Macros that contribute nothing at all -- neither the macro nor its
#: arguments are the author's words.
SKIP_MACROS = {
    # citations
    "cite", "citep", "citet", "citep*", "citet*", "citealp", "citealt",
    "citeauthor", "citeyear", "citeyearpar", "citenum", "fullcite",
    "parencite", "textcite", "autocite", "footcite", "supercite", "nocite",
    # cross references
    "ref", "eqref", "pageref", "autoref", "cref", "Cref", "crefrange",
    "Crefrange", "nameref", "vref", "labelcref", "label",
    # glossaries / acronyms / nomenclature
    "gls", "Gls", "glspl", "Glspl", "glsdisp", "acrshort", "acrlong",
    "acrfull", "acs", "acl", "acf", "ac", "nomenclature", "newacronym",
    "newglossaryentry", "printglossary", "printglossaries", "printnomenclature",
    "makenomenclature", "glsaddall",
    # units and numbers (siunitx)
    "SI", "si", "num", "qty", "unit", "numlist", "SIrange", "qtyrange",
    "ang", "numrange", "SIlist", "qtylist",
    # file inclusion and graphics
    "input", "include", "subfile", "includegraphics", "includepdf",
    "lstinputlisting", "inputminted", "bibliography", "bibliographystyle",
    "addbibresource", "graphicspath",
    # layout and structure with no authored text
    "maketitle", "tableofcontents", "listoffigures", "listoftables",
    "clearpage", "cleardoublepage", "newpage", "pagebreak", "linebreak",
    "newline", "noindent", "indent", "centering", "raggedright", "raggedleft",
    "par", "vspace", "hspace", "vfill", "hfill", "bigskip", "medskip",
    "smallskip", "hrule", "hline", "toprule", "midrule", "bottomrule",
    "cmidrule", "multicolumn", "multirow", "rowcolor", "columnwidth",
    "linewidth", "textwidth", "arraystretch", "setlength", "addtolength",
    "footnotesize", "small", "normalsize", "large", "Large", "huge", "Huge",
    "tiny", "scriptsize", "bfseries", "itshape", "rmfamily", "sffamily",
    "ttfamily", "appendix", "frontmatter", "mainmatter", "backmatter",
}

#: Macros whose argument *is* the author's text.  Unknown macros are treated
#: this way too, so a custom wrapper never silently opens a hole.
PROSE_ARG_MACROS = {
    "section", "subsection", "subsubsection", "paragraph", "subparagraph",
    "chapter", "part", "title", "subtitle", "caption", "captionof",
    "subcaption", "footnote", "footnotetext", "emph", "textbf", "textit",
    "textrm", "textsf", "texttt", "textsc", "textsl", "underline", "uline",
    "text", "mbox", "textnormal", "textsuperscript", "textsubscript",
    "enquote", "quote", "so", "highlight",
}

#: Macros carrying a caption -- collected as prose only when captions belong to
#: the author (the default).
CAPTION_MACROS = {"caption", "captionof", "subcaption"}

#: \% \& \_ \# \$ \{ \} \textbackslash -- escaped literals that read as text.
LITERAL_MACROS = {"%", "&", "_", "#", "$", "{", "}", "textbackslash", "ldots", "dots"}

#: Specials that are spacing or alignment rather than words.  Claude may adjust
#: these (Fig.~\ref{} is a typography fix, not an authorial one).
SKIP_SPECIALS = {"~", "&", "\\\\"}

#: Authored content that lives in the preamble rather than the body.
PREAMBLE_PROSE_MACROS = {
    "title", "subtitle", "shorttitle", "author", "thanks", "keywords",
    "abstract", "affiliation", "institute", "dedication",
}

#: Environments that hold author prose even though they are "structural".
_ALWAYS_PROSE_ENVS = {
    "document", "abstract", "itemize", "enumerate", "description", "list",
    "quote", "quotation", "verse", "center", "flushleft", "flushright",
    "minipage", "columns", "multicols", "frame", "theorem", "lemma", "proof",
    "definition", "remark", "corollary", "proposition", "example",
}

_WORD_SPLIT = re.compile(r"\s+")


class Token(NamedTuple):
    """One author word, with enough position information to report on it."""

    text: str
    pos: int
    line: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.text!r}@L{self.line}"


#: Stands in for a construct that was elided from the prose (a citation, a
#: reference, an equation).  Canonicalisation folds it away together with the
#: whitespace around it, so inserting \cite{} mid-sentence does not disturb the
#: author's text while deleting a real space still does.
GAP = "\x00"

_GAP_RUN = re.compile(r"[ \t\r\n]*\x00[ \t\r\n]*")
_WHITESPACE_RUN = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?)\]}])")


def canonical(segments: Iterable[str]) -> str:
    """Render collected prose segments into a comparable string."""
    text = "".join(segments)
    text = _GAP_RUN.sub(" ", text)
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return text.strip()


class ProseStream(NamedTuple):
    """The result of classifying one LaTeX source."""

    prose: list[Token]
    other: list[str]
    parse_ok: bool
    text: str = ""
    spans: tuple[tuple[int, int], ...] = ()

    @property
    def words(self) -> list[str]:
        return [t.text for t in self.prose]


# --------------------------------------------------------------------------
# Parsing context
# --------------------------------------------------------------------------

def _build_context():
    """Default macro database plus specs for the macros we must see arguments of.

    pylatexenc does not know the argument structure of \\caption, \\gls, \\SI and
    friends; without a spec their braces are parsed as loose groups and would be
    misclassified.
    """
    db = get_default_latex_context_db()
    specs = [
        MacroSpec("caption", "[{"),
        MacroSpec("captionof", "{{"),
        MacroSpec("subcaption", "[{"),
        MacroSpec("gls", "{"), MacroSpec("Gls", "{"),
        MacroSpec("glspl", "{"), MacroSpec("Glspl", "{"),
        MacroSpec("acrshort", "{"), MacroSpec("acrlong", "{"),
        MacroSpec("acrfull", "{"), MacroSpec("ac", "{"),
        MacroSpec("acs", "{"), MacroSpec("acl", "{"), MacroSpec("acf", "{"),
        MacroSpec("newacronym", "[{{{"),
        MacroSpec("newglossaryentry", "{{"),
        MacroSpec("nomenclature", "[{{"),
        MacroSpec("SI", "[{{"), MacroSpec("si", "[{"),
        MacroSpec("num", "[{"), MacroSpec("qty", "[{{"),
        MacroSpec("unit", "[{"), MacroSpec("ang", "[{"),
        MacroSpec("SIrange", "[{{{"), MacroSpec("qtyrange", "[{{{"),
        MacroSpec("paragraph", "*[{"), MacroSpec("subparagraph", "*[{"),
        MacroSpec("href", "{{"), MacroSpec("url", "{"),
        MacroSpec("textsuperscript", "{"), MacroSpec("textsubscript", "{"),
        MacroSpec("subfile", "{"), MacroSpec("includepdf", "[{"),
        MacroSpec("lstinputlisting", "[{"),
        MacroSpec("addbibresource", "{"), MacroSpec("graphicspath", "{"),
        MacroSpec("multicolumn", "{{{"), MacroSpec("multirow", "{{{"),
        MacroSpec("vspace", "*{"), MacroSpec("hspace", "*{"),
        MacroSpec("setlength", "{{"), MacroSpec("addtolength", "{{"),
        MacroSpec("enquote", "{"), MacroSpec("uline", "{"),
        MacroSpec("cmidrule", "[{"),
        # Skipped macros still need a spec, or their bracketed options are
        # parsed as loose text and counted as the author's words.
        MacroSpec("printglossary", "["),
        MacroSpec("printglossaries", "["),
        MacroSpec("printnomenclature", "["),
        MacroSpec("bibliography", "{"),
        MacroSpec("bibliographystyle", "{"),
        MacroSpec("glsaddall", "["),
        MacroSpec("tableofcontents", ""),
        MacroSpec("listoffigures", ""),
        MacroSpec("listoftables", ""),
        MacroSpec("maketitle", ""),
    ]
    db.add_context_category("latex-editor", macros=specs, prepend=True)
    return db


_CONTEXT = _build_context()


def _line_index(text: str) -> list[int]:
    """Offsets at which each line starts, for turning positions into line numbers."""
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return offsets


def _line_of(offsets: list[int], pos: int) -> int:
    lo, hi = 0, len(offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if offsets[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


# --------------------------------------------------------------------------
# The traversal
# --------------------------------------------------------------------------

class _Collector:
    def __init__(self, text: str, captions_are_prose: bool = True):
        self.text = text
        self.captions_are_prose = captions_are_prose
        self.offsets = _line_index(text)
        self.prose: list[Token] = []
        self.other: list[str] = []
        self.segments: list[str] = []
        self.spans: list[tuple[int, int]] = []

    # -- emitters ---------------------------------------------------------
    def _emit(self, chunk: str, pos: int, prose: bool) -> None:
        """Split a verbatim source chunk into words, keeping exact positions."""
        if prose:
            self.segments.append(chunk)
            self.spans.append((pos, len(chunk)))
        for match in re.finditer(r"\S+", chunk):
            at = pos + match.start()
            if prose:
                self.prose.append(Token(match.group(), at, _line_of(self.offsets, at)))
            else:
                self.other.append(match.group())

    def _gap(self, prose: bool) -> None:
        """Note that something Claude owns stood here."""
        if prose:
            self.segments.append(GAP)

    # -- dispatch ---------------------------------------------------------
    def walk(self, nodes: Iterable, prose: bool) -> None:
        for node in nodes or ():
            if node is not None:
                self.visit(node, prose)

    def visit(self, node, prose: bool) -> None:
        if isinstance(node, LatexCharsNode):
            self._emit(node.chars, node.pos, prose)

        elif isinstance(node, LatexCommentNode):
            # Comments never reach the reader, so Claude may write them freely.
            self._emit(node.comment, node.pos, False)

        elif isinstance(node, LatexMathNode):
            self._gap(prose)
            self.walk(node.nodelist, False)

        elif isinstance(node, LatexGroupNode):
            self.walk(node.nodelist, prose)

        elif isinstance(node, LatexSpecialsNode):
            if node.specials_chars in SKIP_SPECIALS:
                self._gap(prose)
            else:
                self._emit(node.specials_chars, node.pos, prose)

        elif isinstance(node, LatexEnvironmentNode):
            self.visit_environment(node, prose)

        elif isinstance(node, LatexMacroNode):
            self.visit_macro(node, prose)

        else:  # pragma: no cover - defensive
            self.walk(getattr(node, "nodelist", None), prose)

    def visit_environment(self, node, prose: bool) -> None:
        # \begin{tabular}{lll} -- an environment's own arguments are structure.
        self.walk(_args_of(node), False)
        body_is_prose = prose and node.environmentname not in CLAUDE_ENVS
        if prose and not body_is_prose:
            self._gap(prose)
        self.walk(node.nodelist, body_is_prose)

    def visit_macro(self, node, prose: bool) -> None:
        name = node.macroname
        args = _args_of(node)

        # A caption is the author's sentence wherever it appears -- including
        # inside a float whose body belongs to Claude.
        if name in CAPTION_MACROS:
            self.walk(args, self.captions_are_prose)
            return

        if name in LITERAL_MACROS:
            self._emit("\\" + name, node.pos, prose)
            self.walk(args, prose)
            return

        # \\, \, and other non-alphabetic control sequences are spacing.
        if name in SKIP_MACROS or not name or not name[0].isalpha():
            self._gap(prose)
            self.walk(args, False)
            return

        # Known text-wrapping macros, and unknown macros too: assume what they
        # wrap is the author's until we learn otherwise, so a custom command
        # never silently opens a hole.
        self.walk(args, prose)


def _args_of(node) -> list:
    argd = getattr(node, "nodeargd", None)
    if argd is None or not getattr(argd, "argnlist", None):
        return []
    return [a for a in argd.argnlist if a is not None]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def classify(text: str, captions_are_prose: bool = True) -> ProseStream:
    """Split a LaTeX source into author prose tokens and everything else."""
    collector = _Collector(text, captions_are_prose)
    parse_ok = True
    try:
        walker = LatexWalker(text, latex_context=_CONTEXT, tolerant_parsing=True)
        nodes, _, _ = walker.get_latex_nodes(pos=0)
    except Exception:
        # A file too broken even for tolerant parsing: report it rather than
        # guessing.  Callers fail closed.
        return ProseStream([], [], False, "", ())

    body = _document_body(nodes)
    if body is None:
        # A section file: everything in it is body text.
        collector.walk(nodes, True)
    else:
        # One pass in source order, so reported positions read top to bottom.
        for node in nodes:
            if node is body:
                collector.walk(_args_of(body), False)
                collector.walk(body.nodelist, True)
            else:
                _collect_preamble(collector, node)
    return ProseStream(
        collector.prose,
        collector.other,
        parse_ok,
        canonical(collector.segments),
        tuple(collector.spans),
    )


def _collect_preamble(collector: "_Collector", node) -> None:
    """The preamble is Claude's, apart from \\title, \\author and friends."""
    if isinstance(node, LatexMacroNode) and node.macroname in PREAMBLE_PROSE_MACROS:
        collector.walk(_args_of(node), True)
        return
    if isinstance(node, LatexEnvironmentNode) and node.environmentname == "abstract":
        collector.walk(node.nodelist, True)
        return
    collector.visit(node, False)


def _document_body(nodes):
    """The `document` environment, if this source has one (a master file)."""
    for node in nodes or ():
        if isinstance(node, LatexEnvironmentNode) and node.environmentname == "document":
            return node
    return None


def prose_words(text: str, captions_are_prose: bool = True) -> list[str]:
    """Just the author's words, in order."""
    return classify(text, captions_are_prose).words


def read_prose(path: str, captions_are_prose: bool = True) -> ProseStream:
    with open(path, "r", encoding="utf-8") as handle:
        return classify(handle.read(), captions_are_prose)


# --------------------------------------------------------------------------
# Comparing two versions of a file
# --------------------------------------------------------------------------

class Verdict(NamedTuple):
    """Whether an edit left the author's words alone."""

    allowed: bool
    reason: str
    added: list[str]
    removed: list[str]


def _is_subsequence(small: list[str], large: list[str]) -> bool:
    it = iter(large)
    return all(token in it for token in small)


def _counts(items: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return out


def compare(before: str, after: str, captions_are_prose: bool = True) -> Verdict:
    """Decide whether an edit is allowed to land.

    The rule is simple: the author's word stream must come out identical.  The
    one exception is a *repair* -- fixing an unclosed environment un-hides prose
    the broken markup had swallowed, which adds words to the stream without
    anybody having typed them.  That is permitted only when every recovered word
    was already sitting in the old file's non-prose regions, and only when
    nothing is lost.  Prose can never disappear.
    """
    old = classify(before, captions_are_prose)
    new = classify(after, captions_are_prose)

    if not new.parse_ok:
        return Verdict(False, "the resulting file could not be parsed as LaTeX", [], [])

    if old.text == new.text:
        return Verdict(True, "author prose unchanged", [], [])

    old_words, new_words = old.text.split(), new.text.split()

    added = _diff_extra(new_words, old_words)
    removed = _diff_extra(old_words, new_words)

    if not removed and _is_subsequence(old_words, new_words):
        available = _counts(old.other)
        if all(available.get(word, 0) >= count for word, count in _counts(added).items()):
            return Verdict(
                True,
                "prose recovered from markup that was swallowing it (syntax repair)",
                added,
                removed,
            )

    if not added and not removed:
        return Verdict(False, "author prose reordered", added, removed)
    return Verdict(False, "author prose changed", added, removed)


def _diff_extra(primary: list[str], secondary: list[str]) -> list[str]:
    """Words in `primary` that `secondary` does not account for, keeping order."""
    remaining = _counts(secondary)
    extra = []
    for word in primary:
        if remaining.get(word, 0) > 0:
            remaining[word] -= 1
        else:
            extra.append(word)
    return extra
