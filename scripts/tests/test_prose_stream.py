"""The guard is only as trustworthy as these tests.

Each case is phrased as a question about one edit: would this change what a
reader sees?  If not, Claude may make it; if so, only the author may.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prose_stream import canonical, classify, compare  # noqa: E402

DOC = r"""\documentclass{article}
\usepackage{amsmath}
\title{A Study of Cooling}
\begin{document}
\maketitle
The reactor was cooled rapidly \cite{smith2019}.
It reached \SI{4}{\kelvin}, as shown in Fig.~\ref{fig:rate}.
\begin{equation}\label{eq:heat}
  \frac{\partial T}{\partial t} = \alpha \nabla^2 T
\end{equation}
\begin{figure}
  \includegraphics[width=\columnwidth]{figures/out/rate.pdf}
  \caption{Cooling rate over time.}
  \label{fig:rate}
\end{figure}
\section{Methods}
This was \emph{important} work.
% Claude note: consider citing Jones here
\end{document}
"""


def allows(before, after):
    return compare(before, after).allowed


def swap(original, new):
    assert original in DOC, f"fixture drift: {original!r} not in DOC"
    return DOC.replace(original, new)


# ---------------------------------------------------------------- classification


def test_body_prose_is_collected():
    words = classify(DOC).words
    assert "reactor" in words and "rapidly" in words


def test_title_is_the_authors_even_though_it_sits_in_the_preamble():
    assert "Study" in classify(DOC).words


def test_claude_owned_material_is_not_prose():
    words = classify(DOC).words
    for owned in ["smith2019", "fig:rate", "eq:heat", r"\alpha", "amsmath", "article"]:
        assert owned not in words


def test_captions_belong_to_the_author_by_default():
    assert "over" in classify(DOC).words  # from "Cooling rate over time."


def test_captions_can_be_handed_to_claude():
    assert "over" not in classify(DOC, captions_are_prose=False).words


def test_comments_are_claudes():
    assert "Jones" not in classify(DOC).words


def test_table_internals_are_claudes():
    table = r"""\begin{document}
\begin{table}\begin{tabular}{lr}
Method & Rate \\ Ours & 3.1
\end{tabular}\caption{Results.}\end{table}
\end{document}"""
    words = classify(table).words
    assert "Method" not in words and "Ours" not in words
    assert "Results." in words


def test_section_file_without_a_document_environment_is_all_body():
    assert "Standalone" in classify("Standalone section text here.\n").words


def test_canonical_folds_gaps_and_whitespace():
    assert canonical(["The  end", "\x00", " ."]) == "The end."


# ---------------------------------------------------------------- allowed edits


@pytest.mark.parametrize(
    "before, after",
    [
        pytest.param("rapidly \\cite{smith2019}.", "rapidly \\cite{smith2019,jones2020}.", id="extra-citation-key"),
        pytest.param("This was \\emph{important} work.", "This was \\emph{important} work~\\cite{a}.", id="citation-before-period"),
        pytest.param("\\section{Methods}", "\\section{Methods}\\label{sec:methods}", id="add-label"),
        pytest.param("This was", "This\\cite{a} was", id="citation-mid-sentence"),
    ],
)
def test_claude_may_add_markup(before, after):
    assert allows(DOC, swap(before, after))


def test_claude_may_add_an_equation():
    assert allows(DOC, swap("\\section{Methods}", "\\begin{align}a &= b\\end{align}\n\\section{Methods}"))


def test_claude_may_add_a_comment():
    assert allows(DOC, swap("\\section{Methods}", "% a note for the author\n\\section{Methods}"))


def test_claude_may_add_a_table():
    table = "\\begin{table}\\begin{tabular}{ll}a & b\\end{tabular}\\caption{}\\end{table}\n"
    assert allows(DOC, swap("\\section{Methods}", table + "\\section{Methods}"))


def test_claude_may_load_a_package():
    assert allows(DOC, swap("\\usepackage{amsmath}", "\\usepackage{amsmath}\n\\usepackage{siunitx}"))


def test_claude_may_reflow_a_paragraph():
    assert allows(DOC, swap("This was \\emph{important} work.", "This was\n\\emph{important}\nwork."))


def test_claude_may_reindent():
    assert allows(DOC, swap("  \\caption{Cooling rate over time.}", "\t\\caption{Cooling rate over time.}"))


def test_claude_may_fill_an_empty_caption_placeholder_only_when_captions_are_its_own():
    before = DOC.replace("\\caption{Cooling rate over time.}", "\\caption{}")
    after = DOC
    assert not compare(before, after).allowed
    assert compare(before, after, captions_are_prose=False).allowed


# ---------------------------------------------------------------- denied edits


@pytest.mark.parametrize(
    "before, after, note",
    [
        ("cooled rapidly", "cooled very rapidly", "added a word"),
        ("The reactor was cooled", "The reactor cooled", "deleted a word"),
        ("rapidly \\cite", "quickly \\cite", "reworded"),
        ("was cooled", "wascooled", "merged two words"),
        ("\\section{Methods}", "\\section{Methodology}", "reworded a heading"),
        ("\\caption{Cooling rate over time.}", "\\caption{Cooling rate against time.}", "reworded a caption"),
        ("\\title{A Study of Cooling}", "\\title{A Study of Rapid Cooling}", "reworded the title"),
    ],
)
def test_claude_may_not_touch_the_authors_words(before, after, note):
    assert not allows(DOC, swap(before, after)), note


def test_reordering_sentences_is_refused():
    one = "The reactor was cooled rapidly \\cite{smith2019}.\nIt reached \\SI{4}{\\kelvin}, as shown in Fig.~\\ref{fig:rate}."
    two = "It reached \\SI{4}{\\kelvin}, as shown in Fig.~\\ref{fig:rate}.\nThe reactor was cooled rapidly \\cite{smith2019}."
    verdict = compare(DOC, swap(one, two))
    assert not verdict.allowed
    assert "reorder" in verdict.reason


def test_moving_prose_into_a_comment_is_refused():
    assert not allows(DOC, swap("This was \\emph{important} work.", "% This was \\emph{important} work."))


def test_unparseable_result_is_refused():
    assert not allows(DOC, "\\begin{document}\n\\begin{" + "\x00" * 3)


# ---------------------------------------------------------------- syntax repair

BROKEN = """\\begin{document}
First sentence here.
\\begin{equation}
E = mc^2
Second sentence here.
\\end{document}
"""
FIXED = """\\begin{document}
First sentence here.
\\begin{equation}
E = mc^2
\\end{equation}
Second sentence here.
\\end{document}
"""


def test_repairing_markup_may_recover_swallowed_prose():
    verdict = compare(BROKEN, FIXED)
    assert verdict.allowed and "repair" in verdict.reason


def test_a_repair_may_not_smuggle_in_new_words():
    sneaky = FIXED.replace("Second sentence here.", "Second sentence here, obviously.")
    assert not allows(BROKEN, sneaky)


def test_a_repair_may_not_lose_prose():
    lossy = FIXED.replace("First sentence here.\n", "")
    assert not allows(BROKEN, lossy)


# ---------------------------------------------------------------- reflow

def test_reflow_splits_sentences_without_touching_words():
    from reflow import reflow_text

    source = "\\begin{document}\nOne sentence. Another sentence. A third.\n\\end{document}"
    out = reflow_text(source)
    assert "One sentence.\nAnother sentence.\nA third." in out
    assert compare(source, out).allowed


@pytest.mark.parametrize(
    "sentence",
    [
        "We follow Smith et al. here.",
        "See Fig. 3 for this.",
        "That is, i.e. the usual way.",
        "J. Smith measured it.",
        "The value was 3.1 exactly.",
    ],
)
def test_reflow_leaves_abbreviations_alone(sentence):
    from reflow import reflow_text

    source = f"\\begin{{document}}\n{sentence}\n\\end{{document}}"
    assert reflow_text(source) == source


def test_reflow_splits_after_a_trailing_macro():
    from reflow import reflow_text

    source = "\\begin{document}\nAs shown \\cite{a}. The next point follows.\n\\end{document}"
    assert "\\cite{a}.\nThe next point" in reflow_text(source)


def test_reflow_does_not_touch_claude_owned_environments():
    from reflow import reflow_text

    source = "\\begin{document}\n\\begin{equation}a = b. c = d.\\end{equation}\n\\end{document}"
    assert reflow_text(source) == source


# ---------------------------------------------------------------- the template

def test_the_shipped_template_starts_with_no_author_words():
    """A fresh main.tex must count as empty, or every word count is skewed."""
    template = Path(__file__).resolve().parents[2] / "templates" / "article" / "main.tex"
    assert classify(template.read_text(encoding="utf-8")).words == []


# ---------------------------------------------------------------- suggestions

def test_a_suggestion_comment_does_not_disturb_the_prose():
    """Inline suggestions rely on this: a comment is invisible to the stream."""
    after = DOC.replace(
        "This was \\emph{important} work.",
        "% SUGGEST: name the technique here. [see review]\nThis was \\emph{important} work.",
    )
    assert compare(DOC, after).allowed


def test_clearing_suggestions_round_trips():
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    import suggestions

    annotated = DOC.replace(
        "\\section{Methods}", "% SUGGEST: tighten this heading.\n\\section{Methods}"
    )
    assert compare(DOC, annotated).allowed
    kept = [
        line
        for line in annotated.splitlines(keepends=True)
        if not suggestions._SUGGESTION.match(line.rstrip("\n"))
    ]
    assert "".join(kept) == DOC


def test_suggestion_pattern_ignores_ordinary_comments_and_escaped_percent():
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    import suggestions

    assert suggestions._SUGGESTION.match("% SUGGEST: do this")
    assert suggestions._SUGGESTION.match("  %% SUGGEST:   spaced out")
    assert not suggestions._SUGGESTION.match("% an ordinary note")
    assert not suggestions._SUGGESTION.match("The value was 50\\% SUGGEST: not a comment")
