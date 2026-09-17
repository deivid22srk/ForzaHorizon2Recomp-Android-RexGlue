# Changelog — ForzaHorizon2Recomp-Android-RexGlue

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
