plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.behrouz.subplayer"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.behrouz.subplayer"
        minSdk = 24
        targetSdk = 36    // Google Play: new apps and updates must target Android 16 (API 36)
        versionCode = 9
        versionName = "2.6"

        // 64-bit ARM phones (practically every phone from the last ~7 years)
        ndk { abiFilters += listOf("arm64-v8a") }

        externalNativeBuild {
            cmake {
                // Whisper must be compiled optimised, even in debug builds, or it is 10x slower.
                // ANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES: 16 KB-aligned native code (Google Play requirement)
                arguments += listOf("-DCMAKE_BUILD_TYPE=Release", "-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON")
            }
        }
    }

    // Two builds from one code base:
    //  play   = Google Play: subscription with a 10-day free trial through Google Play Billing.
    //           No activation codes, no Telegram, no video-link downloads, no Vosk (not 16 KB ready).
    //  direct = the APK you hand out yourself: activation codes + 10-day trial, all features.
    //  bazaar / myket = Cafe Bazaar and Myket (Iran): 10-day trial in the app, then a yearly
    //           subscription paid through that store (Myket's official billing library speaks to both).
    // Public keys of the Iranian stores come from store-keys.properties (from each store's developer panel).
    val storeKeys = java.util.Properties().apply {
        val f = rootProject.file("store-keys.properties")
        if (f.exists()) f.inputStream().use { load(it) }
    }
    fun market(id: String, bind: String, permission: String) = mapOf(
        "marketApplicationId" to id, "marketBindAddress" to bind, "marketPermission" to permission)
    flavorDimensions += "store"
    productFlavors {
        create("play") {
            dimension = "store"
            applicationId = "com.behrouz.subplayer.play"
            buildConfigField("boolean", "PLAY", "true")
            buildConfigField("boolean", "STORE_BILLING", "true")
            buildConfigField("String", "STORE", "\"play\"")
            buildConfigField("String", "IAB_PUBLIC_KEY", "\"\"")
        }
        create("direct") {
            dimension = "store"
            applicationId = "com.behrouz.subplayer"
            buildConfigField("boolean", "PLAY", "false")
            buildConfigField("boolean", "STORE_BILLING", "false")
            buildConfigField("String", "STORE", "\"direct\"")
            buildConfigField("String", "IAB_PUBLIC_KEY", "\"\"")
        }
        create("bazaar") {
            dimension = "store"
            applicationId = "com.behrouz.subplayer.bazaar"
            buildConfigField("boolean", "PLAY", "false")
            buildConfigField("boolean", "STORE_BILLING", "true")
            buildConfigField("String", "STORE", "\"bazaar\"")
            buildConfigField("String", "IAB_PUBLIC_KEY", "\"" + storeKeys.getProperty("bazaar", "").trim() + "\"")
            manifestPlaceholders += market("com.farsitel.bazaar", "ir.cafebazaar.pardakht.InAppBillingService.BIND",
                "com.farsitel.bazaar.permission.PAY_THROUGH_BAZAAR")
        }
        create("myket") {
            dimension = "store"
            applicationId = "com.behrouz.subplayer.myket"
            buildConfigField("boolean", "PLAY", "false")
            buildConfigField("boolean", "STORE_BILLING", "true")
            buildConfigField("String", "STORE", "\"myket\"")
            buildConfigField("String", "IAB_PUBLIC_KEY", "\"" + storeKeys.getProperty("myket", "").trim() + "\"")
            manifestPlaceholders += market("ir.mservices.market", "ir.mservices.market.InAppBillingService.BIND",
                "ir.mservices.market.BILLING")
        }
    }
    sourceSets {
        // Vosk ("Fast" engine) everywhere except Google Play (its library isn't 16 KB aligned)
        getByName("direct") { java.srcDir("src/vosk/java") }
        getByName("bazaar") { java.srcDirs("src/vosk/java", "src/iran/java") }
        getByName("myket") { java.srcDirs("src/vosk/java", "src/iran/java") }
        getByName("play") { java.srcDir("src/novosk/java") }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    // Your permanent signing key. It is NEVER stored in this repository: GitHub
    // passes it to the build from encrypted secrets (SIGNING_KEYSTORE_B64 /
    // SIGNING_PASSWORD). Android only accepts updates signed with the same key.
    val keystorePath: String? = System.getenv("SIGNING_KEYSTORE")
    signingConfigs {
        create("release") {
            if (keystorePath != null) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("SIGNING_PASSWORD")
                keyAlias = "subplayer"
                keyPassword = System.getenv("SIGNING_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (keystorePath != null) signingConfigs.getByName("release")
                            else signingConfigs.getByName("debug")
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
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }
}

dependencies {
    // UI (Jetpack Compose, Material 3)
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("com.google.android.material:material:1.12.0")   // window theme only
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("androidx.work:work-runtime-ktx:2.9.1")   // daily review reminder

    // Video: playback + clip export (Media3)
    implementation("androidx.media3:media3-exoplayer:1.4.1")
    implementation("androidx.media3:media3-ui:1.4.1")
    implementation("androidx.media3:media3-transformer:1.4.1")
    implementation("androidx.media3:media3-effect:1.4.1")
    implementation("androidx.media3:media3-common:1.4.1")

    // Fast offline speech recognition (Vosk). Whisper is built from source (src/main/cpp).
    // (direct build only: its native library is not 16 KB aligned, which Google Play refuses)
    for (f in listOf("direct", "bazaar", "myket")) {
        "${f}Implementation"("net.java.dev.jna:jna:5.13.0@aar")
        "${f}Implementation"("com.alphacephei:vosk-android:0.3.47@aar")
    }

    // Cafe Bazaar + Myket subscription: Myket's official billing library (also supports Bazaar), from JitPack
    "bazaarImplementation"("com.github.myketstore:myket-billing-client:1.19")
    "myketImplementation"("com.github.myketstore:myket-billing-client:1.19")

    // Google Play subscription (play build only). Play requires Billing Library 8 or later.
    "playImplementation"("com.android.billingclient:billing:8.3.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20231013")
}
