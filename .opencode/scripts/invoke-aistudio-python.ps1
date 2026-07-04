param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ScriptPath,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArguments,

    [switch]$AutoInstallIfMissing
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

if ($ScriptArguments) {
    $normalizedArguments = New-Object 'System.Collections.Generic.List[string]'
    foreach ($argument in $ScriptArguments) {
        if ($argument -eq "-AutoInstallIfMissing") {
            $AutoInstallIfMissing = $true
            continue
        }
        $normalizedArguments.Add($argument) | Out-Null
    }
    $ScriptArguments = @($normalizedArguments)
}

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OpenCodeRoot = Split-Path -Parent $ScriptRoot
$ProjectRoot = Split-Path -Parent $OpenCodeRoot
Set-Location -LiteralPath $ProjectRoot

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [string[]]$PrefixArgs = @()
    )

    try {
        & $Command @PrefixArgs --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Add-Candidate {
    param(
        [object]$Candidates,

        [Parameter(Mandatory = $true)]
        [string]$Command,

        [string[]]$PrefixArgs = @()
    )

    if ([string]::IsNullOrWhiteSpace($Command)) {
        return
    }

    $normalized = $Command.Trim()
    $alreadyAdded = $Candidates | Where-Object {
        $_.Command -eq $normalized -and (@($_.PrefixArgs) -join " ") -eq (@($PrefixArgs) -join " ")
    }
    if ($alreadyAdded) {
        return
    }

    $Candidates.Add([pscustomobject]@{
        Command = $normalized
        PrefixArgs = @($PrefixArgs)
    }) | Out-Null
}

function Get-PythonCandidates {
    $candidates = New-Object 'System.Collections.Generic.List[object]'

    if ($env:OPENCODE_PYTHON) {
        Add-Candidate -Candidates $candidates -Command $env:OPENCODE_PYTHON
    }

    try {
        $pyCommand = Get-Command py -ErrorAction Stop
        Add-Candidate -Candidates $candidates -Command $pyCommand.Source -PrefixArgs @("-3")
    }
    catch {
    }

    try {
        $pythonCommands = Get-Command python -CommandType Application -All -ErrorAction Stop
        foreach ($pythonCommand in $pythonCommands) {
            Add-Candidate -Candidates $candidates -Command $pythonCommand.Source
        }
    }
    catch {
    }

    $commonRoots = @(
        "$env:LocalAppData\Programs\Python",
        "$env:ProgramFiles\Python*",
        "$env:SystemDrive\Python*"
    )

    foreach ($root in $commonRoots) {
        try {
            $resolvedRoots = @(Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue)
        }
        catch {
            $resolvedRoots = @()
        }

        foreach ($resolvedRoot in $resolvedRoots) {
            $candidatePath = Join-Path $resolvedRoot.FullName "python.exe"
            if (Test-Path -LiteralPath $candidatePath) {
                Add-Candidate -Candidates $candidates -Command $candidatePath
            }
        }
    }

    return $candidates
}

function Resolve-PythonCommand {
    foreach ($candidate in Get-PythonCandidates) {
        if (Test-PythonCandidate -Command $candidate.Command -PrefixArgs $candidate.PrefixArgs) {
            return $candidate
        }
    }
    return $null
}

function Install-PythonIfPossible {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $installerPath = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
        $installerExitCode = $null
        Write-Host "Python not found. Installing Python 3.11 from python.org..."
        Write-Host "Downloading Python 3.11 installer from python.org..."
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $installerPath -UseBasicParsing
        Write-Host "Running Python 3.11 installer..."
        $installer = Start-Process -FilePath $installerPath -ArgumentList @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_test=0"
        ) -Wait -PassThru
        $installerExitCode = $installer.ExitCode
    }
    catch {
        Write-Host "python.org installer failed: $($_.Exception.Message)"
        return $false
    }

    if ($installerExitCode -ne 0) {
        Write-Host "python.org installer failed with exit code $installerExitCode."
        return $false
    }

    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    return $true
}

$ResolvedScriptPath = if ([System.IO.Path]::IsPathRooted($ScriptPath)) {
    $ScriptPath
}
else {
    Join-Path $ProjectRoot $ScriptPath
}

if (-not (Test-Path -LiteralPath $ResolvedScriptPath)) {
    throw "script not found: $ScriptPath"
}

$python = Resolve-PythonCommand

if (-not $python) {
    $message = @(
        "Python executable was not found.",
        "",
        "Install Python first, then run this command again.",
        "Recommended install command:",
        "   winget install --exact --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements",
        "If winget fails, run first:",
        "   winget source reset --force",
        "",
        "Manual Python path:",
        '- `$env:OPENCODE_PYTHON = ''C:\path\to\python.exe''`'
    ) -join [Environment]::NewLine
    Write-Host $message
    exit 1
}

& $python.Command @($python.PrefixArgs) $ResolvedScriptPath @ScriptArguments
exit $LASTEXITCODE
