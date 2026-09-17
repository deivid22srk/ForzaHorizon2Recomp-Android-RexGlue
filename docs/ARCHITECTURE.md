# Arquitetura do port

## Visão geral

O port segue o modelo **manifest-first do rexglue-SDK v0.10.0**: um único
`fh2_manifest.toml` guia o codegen do entrypoint e dos módulos; o SDK fornece
o runtime completo (kernel HLE derivado do Xenia, filesystem VFS, áudio XMA,
input SDL, renderer Vulkan); o wrapper Android fornece janela (SDL3 embutido),
SAF, HUD de controles e ciclo de vida.

```
┌─────────────────────────── APK ────────────────────────────┐
│  app (Kotlin/Compose)          org.libsdl.app (SDL3 Java)  │
│   MainActivity                  GameActivity (SDLActivity) │
│   DataSelectionScreen (SAF)       ├─ VirtualGamepadView    │
│   SettingsScreen                  └─ FpsCounterView        │
│  ┌──────────────────── jniLibs/arm64-v8a ────────────────┐ │
│  │ libfh2.so            entrypoint recomp + glue + JNI   │ │
│  │ libfh2_SpeechFacade_default.so   módulo (dlopen)      │ │
│  │ libfh2_XMediaFacade_default.so   módulo (dlopen)      │ │
│  │ librexruntime.so     runtime do SDK (kernel HLE, VFS) │ │
│  │ libadrenotools.so + 4 hooks    driver Turnip (opt-in) │ │
│  │ libc++_shared.so                                        │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

## Fluxo de boot

1. `GameActivity.getArguments()` gera `fh2.toml` (log, fps_cap, vblank_hz,
   present-mode FIFO-first, `vulkan_require_*` off para GPUs mobile) e monta
   o argv do `SDL_main` (`--game_data_root`, `--user_data_root`,
   `--cache_root`, `--config`, `--log-level`, `--app-files-dir`,
   `--native-lib-dir`).
2. `android_main.cpp`: crash handler → driver Vulkan custom
   (`REX_VULKAN_LOADER_PATH` de `<files>/drivers/active.txt`) →
   `AndroidInitialize()` do SDK (JNI/SAF) → `cvar::Init` →
   `SDLWindowedAppContext` → `WindowedApp::GetCreator("fh2")` (registrado
   por `REX_DEFINE_APP(fh2, ...)` em `recomp/src/main.cpp`) → loop principal.
3. O `ReXApp` (SDK) resolve o `game_data_root` (ISO GDFX montado in-place
   pelo `DiscImageDevice`, ou pasta via `HostPathDevice`), carrega o
   `default.xex` na memória guest, aplica o codegen (jump table) e entra no
   entrypoint do título. Os facades são carregados por `XexLoadImage`
   → `LoadUserModule` → `dlopen("fh2_<Module>_default")`.

## Decisões tomadas (e por quê)

| Decisão | Justificativa |
|---|---|
| Projeto do jogo DENTRO do repo (`recomp/`) em vez de submódulo | Não existe repo upstream do recomp FH2; mantém manifest+glue versionados juntos. |
| Facades como .so separados | É o contrato do runtime (`RegisterRecompiledModule` + dlopen); espelha o modelo de módulos do 360. |
| Sem shaderc/glslc | O SDK não compila GLSL em runtime — shaderc era exclusivo dos hooks de render do port de referência. Menos ~20min de CI e menos superfície de falha. |
| Vortek removido (v0.1) | Camada de compatibilidade opcional do port de referência; o renderer nativo Vulkan cobre o caminho principal. Backlog. |
| GLES não implementado | O renderer do SDK é Vulkan-only (decisão do SDK, igual ao port de referência). Vulkan 1.0+ é universal em arm64 API 26+. |
| `-gline-tables-only` + artefato `.unstripped` | Backtraces do crash handler resolvíveis offline sem inflar o APK. |
| Envs nativas `RESTUFF_*` mantidas | Contrato interno dos overlays do SDK (leitura de caches/lost art); renomear aumentaria risco sem ganho. |
| Keys de prefs `fh2_*` | App novo (applicationId diferente): sem usuários para migrar. |

## Decisões de renderização (mobile)

| Decisão | Racional |
|---|---|
| `vulkan_require_geometry_shader = false` e `vulkan_require_fill_mode_non_solid = false` | Nenhum Adreno/Mali/Turnip expõe `geometryShader` — exigir rejeitaria TODOS os devices e abortaria o boot com tela preta. Os caminhos de fallback do renderer cobrem a ausência (mesmo default do overlay `vulkan_device.cpp`). |
| Present mode FIFO-first (`vulkan_allow_present_mode_immediate/mailbox/fifo_relaxed = false`) | Preferência desktop do SDK (IMMEDIATE > MAILBOX > …) gera presents sem conteúdo novo (judder/consumo) em painéis Android 60/90/120Hz com pacing wall-clock. FIFO alinha ao vsync do painel e é o único modo garantido nos drivers mobile. |
| **FH2 é 720p fixo por design do título** — NÃO implementar escala dinâmica de resolução | O jogo renderiza internamente a 1280×720 no 360; a "resolução dinâmica" de FH5 não existe no FH2. O upscaling para a tela do device é feito pelo presenter (guest output → swapchain). Não "restaurar" defaults desktop de resolução. |
| `fps_cap` (cvar do port, overlay do presenter) | Pacing por software no início de `PaintAndPresentImpl` — teto host-side para térmica/bateria (30/60/90/120/∞, aplicado ao vivo via `SetFlagByName`). O pacing fino por vsync segue do FIFO. |
| `video_mode_refresh_rate` (cvar do SDK) | Taxa do vblank sintético do guest (relógio de vídeo do título); `kRequiresRestart` — aplica no próximo boot. |

## Threading e memória

- O SDK mapeia a memória guest (X360: 512MB unificada) com `MAP_NORESERVE` e
  gerencia MMIO/handlers próprios; o port Android adiciona
  `AndroidInitialize` (pthreads, ASharedMemory, ponte JNI SAF).
- Present thread com pacing FIFO-first (cvars de present mode pinados no
  `fh2.toml` — decisão mobile: MAILBOX/IMMEDIATE geram judder em painéis
  60/90/120Hz com pacing wall-clock).
- Streaming do mundo aberto: leituras lazy sobre a ISO mmap'ada
  (`MADV_RANDOM` pós-boot — herança do port de referência).

## Segurança do token

O `GH_PAT` vive exclusivamente em `secrets.GH_PAT` (GitHub Actions). Os
scripts leem `GH_TOKEN` do ambiente; nenhum token é commitado, e os `.xex`
baixados ficam em `recomp/assets/` (gitignored) — o CI não os empacota no
APK (verificação fail-fast de libs + `.gitignore` de `*.xex`/`*.iso`).
