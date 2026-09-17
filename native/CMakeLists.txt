# fh2-android — build nativo do port para Android (arm64-v8a)
#
# Consome:
#   -DRECOMP_SOURCE_DIR=<projeto do jogo (recomp/), com codegen já rodado>
#   -DREXSDK_SOURCE_DIR=<rexglue-sdk checkout, com overlays Android aplicados>
#
# O código recompilado (generated/default/ + facades) é produzido ANTES deste
# build pelo CLI rexglue no host (scripts/build_host_codegen.sh) e entra via
# sources.cmake de cada binário.
#
# Alvos produzidos:
#   libfh2.so                      — entrypoint (default.xex) + glue + JNI
#   libfh2_SpeechFacade_default.so — módulo SpeechFacade (carregado via dlopen
#                                    pelo KernelState::LoadUserModule)
#   libfh2_XMediaFacade_default.so — módulo XMediaFacade
#
# NOTA: não inclui o generated/rexglue.cmake do projeto do jogo — ele amarra
# um custom target de codegen ($<TARGET_FILE:rex::rexglue>) que não existe
# nesta build Android (o codegen roda no host, no CI). Os alvos dos módulos
# replicam aqui o contrato do dll_targets.cmake gerado.

cmake_minimum_required(VERSION 3.25)
project(fh2_android LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(RECOMP_SOURCE_DIR "" CACHE PATH "Source tree do projeto do jogo (recomp/)")
set(REXSDK_SOURCE_DIR "" CACHE PATH "Source tree of rexglue-sdk")

if(NOT RECOMP_SOURCE_DIR OR NOT REXSDK_SOURCE_DIR)
    message(FATAL_ERROR "RECOMP_SOURCE_DIR and REXSDK_SOURCE_DIR are required")
endif()

# ----------------------------------------------------------------------
# SDK (rexglue) consumido por add_subdirectory — rexruntime SHARED +
# rexui OBJECT + SDL3 estático. Mesmo contrato do port de referência.
# ----------------------------------------------------------------------
set(REXGLUE_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(REXGLUE_ENABLE_TRACY OFF CACHE BOOL "" FORCE)
add_subdirectory("${REXSDK_SOURCE_DIR}" rexglue-sdk)

# ----------------------------------------------------------------------
# Opções de compilação do código recompilado (mesmo contrato do
# generated/rexglue.cmake upstream; Android: sem -fasync-exceptions, que é
# só para SEH Windows; SIMDE emite NEON no arm64).
#
# ARM PERF/diagnóstico: -gline-tables-only. O crash handler do port
# (android_main.cpp, _Unwind_Backtrace) imprime "módulo+0xOFFSET" usando a
# tabela dinâmica (dladdr) — com line tables o build preserva *.so.unstripped
# (o CI os upa como artefato "forzahorizon2-recomp-debug-symbols") e qualquer
# backtrace de produção se resolve OFFLINE com llvm-symbolizer.
# Custo: +~85-300MB APENAS no artefato de símbolos — zero no APK e zero em
# runtime (as seções .debug_* não são mapeadas pelo loader). Flag clang-only.
# ----------------------------------------------------------------------
function(fh2_apply_recomp_settings target pch_header)
    target_precompile_headers(${target} PRIVATE "${pch_header}")
    target_compile_options(${target} PRIVATE
        $<$<CXX_COMPILER_ID:Clang,AppleClang>:-gline-tables-only>
        $<$<CXX_COMPILER_ID:GNU>:-g0>
        -Wno-unused-parameter
        -Wno-unused-variable
    )
endfunction()

# ----------------------------------------------------------------------
# Código recompilado — entrypoint (generated/default)
# ----------------------------------------------------------------------
set(GENERATED_DIR "${RECOMP_SOURCE_DIR}/generated/default")
set(GENERATED_SOURCES_CMAKE "${GENERATED_DIR}/sources.cmake")
if(NOT EXISTS "${GENERATED_SOURCES_CMAKE}")
    message(FATAL_ERROR
        "${GENERATED_SOURCES_CMAKE} not found. Run the host codegen first "
        "(scripts/build_host_codegen.sh downloads the .xex files and runs "
        "'rexglue codegen').")
endif()
include("${GENERATED_SOURCES_CMAKE}")

# ----------------------------------------------------------------------
# Código recompilado — módulos DLL (facades). Mesmo contrato do
# dll_targets.cmake gerado, sem a dependência do alvo de codegen.
# Cada módulo vira um .so próprio. O module_registry gerado registra
# "fh2_<Módulo>" (SEM prefixo/sufixo) e o KernelState::LoadUserModule
# chama dlopen com esse nome cru — no Android o bionic NÃO normaliza;
# o overlay de dynlib_posix.cpp (src/core) retenta "lib<nome>.so", que é
# a forma empacotada aqui e resolvida no nativeLibraryDir do app.
# ----------------------------------------------------------------------

set(RECOMP_MODS
    "speechfacade_default_xex|fh2_SpeechFacade_default"
    "xmediafacade_default_xex|fh2_XMediaFacade_default"
)
foreach(PAIR IN LISTS RECOMP_MODS)
    string(REPLACE "|" ";" PARTS "${PAIR}")
    list(GET PARTS 0 MOD_OUTDIR_NAME)
    list(GET PARTS 1 MOD_TARGET)
    set(MOD_DIR "${RECOMP_SOURCE_DIR}/generated/${MOD_OUTDIR_NAME}")
    set(MOD_SOURCES_CMAKE "${MOD_DIR}/sources.cmake")
    if(NOT EXISTS "${MOD_SOURCES_CMAKE}")
        message(FATAL_ERROR "${MOD_SOURCES_CMAKE} not found (codegen incompleto?)")
    endif()
    # Preserva GENERATED_SOURCES do entrypoint
    set(_FH2_RESTORE FALSE)
    if(DEFINED GENERATED_SOURCES)
        set(_FH2_PREV_GENERATED ${GENERATED_SOURCES})
        set(_FH2_RESTORE TRUE)
    endif()
    include("${MOD_SOURCES_CMAKE}")
    set(MOD_SOURCES ${GENERATED_SOURCES})
    if(_FH2_RESTORE)
        set(GENERATED_SOURCES ${_FH2_PREV_GENERATED})
    else()
        unset(GENERATED_SOURCES)
    endif()

    add_library(${MOD_TARGET} SHARED ${MOD_SOURCES})
    target_include_directories(${MOD_TARGET} PRIVATE
        "${RECOMP_SOURCE_DIR}"
        "${RECOMP_SOURCE_DIR}/src"
        "${MOD_DIR}"
    )
    target_link_libraries(${MOD_TARGET} PRIVATE rex::runtime)
    set_target_properties(${MOD_TARGET} PROPERTIES CXX_VISIBILITY_PRESET hidden)
    fh2_apply_recomp_settings(${MOD_TARGET} "${MOD_DIR}/fh2_pch.h")
    list(APPEND FH2_MODULE_TARGETS ${MOD_TARGET})
endforeach()

# ----------------------------------------------------------------------
# Fontes do glue do jogo (recomp/src) — main.cpp define REX_DEFINE_APP(fh2,...)
# ----------------------------------------------------------------------
set(FH2_GAME_SOURCES
    "${RECOMP_SOURCE_DIR}/src/main.cpp"
)

# ----------------------------------------------------------------------
# Ponte JNI/Android
# ----------------------------------------------------------------------
set(ANDROID_JNI_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/jni/android_main.cpp"
    # main_android.cpp (hooks embedder) vive no target rexruntime —
    # ver native/overlay/rexglue-sdk/src/system/CMakeLists.txt.
)

# ----------------------------------------------------------------------
# libfh2.so — motor completo (SDL3 estático entra via rex::ui)
# ----------------------------------------------------------------------
add_library(fh2 SHARED
    ${GENERATED_SOURCES}
    ${FH2_GAME_SOURCES}
    ${ANDROID_JNI_SOURCES}
)

target_include_directories(fh2 PRIVATE
    "${RECOMP_SOURCE_DIR}"
    "${RECOMP_SOURCE_DIR}/src"
    "${GENERATED_DIR}"
    # imgui core (rex/ui/style.h inclui <imgui.h>)
    "${REXSDK_SOURCE_DIR}/thirdparty/imgui"
    # renderdoc_app.h (branch não-WIN32)
    "${REXSDK_SOURCE_DIR}/include/renderdoc"
)

# Port Android: frame pointers preservados — o crash handler nativo
# (_Unwind_Backtrace) depende deles para produzir backtraces úteis em Release.
if(ANDROID)
    target_compile_options(fh2 PRIVATE -fno-omit-frame-pointer)
endif()

# rex::runtime traz rexcore/rexfilesystem/rexaudio/rexinput (e SDL3).
# rex::ui é OBJECT library (window_sdl, imgui_drawer, overlay dialogs
# e os objetos imgui) — os objetos entram direto no link do fh2.
target_link_libraries(fh2 PRIVATE
    rex::runtime
    rex::ui
    android
    log
)

# ReXApp (classe base derivada pelo fh2_app.h): compilado direto no alvo
# (mesmo contrato do rexglue_configure_target do pacote instalado).
target_sources(fh2 PRIVATE "${REXSDK_SOURCE_DIR}/src/ui/rex_app.cpp")
# Define de config p/ o stamp de versão (rex_app.cpp usa
# REXGLUE_BUILD_TITLE → REXGLUE_BUILD_CONFIG).
target_compile_definitions(fh2 PRIVATE REXGLUE_BUILD_CONFIG=\"$<CONFIG>\")
fh2_apply_recomp_settings(fh2 "${GENERATED_DIR}/fh2_pch.h")

# NOTA: NÃO usar -Wl,--exclude-libs: os símbolos JNI do SDL3 estático
# (Java_org_libsdl_app_*) precisam permanecer exportados em libfh2.so
# para o bind das classes Java org.libsdl.app.
