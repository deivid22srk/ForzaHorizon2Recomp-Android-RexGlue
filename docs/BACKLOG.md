# Backlog e estado do runtime

Última atualização: 2026-09-17 (v0.1.0 — primeiro pipeline completo)

## Como este backlog funciona

Itens são adicionados a partir de **evidência**: saída do codegen, log do
runtime em device, falhas de CI. Nada é especulativo. Cada item vira issue
no GitHub quando ganha prioridade.

## Fase atual: validação em device

A infraestrutura está completa (codegen ✅, CI ✅, APK assinado ✅). A fase
seguinte exige **testes em device real** para classificar os itens abaixo.

## Runtime (esperado, por modelo de port)

- [ ] **Kernel exports do FH2**: o título usa um conjunto próprio de
      exports xboxkrnl/XAM. O SDK traz o kernel HLE do Xenia; exports
      ausentes aparecem no log como `Unimplemented kernel export` — cada um
      vira issue e implementação incremental no SDK/overlay.
- [ ] **Unimplemented instructions**: auditar com
      `rexglue codegen --log-level trace`; cada opcode vira issue rastreada.
- [ ] **Boot do título**: primeiro log de device define os próximos passos
      (crash no load, tela preta, loop de exceção etc.).
- [ ] **Streaming do mundo aberto**: FH2 é um título de streaming constante
      (terreno, tráfego, clima). Validar thrashing de I/O no ISO mmap'ado e
      ajustar `MADV_*`/readahead.
- [ ] **Clima dinâmico e ciclo dia/noite**: dependem de pipelines de shader
      Xenos → SPIR-V completos; validar variantes de shader geradas em
      device (cache persistente já ancorado em `<files>/cache`).

## Motor (heranças do port de referência NÃO portadas)

- [ ] **Cap de FPS engine-side**: os cvars `fps_cap`/`vblank_hz` são
      aceitos pelo SDK (warn se desconhecidos), mas o limiter por software
      presente no port de referência (hook de present) não existe ainda
      neste port. Os chips 30/60/90/120 do painel rápido aplicam o cvar ao
      vivo; efeito final depende do pacing do SDK.
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
