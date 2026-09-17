# tools/ — análise de recompilação

Scripts auxiliares usados no ciclo de iteração do runtime (não fazem parte
do build do APK). Cada um documenta seu uso no header.

## `xex_extract.py`

Extrai a imagem de memória carregada de um .xex (espelha o loader do SDK:
AES-128-CBC IV-zero + descompressão BASIC). Requer `pycryptodome`.

```bash
python3 tools/xex_extract.py recomp/assets/default.xex /tmp/default.img.bin
```

## `scan_indirect_targets.py`

Enumera alvos de chamadas indiretas orientadas a dados que a análise
estática não alcança (tabelas de construtores CRT percorridas por
`sub_82BFF9E8`, vtables, jump tables). Cruza com as funções já registradas
(`PPCFuncMappings` no `*_init.cpp` gerado) e lista as faltantes para
tagar no `recomp/fh2_manifest.toml`.

```bash
python3 tools/scan_indirect_targets.py /tmp/default.img.bin \
    recomp/generated/default/fh2_init.cpp \
    --load-base 0x82000000 --code-start 0x823F0000 --code-end 0x832F258C \
    --walker-region 0x83300010:0x8333F88C \
    --walker-region 0x8333F890:0x8333F8A0 \
    --out-dir /tmp/scan
```

Os limites das regiões vêm da leitura do código recompilado do walker
(bounds `addi rX,rX,imm` dos loops de passo 4).

### Facade modules (iteração 6)

Cada módulo `[[modules]]` tem seu PRÓPRIO walker de construtores CRT
(cada XEX linka o CRT). O método para localizá-lo no código gerado do
módulo: procurar funções com `REX_CALL_INDIRECT_FUNC` + loop de passo 4
(`addi rN,rN,4` incremental no MESMO registrador dereferenciado por
`lwz rX,0(rN)`), e extrair os bounds absolutos de pares `lis/addi` que
caiam na faixa de dados da imagem do módulo. Nos facades do FH2:

- XMediaFacade (image 0x88000000, code 0x88050000-0x8824873C):
  walker principal `sub_881E8D88` (single-word `0x8800052C`, loops
  `[0x8825001C,0x88250028)` e `[0x88250010,0x88250018)`) + companion
  `sub_881E8E68` (`[0x88250000,0x8825000C)`).
- SpeechFacade (image 0x89000000, code 0x890A0000-0x89208D7C):
  walker principal `sub_891F0058` (single-word `0x8900068C`, loops
  `[0x89210088,0x89210094)` e `[0x89210010,0x89210084)`) + companion
  `sub_891F0138` (`[0x89210000,0x8921000C)`).

Cuidado com a aritmética do `lis`: o imediato é SIGNED 16-bit
(`-30431` → `0x8921`, não `0x8900`) — um erro aqui aponta as regiões
para o header PE da imagem (que também é `MZ`) e o scan retorna
silenciosamente zero candidatos.

## ⚠️ Lição da iteração 5 (não repetir)

Experimentamos tagar proativamente ~3.7k alvos de runs de ponteiros para
código (vtables/jump tables detectadas por varredura de clusters na imagem
inteira). Resultado: **2.528 novos warnings "Unresolved conditional
branch"** — o codegen quebra a tradução de funções existentes quando um
endereço tagado cai DENTRO da extensão delas (os branches internos deixam
de resolver e viram `REX_FATAL` em runtime).

Regra atual:

1. Tagar SOMENTE alvos com evidência de destino real (crash em device,
   `UnresolvedCall` do analisador, ou tabelas de construtor CRT percorridas
   no boot — essas são funções de verdade e traduzem limpas).
2. Cobertura proativa de vtables/jump tables exige o filtro
   **extents-aware v3** (abaixo) — nunca tagar endereço dentro da extensão
   de função registrada.

## ✅ Auditor extents-aware v3 (iteração 9 — tagging em massa seguro)

`audit_vtable_family.py` v3 executa o sweep global com segurança. Diferças
críticas em relação à v2 (iterações 7/8):

1. **Extents EXATOS** (não heuristic): `scripts/extract_extents.py` parseia
   os `fh2_recomp.*.cpp` gerados (1 comentário = 1 instrução guest; labels
   `loc_XXXXXXXX` ancoram endereços) e produz `extents_main.json` com o
   intervalo exato de cada função registrada. O heuristic antecessor da v2
   foi aposentado: um `b` forward INTRA-função fazia o antecessor parecer
   "desviar antes do alvo" quando o alvo era byte mid-function (caso real:
   `0x831E8A74`, `bctrl` dentro de `sub_831E89E8`).
2. **Plausibilidade de entrada**: função real não começa com `bl`
   (clobber de LR), `bctrl`/`bclr`/`mtctr` (dependentes de CTR/LR setados
   antes) nem branch condicional (join point). `b`-first = tail-thunk de
   1 instrução com validação de alvo.
3. **Aceitação em lote**: candidatos aceitos em ordem crescente; candidato
   cujo extent sobrepõe extent já aceito (em qualquer direção) é rejeitado
   — impede dupla tradução em sweeps de centenas de alvos.
4. **Downgrade de chamada direta não resolvida**: `b`/`bl` dentro do extent
   apontando para alvo não registrado/aceito (ponto fixo) → rejeita o
   candidato (evita novo `UnresolvedCall`/FATAL em runtime).
5. **Dedup contra o manifest**: o registry gerado localmente pode estar
   defasado (o codegen roda no CI) — remover tags já presentes no
   `fh2_manifest.toml` antes de inserir os novos.

```bash
# extrair extents exatos (uma vez por build gerado)
python3 scripts/extract_extents.py   # -> xex-cache/extents_main.json

# sweep global (todos os clusters de dados)
python3 tools/audit_vtable_family.py /tmp/default.img.bin 0x82000000 \
    0x823F0000 0x832F258C recomp/generated/default/fh2_register.cpp \
    xex-cache/extents_main.json --all
```

Resultado da iteração 9: 11 clusters / 1.910 alvos alinhados → 102 SAFE
únicos → 81 novos tags (21 já tagados em iterações anteriores). A maioria
esmagadora dos rejeitados (1.804/1.805) cai DENTRO de extents registrados —
a checagem exata fazendo exatamente o trabalho que a iteração 5 exigia.

## ✅ Filtro extents-aware v2 validado (iterações 7/8)

O método do item 2 foi executado pela primeira vez na família de vtables
do enumerador de conteúdo (5 cópias em `0x8229E594..0x8229EA34`), após o
crash `0x8319D238` da quinta sessão de device. Procedimento — para CADA
alvo não registrado encontrado nos slots:

1. **Gap check**: vizinho registrado imediatamente abaixo e acima (tabela
   de `fh2_init.cpp`); o alvo não pode cair dentro da extensão de nenhum
   deles.
2. **Desassemblia do antecessor**: o fluxo dele precisa desviar ANTES do
   alvo (`b` incondicional, `blr`/`bctr`) — sem queda de fluxo possível.
3. **Classificação do alvo**:
   - *thunk de 2 instruções* (`addi r3,r3,-N; b <alvo>`): seguro por
     construção, desde que o alvo do desvio seja uma função REGISTRADA;
   - *função real*: prólogo limpo (acesso a campos de `this`) + extensão
     varrida até o primeiro terminador incondicional (`blr`/`bctr`/`b`
     para fora) + nenhum endereço registrado dentro da extensão.

Resultado: 21/21 alvos verificados e tagados de uma vez (18 thunks + 3
funções reais QueryInterface com IID `0x1337F001`), eliminando 2-3 rodadas
de device nos slots irmãos. Scripts de referência:
`disasm_8319D238.py`, `scan_refs_8319D238.py`, `audit_vtables_8229E9.py`,
`extent_check.py` (pasta `scripts/` do ambiente de trabalho; a lógica está
reproduzida nas descrições acima).
