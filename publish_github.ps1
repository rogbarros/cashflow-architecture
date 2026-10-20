# Publica o projeto do teste tecnico como repositorio PUBLICO standalone.
#
# Uso (depois de rodar `gh auth login`):
#   .\publish_github.ps1                       # cria rogbarros/cashflow-architecture
#   .\publish_github.ps1 -Repo outro-nome
#
# O script NAO toca no repo privado projeto-x: inicializa um git limpo
# DENTRO da propria pasta do projeto e empurra para um repo novo.
param(
    [string]$Repo = "cashflow-architecture",
    [string]$Description = "Desafio tecnico: arquitetura de integracao para fluxo de caixa do comerciante (2 servicos desacoplados por evento persistido)"
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "== 1. Rodando os testes antes de publicar =="
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Push-Location src
& $py -m pytest -q
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "Testes falharam - publicacao abortada." }

Write-Host "== 2. Inicializando git standalone =="
if (-not (Test-Path ".git")) { git init -b main | Out-Null }
git add -A
git commit -m "Desafio tecnico: fluxo de caixa do comerciante - arquitetura + PoC" 2>$null

Write-Host "== 3. Criando repositorio publico e enviando =="
gh repo create $Repo --public --source=. --remote=origin --push `
    --description $Description

$user = (gh api user --jq .login)
Write-Host ""
Write-Host "Publicado: https://github.com/$user/$Repo"
Write-Host "Envie esse link para a Thais (Keyrus)."
