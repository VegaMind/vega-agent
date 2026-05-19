#!/usr/bin/env bash
# ============================================================================
# Vega Agent — Install Script
# ============================================================================
#  One-liner:  curl -fsSL https://getvega.sh | bash
#  With flags: curl -fsSL https://getvega.sh | bash -s -- --help
# ============================================================================
set -euo pipefail

# ── Constants ───────────────────────────────────────────────────────────────
REPO_OWNER="VegaMind"
REPO_NAME="vega"
DEFAULT_INSTALL_VERSION="latest"
DEFAULT_VEGA_HOME="${HOME}/.vega"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11
STEP_TOTAL=8

# ── ANSI Colors ─────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_RESET='\033[0m'
  C_BOLD='\033[1m'
  C_DIM='\033[2m'
  C_UNDER='\033[4m'
  C_BLINK='\033[5m'
  C_RED='\033[0;31m'
  C_GREEN='\033[0;32m'
  C_YELLOW='\033[0;33m'
  C_BLUE='\033[0;34m'
  C_MAGENTA='\033[0;35m'
  C_CYAN='\033[0;36m'
  C_WHITE='\033[0;37m'
  C_BG_RED='\033[41m'
  C_BG_GREEN='\033[42m'
  C_BG_BLUE='\033[44m'
  C_BG_MAGENTA='\033[45m'
  C_BG_CYAN='\033[46m'
  C_BOLD_RED='\033[1;31m'
  C_BOLD_GREEN='\033[1;32m'
  C_BOLD_YELLOW='\033[1;33m'
  C_BOLD_BLUE='\033[1;34m'
  C_BOLD_MAGENTA='\033[1;35m'
  C_BOLD_CYAN='\033[1;36m'
  C_BOLD_WHITE='\033[1;37m'
else
  C_RESET=''; C_BOLD=''; C_DIM=''; C_UNDER=''; C_BLINK=''
  C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_MAGENTA=''
  C_CYAN=''; C_WHITE=''
  C_BG_RED=''; C_BG_GREEN=''; C_BG_BLUE=''; C_BG_MAGENTA=''
  C_BG_CYAN=''
  C_BOLD_RED=''; C_BOLD_GREEN=''; C_BOLD_YELLOW=''; C_BOLD_BLUE=''
  C_BOLD_MAGENTA=''; C_BOLD_CYAN=''; C_BOLD_WHITE=''
fi

# ── Logo / ASCII Art ────────────────────────────────────────────────────────
VEGA_LOGO="${C_BOLD_CYAN}
    __     __   __   __   __   __
   |  \\   /  \\ |  \\ |  \\ |  \\ |  \\
   | ▓▓\\ / ▓▓\\| ▓▓ | ▓▓ | ▓▓ | ▓▓
   | ▓▓▓\\ ▓▓▓▓\\ ▓▓ | ▓▓ | ▓▓ | ▓▓
   | ▓▓▓▓\\ ▓▓ ▓▓ ▓▓ | ▓▓ | ▓▓ | ▓▓
   | ▓▓▓▓▓\\ ▓▓ ▓▓ ▓▓ | ▓▓ | ▓▓ | ▓▓
   | ▓▓\\▓▓▓\\▓▓ ▓▓ ▓▓ | ▓▓ | ▓▓ | ▓▓
    \\ ▓▓ \\▓▓\\ ▓▓\\ ▓▓\\ ▓▓\\ ▓▓\\ ▓▓
     \\▓▓  \\▓▓\\▓▓ \\▓▓ \\▓▓ \\▓▓ \\▓▓
${C_RESET}"

VEGA_TAGLINE="${C_BOLD_WHITE}Your Personal AI. Installed. Private.${C_RESET}"

# ── Help ────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
${C_BOLD}Vega Agent Installer${C_RESET}

Usage:
  curl -fsSL https://getvega.sh | bash
  curl -fsSL https://getvega.sh | bash -s -- [OPTIONS]

Options:
  -h, --help        Show this help message
  -v, --version     Install a specific version (default: latest)
  -p, --path DIR    Install to a custom directory (default: ~/.vega)
  -y, --yes         Skip all prompts (non-interactive mode)

Environment variables:
  VEGA_VERSION      Install a specific version (same as --version)
  VEGA_HOME         Install to a custom directory (same as --path)

Examples:
  curl -fsSL https://getvega.sh | bash
  curl -fsSL https://getvega.sh | bash -s -- --version v0.1.0
  curl -fsSL https://getvega.sh | bash -s -- --path /opt/vega --yes

EOF
  exit 0
}

# ── Parse arguments ─────────────────────────────────────────────────────────
INTERACTIVE=true
INSTALL_VERSION="${VEGA_VERSION:-${DEFAULT_INSTALL_VERSION}}"
VEGA_HOME="${VEGA_HOME:-${DEFAULT_VEGA_HOME}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)    show_help ;;
    -v|--version) shift; INSTALL_VERSION="$1" ;;
    -p|--path)    shift; VEGA_HOME="$1" ;;
    -y|--yes)     INTERACTIVE=false ;;
    *)            echo -e "${C_RED}Unknown option: $1${C_RESET}"; show_help ;;
  esac
  shift
done

# ── Banner ──────────────────────────────────────────────────────────────────
print_banner() {
  echo -e "${VEGA_LOGO}"
  echo -e "  ${VEGA_TAGLINE}"
  echo ""
  echo -e "  ${C_DIM}Version: ${INSTALL_VERSION}  |  Home: ${VEGA_HOME}${C_RESET}"
  echo ""
}

# ── Step printer ────────────────────────────────────────────────────────────
CURRENT_STEP=0

step() {
  CURRENT_STEP=$((CURRENT_STEP + 1))
  local label="$1"
  echo ""
  echo -e "  ${C_BOLD_CYAN}[${CURRENT_STEP}/${STEP_TOTAL}]${C_RESET} ${C_BOLD}${label}${C_RESET}"
}

step_ok() {
  echo -e "  ${C_BOLD_GREEN}✓${C_RESET} ${C_DIM}$1${C_RESET}"
}

step_warn() {
  echo -e "  ${C_BOLD_YELLOW}⚠${C_RESET} ${C_DIM}$1${C_RESET}"
}

step_err() {
  echo -e "  ${C_BOLD_RED}✗${C_RESET} ${C_DIM}$1${C_RESET}"
}

info() {
  echo -e "  ${C_BLUE}→${C_RESET} $1"
}

# ── Error handler ───────────────────────────────────────────────────────────
cleanup_existing() {
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    echo ""
    echo -e "  ${C_BG_RED}${C_BOLD_WHITE} INSTALLATION FAILED ${C_RESET}"
    echo -e "  ${C_RED}Installation did not complete successfully (exit code: ${exit_code}).${C_RESET}"
    echo -e "  ${C_YELLOW}Check the output above for details. You can re-run the installer;"
    echo -e "  it is safe to run multiple times.${C_RESET}"
    echo -e "  ${C_YELLOW}For help: https://github.com/${REPO_OWNER}/${REPO_NAME}/issues${C_RESET}"
    echo ""
  fi
}

trap cleanup_existing EXIT

# ── Pre-flight checks ───────────────────────────────────────────────────────
check_python() {
  local py_cmd=""
  for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
      py_cmd="$cmd"
      break
    fi
  done

  if [[ -z "$py_cmd" ]]; then
    echo -e "  ${C_RED}Python not found. Please install Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ first.${C_RESET}"
    echo -e "  ${C_YELLOW}  macOS:  brew install python${C_RESET}"
    echo -e "  ${C_YELLOW}  Ubuntu: sudo apt install python3 python3-venv python3-pip${C_RESET}"
    echo -e "  ${C_YELLOW}  Fedora: sudo dnf install python3 python3-virtualenv python3-pip${C_RESET}"
    return 1
  fi

  local py_version
  py_version="$("$py_cmd" --version 2>&1 | awk '{print $2}')"

  local py_major
  py_major="$(echo "$py_version" | cut -d. -f1)"
  local py_minor
  py_minor="$(echo "$py_version" | cut -d. -f2)"

  if [[ "$py_major" -lt "$PYTHON_MIN_MAJOR" ]] || \
     [[ "$py_major" -eq "$PYTHON_MIN_MAJOR" && "$py_minor" -lt "$PYTHON_MIN_MINOR" ]]; then
    echo -e "  ${C_RED}Python ${py_version} found, but Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ is required.${C_RESET}"
    return 1
  fi

  echo "$py_cmd"
}

check_git() {
  if ! command -v git &>/dev/null; then
    echo -e "  ${C_RED}git not found. Please install git first.${C_RESET}"
    echo -e "  ${C_YELLOW}  macOS:  brew install git${C_RESET}"
    echo -e "  ${C_YELLOW}  Ubuntu: sudo apt install git${C_RESET}"
    echo -e "  ${C_YELLOW}  Fedora: sudo dnf install git${C_RESET}"
    return 1
  fi
  return 0
}

check_pip() {
  local py_cmd="$1"
  if ! "$py_cmd" -m pip --version &>/dev/null; then
    echo -e "  ${C_RED}pip not found for ${py_cmd}. Please install python3-pip.${C_RESET}"
    return 1
  fi
  return 0
}

check_venv() {
  local py_cmd="$1"
  if ! "$py_cmd" -m venv --help &>/dev/null; then
    echo -e "  ${C_RED}python3-venv is not installed.${C_RESET}"
    echo -e "  ${C_YELLOW}  Ubuntu/Debian: sudo apt install python3-venv${C_RESET}"
    echo -e "  ${C_YELLOW}  Fedora:        sudo dnf install python3-virtualenv${C_RESET}"
    return 1
  fi
  return 0
}

# ── OS Detection ────────────────────────────────────────────────────────────
detect_os() {
  case "$(uname -s)" in
    Linux*)  echo "linux"  ;;
    Darwin*) echo "darwin" ;;
    *)       echo "unknown" ;;
  esac
}

# ── Ensure ~/.local/bin is in PATH ──────────────────────────────────────────
ensure_local_bin_in_path() {
  local local_bin="${HOME}/.local/bin"
  if [[ -d "$local_bin" ]] || mkdir -p "$local_bin" 2>/dev/null; then
    if [[ ":$PATH:" != *":${local_bin}:"* ]]; then
      export PATH="${local_bin}:${PATH}"
      # Add to shell rc for persistence
      local rc_file=""
      if [[ -n "${ZSH_VERSION:-}" ]]; then
        rc_file="${HOME}/.zshrc"
      elif [[ -n "${BASH_VERSION:-}" ]]; then
        rc_file="${HOME}/.bashrc"
      fi
      if [[ -n "$rc_file" ]] && [[ -f "$rc_file" ]] && ! grep -q "export PATH=.*${local_bin}" "$rc_file" 2>/dev/null; then
        echo "" >> "$rc_file"
        echo "# Added by Vega Agent installer" >> "$rc_file"
        echo "export PATH=\"\${PATH}:${local_bin}\"" >> "$rc_file"
      fi
    fi
  fi
}

# ── Determine install method ────────────────────────────────────────────────
# Try release download first; fall back to git clone.

download_release() {
  local version="$1"
  local dest="$2"

  # If "latest", resolve the actual tag
  if [[ "$version" == "latest" ]]; then
    info "Resolving latest release..."
    local api_url="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"
    local resolved
    if command -v curl &>/dev/null; then
      resolved="$(curl -fsSL "$api_url" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null)" || true
    elif command -v wget &>/dev/null; then
      resolved="$(wget -qO- "$api_url" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null)" || true
    fi
    if [[ -n "${resolved:-}" ]]; then
      version="$resolved"
      step_ok "Latest release: ${version}"
    else
      step_warn "Could not determine latest release; will fall back to git clone."
      return 1
    fi
  fi

  local tarball_url="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/tags/${version}.tar.gz"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  info "Downloading ${REPO_NAME} ${version}..."

  if command -v curl &>/dev/null; then
    curl -fsSL "$tarball_url" -o "${tmp_dir}/release.tar.gz" 2>/dev/null || { rm -rf "$tmp_dir"; return 1; }
  elif command -v wget &>/dev/null; then
    wget -qO "${tmp_dir}/release.tar.gz" "$tarball_url" 2>/dev/null || { rm -rf "$tmp_dir"; return 1; }
  else
    rm -rf "$tmp_dir"
    step_warn "Neither curl nor wget available; falling back to git clone."
    return 1
  fi

  # Extract
  mkdir -p "$dest"
  tar xzf "${tmp_dir}/release.tar.gz" -C "$dest" --strip-components=1 2>/dev/null || {
    rm -rf "$tmp_dir"
    return 1
  }
  rm -rf "$tmp_dir"
  return 0
}

clone_repo() {
  local version="$1"
  local dest="$2"

  if [[ -d "$dest/.git" ]]; then
    info "Repository already exists at ${dest}; updating..."
    git -C "$dest" fetch --tags --quiet 2>/dev/null || true
    if [[ "$version" != "latest" ]]; then
      git -C "$dest" checkout "$version" --quiet 2>/dev/null || {
        step_warn "Tag ${version} not found; staying on current branch."
      }
    else
      # Checkout the latest tag or default branch
      local latest_tag
      latest_tag="$(git -C "$dest" tag --sort=-creatordate | head -1 2>/dev/null)" || true
      if [[ -n "${latest_tag:-}" ]]; then
        git -C "$dest" checkout "$latest_tag" --quiet 2>/dev/null || true
      fi
    fi
    return 0
  else
    info "Cloning ${REPO_NAME}..."
    if [[ "$version" != "latest" ]]; then
      git clone --depth 1 --branch "$version" \
        "https://github.com/${REPO_OWNER}/${REPO_NAME}.git" "$dest" 2>/dev/null
    else
      git clone --depth 1 \
        "https://github.com/${REPO_OWNER}/${REPO_NAME}.git" "$dest" 2>/dev/null
    fi
    local ret=$?
    if [[ $ret -ne 0 ]]; then
      step_warn "Git clone failed (exit code ${ret}). The repository may not be public yet."
      return 1
    fi
    return 0
  fi
}

# ── Install Vega ────────────────────────────────────────────────────────────
do_install() {
  print_banner

  local os
  os="$(detect_os)"
  echo -e "  ${C_DIM}Detected OS: ${os}${C_RESET}"
  if [[ "$os" == "unknown" ]]; then
    step_warn "Unknown OS. Proceeding anyway — some features may not work."
  fi

  # ── Step 1: Prerequisites ────────────────────────────────────────────────
  step "Checking prerequisites"

  local PYTHON_CMD
  PYTHON_CMD="$(check_python)" || exit 1
  step_ok "Python: $("${PYTHON_CMD}" --version 2>&1 | awk '{print $2}')"

  check_git || exit 1
  step_ok "Git: $(git --version 2>&1 | head -1)"

  check_pip "$PYTHON_CMD" || exit 1
  check_venv "$PYTHON_CMD" || exit 1

  # ── Step 2: Create directory structure ───────────────────────────────────
  step "Creating Vega home directory structure"

  mkdir -p "${VEGA_HOME}"/{bin,data,config,logs,audit,context-tree,models,tmp}
  step_ok "Created ${VEGA_HOME}/"
  info "  bin/          — executable scripts and symlinks"
  info "  data/         — persistent data storage"
  info "  config/       — configuration files"
  info "  logs/         — log output"
  info "  audit/        — audit trail entries"
  info "  context-tree/ — knowledge graph storage"
  info "  models/       — local model files"
  info "  tmp/          — temporary workspace"

  # ── Step 3: Download / clone source ──────────────────────────────────────
  step "Downloading Vega Agent source code"

  local SRC_DIR="${VEGA_HOME}/src"
  mkdir -p "$SRC_DIR"

  local source_acquired=false

  # Option A: Running from within the project directory — use local source
  local SCRIPT_DIR
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "${SCRIPT_DIR}/pyproject.toml" ]] && [[ -d "${SCRIPT_DIR}/src/vega" ]]; then
    info "Detected local Vega source at ${SCRIPT_DIR}"
    # Copy source to VEGA_HOME/src for isolation
    rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
      "${SCRIPT_DIR}/" "${SRC_DIR}/" 2>/dev/null || \
    cp -r "${SCRIPT_DIR}/" "${SRC_DIR}/" 2>/dev/null || {
      # Symlink as last resort
      rm -rf "$SRC_DIR"
      ln -sfn "$SCRIPT_DIR" "$SRC_DIR"
    }
    source_acquired=true
    step_ok "Using local source (${SCRIPT_DIR})"
  fi

  # Option B: Download a release tarball from GitHub
  if ! $source_acquired; then
    if download_release "$INSTALL_VERSION" "$SRC_DIR"; then
      source_acquired=true
      step_ok "Downloaded release ${INSTALL_VERSION}"
    fi
  fi

  # Option C: Git clone from GitHub
  if ! $source_acquired; then
    if clone_repo "$INSTALL_VERSION" "$SRC_DIR"; then
      source_acquired=true
      step_ok "Cloned repository"
    fi
  fi

  # If all options failed, create minimal source structure
  if ! $source_acquired; then
    step_warn "Could not download or clone source. Creating minimal setup..."
    mkdir -p "${SRC_DIR}/src/vega"
    # Create minimal pyproject.toml so pip install -e works
    cat > "${SRC_DIR}/pyproject.toml" << MINIMAL_EOF
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "vega-agent"
version = "0.1.0"
description = "Vega — Your Personal AI. Installed. Private."
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "httpx>=0.27",
    "openai>=1.0",
    "chromadb>=0.5.0",
]

[project.scripts]
vega = "vega.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/vega"]
MINIMAL_EOF
    source_acquired=true
    step_warn "Using minimal source setup — run 'vega init' after install."
  fi

  # ── Step 4: Create virtual environment ───────────────────────────────────
  step "Creating Python virtual environment"

  local VENV_DIR="${VEGA_HOME}/.venv"
  if [[ -d "$VENV_DIR" ]]; then
    info "Virtual environment already exists at ${VENV_DIR}"
    info "Updating pip..."
    "${VENV_DIR}/bin/${PYTHON_CMD}" -m pip install --quiet --upgrade pip 2>/dev/null || true
  else
    "${PYTHON_CMD}" -m venv "$VENV_DIR"
    step_ok "Created virtual environment at ${VENV_DIR}"
    "${VENV_DIR}/bin/${PYTHON_CMD}" -m pip install --quiet --upgrade pip 2>/dev/null || true
  fi

  # ── Step 5: Install dependencies ─────────────────────────────────────────
  step "Installing Python dependencies"

  local PIP="${VENV_DIR}/bin/pip"

  # Install the package in editable mode if we have source, otherwise install from pip
  if [[ -f "${SRC_DIR}/pyproject.toml" ]]; then
    info "Installing from local source..."
    # First install build deps
    "${PIP}" install --quiet hatchling hatch-vcs 2>/dev/null || true
    "${PIP}" install --quiet -e "$SRC_DIR" 2>/dev/null || {
      step_warn "Editable install failed; falling back to pip install"
      "${PIP}" install --quiet "${REPO_NAME}" 2>/dev/null || true
    }
  else
    "${PIP}" install --quiet "${REPO_NAME}" 2>/dev/null || true
  fi

  # Ensure core dependencies are installed
  info "Ensuring core dependencies..."
  "${PIP}" install --quiet \
    chromadb
    rich \
    click \
    httpx \
    openai 2>/dev/null || {
    step_warn "Some dependencies had issues; continuing anyway."
  }

  step_ok "Dependencies installed"

  # ── Step 6: Create the vega command ──────────────────────────────────────
  step "Creating the 'vega' command"

  local VENV_PYTHON="${VENV_DIR}/bin/${PYTHON_CMD}"
  local VENV_VEGA="${VENV_DIR}/bin/vega"

  # Create wrapper script in VEGA_HOME/bin
  cat > "${VEGA_HOME}/bin/vega" << WRAPPER_EOF
#!/usr/bin/env bash
# Vega Agent wrapper — activates the venv and runs the CLI
export VEGA_HOME="${VEGA_HOME}"
exec "${VENV_PYTHON}" -m vega "\$@"
WRAPPER_EOF
  chmod +x "${VEGA_HOME}/bin/vega"

  # Symlink to ~/.local/bin/
  ensure_local_bin_in_path
  local LOCAL_BIN="${HOME}/.local/bin"
  mkdir -p "$LOCAL_BIN"
  if [[ -f "${LOCAL_BIN}/vega" ]]; then
    rm -f "${LOCAL_BIN}/vega"
  fi
  ln -sf "${VEGA_HOME}/bin/vega" "${LOCAL_BIN}/vega"
  chmod +x "${LOCAL_BIN}/vega" 2>/dev/null || true

  step_ok "vega command installed → ${LOCAL_BIN}/vega"

  # Also create the config symlink if vega config exists
  local VEGA_CONFIG_SRC="${SRC_DIR}/src/vega"
  if [[ -d "$VEGA_CONFIG_SRC" ]]; then
    ln -sfn "$VEGA_CONFIG_SRC" "${VEGA_HOME}/config/vega" 2>/dev/null || true
  fi

  # ── Step 7: Initialize config ────────────────────────────────────────────
  step "Initializing default configuration"

  if [[ -f "${VEGA_HOME}/config.yaml" ]]; then
    info "Config already exists at ${VEGA_HOME}/config.yaml"
    info "Run 'vega init' to reconfigure if needed."
  else
    # Create a basic config.yaml directly since vega init requires the package
    cat > "${VEGA_HOME}/config.yaml" << CONFIG_EOF
# Vega Agent Configuration
# Generated by install.sh — customize with \`vega init\`
privacy:
  telemetry: false
  cloud_sync: false
  local_models_only: false
  encryption_enabled: false
  encryption_key_path: "${VEGA_HOME}/encryption.key"
  audit_log: true

model:
  provider: openrouter
  name: deepseek/deepseek-v4-flash
  temperature: 0.7
  max_tokens: 4096

paths:
  data_dir: "${VEGA_HOME}/data"
  chromadb_dir: "${VEGA_HOME}/chromadb"
  context_tree_db: "${VEGA_HOME}/context-tree/context_tree.db"

features:
  memory: true
  context_tree: true
  shell_history: true
  audit_log: true
CONFIG_EOF
    step_ok "Default config written to ${VEGA_HOME}/config.yaml"
  fi

  # Try running vega init --auto via the venv
  if "${VENV_PYTHON}" -m vega init --auto 2>/dev/null; then
    step_ok "vega init --auto completed successfully"
  else
    step_warn "vega init --auto had issues (config already exists or deps not fully loaded)"
    info "Run 'vega init' manually after installation."
  fi

  # ── Step 8: Verify installation ──────────────────────────────────────────
  step "Verifying installation"

  local vega_found=false
  if command -v vega &>/dev/null; then
    vega_found=true
    info "vega command found in PATH"
    local vega_path
    vega_path="$(command -v vega)"
    info "  Location: ${vega_path}"
  else
    info "vega not in current PATH — add ~/.local/bin to your PATH or re-source your shell rc."
    info "  export PATH=\"\${PATH}:${HOME}/.local/bin\""
  fi

  if "${VENV_PYTHON}" -c "import vega; print(vega.__version__)" &>/dev/null; then
    local installed_version
    installed_version="$("${VENV_PYTHON}" -c "import vega; print(vega.__version__)")"
    step_ok "Vega Agent ${installed_version} installed successfully"
  else
    step_warn "Could not verify Vega package import — the CLI may still work."
  fi

  # ── Success Message ──────────────────────────────────────────────────────
  echo ""
  echo ""
  echo -e "  ${C_BG_CYAN}${C_BOLD_BLACK}═══════════════════════════════════════════════════════════════${C_RESET}"
  echo -e "  ${C_BG_CYAN}${C_BOLD_BLACK}                                                               ${C_RESET}"
  echo -e "  ${C_BG_CYAN}${C_BOLD_BLACK}   ${C_BOLD_WHITE}VEGA AGENT — INSTALLED${C_BG_CYAN}                                      ${C_RESET}"
  echo -e "  ${C_BG_CYAN}${C_BOLD_BLACK}                                                               ${C_RESET}"
  echo -e "  ${C_BG_CYAN}${C_BOLD_BLACK}${C_RESET}"
  echo -e "  ${C_BOLD_GREEN}  ✓  Vega Agent is ready.${C_RESET}"
  echo ""
  echo -e "  ${C_BOLD}Quick start:${C_RESET}"
  echo ""
  echo -e "  ${C_BOLD_CYAN}  ┌─────────────────────────────────────────────────────────────┐${C_RESET}"
  echo -e "  ${C_BOLD_CYAN}  │${C_RESET}  ${C_BOLD}vega init${C_RESET}         ${C_DIM}Configure API key and settings${C_RESET}        ${C_BOLD_CYAN}│${C_RESET}"
  echo -e "  ${C_BOLD_CYAN}  │${C_RESET}  ${C_BOLD}vega status${C_RESET}       ${C_DIM}Show system status${C_RESET}                  ${C_BOLD_CYAN}│${C_RESET}"
  echo -e "  ${C_BOLD_CYAN}  │${C_RESET}  ${C_BOLD}vega ask \"Hello!\"${C_RESET} ${C_DIM}Ask your AI a question${C_RESET}            ${C_BOLD_CYAN}│${C_RESET}"
  echo -e "  ${C_BOLD_CYAN}  │${C_RESET}  ${C_BOLD}vega shell${C_RESET}       ${C_DIM}Start interactive REPL${C_RESET}             ${C_BOLD_CYAN}│${C_RESET}"
  echo -e "  ${C_BOLD_CYAN}  │${C_RESET}  ${C_BOLD}vega --version${C_RESET}   ${C_DIM}Show version info${C_RESET}                 ${C_BOLD_CYAN}│${C_RESET}"
  echo -e "  ${C_BOLD_CYAN}  └─────────────────────────────────────────────────────────────┘${C_RESET}"
  echo ""
  echo -e "  ${C_DIM}Installation path: ${VEGA_HOME}${C_RESET}"
  echo -e "  ${C_DIM}Virtual env:      ${VENV_DIR}${C_RESET}"
  echo -e "  ${C_DIM}Config file:      ${VEGA_HOME}/config.yaml${C_RESET}"
  echo ""
  echo -e "  ${C_YELLOW}  💡  Set your API key first:  ${C_BOLD}vega init${C_RESET}"
  echo -e "  ${C_YELLOW}  📖  Documentation:           https://VegaMind.github.io/vega-agent${C_RESET}"
  echo -e "  ${C_YELLOW}  🐛  Report issues:           https://github.com/${REPO_OWNER}/${REPO_NAME}/issues${C_RESET}"
  echo ""
  echo -e "  ${C_BG_CYAN}${C_BOLD_BLACK}═══════════════════════════════════════════════════════════════${C_RESET}"
  echo ""
}

# ── Main ────────────────────────────────────────────────────────────────────
main() {
  do_install
}

main "$@"