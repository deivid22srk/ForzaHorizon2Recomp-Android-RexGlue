plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.deivid22srk.fh2recomp"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.deivid22srk.fh2recomp"
        minSdk = 26
        targetSdk = 35
        // versionCode acompanha o número do run do GitHub Actions: cada build
        // nova instala por cima da anterior (in-place upgrade). Para builds
        // locais/manual overrides, FH2_VERSION_CODE sobrepõe o run number —
        // mantendo a sequência monotônica entre reinstalações.
        versionCode = System.getenv("FH2_VERSION_CODE")?.toIntOrNull()
            ?: System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1
        // FH2_VERSION_NAME sobrepõe o nome da versão (ex.: tag de release);
        // builds de CI continuam com "1.0.<run>".
        versionName = System.getenv("FH2_VERSION_NAME")
            ?: "1.0.${System.getenv("GITHUB_RUN_NUMBER") ?: "0"}"

        // ABI única: o recomp (SIMDE/NEON) + SDL3 + Vulkan visam arm64 moderno.
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    // A lib nativa (libfh2.so) é construída por scripts/build_android_native.sh
    // (CMake + NDK, incluindo codegen do recomp) e empacotada de jniLibs.
    sourceSets {
        getByName("main") {
            jniLibs.srcDir("src/main/jniLibs")
        }
    }

    // Keystores VERSIONADOS no repo (projeto hobby, distribuição via GitHub
    // Releases / artefatos de CI — senha documentada, não é segredo neste
    // modelo): todas as builds saem com a MESMA assinatura, então o usuário
    // atualiza o app por cima sem desinstalar — preserva os dados e a
    // permissão SAF da pasta do jogo. (NUNCA use estas configurações para
    // publicar na Play Store — gere um keystore privado seu.)
    signingConfigs {
        getByName("debug") {
            storeFile = rootProject.file("keystore/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
        // Keystore de RELEASE dedicado (assina os APKs release do build.yml).
        // Sobrescrevível por env p/ assinar com chave própria sem editar o
        // repo (FH2_STORE_PASSWORD/FH2_KEY_ALIAS/FH2_KEY_PASSWORD). O SHA-256
        // de cada APK é impresso no log e publicado no artefato
        // SHA256SUMS.txt para conferência de integridade (FAQ do README).
        create("release") {
            storeFile = rootProject.file("keystore/release.keystore")
            storePassword = System.getenv("FH2_STORE_PASSWORD") ?: "fh2recomp-release-2026"
            keyAlias = System.getenv("FH2_KEY_ALIAS") ?: "fh2recomp-release"
            keyPassword = System.getenv("FH2_KEY_PASSWORD") ?: "fh2recomp-release-2026"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Assinatura de release dedicada (keystore/release.keystore) —
            // usada pelo build.yml para os APKs release de cada run.
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
        jniLibs {
            // OBRIGATÓRIO p/ AdrenoTools (driver Turnip custom): os hooks
            // (libmain_hook.so etc.) precisam existir COMO ARQUIVOS em
            // nativeLibraryDir — com descompactação desligada o Android lê
            // os .so direto do APK e o hookLibDir do adrenotools não aponta
            // para arquivos reais (o hook falha e o driver do sistema é
            // usado em silêncio, ou 0 devices são enumerados).
            useLegacyPackaging = true
            // NOTA (ARM PERF/diagnóstico): as line tables do libfh2.so
            // NÃO ficam no APK — o build_android_native.sh stripa --strip-debug
            // a lib para o jniLibs e preserva a versão com debug em
            // libfh2.so.unstripped, que o CI upa como artefato separado
            // "forzahorizon2-recomp-debug-symbols". Backtraces "module+0xOFFSET"
            // se resolvem offline com llvm-symbolizer contra ESSE artefato.
        }
    }
}

dependencies {
    // Núcleo Android
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.3")

    // Jetpack Compose (BOM alinha todas as versões)
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.animation:animation")
    implementation("androidx.compose.material3:material3")
    // Ícones completos (Folder, ErrorOutline etc.) — core tem só o subconjunto básico
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // ViewModel + ciclo de vida Compose
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // Navegação entre a tela de seleção e a tela de Configurações
    implementation("androidx.navigation:navigation-compose:2.8.4")

    // DocumentFile — navegação em pastas via Storage Access Framework
    implementation("androidx.documentfile:documentfile:1.0.1")

    // Testes de unidade (JVM puro — sem Robolectric):
    // ActiveFileStoreTest cobre o fix do ENOENT do Vortek e o self-heal
    // do reconcile (roda no CI antes do build nativo de ~45min).
    testImplementation("junit:junit:4.13.2")
}
