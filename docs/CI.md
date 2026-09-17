# CI/CD — configuração e funcionamento

## Secrets necessários

| Secret | Valor | Uso |
|---|---|---|
| `GH_PAT` | PAT classic com escopo `repo` (e acesso ao repo privado `deivid22srk/forza-horizon-2-xex`) | download dos `.xex` para o codegen no host |

Configure em **Settings → Secrets and variables → Actions**. O token **não**
pode ser commitado em nenhum arquivo do repositório.

O step `Check GH_PAT` falha cedo (com mensagem orientando a configuração)
quando o secret está ausente — os APKs de CI dependem do codegen, que
depende dos binários.

## Fluxo do `build.yml`

1. **Checkout** com `submodules: recursive` (`rexglue-sdk` @ c94f5eb,
   `libadrenotools` @ 8fae8ce)
2. **Host toolchain**: JDK 17 + clang-19 (o SDK exige Clang e `std::expected`
   funcional) + Android SDK + NDK 27.2.12479018
3. **Overlays** Android sobre o SDK (`scripts/apply_overlays.sh`)
4. **Kotlin unit tests** — falham em segundos, antes do build pesado
5. **Host codegen** — `scripts/build_host_codegen.sh`:
   baixa `.xex` → build do CLI `rexglue` → `rexglue codegen
   recomp/fh2_manifest.toml` (~5-8 min de análise PPC; saída 643 arquivos)
6. **Native build** — `scripts/build_android_native.sh`:
   adrenotools → `libfh2.so` + `libfh2_SpeechFacade_default.so` +
   `libfh2_XMediaFacade_default.so` + `librexruntime.so` +
   `libc++_shared.so` → `app/src/main/jniLibs/arm64-v8a/`
7. **Gradle**: `assembleRelease` + `assembleDebug` (assinados com o keystore
   versionado em `keystore/`)
8. **Verify APK** — fail-fast se qualquer lib obrigatória faltar
9. **Artifacts**: `forzahorizon2-recomp-apk` (APKs),
   `forzahorizon2-recomp-debug-symbols` (`*.so.unstripped` p/
   llvm-symbolizer), `build-logs` (em falha)

## Por que os .xex não entram no APK

Os binários servem **apenas** ao codegen (análise estática do código
PowerPC no host). O APK final contém somente o código RECOMPILADO (C++
nativo) — nenhum byte do executável original é distribuído, e nenhum asset
do jogo (texturas/áudio/mapas) vem do repositório: o usuário fornece o ISO
na primeira execução.

## Timeout e dimensionamento

`timeout-minutes: 240`. O codegen do FH2 leva ~5-8 min no runner (análise de
21.8MB de PowerPC) e o build nativo dos ~250 TUs do entrypoint é a etapa
mais longa (linha-tables-only, sem LTO). Se o runner mudar de tier, reduzir
`--parallel` do ninja controla memória por TU.
