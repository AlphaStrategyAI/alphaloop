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

function Assert-NoConsoleWindow {
    $procs = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name
    $children = @{}
    foreach ($proc in $procs) {
        $parent = [int]$proc.ParentProcessId
        if (-not $children.ContainsKey($parent)) { $children[$parent] = @() }
        $children[$parent] += [int]$proc.ProcessId
    }
    $tree = New-Object System.Collections.Generic.HashSet[int]
    $stack = New-Object System.Collections.Generic.Stack[int]
    foreach ($proc in $procs) {
        if ($proc.Name -in @("alphaloop-desktop.exe", "alphaloop-engine.exe")) {
            $stack.Push([int]$proc.ProcessId)
        }
    }
    while ($stack.Count -gt 0) {
        $id = $stack.Pop()
        if (-not $tree.Add($id)) { continue }
        if ($children.ContainsKey($id)) {
            foreach ($child in $children[$id]) { $stack.Push([int]$child) }
        }
    }
    foreach ($proc in $procs) {
        if ($proc.Name -eq "conhost.exe" -and $tree.Contains([int]$proc.ParentProcessId)) {
            [void]$tree.Add([int]$proc.ProcessId)
        }
    }
    if ($tree.Count -eq 0) { throw "alphaloop-desktop.exe is not running" }
    Add-Type @"
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
public static class AlphaloopConsoles {
  delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hWnd, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
  public static string Find(int[] pids) {
    var set = new HashSet<int>(pids);
    var bad = new List<string>();
    EnumWindows((h, l) => {
      uint pid;
      GetWindowThreadProcessId(h, out pid);
      if (!set.Contains((int)pid)) return true;
      var cls = new StringBuilder(256);
      GetClassName(h, cls, cls.Capacity);
      string name = "";
      try { name = Process.GetProcessById((int)pid).ProcessName; } catch {}
      bool visible = IsWindowVisible(h);
      if (cls.ToString() == "ConsoleWindowClass" || (name.Equals("conhost", StringComparison.OrdinalIgnoreCase) && visible)) {
        bad.Add(name + " class=" + cls + " pid=" + pid + " visible=" + visible);
      }
      return true;
    }, IntPtr.Zero);
    return string.Join("; ", bad);
  }
}
"@ -ErrorAction SilentlyContinue
    $ids = New-Object int[] $tree.Count
    $tree.CopyTo($ids)
    $found = [AlphaloopConsoles]::Find($ids)
    if ($found) { throw "console window open: $found" }
    Write-Probe "no console window"
}

function Protect-Logs([string]$Token) {
    $secrets = @($Token) | Where-Object { $_ -and $_.Length -ge 6 }
    $files = Get-ChildItem -Path $logs, $shots -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -ne ".png" }
    foreach ($file in $files) {
        $text = [System.IO.File]::ReadAllText($file.FullName)
        $updated = [regex]::Replace($text, '"auth_token"\s*:\s*"[^"]*"', '"auth_token": "[redacted]"')
        foreach ($secret in $secrets) { $updated = $updated.Replace($secret, "[redacted]") }
        if ($updated -ne $text) { [System.IO.File]::WriteAllText($file.FullName, $updated) }
    }
    if ($Token) {
        $hit = @()
        foreach ($file in $files) {
            if ([System.IO.File]::ReadAllText($file.FullName).Contains($Token)) { $hit += $file.Name }
        }
        if ($hit.Count -gt 0) { throw "auth_token still present in $($hit -join ', ')" }
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
$script:authToken = ""
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
    $exitHex = "unknown"
    if ($null -ne $exitCode) {
        try { $exitHex = "{0:X8}" -f $exitCode } catch { $exitHex = [string]$exitCode }
    }
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
    Assert-NoConsoleWindow
    $rawHandshake = Read-Shared $stdout
    if ($rawHandshake -match '"auth_token"\s*:\s*"([^"]+)"') { $script:authToken = $Matches[1] }
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
    Protect-Logs $script:authToken
}
