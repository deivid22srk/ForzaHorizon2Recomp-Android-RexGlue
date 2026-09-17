#!/usr/bin/env bash
# Build do CLI rexglue no HOST (linux-x64) + codegen do projeto do jogo FH2.
#
# O codegen lê os .xex em recomp/assets/ (baixados por scripts/fetch_xex.sh)
# e gera recomp/generated/{default,speechfacade_default_xex,xmediafacade_default_xex}/
# — as fontes recompiladas que o build Android consome.
#
# Entradas:
#   RECOMP_SRC   (default: <repo>/recomp)
#   REXSDK_SRC   (default: <repo>/rexglue-sdk — submódulo)
#   GH_TOKEN     (para o download dos .xex; repo privado do portador)
#   SKIP_CLI_BUILD=1  — reusa build-host existente
#   FORCE_CODEGEN=1   — regenera o recomp
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECOMP_SRC="${RECOMP_SRC:-$ROOT/recomp}"
REXSDK_SRC="${REXSDK_SRC:-$ROOT/rexglue-sdk}"
BUILD_DIR="$ROOT/build/host-codegen"

echo "== [1/3] .xex do jogo (repo privado via GH_TOKEN) =="
if [[ ! -f "$RECOMP_SRC/assets/default.xex" ]]; then
    GH_TOKEN="${GH_TOKEN:-}" bash "$ROOT/scripts/fetch_xex.sh" "$RECOMP_SRC/assets"
else
    echo "  .xex já presentes — pulando download"
fi
ls -la "$RECOMP_SRC/assets/"

echo "== [2/3] Build do CLI rexglue (host) =="
HOST_ARCH_FLAGS="-march=x86-64-v2"  # mesmo piso do preset linux-base do SDK
if [[ "${SKIP_CLI_BUILD:-0}" != "1" || ! -d "$BUILD_DIR" ]]; then
    cmake -S "$REXSDK_SRC" -B "$BUILD_DIR" \
        -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_STANDARD=11 \
        -DCMAKE_CXX_STANDARD=23 \
        -DCMAKE_C_FLAGS="$HOST_ARCH_FLAGS" \
        -DCMAKE_CXX_FLAGS="$HOST_ARCH_FLAGS" \
        -DREXGLUE_BUILD_TESTS=OFF \
        -DREXGLUE_ENABLE_TRACY=OFF \
        -DREXGLUE_ENABLE_PERF_COUNTERS=OFF
fi
cmake --build "$BUILD_DIR" --target rexglue --parallel "$(nproc)"

echo "== [3/3] Codegen =="
# O SDK redireciona RUNTIME_OUTPUT p/ out/<plataforma>-<arch>/ (não fica em
# build/host-codegen/src/rexglue). Resolver o binário de forma robusta:
REXGLUE_CLI=""
for cand in \
    "$REXSDK_SRC/out/linux-amd64/rexglue" \
    "$BUILD_DIR/src/rexglue/rexglue" \
    "$REXSDK_SRC/out/linux-$(uname -m | sed 's/x86_64/amd64/')/rexglue"
do
    if [[ -x "$cand" ]]; then REXGLUE_CLI="$cand"; break; fi
done
if [[ -z "$REXGLUE_CLI" ]]; then
    REXGLUE_CLI=$(find "$REXSDK_SRC/out" "$BUILD_DIR" -type f -name rexglue -perm -u+x 2>/dev/null | head -1)
fi
if [[ -z "$REXGLUE_CLI" ]]; then
    echo "ERRO: binário rexglue não encontrado após o build" >&2
    exit 1
fi
echo "  CLI: $REXGLUE_CLI"
# Não regenerar se já existe (build Android consome o mesmo output).
if [[ -f "$RECOMP_SRC/generated/default/sources.cmake" && "${FORCE_CODEGEN:-0}" != "1" ]]; then
    echo "  codegen já presente — pulando (FORCE_CODEGEN=1 para regenerar)"
else
    "$REXGLUE_CLI" codegen "$RECOMP_SRC/fh2_manifest.toml"
fi
ls "$RECOMP_SRC/generated/default/" | head -8 || true
echo "Codegen concluído."
