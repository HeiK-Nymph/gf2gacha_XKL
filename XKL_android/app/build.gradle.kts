import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val biliProperties = Properties().apply {
    val localConfig = rootProject.file("bili.properties")
    if (localConfig.exists()) localConfig.inputStream().use { load(it) }
}
val biliAppKey = biliProperties.getProperty("appKey", "")
require(biliAppKey.isEmpty() || biliAppKey.matches(Regex("[A-Za-z0-9]{32}"))) {
    "bili.properties appKey must be a 32-character SDK key"
}

android {
    namespace = "uk.gf2gacha.xkl"
    compileSdk = 34

    defaultConfig {
        applicationId = "uk.gf2gacha.xkl"
        minSdk = 24
        targetSdk = 34
        versionCode = 12
        versionName = "0.1.4"
        buildConfigField("String", "BILI_APP_KEY", "\"$biliAppKey\"")
        testInstrumentationRunner = "uk.gf2gacha.xkl.MiniProgramKeyInstrumentation"
        resourceConfigurations += listOf("zh", "en")

        // 「检查更新」读的远端文件（发布包写死线上地址；调试包在下面 buildTypes.debug 里覆盖成
        // http://127.0.0.1:8000/...，配合 adb reverse 就能在真机上把整条更新链路跑一遍）
        buildConfigField(
            "String",
            "UPDATE_VERSION_URL",
            "\"https://r2.gf2gacha-xkl.uk/version_android.json\""
        )
    }

    // release 签名：从 keystore.properties 读（该文件不进 git）
    signingConfigs {
        create("release") {
            val propsFile = rootProject.file("keystore.properties")
            if (propsFile.exists()) {
                val props = Properties()
                propsFile.inputStream().use { props.load(it) }
                storeFile = rootProject.file(props.getProperty("storeFile"))
                storePassword = props.getProperty("storePassword")
                keyAlias = props.getProperty("keyAlias")
                keyPassword = props.getProperty("keyPassword")
            }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    // 真机协议测试使用与已安装应用相同的 release 变体，不递增版本号。
    testBuildType = "release"

    buildTypes {
        debug {
            // 调试包换个包名（...test），可以和正式版同时装在手机上互不影响；
            // 更新地址指向本机 8000 端口，配合 `adb reverse tcp:8000 tcp:8000` 自测更新流程
            applicationIdSuffix = ".test"
            versionNameSuffix = "-debug"
            buildConfigField(
                "String",
                "UPDATE_VERSION_URL",
                "\"http://127.0.0.1:8000/version_android.json\""
            )
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (rootProject.file("keystore.properties").exists()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("com.google.android.material:material:1.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("io.coil-kt:coil:2.7.0")
}
