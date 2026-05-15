# Dulus one-liner installer — Windows.
#
#   iwr -useb https://raw.githubusercontent.com/KevRojo/Dulus/main/install.ps1 | iex
#
# Flags (PowerShell-native — pass them like normal):
#   .\install.ps1 -DryRun
#   .\install.ps1 -Profile full
#   .\install.ps1 -Profile standard -Pre
#   .\install.ps1 -NoDeps
#   .\install.ps1 -Installer pipx
#
# When piped via iex, you can preset with $env:DULUS_PROFILE / $env:DULUS_INSTALLER:
#   $env:DULUS_PROFILE='full'; iwr -useb ...install.ps1 | iex
#
# Idempotent — re-running upgrades Dulus to the latest version and leaves
# already-installed system packages alone.

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoDeps,
    [switch]$Pre,
    [ValidateSet('full','standard','basic','custom','')]
    [string]$Profile = '',
    [ValidateSet('uv','pipx','pip','')]
    [string]$Installer = ''
)

# Env-var fallbacks so `iwr | iex` users can still pick a profile.
if ([string]::IsNullOrEmpty($Profile))   { $Profile   = $env:DULUS_PROFILE }
if ([string]::IsNullOrEmpty($Installer)) { $Installer = $env:DULUS_INSTALLER }

$ErrorActionPreference = 'Stop'

# ── Colors / helpers ─────────────────────────────────────────────────────────
function Say   ($t) { Write-Host $t -ForegroundColor Cyan }
function OK    ($t) { Write-Host "[OK] $t" -ForegroundColor Green }
function Warn  ($t) { Write-Host "[!] $t" -ForegroundColor Yellow }
function Err   ($t) { Write-Host "[x] $t" -ForegroundColor Red }
function Header($t) {
    Write-Host ""
    Write-Host $t -ForegroundColor Cyan
    Write-Host ("-" * 60) -ForegroundColor DarkGray
}

function Invoke-Step {
    param([string]$Cmd)
    Write-Host "$ $Cmd" -ForegroundColor DarkGray
    if (-not $DryRun) {
        Invoke-Expression $Cmd
    }
}

# ── Banner ───────────────────────────────────────────────────────────────────
@'

  > DULUS - installer
  Multi-provider AI CLI . The bird, not the rocket

'@ | Write-Host -ForegroundColor Cyan

if ($DryRun) { Warn "Dry run mode - nothing will actually be installed." }

# ═══════════════════════════════════════════════════════════════════════════
# 1. ENVIRONMENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════
Header "1. Detecting your environment"

# OS / version
$osVersion = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
if (-not $osVersion) { $osVersion = "Windows ($env:PROCESSOR_ARCHITECTURE)" }
Write-Host "  OS:        " -NoNewline; Write-Host $osVersion -ForegroundColor White

# Architecture
$arch = $env:PROCESSOR_ARCHITECTURE
Write-Host "  Arch:      " -NoNewline; Write-Host $arch -ForegroundColor White

# Are we elevated? (some installs need admin)
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')
Write-Host "  Elevated:  " -NoNewline
if ($isAdmin) { Write-Host "yes" -ForegroundColor Green }
else          { Write-Host "no (some installs may prompt UAC)" -ForegroundColor Yellow }

# Package manager (winget > scoop > choco)
$pkgMgr = $null
if (Get-Command winget -ErrorAction SilentlyContinue) {
    $pkgMgr = 'winget'
} elseif (Get-Command scoop  -ErrorAction SilentlyContinue) {
    $pkgMgr = 'scoop'
} elseif (Get-Command choco  -ErrorAction SilentlyContinue) {
    $pkgMgr = 'choco'
}
Write-Host "  Pkg mgr:   " -NoNewline
if ($pkgMgr) { Write-Host $pkgMgr -ForegroundColor White }
else { Write-Host "none (winget/scoop/choco not detected)" -ForegroundColor Yellow }

# Python ≥3.11 — probe the common interpreter names. We avoid argument
# splatting (incompat between PowerShell 5.1 and 7+) and instead just call
# each candidate directly with a single -c string.
$pyBin = $null
$pyVer = $null
# PowerShell + native-command quoting quirk: a single-quoted string with
# embedded double quotes gets mangled when passed via `&`, leaving Python
# with an empty argv. Using double quotes outside + single quotes inside
# is the form that round-trips cleanly through both PS 5.1 and PS 7+.
$probeScript = "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))"
foreach ($cand in @('python3.13','python3.12','python3.11','python','py')) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        try {
            if ($cand -eq 'py') {
                $v = & $cand -3 -c $probeScript 2>$null
            } else {
                $v = & $cand -c $probeScript 2>$null
            }
            if ($v -and $v -match '^(\d+)\.(\d+)') {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -eq 3 -and $minor -ge 11) {
                    $pyBin = $cand
                    $pyVer = ($v | Out-String).Trim()
                    break
                }
            }
        } catch { }
    }
}

if (-not $pyBin) {
    Err "No Python 3.11+ found on PATH."
    if ($pkgMgr -eq 'winget') {
        Say "  Install with: winget install -e --id Python.Python.3.13"
    } elseif ($pkgMgr -eq 'scoop') {
        Say "  Install with: scoop install python"
    } elseif ($pkgMgr -eq 'choco') {
        Say "  Install with: choco install -y python313"
    } else {
        Say "  Download from https://www.python.org/downloads/"
    }
    exit 1
}
Write-Host "  Python:    " -NoNewline; Write-Host "$pyBin ($pyVer)" -ForegroundColor White

# Python installer (uv > pipx > pip)
if (-not $Installer) {
    if     (Get-Command uv   -ErrorAction SilentlyContinue) { $Installer = 'uv' }
    elseif (Get-Command pipx -ErrorAction SilentlyContinue) { $Installer = 'pipx' }
    else                                                    { $Installer = 'pip' }
}
Write-Host "  Installer: " -NoNewline; Write-Host $Installer -ForegroundColor White

# Tmux probe (optional — used by /bg start)
$haveTmux = [bool](Get-Command tmux -ErrorAction SilentlyContinue)
if ($haveTmux) {
    Write-Host "  Tmux:      installed" -ForegroundColor White
}

# ═══════════════════════════════════════════════════════════════════════════
# 2. PROFILE PICKER
# ═══════════════════════════════════════════════════════════════════════════
Header "2. Pick an install profile"

@"

  1) full      - everything. Voice (Whisper+sounddevice), browser tools (Playwright),
                 MemPalace semantic memory, tmux. Heaviest install. ~1.5 GB.
                 Best for daily-driver setups.

  2) standard  - REPL + webchat + tmux daemon + Telegram bridge.
                 Skips voice, browser automation, semantic memory.
                 ~300 MB. The "I just want to chat" sweet spot.

  3) basic     - bare pip install dulus. No system deps installed.
                 ~150 MB. For minimal sandboxes / scripted environments.

  4) custom    - toggle each feature one by one.

"@ | Write-Host

if ($Profile) {
    OK "Profile preselected: $Profile"
} else {
    # When run via `iwr | iex` we have an interactive console; Read-Host works.
    $choice = Read-Host "Pick 1-4 [default: 1]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = '1' }
    switch ($choice) {
        '1'        { $Profile = 'full' }
        'full'     { $Profile = 'full' }
        '2'        { $Profile = 'standard' }
        'standard' { $Profile = 'standard' }
        '3'        { $Profile = 'basic' }
        'basic'    { $Profile = 'basic' }
        '4'        { $Profile = 'custom' }
        'custom'   { $Profile = 'custom' }
        default    { Err "Invalid choice - aborting."; exit 1 }
    }
}

# Profile → feature flags
$wantVoice     = $false
$wantTmux      = $false
$wantWebbridge = $false
$wantMempalace = $false

switch ($Profile) {
    'full'     { $wantVoice = $true; $wantTmux = $true; $wantWebbridge = $true; $wantMempalace = $true }
    'standard' { $wantTmux = $true }
    'basic'    { }
    'custom'   {
        function Ask($q,$def) {
            $r = Read-Host "  $q [Y/n]"
            if ([string]::IsNullOrWhiteSpace($r)) { $r = $def }
            return $r -match '^[Yy]'
        }
        if (Ask "Voice input (Whisper + sounddevice)?" 'Y') { $wantVoice = $true }
        if (Ask "Tmux for /bg start daemon?"            'Y') { $wantTmux = $true }
        if (Ask "Browser automation (Playwright)?"      'N') { $wantWebbridge = $true }
        if (Ask "Semantic memory (MemPalace)?"          'Y') { $wantMempalace = $true }
    }
}
OK "Profile: $Profile"

# ═══════════════════════════════════════════════════════════════════════════
# 3. COMPUTE NEEDED PACKAGES (winget/scoop/choco)
# ═══════════════════════════════════════════════════════════════════════════
$neededPkgs = @()

function PkgInstalled-Winget($id) {
    $r = winget list --id $id --exact --accept-source-agreements 2>$null | Out-String
    return $r -match $id
}
function PkgInstalled-Scoop($id)  {
    $r = scoop list 2>$null | Out-String
    return $r -match "(?im)^\s*${id}\s"
}
function PkgInstalled-Choco($id)  {
    $r = choco list --local-only $id 2>$null | Out-String
    return $r -match "(?im)^${id}\s"
}

if (-not $NoDeps -and $pkgMgr) {
    # On Windows, tkinter ships with the official python.org installer, so we
    # don't track it separately. PortAudio is bundled into the `sounddevice`
    # wheel on Windows — no system lib needed. So the only system dep we
    # really care about is tmux (for /bg start).
    if ($wantTmux -and -not $haveTmux) {
        switch ($pkgMgr) {
            'winget' {
                if (-not (PkgInstalled-Winget 'Microsoft.Tmux')) {
                    # Microsoft.Tmux doesn't exist on Windows officially; we
                    # rely on a community port. Try the well-known one.
                    if (-not (PkgInstalled-Winget 'JonathanRDev.tmux')) {
                        $neededPkgs += 'JonathanRDev.tmux'
                    }
                }
            }
            'scoop'  { if (-not (PkgInstalled-Scoop 'tmux'))   { $neededPkgs += 'tmux' } }
            'choco'  { if (-not (PkgInstalled-Choco 'tmux'))   { $neededPkgs += 'tmux' } }
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 4. ASK USER HOW TO INSTALL SYSTEM PACKAGES
# ═══════════════════════════════════════════════════════════════════════════
if ($neededPkgs.Count -gt 0) {
    Header "3. System dependencies"
    Say "Missing for profile '$Profile':"
    foreach ($p in $neededPkgs) { Write-Host "  * $p" }
    Write-Host ""
    Write-Host "  1) Auto-install now (will request UAC if needed)"
    Write-Host "  2) Show me the command, I will run it manually"
    Write-Host "  3) Skip - proceed with pip install only"
    Write-Host ""
    $choice = Read-Host "Pick 1-3 [default: 1]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = '1' }

    switch ($choice) {
        '1' {
            Header "Installing system packages"
            foreach ($p in $neededPkgs) {
                switch ($pkgMgr) {
                    'winget' { Invoke-Step "winget install --silent --accept-source-agreements --accept-package-agreements --id $p" }
                    'scoop'  { Invoke-Step "scoop install $p" }
                    'choco'  { Invoke-Step "choco install -y $p" }
                }
            }
            OK "System dependencies installed."
        }
        '2' {
            Header "Manual install"
            Say "Run these in another terminal, then re-run me:"
            foreach ($p in $neededPkgs) {
                switch ($pkgMgr) {
                    'winget' { Write-Host "  winget install --id $p" }
                    'scoop'  { Write-Host "  scoop install $p" }
                    'choco'  { Write-Host "  choco install -y $p" }
                }
            }
            exit 0
        }
        '3' { Warn "Skipping system deps - some features won't work until installed manually." }
        default { Err "Invalid choice - aborting."; exit 1 }
    }
} elseif (-not $NoDeps) {
    OK "All system packages for profile '$Profile' are already present."
}

# ═══════════════════════════════════════════════════════════════════════════
# 5. PIP EXTRAS
# ═══════════════════════════════════════════════════════════════════════════
$extras = @()
if ($wantVoice)     { $extras += 'voice' }
if ($wantWebbridge) { $extras += 'webbridge' }
if ($wantMempalace) { $extras += 'memory' }

if ($extras.Count -gt 0) {
    $extrasSpec = "dulus[$($extras -join ',')]"
} else {
    $extrasSpec = "dulus"
}

# ═══════════════════════════════════════════════════════════════════════════
# 6. INSTALL DULUS
# ═══════════════════════════════════════════════════════════════════════════
Header "5. Installing Dulus"

$preFlag = if ($Pre) { '--pre' } else { '' }

switch ($Installer) {
    'uv' {
        OK "Using uv (fastest, isolated)"
        try {
            Invoke-Step "uv tool install '$extrasSpec' $preFlag --python $pyBin"
        } catch {
            Invoke-Step "uv tool upgrade dulus"
        }
    }
    'pipx' {
        OK "Using pipx (isolated venv)"
        if ($extras.Count -gt 0) {
            Invoke-Step "pipx install 'dulus[$($extras -join ',')]' $preFlag --python $pyBin --force"
        } else {
            Invoke-Step "pipx install dulus $preFlag --python $pyBin --force"
        }
    }
    'pip' {
        OK "Using pip"
        Invoke-Step "$pyBin -m pip install --upgrade $preFlag '$extrasSpec'"
    }
}

# Playwright browser binaries when webbridge is requested
if ($wantWebbridge -and -not $DryRun) {
    if (Get-Command playwright -ErrorAction SilentlyContinue) {
        Invoke-Step "playwright install chromium"
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 7. VERIFY
# ═══════════════════════════════════════════════════════════════════════════
Header "6. Verifying"

$dulusBin = $null
foreach ($cand in @(
    "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\dulus.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\dulus.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts\dulus.exe",
    "$env:USERPROFILE\.local\bin\dulus.exe",
    "$env:USERPROFILE\.uv\tools\dulus\bin\dulus.exe"
)) {
    if (Test-Path $cand) { $dulusBin = $cand; break }
}
if (-not $dulusBin) {
    $cmd = Get-Command dulus -ErrorAction SilentlyContinue
    if ($cmd) { $dulusBin = $cmd.Source }
}

if (-not $dulusBin) {
    Warn "dulus binary not found on PATH yet - open a new PowerShell."
    Warn "If pipx/uv was used: run 'pipx ensurepath' or 'uv tool update-shell', then reopen."
} else {
    if (-not $DryRun) {
        try {
            $ver = (& $dulusBin --version 2>$null) -split ' ' | Select-Object -Last 1
            OK "Installed: $dulusBin ($ver)"
        } catch {
            OK "Installed: $dulusBin"
        }
    } else {
        OK "(dry-run) would verify: $dulusBin --version"
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 8. NEXT STEPS
# ═══════════════════════════════════════════════════════════════════════════
Header "All set"
@"

  Get going:
    dulus                    open the REPL
    dulus --help             list flags
    dulus -c "help"          list every slash command
    dulus -c "bg start"      run headless daemon in tmux + webchat

  First-run picks:
    * Pick a model with /model (NVIDIA tier is free - 14 frontier models)
    * Set your soul with /soul (English / Spanish / your own)
    * /help inside the REPL shows everything

  Trouble?
    dulus -c "doctor"        run the full health check

  Profile installed:  $Profile
  Re-install / switch profile any time:
    iwr -useb https://raw.githubusercontent.com/KevRojo/Dulus/main/install.ps1 | iex

  Docs . github.com/KevRojo/Dulus
  X    . @KevRojox
  PyPI . pypi.org/project/dulus

  > The bird, not the rocket.

"@ | Write-Host -ForegroundColor White
