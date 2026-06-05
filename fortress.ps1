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
        docker compose up -d keycloak litellm
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Invoke-Fortress @("pipeline")
    }
    "all" {
        docker compose up -d --build postgres minio minio-init keycloak mlflow oauth2-proxy-mlflow api-scoring api-antifraud litellm dashboard
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Invoke-Fortress @("bootstrap")
        Invoke-Fortress @("train")
        Invoke-Fortress @("demo")
        Write-Host "Open: MLflow http://localhost:5000 | Dashboard http://localhost:8502"
    }
    default {
        $all = @($Command) + $Args
        Invoke-Fortress $all
    }
}
