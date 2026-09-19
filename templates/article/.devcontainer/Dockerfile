FROM node:20

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Install basic development tools and iptables/ipset
RUN apt-get update && apt-get install -y --no-install-recommends \
  less \
  git \
  procps \
  sudo \
  fzf \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  nano \
  vim \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# LaTeX toolchain.
#
# This layer is large and slow and almost never changes, so it sits high in the
# file: everything below it rebuilds far more often, and Docker caches by layer.
#
# The container's sudo is restricted to the firewall script, so a package that is
# missing here cannot be installed at runtime. That is deliberate -- the build
# environment stays a file in git rather than undocumented state on your laptop --
# but it means installing generously. If a document needs something that isn't
# here, add it to this list and rebuild the container.
#
# texlive-publishers carries elsarticle, IEEEtran and the Springer classes.
# texlive-xetex/luatex make the `engine` setting in .latex-editor.yml real.
# texlive-font-utils provides epstopdf, for the `eps` figure format.
# poppler-utils provides pdftoppm, for rendering a page to an image.
# texlive-extra-utils provides latexindent (there is no standalone package for
#   it) and latexpand, which the submission packager will want for flattening.
# latexdiff marks up changes between two revisions -- for supervisors and for
#   journal revision rounds. Installed now because sudo is locked down later.
# ---------------------------------------------------------------------------
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  texlive-latex-recommended \
  texlive-latex-extra \
  texlive-science \
  texlive-fonts-recommended \
  texlive-fonts-extra \
  texlive-bibtex-extra \
  texlive-pictures \
  texlive-publishers \
  texlive-xetex \
  texlive-luatex \
  texlive-font-utils \
  texlive-plain-generic \
  latexmk \
  biber \
  chktex \
  texlive-extra-utils \
  latexdiff \
  hunspell \
  hunspell-en-gb \
  python3 \
  python3-pip \
  ghostscript \
  poppler-utils \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# The prose guard's dependencies. PyPI is not on the firewall allowlist, so these
# cannot be installed once the container is running -- they must be baked in here,
# while the build still has unrestricted network.
# (Debian bookworm marks its Python as externally managed, hence the flag.)
RUN pip3 install --no-cache-dir --break-system-packages pylatexenc PyYAML pytest

# Fail the build loudly rather than at 11pm on the first edit: the prose guard
# fails closed, so a container without pylatexenc refuses every .tex edit.
RUN python3 -c "import pylatexenc, yaml" \
  && latexmk --version >/dev/null \
  && biber --version >/dev/null \
  && for tool in chktex latexindent latexdiff epstopdf pdftoppm hunspell; do \
       command -v "$tool" >/dev/null || { echo "missing tool: $tool"; exit 1; }; \
     done \
  && echo "toolchain verified"

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Persist bash history.
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R $USERNAME /commandhistory

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

# Create workspace and config directories and set permissions
RUN mkdir -p /workspace /home/node/.claude && \
  chown -R node:node /workspace /home/node/.claude

WORKDIR /workspace

ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  wget "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  sudo dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

# Set up non-root user
USER node

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# Set the default shell to zsh rather than sh
ENV SHELL=/bin/zsh

# Set the default editor and visual
ENV EDITOR=nano
ENV VISUAL=nano

# Default powerline10k theme
ARG ZSH_IN_DOCKER_VERSION=1.2.0
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
  -p git \
  -p fzf \
  -a "source /usr/share/doc/fzf/examples/key-bindings.zsh" \
  -a "source /usr/share/doc/fzf/examples/completion.zsh" \
  -a "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  -x

# Install Claude. Kept last: CLAUDE_CODE_VERSION=latest invalidates this layer on
# every rebuild, and anything below it would be rebuilt along with it.
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}


# Copy and set up firewall script
COPY init-firewall.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh && \
  echo "node ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/node-firewall && \
  chmod 0440 /etc/sudoers.d/node-firewall
USER node
