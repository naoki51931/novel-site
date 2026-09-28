plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.novelsite.mobile"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.novelsite.mobile"
        minSdk = 24
        targetSdk = 34
        versionCode = (System.getenv("LEXIS_VERSION_CODE") ?: "13").toInt()
        versionName = System.getenv("LEXIS_VERSION_NAME") ?: "1.0.13"
        fun configValue(key: String): String {
            val env = (System.getenv(key) ?: "").trim()
            if (env.isNotBlank()) return env
            val prop = (project.findProperty(key) as String?)?.trim().orEmpty()
            if (prop.isNotBlank()) return prop
            return ""
        }
        val firebaseAppId = configValue("FIREBASE_APP_ID").replace("\"", "\\\"")
        val firebaseApiKey = configValue("FIREBASE_API_KEY").replace("\"", "\\\"")
        val firebaseProjectId = configValue("FIREBASE_PROJECT_ID").replace("\"", "\\\"")
        val firebaseSenderId = configValue("FIREBASE_MESSAGING_SENDER_ID").replace("\"", "\\\"")
        buildConfigField("String", "FIREBASE_APP_ID", "\"$firebaseAppId\"")
        buildConfigField("String", "FIREBASE_API_KEY", "\"$firebaseApiKey\"")
        buildConfigField("String", "FIREBASE_PROJECT_ID", "\"$firebaseProjectId\"")
        buildConfigField("String", "FIREBASE_MESSAGING_SENDER_ID", "\"$firebaseSenderId\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        create("lexisRelease") {
            val ks = System.getenv("LEXIS_KEYSTORE_PATH")
            if (!ks.isNullOrBlank()) {
                storeFile = file(ks)
                storePassword = System.getenv("LEXIS_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("LEXIS_KEY_ALIAS")
                keyPassword = System.getenv("LEXIS_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("lexisRelease")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { buildConfig = true }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.firebase:firebase-messaging:24.0.1")
}
