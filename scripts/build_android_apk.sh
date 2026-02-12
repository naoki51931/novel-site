#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_DIR="$ROOT_DIR/smaho-app/android"
SDK_DIR="$ROOT_DIR/.android-sdk"
GRADLE_BIN="$ROOT_DIR/.tools/gradle-8.7/bin/gradle"
OUT_APK="$ROOT_DIR/static/app_downloads/novelsite-android.apk"
SRC_APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"

if [[ ! -x "$GRADLE_BIN" ]]; then
  echo "Gradle not found: $GRADLE_BIN" >&2
  exit 1
fi

if [[ ! -d "$SDK_DIR" ]]; then
  echo "Android SDK not found: $SDK_DIR" >&2
  exit 1
fi

export ANDROID_SDK_ROOT="$SDK_DIR"
export ANDROID_HOME="$SDK_DIR"

"$GRADLE_BIN" -p "$ANDROID_DIR" assembleDebug

mkdir -p "$(dirname "$OUT_APK")"
cp -f "$SRC_APK" "$OUT_APK"

echo "APK copied to: $OUT_APK"
