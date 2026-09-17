/*
 * ============================================================================
 *  BRANDING DO PORT FORZA HORIZON 2 RECOMP
 * ============================================================================
 *
 * Identidade visual e textual do port: nome, paleta ciano de horizonte, arte de
 * fundo (bg_cinematic.jpg — arte original do port), marca vetorial de
 * velocímetro (ic_logo_mark.xml), arquivos de dados esperados
 * (Default.xex / .iso da edição de Xbox 360) e links do portador.
 *
 * A arquitetura continua paramétrica (nada de cor/texto fixado no layout das
 * telas): quem forjar um novo port reaproveita o esqueleto trocando apenas
 * os valores do objeto [PortBranding] e os dois recursos gráficos acima.
 * ============================================================================
 */
package com.deivid22srk.fh2recomp.config

import androidx.compose.ui.graphics.Color

/**
 * Tipos de partícula ambiente parametrizáveis. Escolha o clima do seu port:
 * - [DUST]   : poeira cinematográfica cinza, flutuação lenta e discreta.
 * - [EMBERS] : brasas quentes subindo (combina com paleta âmbar/fogo).
 * - [SPARKS] : faíscas rápidas com rastro, clima energético/arcano.
 * - [MIST]   : névoa volumétrica em blobs grandes e muito lentos.
 * - [NONE]   : sem partículas (economiza bateria em aparelhos fracos).
 */
enum class ParticleType { DUST, EMBERS, SPARKS, MIST, NONE }

/**
 * Link de crédito exibido no diálogo "Portado por ..." (botão de assinatura
 * da tela). [iconKey] escolhe o ícone desenhado: "youtube", "github",
 * "telegram" ou "project" (qualquer outro valor usa um ícone de link neutro).
 */
data class PortLink(
    /** Nome do destino (ex.: "Canal no YouTube"). */
    val label: String,
    /** Linha de detalhe abaixo do nome (ex.: "@hail-games1"). */
    val description: String,
    /** URL aberta no navegador ao tocar. */
    val url: String,
    /** Chave do ícone: "youtube" | "github" | "telegram" | "project". */
    val iconKey: String,
    /** Cor do ícone e do fundo do selo do link. */
    val tint: Color,
)

/**
 * Contrato completo de branding do port. Cada campo documenta o efeito exato
 * que produz na tela, para que a personalização seja feita sem ler o layout.
 */
data class PortBrandingConfig(

    // ------------------------------------------------------------------
    // IDENTIDADE / CONTEÚDO
    // ------------------------------------------------------------------

    /** Título principal da tela (exibido grande, com halo/pulso se ativado). */
    val portTitle: String,

    /** Subtítulo curto em caixa alta acima do título (estilo "eyebrow"). */
    val portSubtitle: String,

    /** Exibe a marca vetorial [R.drawable.ic_logo_mark] acima do título. */
    val showLogo: Boolean,

    // ------------------------------------------------------------------
    // PALETA
    // ------------------------------------------------------------------

    /** Cor de acento: glow do título, orbes de luz, botão, partículas. */
    val accent: Color,

    /**
     * Variação escura do acento usada em gradientes (borda inferior do vidro,
     * camadas de profundidade). Em geral = accent com hue deslocado/mais escuro.
     */
    val accentDeep: Color,

    /** Cor das partículas quando o tipo é EMBERS/SPARKS (DUST usa cinza frio). */
    val particleColor: Color,

    // ------------------------------------------------------------------
    // ARTE DE FUNDO
    // ------------------------------------------------------------------

    /**
     * Resource da arte de fundo cinematográfica. Recomendado: JPG 1080x1920
     * em drawable-nodpi. Use `null` para fundo procedural (gradientes + orbes),
     * útil quando o port ainda não tem arte pronta.
     */
    val backgroundArtRes: Int?,

    // ------------------------------------------------------------------
    // DETECÇÃO DE DADOS DO JOGO
    // ------------------------------------------------------------------

    /**
     * Nomes de arquivo exatos procurados na pasta escolhida pelo usuário
     * (case-insensitive). O primeiro encontrado define o estado "pronto".
     * Exemplos por plataforma: "default.xex" (Xbox 360), "game.iso",
     * "SLUS_123.45" (PS1), "data.pak", "main.dol" (Wii).
     */
    val expectedDataFiles: List<String>,

    /**
     * Extensões aceitáveis como fallback: se nenhum nome exato for achado,
     * qualquer arquivo terminando com uma destas extensões valida a pasta.
     * Deixe vazia para aceitar SOMENTE os nomes exatos acima.
     */
    val acceptableExtensions: List<String>,

    // ------------------------------------------------------------------
    // ATMOSFERA / MOTION
    // ------------------------------------------------------------------

    /** Tipo do sistema de partículas ambiente. */
    val particleType: ParticleType,

    /** Quantidade base de partículas (reduzida automaticamente em telas baixas). */
    val particleCount: Int,

    /** Liga/desliga o sistema de partículas por completo. */
    val particlesEnabled: Boolean,

    /** Halo/pulso cinematográfico no título (multi-camadas, custo baixo). */
    val titleGlowEnabled: Boolean,

    /** Chip técnico (motor/GPU/ABI) no canto inferior esquerdo. */
    val showTechChip: Boolean,

    // ------------------------------------------------------------------
    // TEXTOS DA INTERFACE (PT-BR no demo; troque para localizar o port)
    // ------------------------------------------------------------------

    /** Botão primário no estado "aguardando seleção"/"não encontrado". */
    val labelSelectData: String,

    /** Botão primário no estado "dados encontrados" (dispara o jogo). */
    val labelStartGame: String,

    /** Botão secundário para escolher outra pasta. */
    val labelSelectFolder: String,

    /** Estado de status: pasta escolhida/validação em andamento. */
    val labelValidating: String,

    /** Estado de status: nenhum dado selecionado ainda (estado inicial). */
    val labelIdle: String,

    /** Dica do estado inicial — explica o que o usuário deve fazer. */
    val labelIdleHint: String,

    /** Estado de status: pasta/dados não encontrados. */
    val labelNotFound: String,

    /** Dica do estado "não encontrado"; %s é substituído pelo arquivo esperado. */
    val labelNotFoundHint: String,

    /** Estado de status: dados validados e prontos. */
    val labelFound: String,

    /** Linha complementar do estado pronto; %s = nome do arquivo detectado. */
    val labelFoundFile: String,

    /** Estado de status: permissão de leitura negada/revogada. */
    val labelPermissionError: String,

    /** Botão de fechar do diálogo de créditos. */
    val labelClose: String,

    /** Rótulo do toggle de partículas (tela de Configurações → Efeitos). */
    val labelToggleParticles: String,

    /** Rótulo do toggle "reduzir movimento" (tela de Configurações → Efeitos). */
    val labelToggleMotion: String,

    // ------------------------------------------------------------------
    // TELA DE CONFIGURAÇÕES DEDICADA (engrenagem navega para ela)
    // ------------------------------------------------------------------

    /** Título da tela de configurações (barra superior). */
    val labelSettingsTitle: String,

    /** Subtítulo da tela de configurações. */
    val labelSettingsSubtitle: String,

    /** Rodapé explicativo da tela de configurações. */
    val labelSettingsFooter: String,

    /** Botão que apaga a pasta persistida e volta ao estado inicial. */
    val labelClearSelection: String,

    // ------------------------------------------------------------------
    // CRÉDITOS / LINKS DO PORTADOR ("Portado por ...")
    // ------------------------------------------------------------------

    /** Rótulo do botão de assinatura (pill com coração). */
    val portedByLabel: String,

    /** Título do diálogo de créditos. */
    val creditsTitle: String,

    /** Subtítulo do diálogo de créditos. */
    val creditsSubtitle: String,

    /** Rodapé do diálogo de créditos. */
    val creditsFooter: String,

    /** Lista de links abertos pelo diálogo (YouTube, GitHub, Telegram, base). */
    val links: List<PortLink>,

    // ------------------------------------------------------------------
    // ACESSIBILIDADE (contentDescription)
    // ------------------------------------------------------------------

    /** Descrição do ícone de play / ação do botão primário. */
    val contentDescPlay: String,

    /** Descrição do botão de engrenagem. */
    val contentDescSettings: String,

    /** Descrição do botão secundário de pasta. */
    val contentDescFolder: String,

    /** Descrição da arte de fundo (lida por leitores de tela). */
    val contentDescBackground: String,

    /** Descrição do botão de voltar da tela de configurações. */
    val contentDescBack: String,

    /** Descrição do botão "Portado por ...". */
    val contentDescCredits: String,
)

/**
 * ===========================================================================
 *  VALORES DO PORT FORZA HORIZON 2 RECOMP
 * ===========================================================================
 *  Paleta do festival de corrida: ciano de horizonte sobre azul profundo,
 *  faíscas rápidas (velocidade/festival) e detecção do Default.xex /
 *  imagem .iso da edição de Xbox 360.
 * ===========================================================================
 */
object PortBranding {

    val config: PortBrandingConfig = PortBrandingConfig(
        // ---- Identidade ---------------------------------------------------
        portTitle = "FORZA HORIZON 2",
        portSubtitle = "RECOMP · XBOX 360 · ANDROID",
        showLogo = true,

        // ---- Paleta -------------------------------------------------------
        accent = Color(0xFF3EC6FF),        // ciano horizonte
        accentDeep = Color(0xFF1B6CA8),    // azul profundo
        particleColor = Color(0xFF9FE8FF), // faíscas claras

        // ---- Arte de fundo ------------------------------------------------
        // Troque o arquivo bg_cinematic.jpg pela arte do port mantendo o nome.
        backgroundArtRes = com.deivid22srk.fh2recomp.R.drawable.bg_cinematic,

        // ---- Detecção de dados --------------------------------------------
        // Modo ISO: o usuário seleciona o .iso do Forza Horizon 2
        // (Storage Access Framework, URI persistido, o arquivo NUNCA é copiado
        // para o armazenamento do app).
        // Modo pasta: o app também aceita uma pasta já extraída (Default.xex).
        expectedDataFiles = listOf(
            "default.xex"    // executável do jogo (Xbox 360)
        ),
        acceptableExtensions = listOf(
            ".iso"           // imagem de disco GDFX/XGD (Forza Horizon 2)
        ),

        // ---- Atmosfera ----------------------------------------------------
        particleType = ParticleType.SPARKS,
        particleCount = 54,
        particlesEnabled = true,
        titleGlowEnabled = true,
        showTechChip = true,

        // ---- Textos -------------------------------------------------------
        labelSelectData = "Selecionar ISO",
        labelStartGame = "Iniciar Jogo",
        labelSelectFolder = "Selecionar Pasta Extraída",
        labelValidating = "Validando…",
        labelIdle = "Nenhum dado selecionado",
        labelIdleHint = "Toque em Selecionar ISO e escolha a imagem do jogo — ela roda direto de onde está, sem cópia.",
        labelNotFound = "Dados não encontrados",
        labelNotFoundHint = "Selecione o .iso do jogo ou a pasta que contém %s",
        labelFound = "Dados prontos",
        labelFoundFile = "Pronto para iniciar: %s",
        labelPermissionError = "Permissão negada",
        labelClose = "Fechar",
        labelToggleParticles = "Partículas ambiente",
        labelToggleMotion = "Reduzir movimento",

        // ---- Tela de configurações ----------------------------------------
        labelSettingsTitle = "Configurações",
        labelSettingsSubtitle = "Ajustes do port para o seu aparelho",
        labelSettingsFooter = "Motor, driver e controles são aplicados na próxima inicialização do jogo; efeitos da tela inicial valem na hora.",
        labelClearSelection = "Limpar seleção salva",

        // ---- Créditos / links do portador ----------------------------------
        portedByLabel = "Portado por Hailgames",
        creditsTitle = "Hailgames",
        creditsSubtitle = "Ports Android · Forza Horizon 2 Recomp",
        creditsFooter = "Recompilação do Forza Horizon 2 (Xbox 360) para Android com rexglue-SDK. Requer os arquivos default.xex e SpeechFacade/XMediaFacade (vindos com o jogo) e a imagem do disco fornecida por você.",
        links = listOf(
            PortLink(
                label = "Canal no YouTube",
                description = "@hail-games1",
                url = "https://youtube.com/@hail-games1?si=rREmvIBB6s98N-2m",
                iconKey = "youtube",
                tint = Color(0xFFFF5147)
            ),
            PortLink(
                label = "GitHub",
                description = "deivid22srk · todos os repositórios",
                url = "https://github.com/deivid22srk?tab=repositories",
                iconKey = "github",
                tint = Color(0xFFE8EAF2)
            ),
            PortLink(
                label = "Telegram",
                description = "@hailgames2",
                url = "https://t.me/hailgames2",
                iconKey = "telegram",
                tint = Color(0xFF41B3E3)
            ),
            PortLink(
                label = "Motor de recompilação",
                description = "rexglue-SDK",
                url = "https://github.com/rexglue/rexglue-sdk",
                iconKey = "project",
                tint = Color(0xFF3EC6FF)
            ),
        ),

        // ---- Acessibilidade ------------------------------------------------
        contentDescPlay = "Iniciar",
        contentDescSettings = "Abrir configurações",
        contentDescFolder = "Selecionar outra pasta de dados",
        contentDescBackground = "Arte de fundo do port",
        contentDescBack = "Voltar para a tela inicial",
        contentDescCredits = "Abrir links do portador",
    )
}
