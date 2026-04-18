echo "创建启动器： $WRAPPER_PATH"
#!/usr/bin/env bash
set -euo pipefail



PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
WRAPPER_NAME="hsharp"
LOCAL_BIN="$HOME/.local/bin"

usage(){
  cat <<EOF
Usage: $0 [--venv DIR] [--system] [--with-pyinstaller] [--target-bin PATH] [--install-python] [--auto]

Options:
  --venv DIR         虚拟环境目录（默认: ./.venv）
  --system           不创建虚拟环境，直接使用系统 python 安装依赖
  --with-pyinstaller 安装 PyInstaller（用于构建独立二进制）
  --target-bin PATH  将启动器安装到指定路径（默认: /usr/local/bin，否则 $LOCAL_BIN）
  --with-pyqt        安装 PyQt（一键安装，优先使用 pip，失败后尝试 Homebrew）
  --pyqt-version V   指定 PyQt 版本（例如: 5.15.7），与 --with-pyqt 一起使用
  --install-python   如果系统无 python3，使用 Homebrew 安装 Python3（会提示）
  --auto             无提示自动安装（非交互式，谨慎使用）
  -h, --help         显示本帮助
EOF
}

# defaults
WITH_PYINSTALLER=0
USE_SYSTEM=0
TARGET_BIN="/usr/local/bin"
INSTALL_PYTHON=0
AUTO=0
WITH_PYQT=0
PYQT_VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV_DIR="$2"; shift 2;;
    --with-pyinstaller) WITH_PYINSTALLER=1; shift;;
    --with-pyqt) WITH_PYQT=1; shift;;
    --pyqt-version) PYQT_VERSION="$2"; shift 2;;
    --system) USE_SYSTEM=1; shift;;
    --target-bin) TARGET_BIN="$2"; shift 2;;
    --install-python) INSTALL_PYTHON=1; shift;;
    --auto) AUTO=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

echo "项目目录: $PROJECT_DIR"

ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

# Optionally install Python via Homebrew (macOS)
if [[ $INSTALL_PYTHON -eq 1 ]]; then
  if ensure_command python3; then
    echo "已检测到 python3，跳过安装。"
  else
    if [[ "$(uname)" != "Darwin" ]]; then
      echo "自动安装 Python 仅在 macOS 上支持，请手动安装 python3。" >&2
      exit 2
    fi

    if ! ensure_command brew; then
      if [[ $AUTO -eq 1 ]]; then
        echo "自动安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      else
        read -p "未检测到 Homebrew，是否现在安装 Homebrew? [y/N] " ans
        if [[ "$ans" =~ ^[Yy]$ ]]; then
          /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        else
          echo "请先安装 Homebrew 或手动安装 Python3。" >&2
          exit 3
        fi
      fi
    fi

    echo "使用 Homebrew 安装 python..."
    if [[ $AUTO -eq 1 ]]; then
      brew install python
    else
      read -p "About to run: brew install python  (press Enter to continue)" _
      brew install python
    fi

    # ensure brew prefix is in PATH for current shell
    if ensure_command brew; then
      BREW_PREFIX=$(brew --prefix)
      if [[ -d "$BREW_PREFIX/bin" && ":$PATH:" != *":$BREW_PREFIX/bin:"* ]]; then
        echo "将 Homebrew bin 添加到 PATH 临时会话中: $BREW_PREFIX/bin"
        export PATH="$BREW_PREFIX/bin:$PATH"
        # also suggest adding to shell rc
        SHELL_RC="$HOME/.zshrc"
        if [[ -n "$SHELL" && "$SHELL" == */bash ]]; then SHELL_RC="$HOME/.bash_profile"; fi
        if ! grep -q "export PATH=\"$BREW_PREFIX/bin:\$PATH\"" "$SHELL_RC" 2>/dev/null; then
          echo "建议将 Homebrew 路径加入 $SHELL_RC："
          echo "  echo 'export PATH=\"$BREW_PREFIX/bin:\$PATH\"' >> $SHELL_RC"
        fi
      fi
    fi
  fi
fi

# choose python executable
PY=python3
if ! ensure_command "$PY"; then
  echo "未找到 python3。请使用 --install-python 或手动安装 Python3。" >&2
  exit 4
fi

if [[ "$USE_SYSTEM" -eq 0 ]]; then
  echo "创建/使用虚拟环境： $VENV_DIR"
  "$PY" -m venv "$VENV_DIR"
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip setuptools wheel
else
  echo "使用系统 Python 安装依赖（不会创建虚拟环境）"
fi

# Install project (prefer installing the package if packaging metadata exists)
if [[ -f "$PROJECT_DIR/setup.py" || -f "$PROJECT_DIR/pyproject.toml" ]]; then
  echo "检测到 packaging 元数据，使用 pip 安装项目（可编辑安装）..."
  # prefer editable install during development; production can omit -e
  pip install --upgrade "$PROJECT_DIR" || pip install --upgrade -e "$PROJECT_DIR"
else
  if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
    echo "安装 requirements.txt 中列出的依赖..."
    pip install -r "$PROJECT_DIR/requirements.txt"
  else
    echo "未检测到 requirements.txt，至少尝试安装 PyQt5（如果需要 GUI）"
    pip install PyQt5 || true
  fi
fi

if [[ "$WITH_PYINSTALLER" -eq 1 ]]; then
  echo "安装 PyInstaller..."
  pip install pyinstaller
fi

# one-click PyQt install (pip preferred; fallback to Homebrew on macOS)
if [[ "$WITH_PYQT" -eq 1 ]]; then
  echo "准备安装 PyQt..."
  if [[ -n "$PYQT_VERSION" ]]; then
    PKG="PyQt5==$PYQT_VERSION"
  else
    PKG="PyQt5"
  fi
  echo "尝试使用 pip 安装 $PKG ..."
  if pip install --upgrade "$PKG"; then
    echo "PyQt 已通过 pip 安装。"
  else
    echo "pip 安装失败，尝试在 macOS 上使用 Homebrew 安装 pyqt（如果可用）..."
    if [[ "$(uname)" == "Darwin" && $(command -v brew || true) ]]; then
      echo "使用 Homebrew 安装 pyqt..."
      brew install pyqt || echo "Homebrew 安装失败，请手动处理 PyQt 安装。"
    else
      echo "无法通过 Homebrew 自动安装（非 macOS 或未安装 brew）。请手动安装 PyQt。"
    fi
  fi
fi

# choose target bin
if [[ -w /usr/local/bin ]]; then
  :
else
  # if cannot write to /usr/local/bin, fallback to $HOME/.local/bin
  if [[ ! -d "$LOCAL_BIN" ]]; then
    mkdir -p "$LOCAL_BIN"
  fi
  if [[ -w "$LOCAL_BIN" || ! -e /usr/local/bin ]]; then
    echo "/usr/local/bin 无写权限，安装到 $LOCAL_BIN"
    TARGET_BIN="$LOCAL_BIN"
  fi
fi

WRAPPER_PATH="$TARGET_BIN/$WRAPPER_NAME"

# create wrapper script
echo "创建启动器： $WRAPPER_PATH"
mkdir -p "$(dirname "$WRAPPER_PATH")"
cat > "$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
# H# 启动器，执行项目中的 hsharp.py（位于 $PROJECT_DIR）
VENV="$VENV_DIR"
PROJECT="$PROJECT_DIR"
if [[ -d "${VENV}" && -x "${VENV}/bin/python" ]]; then
  exec "${VENV}/bin/python" "${PROJECT}/hsharp.py" "$@"
else
  # fallback to system python
  exec python3 "${PROJECT}/hsharp.py" "$@"
fi
EOF

chmod +x "$WRAPPER_PATH"

echo "安装完成。"
if [[ "$TARGET_BIN" == "$LOCAL_BIN" ]]; then
  echo "请将 $LOCAL_BIN 添加到 PATH，例如："
  echo "  echo 'export PATH=\$HOME/.local/bin:\$PATH' >> \$HOME/.zshrc"
fi

echo "示例：运行 hsharp CLI"
echo "  $WRAPPER_NAME --help"

exit 0
