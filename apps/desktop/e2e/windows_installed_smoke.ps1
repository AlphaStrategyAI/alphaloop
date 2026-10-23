# De-elevated smoke for the installed NSIS build. No WebDriver.
# Installs, probes the PyInstaller engine, launches the app, and screenshots the window.
param(
    [Parameter(Mandatory = $true)][string]$Installer
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$shots = Join-Path $repo "e2e-artifacts\screenshots"
$logs = Join-Path $repo "e2e-artifacts\logs"
New-Item -ItemType Directory -Force -Path $shots, $logs | Out-Null
$dataRoot = Join-Path $env:TEMP "alphaloop-smoke-data"
if (Test-Path $dataRoot) { Remove-Item -Recurse -Force $dataRoot }
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
$env:ALPHALOOP_DATA_ROOT = $dataRoot
$env:ALPHALOOP_OFFLINE_MARKET_DATA = "1"

function Read-Shared([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    $stream = [System.IO.File]::Open($Path, "Open", "Read", "ReadWrite")
    try {
        $reader = New-Object System.IO.StreamReader($stream)
        return $reader.ReadToEnd()
    } finally {
        $reader.Dispose()
    }
}

function Write-Probe([string]$Message) {
    Write-Host $Message
    Add-Content -Path (Join-Path $logs "engine-probe.txt") -Value $Message
}

function Stop-Alphaloop {
    foreach ($name in @("alphaloop-desktop", "alphaloop-engine")) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

function Uninstall-Alphaloop([string]$DesktopExe) {
    $candidates = @(
        (Join-Path (Split-Path $DesktopExe) "uninstall.exe"),
        (Join-Path (Split-Path $DesktopExe) "Uninstall alphaloop.exe")
    )
    $uninstaller = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $uninstaller) {
        Write-Probe "uninstaller not found next to $DesktopExe"
        return
    }
    $proc = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru
    Write-Probe "uninstaller exit $($proc.ExitCode)"
}

$desktop = $null
try {
    if (-not (Test-Path $Installer)) { throw "installer missing: $Installer" }
    Unblock-File -Path $Installer -ErrorAction SilentlyContinue
    $install = Start-Process -FilePath $Installer -ArgumentList "/S" -Wait -PassThru
    if ($install.ExitCode -ne 0) { throw "NSIS installer exited $($install.ExitCode)" }
    $desktop = Join-Path $env:LOCALAPPDATA "alphaloop\alphaloop-desktop.exe"
    if (-not (Test-Path $desktop)) { throw "installed exe missing: $desktop" }
    Write-Probe "desktop $desktop"

    $engine = Get-ChildItem -Path (Split-Path $desktop) -Filter alphaloop-engine.exe -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $engine) { throw "alphaloop-engine.exe was not installed under $(Split-Path $desktop)" }
    $engineDir = $engine.DirectoryName
    Write-Probe "engine $($engine.FullName)"
    $top = Get-ChildItem -LiteralPath $engineDir | ForEach-Object { $_.Name }
    Write-Probe ("engine dir entries: " + ($top -join ", "))
    $internal = Join-Path $engineDir "_internal"
    Write-Probe ("_internal exists: " + (Test-Path -LiteralPath $internal))
    if (Test-Path -LiteralPath $internal) {
        $pythonDll = Get-ChildItem -LiteralPath $internal -Filter "python*.dll" -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty Name
        Write-Probe ("python dll: " + ($(if ($pythonDll) { $pythonDll -join ", " } else { "(none)" })))
    }
    $zone = Get-Item -LiteralPath $engine.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue
    Write-Probe ("engine Mark-of-the-Web: " + $(if ($zone) { "present" } else { "absent" }))
    $probeFile = Join-Path $engineDir "_alphaloop_write_probe"
    try {
        Set-Content -LiteralPath $probeFile -Value "probe" -ErrorAction Stop
        Remove-Item -LiteralPath $probeFile -Force
        Write-Probe "install dir writable: yes"
    } catch {
        Write-Probe "install dir writable: no ($($_.Exception.Message))"
    }
    Get-ChildItem -LiteralPath (Split-Path $desktop) -Recurse -File -ErrorAction SilentlyContinue |
        Unblock-File -ErrorAction SilentlyContinue

    $stdout = Join-Path $logs "engine-direct-stdout.txt"
    $stderr = Join-Path $logs "engine-direct-stderr.txt"
    $direct = Start-Process -FilePath $engine.FullName -ArgumentList @("--owner", "desktop") `
        -WorkingDirectory $engineDir -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $sawHandshake = $false
    $deadline = (Get-Date).AddSeconds(25)
    while ((Get-Date) -lt $deadline) {
        $text = Read-Shared $stdout
        if ($text.Contains('"status"')) {
            $sawHandshake = $true
            break
        }
        if ($direct.HasExited) { break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $direct.HasExited) {
        Stop-Process -Id $direct.Id -Force -ErrorAction SilentlyContinue
        [void]$direct.WaitForExit()
    }
    $exitCode = $direct.ExitCode
    # Stop-Process reports -1. Format as unsigned so a loader NTSTATUS still prints.
    $exitHex = if ($null -eq $exitCode) { "unknown" } else { "{0:X8}" -f ($exitCode -band 0xFFFFFFFF) }
    Write-Probe "direct engine exit $exitCode hex $exitHex handshake=$sawHandshake"
    if (Test-Path $stderr) {
        $errText = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
        if ($errText) { Write-Probe "direct engine stderr: $errText" }
    }
    $directFailed = -not $sawHandshake
    if ($directFailed) {
        $outText = Read-Shared $stdout
        Write-Probe "direct engine stdout: $outText"
    }

    Stop-Alphaloop
    Start-Sleep -Seconds 1
    $app = Start-Process -FilePath $desktop -WorkingDirectory (Split-Path $desktop) -PassThru
    $logPath = Join-Path $dataRoot "desktop.log"
    $ready = $false
    $deadline = (Get-Date).AddSeconds(40)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $logPath) {
            $log = Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
            if ($log -and $log.Contains("alphaloop-engine handshake status=ready")) {
                $ready = $true
                break
            }
        }
        if ($app.HasExited) { break }
        Start-Sleep -Milliseconds 400
    }
    $app.Refresh()
    $handle = $app.MainWindowHandle
    if ($handle -eq [IntPtr]::Zero) {
        $named = Get-Process -Name "alphaloop-desktop" -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } |
            Select-Object -First 1
        if ($named) { $handle = $named.MainWindowHandle }
    }
    if ($handle -eq [IntPtr]::Zero) { throw "alphaloop window was not created" }
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class AlphaloopWindow {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}
"@
    $rect = New-Object AlphaloopWindow+RECT
    [void][AlphaloopWindow]::GetWindowRect($handle, [ref]$rect)
    $width = [Math]::Max(1, $rect.Right - $rect.Left)
    $height = [Math]::Max(1, $rect.Bottom - $rect.Top)
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $width, $height))
    $shot = Join-Path $shots "installed-window.png"
    $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bmp.Dispose()
    Write-Probe "screenshot $shot ${width}x${height}"
    if (Test-Path $logPath) { Copy-Item -LiteralPath $logPath -Destination (Join-Path $logs "desktop.log") -Force }
    $engineLog = Join-Path $dataRoot "engine.log"
    if (Test-Path $engineLog) { Copy-Item -LiteralPath $engineLog -Destination (Join-Path $logs "engine.log") -Force }
    if ($directFailed -or -not $ready) {
        $log = if (Test-Path $logPath) { Get-Content -LiteralPath $logPath -Raw } else { "(desktop.log missing)" }
        throw "engine handshake failed (direct=$sawHandshake app=$ready). desktop.log: $log"
    }
    Write-Probe "engine handshake status=ready"
}
finally {
    Stop-Alphaloop
    if ($desktop -and (Test-Path $desktop)) { Uninstall-Alphaloop $desktop }
}
