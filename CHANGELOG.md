# Changelog — ForzaHorizon2Recomp-Android-RexGlue

## v0.1.3 (2026-09-17)

Ciclo de iteração de runtime #4 (evidências da quarta sessão em device,
`log3.zip`).

- **Confirmação da correção do dlopen (run #12)**: o XMediaFacade agora é
  carregado e seu código executa — a sessão 3 de device chegava a
  "Failed to load shared library for module 'xmediafacade_default.xex'" e
  abortava; a sessão 4 passou desse ponto e registrou 3.196 funções do
  módulo.
- **Iteração 6 de codegen — 1 novo alvo tagado** no `[modules.functions]`
  (XMediaFacade): `0x882435D8`. O walker de construtores CRT do próprio
  módulo (`sub_881E8D88`, homólogo de `sub_82BFF9E8` do módulo principal)
  percorre tabelas de ponteiros em `0x88250000..0x88250028` e chama cada
  entrada via `bctrl`; `0x882435D8` era a única entrada não registrada
  (evidência: `[FATAL] Call to invalid or unregistered function at guest
  address 0x882435D8` durante o `LoadUserModule`, crash em
  `function_dispatcher.cpp:39` + SIGABRT).
- **Análise proativa do SpeechFacade** com o mesmo método (walkers
  `sub_891F0058`/`sub_891F0138`, tabelas em `0x89210000..0x89210094` +
  single-word `0x8900068C`): 32/32 alvos já registrados — nenhuma tag
  necessária. Evita uma 5ª sessão de device apenas para descobrir o mesmo
  crash no próximo facade a ser carregado.
- Segurança da tag verificada contra a lição da iteração 5: `0x882435D8`
  está em gap entre `sub_88242BC0` e `sub_882435E8`, é um thunk real de 3
  instruções (addis/addi/b) e o fluxo da função antecessora desvia antes
  dele (bc condicional + b incondicional) — não há risco de quebrar a
  tradução de função existente.

## v0.1.2 (2026-09-17)

Ciclo de iteração de runtime #3 (evidências da terceira sessão em device).

- **Correção de carregamento dos módulos facade**: o `module_registry`
  gerado registra `fh2_XMediaFacade_default` sem prefixo/sufixo e o bionic
  não normaliza nomes no `dlopen` — em device o boot chegava ao
  `XexLoadImage` dos facades e abortava com "Dirty Disc" (evidência:
  `log2.zip`, terceira sessão). O overlay
  `native/overlay/rexglue-sdk/src/core/dynlib_posix.cpp` agora retenta com
  `lib<nome>.so` (forma empacotada no jniLibs); validado em host com
  biblioteca de teste (5/5 checks).
- Rodada 2 da avaliação crítica independente: **9.2/10** — resíduos
  documentais corrigidos (`release.yml` citado 4x em comentários do
  `build.gradle.kts` + afirmação falsa de histórico de assinatura;
  `vblank_hz` em comentários do `PortSettings.kt`; `on_swap` no
  `NativeBridge`; `RestuffCrashHandler` no `android_main`; issues #1-#4
  citadas por número nos docs).
- Confirmação da iteração 5 em device: 85.449 funções registradas, walker
  de construtores CRT passou, chamadas de kernel reais executando.

## v0.1.1 (2026-09-17)

Ciclo de iteração de runtime #2 (evidências da segunda sessão em device).

- **Iteração 5 de codegen — 29 novos alvos tagados** no
  `recomp/fh2_manifest.toml`: todas as entradas não registradas das tabelas
  de construtores CRT percorridas pelo walker `sub_82BFF9E8` no xstart
  (evidência: crash `[FATAL] … 0x83243770` em device real). A análise foi
  feita com as novas ferramentas `tools/xex_extract.py` +
  `tools/scan_indirect_targets.py` — encerra a dinâmica de um endereço por
  rodada de device para esta classe de crash.
- `tools/` + `docs/RECOMPILATION.md §3.1`: método documentado para alvos de
  chamadas indiretas orientadas a dados (tabelas em DATA), com a lição do
  experimento rejeitado de tagamento em massa de vtables (2.528
  `Unresolved conditional branch` → plano extents-aware no backlog).
- `docs/BACKLOG.md`: evidências da segunda sessão (ISO montada in-place com
  2.996 arquivos, 85.420 funções registradas, imports krnl/xam patcheados),
  baseline de warnings de codegen e plano de cobertura extents-aware.

## v0.1.0 (2026-09-17)

Primeira versão pública do port Android.

- Projeto Android completo (Kotlin + Jetpack Compose + SDL3) adaptado do modelo
  de port comprovado do `naughtybear-restuff-android`.
- Pipeline de recompilação RexGlue end-to-end: `rexglue init`/`init module` +
  `codegen` do `default.xex` (entrypoint) + `SpeechFacade_default.xex` +
  `XMediaFacade_default.xex` — 643 arquivos C++ gerados, análise PowerPC
  validada (16 funções tagadas manualmente no `recomp/fh2_manifest.toml`,
  incluindo a evidência de device real 0x83243750).
- Build nativo Android (arm64-v8a): `libfh2.so` (entrypoint + glue + JNI),
  `libfh2_SpeechFacade_default.so`, `libfh2_XMediaFacade_default.so`,
  `librexruntime.so` e AdrenoTools (driver Turnip custom) — sem shaderc
  (o SDK de recompilação não usa GLSL em runtime).
- Limiter de FPS real: cvar `fps_cap` definido no overlay do presenter com
  pacing por software em `PaintAndPresentImpl` (30/60/90/120/∞ ao vivo);
  `video_mode_refresh_rate` (cvar do SDK) exposto como refresh do modo de
  vídeo guest; gatilhos LT/RT do HUD touch são analógicos (rampa ao longo
  da pílula).
- CI GitHub Actions: baixa os .xex do repositório privado via
  `secrets.GH_PAT`, roda codegen no host, compila o nativo e assina os APKs
  (release/debug) — artefatos por run.
- UI de primeira execução com seleção de ISO/pasta via SAF (boot in-place,
  modelo XenDroid), HUD de controles touch padrão Xbox 360 com
  opacidade/tamanho/haptics, gamepads Bluetooth/USB, painel rápido
  (4 dedos), diagnóstico e logs persistentes.
