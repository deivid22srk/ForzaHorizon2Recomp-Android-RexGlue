# Backlog e estado do runtime

Última atualização: 2026-09-17 (v0.1.3 — iteração de runtime #4)

## Como este backlog funciona

Itens são adicionados a partir de **evidência**: saída do codegen, log do
runtime em device, falhas de CI. Nada é especulativo. Cada item vira issue
no GitHub quando ganha prioridade.

## Fase atual: validação em device

A infraestrutura está completa (codegen ✅, CI ✅, APK assinado ✅).

### Evidências de device real (moto g34 5G, Adreno, Android 15 / SDK 35)

Primeira sessão (2026-09-17, APK run #6):

- ✅ Instalação, tela inicial Compose, seleção de dados, GameActivity.
- ✅ `libfh2.so` carregado via classloader; SDL3 sobe; contexto SDL ok.
- ✅ `ReXApp::OnInitialize -> ok` (~8 s: kernel init + load do xex + recomp).
- ✅ **Código guest começou a executar** (~200 ms de execução real).
- ❌ Crash esperado desta fase: `[FATAL] Call to invalid or unregistered
  function at guest address 0x83243750` (function_dispatcher.cpp:39) —
  chamada indireta (ponteiro de função/vtable) para função não descoberta
  pela análise estática. Corrigido no manifest (iteração 4, commit
  correspondente); próximos alvos serão tratados igualmente.
- ℹ️ Duplicatas de `cvar: duplicate registration` (present_*, vulkan_*,
  window_*...) são INOFENSIVAS ("second registration ignored"): os TUs do
  `rex::ui` (OBJECT lib, dentro do libfh2.so) e do `librexruntime.so`
  registram os mesmos cvars estáticos — comportamento estrutural do SDK,
  presente também no port de referência. Tratamento: ignorar (o primeiro
  registro vence; mesmos defaults).
- ℹ️ Backtrace do crash handler funcionou (fh2-rex + abort + frames com
  símbolos) — valida a cadeia de diagnóstico.

Loop de iteração desta fase: cada novo endereço "unregistered function" que
aparecer em device = nova entrada em `[entrypoint.functions]` (com evidência
comentada) → codegen → CI → novo APK.

### Evidências — segunda sessão (2026-09-17, APK run #8, `log.zip`)

- ✅ **ISO montada in-place**: `DiscImageDevice` monta a ISO do jogo direto
  do armazenamento (`2996 files, 7917078618 bytes`) e publica os symlinks
  `game:` e `d:` — sem extração prévia.
- ✅ **85.420 funções recompiladas registradas** (0 duplicatas, 0
  rejeitadas); imports xboxkrnl (219) e xam (182) patcheados; achievement
  store com 46 entradas do título carregada.
- ✅ Driver Vulkan custom (Turnip via AdrenoTools) carregado do
  app-private dir; crash handler gravando log em storage.
- ❌ Crash no boot do módulo: `[FATAL] Call to invalid or unregistered
  function at guest address 0x83243770` dentro de `sub_82BFF9E8`
  (`xstart` → Kernel Dispatch) — o walker de construtores CRT chama
  entradas de tabelas em DATA que a análise estática não alcança.
- ✅ Correção (iteração 5): TODAS as 29 entradas não registradas dessas
  tabelas enumeradas com `tools/scan_indirect_targets.py` e tagadas de uma
  vez (famílias 0x83243770-B0, 0x83250C50-B0, 0x83251980-E0, 0x8325F900-60,
  0x8326F7C0-20) — encerra a dinâmica de um endereço por rodada de device.
  Codegen local revalidado: warnings idênticos ao baseline, TUs críticos
  compilam limpos no host (clang 19).
- ⚠️ Experimento REJEITADO no mesmo ciclo: tagar proativamente ~3.7k alvos
  de vtables/jump tables (clusters de ponteiros na imagem) quebrou a
  tradução de funções existentes — 2.528 `Unresolved conditional branch`
  (REX_FATAL em runtime). Revertido; lição documentada em
  `tools/README.md` e plano extents-aware no item abaixo.
- ℹ️ `cvar: duplicate registration` persiste (inofensivo — ver primeira
  sessão).

### Evidências — terceira sessão (2026-09-17, APK run #10, `log2.zip`)

- ✅ **Iteração 5 confirmada em device**: 85.449 funções registradas
  (+29 exatas) e o walker de construtores CRT **passou** — o boot seguiu
  para chamadas de kernel reais (`XamApp('GAME')`, ~20 lookups
  `GetProcAddressByOrdinal` com thunks alocados em 0x832F258C+).
- ❌ Novo ponto de falha (última etapa do boot): carregamento dos módulos
  facade — `Failed to load shared library for module
  'xmediafacade_default.xex'` → o jogo trata como disco sujo
  (`XamShowDirtyDiscErrorUI`) e aborta. Causa raiz: o `module_registry`
  gerado registra `fh2_XMediaFacade_default` (sem `lib`/`.so`) e o bionic
  não normaliza nomes no `dlopen` — caminho nunca exercitado pelo port de
  referência (jogo de módulo único).
- ✅ Correção: overlay `native/overlay/rexglue-sdk/src/core/dynlib_posix.cpp`
  retenta com a forma canônica `lib<nome>.so` (comportamento preservado
  para nomes já canônicos). Validado em host com lib de teste: 5/5 checks
  (nome cru carrega, símbolo exportado resolvível, nome canônico inalterado,
  lib ausente falha com erro acionável no `last_error`).

### Evidências — quinta sessão (2026-09-17, APK run #14, `log4.zip`)

- ✅ **Iteração 6 confirmada em device**: o XMediaFacade passou da init CRT
  (walker `sub_881E8D88` percorreu as tabelas e não encontrou mais alvos
  não registrados). O boot avançou para a fase de enumeração de conteúdo
  na thread principal (varredura de `\media`, XamContentCreateEnumerator).
- ❌ Novo ponto de falha (thread principal, pós-enumerador):
  `[FATAL] Call to invalid or unregistered function at guest address
  0x8319D238` a partir de `sub_8319CAC8` (+4408) — slot de vtable de
  família de classes de enumeração de conteúdo (5 cópias de vtable em
  `0x8229E594..0x8229EA34`).
- ✅ Correção (iteração 7): **auditoria extents-aware da FAMÍLIA inteira** —
  o método previsto desde a iteração 5 foi executado pela primeira vez e
  21 alvos únicos não registrados foram tagados de uma vez (18 thunks de
  2 instruções com alvo registrado + 3 funções reais QueryInterface:
  0x8319D238, 0x8319E478, 0x83198118), todos com gap/extensão verificados
  endereço a endereço contra as 85.449 funções registradas. Evita 2-3
  rodadas de device que crashariam nos slots irmãos.
- ⚠️ Observações não fatais da sessão (mantidas das sessões anteriores):
  - `NtCreateFile('game:\media\stringtables\en\')` → `0xc000000f`:
    probe de diretório pelo título, segue após o erro — ruído de log.
  - `cache:\` / `gamecontrollerdb.txt` / `\Device\Image`: ver 4ª sessão.

### Evidências — quarta sessão (2026-09-17, APK run #12, `log3.zip`)

- ✅ **Correção do dlopen confirmada em device**: o XMediaFacade foi
  carregado (`dlopen` na forma canônica ok), sua função table inicializada
  (`code=88050000-8824873C`) e 3.196 funções registradas.
- ❌ Novo ponto de falha (dentro da init CRT do módulo): o walker de
  construtores do próprio facade (`sub_881E8D88`) chamou
  `0x882435D8` — não registrada → `[FATAL]` + SIGABRT. Corrigido na
  iteração 6 (1 tag em `[modules.functions]`); SpeechFacade auditado
  preventivamente (32/32 alvos já registrados, zero tags).
- ⚠️ Observações não fatais da sessão (não bloqueiam o boot, registrar
  aqui até virarem itens priorizados):
  - `NtCreateFile('cache:\')` → `0xc000000f`: o título tenta abrir o
    device de cache e o runtime não registra `cache:`. Hoje o jogo segue
    (trata o erro), mas mecânicas que escrevem cache podem degradar.
    Candidato a fix: symlink `cache:` → diretório interno do app.
  - `SDL GameControllerDB: file 'gamecontrollerdb.txt' does not exist`:
    mapeamento estendido de gamepads ausente no APK. Impacto baixo
    (Xbox 360 pad nativo já é reconhecido pelo SDL embutido).
  - `NtCreateFile('\Device\Image')` → `0xc000000f`: probe padrão do
    título, segue após o erro — apenas ruído de log.

## Runtime (esperado, por modelo de port)

- [ ] **Kernel exports do FH2**: o título usa um conjunto próprio de
      exports xboxkrnl/XAM. O SDK traz o kernel HLE do Xenia; exports
      ausentes aparecem no log como `Unimplemented kernel export` — cada um
      vira issue e implementação incremental no SDK/overlay.
- [ ] **Unimplemented instructions**: auditar com
      `rexglue codegen --log-level trace`; cada opcode vira issue rastreada.
      Baseline atual (4 warnings conhecidos, rastreados nas issues #1-#3):
      `bdz` fora de função em 0x82C5C388/0x82C5C38C (#1), `Unresolved
      function 0x831D75A0` a partir de 0x831D5F58 (#2), função gigante
      0x8242A170 (2.5 MB > max_file_size, #3).
- [ ] **Cobertura extents-aware de vtables/jump tables** (#4): os 3.744 alvos
      não registrados encontrados por cluster scan (1151 runs) NÃO foram
      tagados em massa (ver lição da iteração 5). Plano: extrair extensões
      reais das funções registradas (início + contagem de instruções do
      codegen) e tagar apenas alvos FORA dessas extensões; validar com
      codegen local (0 novos warnings) antes de qualquer push.
      **VALIDADO EM ESCALA DE FAMÍLIA (iteração 7)**: o método foi aplicado
      pela primeira vez à família de vtables do enumerador de conteúdo
      (21/21 alvos verificados e tagados, zero risco de extent overlap) —
      o que falta agora é generalizar o filtro para os 3.744 alvos do
      cluster scan global (mesma verificação, aplicada em lote com
      relatório de rejeitados).
- [ ] **Warnings de codegen baseline** (issues #1, #2, #3):
      investigar se são padrões legítimos do título (tail-call fora de
      função / branches com destino computado) ou lacunas do analisador;
      cada um vira issue com endereço e contexto.
- [ ] **Boot do título**: primeiro log de device define os próximos passos
      (crash no load, tela preta, loop de exceção etc.).
- [ ] **Streaming do mundo aberto**: FH2 é um título de streaming constante
      (terreno, tráfego, clima). Validar thrashing de I/O no ISO mmap'ado e
      ajustar `MADV_*`/readahead.
- [ ] **Clima dinâmico e ciclo dia/noite**: dependem de pipelines de shader
      Xenos → SPIR-V completos; validar variantes de shader geradas em
      device (cache persistente já ancorado em `<files>/cache`).

## Motor (heranças do port de referência NÃO portadas)

- [ ] **Release pipeline** (`release.yml` adaptado com verificação de CN e
      GitHub Release automática) — o `build.yml` já entrega APKs assinados
      por run.
- [ ] **Vortek (camada de compatibilidade Vulkan)** — removido na v0.1 por
      não estar no caminho crítico do renderer nativo; reavaliar para GPUs
      com drivers problemáticos.

## Conhecidos e aceitos (v0.1)

- `.xex` ficam em `recomp/assets/` (gitignored) no local e são baixados pelo
  CI via `secrets.GH_PAT` — nunca versionados.
- `recomp/generated/` é gitignored: o CI roda codegen a cada build
  (reprodutível a partir do manifest + binários). Builds locais podem
  reusar com `SKIP_CLI_BUILD=1`.
- Envs nativas `RESTUFF_*` (contrato dos overlays do SDK) mantêm o nome
  histórico — ver `docs/ARCHITECTURE.md`.
