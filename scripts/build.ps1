# packs/ -> library/ -> listing -> local server, with an installed Blender instead of the bpy module.
# Downloads are done by scripts/pipeline.py --no-build (any Python 3.11+).
# Usage:  .\scripts\build.ps1 -Blender "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" [-Public]
param(
    [string]$Blender = "blender",
    [switch]$Public,
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$flags = @(); if ($Public) { $flags += "--public" }

& $Blender -b --factory-startup -P "$root\scripts\mark_assets.py" -- "$root\packs" "$root\library" @flags
Copy-Item "$root\library-meta.json" "$root\library\_asset-library-meta.json" -Force
& $Blender -b -c asset_listing generate "$root\library"

Write-Host "`nLibrary URL for Blender Preferences > Asset Libraries: http://127.0.0.1:$Port/"
Set-Location "$root\library"
python -m http.server $Port --bind 127.0.0.1
