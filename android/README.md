# Android build

The Android application starts the existing FastAPI backend inside an embedded
Python 3.11 runtime and displays the existing responsive frontend in a WebView.
It does not require a separately deployed Polyglot Quiz server.

Prerequisites: JDK 17, Python 3.11, and Android SDK 35.

```bash
cd android
./gradlew assembleDebug
```

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. Quiz
generation and URL extraction still require network access. Configure an
OpenAI-compatible model from the settings dialog after installing the app.

The bundled `wheels/pydantic-1.10.24-py3-none-any.whl` is built from the
official Pydantic 1.10.24 source with its `SKIP_CYTHON=1` option. Android uses
this pure-Python compatibility runtime because Pydantic Core does not publish
Android wheels. Desktop and server installations continue to use Pydantic 2.
