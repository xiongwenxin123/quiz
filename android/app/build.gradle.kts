plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "com.polyglotquiz.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.polyglotquiz.app"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }

    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

}

chaquopy {
    defaultConfig {
        version = "3.11"
        buildPython("python3.11")
        pip {
            options(
                "--index-url", "https://mirrors.aliyun.com/pypi/simple",
                "--extra-index-url", "https://chaquo.com/pypi-13.1",
                "--timeout", "300",
                "--retries", "10",
            )
            install("httpx>=0.27,<1")
            install("../wheels/pydantic-1.10.24-py3-none-any.whl")
            install("fastapi==0.103.2")
            install("anyio==3.7.1")
            install("uvicorn>=0.30,<1")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("../../src")
        }
    }
}
