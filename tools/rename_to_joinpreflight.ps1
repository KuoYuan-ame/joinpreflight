# Run from the project root after making a git checkpoint or backup.
# This script changes Python source files under src/, tests/, and examples/ only.
# It does not touch .venv, Git history, data files, or the project root folder.
param(
    [string]$ProjectRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$oldPackage = Join-Path $ProjectRoot "src\granguard"
$newPackage = Join-Path $ProjectRoot "src\joinpreflight"

if (-not (Test-Path -LiteralPath $oldPackage -PathType Container)) {
    throw "Expected old package directory not found: $oldPackage"
}
if (Test-Path -LiteralPath $newPackage) {
    throw "Target directory already exists: $newPackage"
}

Rename-Item -LiteralPath $oldPackage -NewName "joinpreflight"

$targets = @(
    (Join-Path $ProjectRoot "src\joinpreflight"),
    (Join-Path $ProjectRoot "tests"),
    (Join-Path $ProjectRoot "examples")
)

$encoding = New-Object System.Text.UTF8Encoding($false)
$updated = 0

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target -PathType Container)) { continue }

    Get-ChildItem -LiteralPath $target -Recurse -File -Filter "*.py" | ForEach-Object {
        $file = $_.FullName
        $original = [System.IO.File]::ReadAllText($file)
        $revised = $original.Replace("GRAINGUARD", "JOINPREFLIGHT")
        $revised = $revised.Replace("GrainGuard", "JoinPreflight")
        $revised = $revised.Replace("granguard", "joinpreflight")
        if ($revised -cne $original) {
            [System.IO.File]::WriteAllText($file, $revised, $encoding)
            $updated++
        }
    }
}

Write-Host "Python package folder renamed: src\joinpreflight"
Write-Host "Updated $updated Python source/test/example files."
Write-Host "Replace pyproject.toml, README.md, and GitHub configuration using the release kit."
Write-Host "Then uninstall granguard and reinstall joinpreflight in editable mode."
