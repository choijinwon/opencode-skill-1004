$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

$Self = $MyInvocation.MyCommand.Path
$Command = Get-Command opencode -CommandType Application,ExternalScript -All |
    Where-Object { $_.Source -ne $Self } |
    Select-Object -First 1

if (-not $Command) {
    throw "real opencode command was not found in PATH"
}

& $Command.Source . --agent aistudio @args
