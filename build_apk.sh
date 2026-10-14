#!/usr/bin/env bash
# Builds build/luna-spell-car.apk without Gradle: aapt2 -> javac -> d8 -> zipalign -> apksigner.
# Needs: JDK 17+, Python 3, Android SDK with platforms;android-34 and build-tools;34.0.0.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/opt/android-sdk}}"
BT="$SDK/build-tools/34.0.0"
JAR="$SDK/platforms/android-34/android.jar"
VERSION_NAME="${VERSION_NAME:-1.0.0}"
VERSION_CODE="${VERSION_CODE:-1}"
A="$ROOT/android"; OUT="$ROOT/build"
KS="${KEYSTORE:-$A/luna-debug.keystore}"; KS_PASS="${KEYSTORE_PASS:-android}"; KS_ALIAS="${KEY_ALIAS:-luna}"

rm -rf "$OUT"; mkdir -p "$OUT/res" "$OUT/gen" "$OUT/classes" "$OUT/dex"
python3 "$ROOT/web/build.py"

"$BT/aapt2" compile --dir "$A/res" -o "$OUT/res/res.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$JAR" \
  --manifest "$A/AndroidManifest.xml" --min-sdk-version 24 --target-sdk-version 34 \
  --version-code "$VERSION_CODE" --version-name "$VERSION_NAME" \
  -A "$A/assets" --java "$OUT/gen" "$OUT/res/res.zip"

javac --release 11 -nowarn -cp "$JAR" -d "$OUT/classes" \
  $(find "$A/java" "$OUT/gen" -name '*.java')
"$BT/d8" --release --min-api 24 --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && zip -q -j "$OUT/unsigned.apk" classes.dex)
"$BT/zipalign" -p -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass "pass:$KS_PASS" --ks-key-alias "$KS_ALIAS" \
  --out "$OUT/luna-spell-car.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify "$OUT/luna-spell-car.apk"
echo "Built $OUT/luna-spell-car.apk ($(du -h "$OUT/luna-spell-car.apk" | cut -f1))"
