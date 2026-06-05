# Build and push FORTRESS images to Docker Hub
param(
    [string]$User = "rinakt",
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:DOCKERHUB_USER = $User
$env:IMAGE_TAG = $Tag

$repos = @(
    "mlsecops-fortress",
    "mlsecops-mlflow",
    "mlsecops-api-scoring",
    "mlsecops-api-antifraud",
    "mlsecops-litellm",
    "mlsecops-dashboard"
)

Write-Host "==> docker compose build..."
docker compose build fortress mlflow api-scoring api-antifraud litellm dashboard
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> docker push ${User}/*:${Tag}..."
foreach ($repo in $repos) {
    $ref = "${User}/${repo}:${Tag}"
    Write-Host "Pushing $ref"
    docker push $ref
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Push failed. Run: docker login -u $User" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host ""
Write-Host "Hub profile: https://hub.docker.com/u/$User"
foreach ($repo in $repos) {
    Write-Host "  https://hub.docker.com/r/$User/$repo"
}
