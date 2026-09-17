#!/usr/bin/env bash
# Build nativo Android do port FH2:
#   [1] AdrenoTools (libadrenotools + hooks p/ driver Turnip custom)
#   [2] libfh2.so + libfh2_SpeechFacade_default.so + libfh2_XMediaFacade_default.so
#       (código recompilado + glue do jogo + SDK + JNI)
#   [3] cópia para app/src/main/jniLibs/arm64-v8a (com librexruntime.so e
#       libc++_shared.so)
#
# Diferenças do port de referência: SEM shaderc/glslc (o SDK de recompilação
# não usa GLSL em runtime — era exclusivo dos hooks de render do NB) e SEM
# Vortek (backlog; ver docs/BACKLOG.md).
#
# Requer: ANDROID_NDK_HOME (ou NDK via ANDROID_HOME/ndk/<ver>), cmake, ninja.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECOMP_SRC="${RECOMP_SRC:-$ROOT/recomp}"
REXSDK_SRC="${REXSDK_SRC:-$ROOT/rexglue-sdk}"
ABI="${ABI:-arm64-v8a}"
API="${API:-26}"
JNILIBS_DIR="$ROOT/app/src/main/jniLibs/$ABI"

# --- Localizar o NDK ------------------------------------------------------
if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
    if [[ -n "${ANDROID_HOME:-}" && -d "$ANDROID_HOME/ndk" ]]; then
        NDK_DIR=$(ls -d "$ANDROID_HOME"/ndk/* | sort | tail -1)
    elif [[ -d "$HOME/Android/Sdk/ndk" ]]; then
        NDK_DIR=$(ls -d "$HOME"/Android/Sdk/ndk/* | sort | tail -1)
    else
        echo "ANDROID_NDK_HOME não definido e nenhum NDK encontrado" >&2
        exit 1
    fi
else
    NDK_DIR="$ANDROID_NDK_HOME"
fi
export ANDROID_NDK_HOME="$NDK_DIR"
TOOLCHAIN="$NDK_DIR/build/cmake/android.toolchain.cmake"
echo "NDK: $NDK_DIR"

BUILD_OUT="$ROOT/build/android/$ABI"
mkdir -p "$BUILD_OUT" "$JNILIBS_DIR"

# --- [1] AdrenoTools (libadrenotools + hooks p/ driver Turnip custom) ------
# Motor do carregamento REAL do driver customizado: adrenotools_open_libvulkan
# devolve o handle do loader do sistema com hooks que redirecionam a abertura
# do driver para o .so importado (namespace ligado ao sphal, onde
# libcutils/libhardware resolvem). Requer:
#   - submódulo native/thirdparty/libadrenotools (com lib/linkernsbypass)
#   - useLegacyPackaging=true no APK (hooks como ARQUIVOS em nativeLibraryDir)
# API mínima 28 (linkernsbypass); em API < 28 o adrenotools devolve nullptr e
# o port cai no driver do sistema (fallback logado).
ADRENOTOOLS_SRC="${ADRENOTOOLS_SRC:-$ROOT/native/thirdparty/libadrenotools}"
if [[ ! -d "$ADRENOTOOLS_SRC/lib/linkernsbypass" ]]; then
    echo "ERRO: $ADRENOTOOLS_SRC sem lib/linkernsbypass (submódulos inicializados?)" >&2
    exit 1
fi
ADRENOTOOLS_BUILD="$ROOT/build/adrenotools-$ABI"
if [[ ! -f "$ADRENOTOOLS_BUILD/libadrenotools.so" ]]; then
    echo "== adrenotools: build Android ($ABI) =="
    # BUILD_SHARED_LIBS=ON: add_library(adrenotools) do upstream não declara
    # tipo → sem isso vira .a (e o --exclude-libs do upstream exige shared).
    # CMAKE_LIBRARY_OUTPUT_DIRECTORY: os 4 hooks vivem em src/hook/ sem isso —
    # unifica tudo na raiz do build p/ o loop de cópia abaixo.
    cmake -S "$ADRENOTOOLS_SRC" -B "$ADRENOTOOLS_BUILD" \
        -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
        -DANDROID_ABI="$ABI" \
        -DANDROID_PLATFORM="android-28" \
        -DANDROID_STL=c++_shared \
        -DBUILD_SHARED_LIBS=ON \
        -DCMAKE_LIBRARY_OUTPUT_DIRECTORY="$ADRENOTOOLS_BUILD" \
        -DCMAKE_BUILD_TYPE=Release
    cmake --build "$ADRENOTOOLS_BUILD" --parallel "$(nproc)"
fi
# libadrenotools + hooks (precisam existir COMO ARQUIVOS — useLegacyPackaging)
for adrlib in libadrenotools.so libmain_hook.so libhook_impl.so \
              libfile_redirect_hook.so libgsl_alloc_hook.so; do
    if [[ ! -f "$ADRENOTOOLS_BUILD/$adrlib" ]]; then
        echo "ERRO FATAL: $adrlib não construído (build adrenotools)" >&2
        exit 1
    fi
    cp "$ADRENOTOOLS_BUILD/$adrlib" "$JNILIBS_DIR/"
done
echo "  adrenotools: 5 libs copiadas para jniLibs"

# --- [2] libfh2.so + módulos facades ---------------------------------------
echo "== libfh2.so + facades ($ABI) =="
cmake -S "$ROOT/native" -B "$BUILD_OUT" \
    -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
    -DANDROID_ABI="$ABI" \
    -DANDROID_PLATFORM="android-$API" \
    -DANDROID_STL=c++_shared \
    -DCMAKE_BUILD_TYPE="${CONFIGURATION:-Release}" \
    -DRECOMP_SOURCE_DIR="$RECOMP_SRC" \
    -DREXSDK_SOURCE_DIR="$REXSDK_SRC"
cmake --build "$BUILD_OUT" --target fh2 fh2_SpeechFacade_default fh2_XMediaFacade_default \
    --parallel "$(nproc)"

# ARM PERF/diagnóstico: o alvo compila com -gline-tables-only (crash
# backtraces resolvíveis offline). As tabelas NÃO podem ir para o APK de
# todo usuário — preserva o build COM debug em *.so.unstripped (o CI os upa
# como artefato separado) e entrega ao APK a versão stripada.
# llvm-strip --strip-debug remove SÓ .debug_*; .dynsym (símbolos JNI),
# .eh_frame (unwind do crash handler) e todo o código/rodata ficam intactos.
# NOTA: no NDK r27 os binários de toolchain são SYMLINKS — o find NÃO pode
# filtrar por -type f (primeira iteração perdeu o llvm-strip por isso);
# fallbacks: llvm-strip/llvm-strip-19 do PATH.
LLVM_STRIP=$(find "$NDK_DIR/toolchains/llvm/prebuilt" -name llvm-strip 2>/dev/null | head -1)
if [[ -z "$LLVM_STRIP" ]]; then
    for cand in llvm-strip llvm-strip-19; do
        if command -v "$cand" >/dev/null 2>&1; then LLVM_STRIP="$cand"; break; fi
    done
fi
strip_debug() {
    local so="$1"
    if [[ -n "$LLVM_STRIP" ]]; then
        cp "$so" "$so.unstripped"
        "$LLVM_STRIP" --strip-debug "$so"
    else
        echo "AVISO: llvm-strip não encontrado (NDK nem PATH) — APK incluirá as line tables" >&2
    fi
}
strip_debug "$BUILD_OUT/libfh2.so"
for mod in fh2_SpeechFacade_default fh2_XMediaFacade_default; do
    if [[ -f "$BUILD_OUT/lib$mod.so" ]]; then
        strip_debug "$BUILD_OUT/lib$mod.so"
    else
        echo "ERRO FATAL: lib$mod.so não construída" >&2
        exit 1
    fi
done

# --- [3] Empacotar jniLibs -------------------------------------------------
cp "$BUILD_OUT/libfh2.so" "$JNILIBS_DIR/"
cp "$BUILD_OUT/libfh2_SpeechFacade_default.so" "$JNILIBS_DIR/"
cp "$BUILD_OUT/libfh2_XMediaFacade_default.so" "$JNILIBS_DIR/"
echo "  libs do port copiadas para jniLibs"

# O SDK constrói rexruntime como SHARED e despeja binários em
# rexglue-sdk/out/<REX_PLATFORM>/ (no NDK a detecção do SDK não tem branch
# Android → vira "linux-arm64"). Buscar nos dois lugares:
REXRUNTIME=$(find "$REXSDK_SRC/out" "$BUILD_OUT" -name "librexruntime.so" -type f 2>/dev/null | head -1)
if [[ -n "$REXRUNTIME" ]]; then
    cp "$REXRUNTIME" "$JNILIBS_DIR/"
    echo "  librexruntime: $REXRUNTIME"
else
    echo "AVISO: librexruntime.so não encontrada" >&2
fi

# STL compartilhada: OBRIGATÓRIA com c++_shared (rexruntime SHARED e
# libfh2/facades passam std::string/vector entre si — duas libc++ estáticas
# num mesmo processo = heaps duplicados = crash em tempo de execução).
# ⚠️ O sysroot do NDK usa o TRIPLE LLVM, não o nome do ABI Android:
#    arm64-v8a → aarch64-linux-android (procurar por "arm64-v8a" falha
#    silenciosamente e o APK sai sem libc++_shared.so → dlopen crash).
case "$ABI" in
    arm64-v8a)   TRIPLE="aarch64-linux-android" ;;
    armeabi-v7a) TRIPLE="armv7a-linux-androideabi" ;;
    x86_64)      TRIPLE="x86_64-linux-android" ;;
    *)           TRIPLE="i686-linux-android" ;;
esac
SYSROOT_LIB="$NDK_DIR/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/$TRIPLE"
LIBCXX_SHARED="$SYSROOT_LIB/libc++_shared.so"
if [[ ! -f "$LIBCXX_SHARED" ]]; then
    # Fallback: busca genérica pelo triple no prebuilt
    LIBCXX_SHARED=$(find "$NDK_DIR/toolchains/llvm/prebuilt" \
        -path "*/sysroot/usr/lib/$TRIPLE/libc++_shared.so" -type f 2>/dev/null | head -1)
fi
if [[ -z "$LIBCXX_SHARED" || ! -f "$LIBCXX_SHARED" ]]; then
    echo "ERRO FATAL: libc++_shared.so não encontrada no NDK (triple: $TRIPLE)" >&2
    echo "  Sem ela o APK crasha no device: dlopen failed: libc++_shared.so not found" >&2
    exit 1
fi
cp "$LIBCXX_SHARED" "$JNILIBS_DIR/"
echo "  libc++_shared: $LIBCXX_SHARED"
# Garantia final: as libs TEM que estar no jniLibs
for so in libfh2.so libfh2_SpeechFacade_default.so libfh2_XMediaFacade_default.so librexruntime.so libc++_shared.so; do
    test -f "$JNILIBS_DIR/$so" || { echo "ERRO FATAL: $so ausente no jniLibs" >&2; exit 1; }
done
ls -la "$JNILIBS_DIR/"
echo "Build nativo Android concluído."
