#!/usr/bin/env bash
# Download autenticado dos .xex do Forza Horizon 2 (repositório PRIVADO do
# portador) para recomp/ assets.
#
# Requisitos:
#   GH_TOKEN no ambiente (PAT com escopo repo + acesso a
#   deivid22srk/forza-horizon-2-xex). No GitHub Actions o token vem de
#   secrets.GH_PAT (NUNCA hardcoded no repositório).
#
# Valida cada arquivo: tamanho > 0 e magic "XEX2" no header.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$REPO_ROOT/recomp/assets}"
BASE_URL="${FH2_XEX_BASE_URL:-https://raw.githubusercontent.com/deivid22srk/forza-horizon-2-xex/main}"

if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "ERRO: GH_TOKEN não definido." >&2
    echo "  No CI: configure o secret GH_PAT (Settings → Secrets and variables → Actions)." >&2
    echo "  Local: export GH_TOKEN=<seu PAT com escopo repo>" >&2
    exit 1
fi

mkdir -p "$DEST"
for f in default.xex SpeechFacade_default.xex XMediaFacade_default.xex; do
    out="$DEST/$f"
    echo "baixando $f ..."
    curl -sL --fail --retry 3 \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        -H "User-Agent: fh2-recomp-fetch" \
        -o "$out" "$BASE_URL/$f"
    if [[ ! -s "$out" ]]; then
        echo "ERRO: $f vazio/ausente" >&2
        exit 1
    fi
    magic=$(head -c 4 "$out")
    if [[ "$magic" != "XEX2" ]]; then
        echo "ERRO: magic XEX2 inválido em $f (obtido: '$magic')" >&2
        exit 1
    fi
    printf "  ok: %s (%s bytes)\n" "$f" "$(stat -c%s "$out")"
done
echo "Todos os .xex baixados e validados em $DEST"
