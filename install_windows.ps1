
param(
    [string]$VenvDir = ".\.venv",
    [switch]$UseSystem,
    [switch]$WithPyInstaller,
    [switch]$WithPyQt,
    [string]$PyQtVersion = "",
    [switch]$InstallPython,
    [switch]$Auto,
    [string]$TargetBin = "$env:USERPROFILE\\bin"
)

function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-ErrorExit($m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 1 }

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Info "项目目录: $projectDir"

# check python
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python3 -ErrorAction SilentlyContinue }

if (-not $pyCmd) {
    if ($InstallPython) {
        Write-Info "未检测到 python，准备通过 Chocolatey 安装（需要已安装 choco）"
        $choco = Get-Command choco -ErrorAction SilentlyContinue
        if (-not $choco) {
            if ($Auto) {
                Write-ErrorExit "自动安装 Chocolatey 未实现，请先手动安装 Chocolatey 或 python。"
            } else {
                $yn = Read-Host "未检测到 Chocolatey。是否现在打开 https://chocolatey.org/install 并手动安装？ (Y/n)"
                if ($yn -ne 'Y' -and $yn -ne 'y' -and $yn -ne '') { Write-ErrorExit "需要 Chocolatey 才能自动安装 Python。" }
                Write-Host "请按照页面说明安装 Chocolatey 后再次运行脚本。"; exit 1
            }
        }
        Write-Info "使用 choco 安装 python..."
        choco install python -y
        $pyCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pyCmd) { Write-ErrorExit "安装后仍无法找到 python，请检查 Chocolatey 安装日志。" }
    } else {
        Write-ErrorExit "未检测到 python，请使用 -InstallPython 或手动安装 Python。"
    }
}

# choose python exe path
$pythonExe = $pyCmd.Path
Write-Info "使用 Python: $pythonExe"

# create virtualenv (unless UseSystem)
if (-not $UseSystem) {
    Write-Info "创建虚拟环境: $VenvDir"
    & "$pythonExe" -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-ErrorExit "创建 venv 失败" }
    $venvPython = Join-Path (Resolve-Path $VenvDir) "Scripts\\python.exe"
} else {
    Write-Info "使用系统 Python，不创建虚拟环境"
    $venvPython = $pythonExe
}

# upgrade pip
Write-Info "升级 pip"
& "$venvPython" -m pip install --upgrade pip setuptools wheel

# install requirements or default PyQt
$reqFile = Join-Path $projectDir "requirements.txt"
if (Test-Path $reqFile) {
    Write-Info "安装 requirements.txt 中的依赖"
    & "$venvPython" -m pip install -r $reqFile
} else {
    Write-Info "未找到 requirements.txt"
    if ($WithPyQt) {
        if ($PyQtVersion) { $pkg = "PyQt5==$PyQtVersion" } else { $pkg = "PyQt5" }
        Write-Info "尝试用 pip 安装 $pkg"
        if (& "$venvPython" -m pip install --upgrade $pkg) { Write-Info "PyQt 安装成功（pip）" } else {
            Write-Host "pip 安装 PyQt 失败，建议手动安装 Qt 或使用官方二进制。" -ForegroundColor Yellow
        }
    }
}

if ($WithPyInstaller) {
    Write-Info "安装 PyInstaller"
    & "$venvPython" -m pip install pyinstaller
}

# create target bin dir and wrapper
if (-not (Test-Path $TargetBin)) { New-Item -ItemType Directory -Path $TargetBin -Force | Out-Null }
$wrapperPath = Join-Path $TargetBin "hsharp.bat"
$absProject = (Resolve-Path $projectDir).Path
$absVenv = (Resolve-Path $VenvDir).Path
$pythonInVenv = Join-Path $absVenv "Scripts\\python.exe"

$launcherContent = "@echo off`n"
if (-not $UseSystem) {
    $launcherContent += "\"$pythonInVenv\" \"$absProject\\hsharp.py\" %*\n"
} else {
    $launcherContent += "python \"$absProject\\hsharp.py\" %*\n"
}

Set-Content -Path $wrapperPath -Value $launcherContent -Encoding ASCII
Write-Info "创建启动器: $wrapperPath"

Write-Host "安装完成。请将 $TargetBin 添加到 PATH（用户环境变量），例如:" -ForegroundColor Green
Write-Host "  setx PATH \"%PATH%;$TargetBin\"" -ForegroundColor Green
Write-Host "然后在新终端中运行: hsharp --help"

Write-Host "注意: 如果你需要 GUI 功能，请确保 PyQt 与 Qt 运行时正确安装并测试 GUI 程序。" -ForegroundColor Yellow

exit 0
