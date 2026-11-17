# Phase 0: packs/ -> library/ -> listing -> local server
# Usage:  .\scripts\build.ps1 -Blender "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
param(
    [string]$Blender = "blender",
    [string]$Author = "Kenney",
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

& $Blender -b --factory-startup -P "$root\scripts\mark_assets.py" -- "$root\packs" "$root\library" --author $Author
Copy-Item "$root\library-meta.json" "$root\library\_asset-library-meta.json" -Force
& $Blender -b -c asset_listing generate "$root\library"

Write-Host "`nLibrary URL for Blender Preferences > Asset Libraries: http://127.0.0.1:$Port/"
Set-Location "$root\library"
python -m http.server $Port --bind 127.0.0.1
