# Pipeline de recompilação (RexGlue)

## Ferramentas

| Etapa | Ferramenta | Onde roda |
|---|---|---|
| Download dos .xex | `scripts/fetch_xex.sh` (GH_TOKEN) | CI / local |
| Codegen | CLI `rexglue` (build do próprio SDK) | host linux-x64 |
| Build nativo | CMake + NDK r27 | CI / local |

## Fluxo end-to-end

```
default.xex ─┐
SpeechFacade_default.xex ─┤→ rexglue codegen fh2_manifest.toml → generated/
XMediaFacade_default.xex ─┘       (análise PPC + C++ nativo)
                                       │
                        build NDK (arm64) → libfh2.so + facades .so
```

### 1. Manifest (`recomp/fh2_manifest.toml`)

```toml
[project]
name = "fh2"                  # gera classes Fh2*, creator "fh2"
sdk_version = "0.10.0"
game_root = "assets"

[entrypoint]
file_path = "assets/default.xex"
out_directory_path = "generated/default"

[entrypoint.functions]        # funções tagadas manualmente (ver §3)
0x8305E91C = {}

[[modules]]                   # facades carregados via XexLoadImage
guest_path = "speechfacade_default.xex"
file_path = "assets/SpeechFacade_default.xex"
out_directory_path = "generated/speechfacade_default_xex"
```

### 2. Codegen

```bash
bash scripts/build_host_codegen.sh        # CLI + codegen (usa FORCE_CODEGEN=1 p/ regenerar)
```

Fases por binário: `Register → Scan → Discover → GapFill → Merge → Validate
→ Write`. A validação falha se existir chamada não resolvida — o pipeline só
produz código quando TODA função é alcançável.

### 3. Iteração de funções não resolvidas (processo de stub)

Quando `rexglue codegen` reporta `UnresolvedCall (N)`, cada endereço-alvo é
adicionado em `[entrypoint.functions]` (ou `[modules.functions]` para os
facades) como entrada vazia `{}` — o analisador passa a tratá-lo como função.
Histórico real do FH2 (todas documentadas no manifest):

| Iteração | Novos alvos | Origem |
|---|---|---|
| 1 | 10 endereços (0x8305E91C, 0x82C9EFF0…F010, 0x82E83A70, 0x830453EC, 0x8305E804) | tail-calls diretos fora de função detectada |
| 2 | 4 endereços (0x82CBFCB8…CD0) | jump table alcançada a partir dos alvos da iteração 1 |
| 3 | 1 endereço (0x855B80→0x88055B80, XMediaFacade) | `b` direto a partir de 0x880503D0 |
| 4 | 1 endereço (0x83243750) | chamada indireta em DEVICE REAL (ponteiro de função/vtable) — crash function_dispatcher.cpp:39 ~200ms após OnInitialize; primeira evidência de execução guest |

Convenção: cada entrada nova recebe comentário com a iteração e o motivo.
**Nenhuma entrada é "chutada"** — todas vêm da saída do analisador.

### 4. Warnings de instrução não implementada

Toda ocorrência é tratada como **item de backlog rastreável** (issue no
GitHub com o endereço e o opcode), nunca ignorada silenciosamente. Para
auditar:

```bash
rexglue codegen fh2_manifest.toml --log-level trace 2>&1 | grep -i "unimplemented"
```

## SDK versioning

O manifest carrega `sdk_version = "0.10.0"` (stamp gravado pelo CLI). O
submódulo `rexglue-sdk` está fixado em `c94f5eb` (release v0.10.0) — o mesmo
SHA validado pelo port de referência. Atualizar o SDK exige rodar o codegen
de novo e revisar os overlays Android (`scripts/apply_overlays.sh`).
