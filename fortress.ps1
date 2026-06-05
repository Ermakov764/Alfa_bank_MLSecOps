# OS-independent FORTRESS launcher (requires Docker Desktop)
param(
    [Parameter(Position = 0)]
    [string]$Command = "help",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
}

function Invoke-Fortress {
    param([string[]]$CmdArgs)
    docker compose --profile tools run --rm fortress @CmdArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

switch ($Command) {
    "up" {
        docker compose up -d --build @Args
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        docker compose up keycloak-bootstrap
        exit $LASTEXITCODE
    }
    "down" {
        docker compose down @Args
        exit $LASTEXITCODE
    }
    "ps" {
        docker compose ps @Args
        exit $LASTEXITCODE
    }
    "logs" {
        docker compose logs -f @Args
        exit $LASTEXITCODE
    }
    "build" {
        docker compose build fortress @Args
        docker compose build @Args
        exit $LASTEXITCODE
    }
    "deploy" {
        $all = @("deploy") + $Args
        Invoke-Fortress $all
    }
    "pipeline" {
        docker compose up -d keycloak
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Invoke-Fortress @("pipeline")
    }
    "all" {
        docker compose up -d --build postgres minio minio-init keycloak mlflow keycloak-bootstrap oauth2-proxy-mlflow dashboard jupyter
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        docker compose up keycloak-bootstrap
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Invoke-Fortress @("bootstrap")
        Invoke-Fortress @("pipeline")
        Write-Host "Open: FORTRESS http://localhost:8502 | MLflow http://localhost:5000 | Jupyter http://localhost:8888"
    }
    default {
        $all = @($Command) + $Args
        Invoke-Fortress $all
    }
}
