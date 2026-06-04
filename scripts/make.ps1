# Windows substitute for Makefile: .\scripts\make.ps1 <target>
# Examples: .\scripts\make.ps1 up | bootstrap | ci-pipeline | demo | test
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Target
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root
$Py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

function Load-DotEnv {
    if (Test-Path ".env") {
        Get-Content ".env" | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
            }
        }
    }
}
Load-DotEnv

switch ($Target) {
    "up" {
        & "$PSScriptRoot\up.ps1"
    }
    "down" {
        docker compose down
    }
    "bootstrap" {
        & "$PSScriptRoot\bootstrap.ps1"
    }
    "ci-pipeline" {
        & $Py scripts/ci/run_pipeline.py
    }
    "train-all" {
        & $Py models/m1_scoring/train.py
        & $Py models/m2_antifraud/train.py
        & $Py models/m3_nlp/train.py
    }
    "test" {
        & $Py -m pytest tests/ -q
    }
    "demo" {
        & "$PSScriptRoot\demo.ps1"
    }
    "demo-local" {
        & "$PSScriptRoot\demo-local.ps1"
    }
    default {
        Write-Host "Unknown target: $Target"
        Write-Host "Targets: up, down, bootstrap, ci-pipeline, train-all, test, demo"
        exit 1
    }
}
