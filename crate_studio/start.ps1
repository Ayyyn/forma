$ErrorActionPreference = 'Stop'
$formaRoot = Split-Path -Parent $PSScriptRoot
$formaCandidates = @((Join-Path $formaRoot '.venv-forma/Scripts/python.exe'), (Join-Path $formaRoot 'research/vendor/cad-runtime/Scripts/python.exe'))
$formaPython = $formaCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $formaPython) {
    throw 'Create an isolated Python environment and install requirements-forma.txt. See crate_studio/README.md.'
}
Set-Location -LiteralPath $formaRoot
Write-Host 'Forma: http://127.0.0.1:8770'
& $formaPython -m crate_studio --port 8770
