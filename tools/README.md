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
2. Cobertura proativa de vtables/jump tables depende de um filtro
   **extents-aware** (tagar apenas endereços fora da extensão de funções já
   registradas) antes de qualquer nova tentativa — ver `docs/BACKLOG.md`.
