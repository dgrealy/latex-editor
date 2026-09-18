FROM mcr.microsoft.com/devcontainers/base:bookworm

# TeX Live: a scientific-article subset rather than the 5 GB full install.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-science \
        texlive-fonts-recommended \
        texlive-bibtex-extra \
        texlive-pictures \
        latexmk \
        biber \
        chktex \
        latexindent \
        hunspell hunspell-en-gb \
        python3 python3-pip \
        ghostscript poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# The prose guard's dependencies. It fails closed, so these are not optional.
RUN pip3 install --no-cache-dir --break-system-packages pylatexenc PyYAML pytest

# Claude Code itself.
RUN su vscode -c "npm install -g @anthropic-ai/claude-code"
