#!/usr/bin/env bash
# Instala Flutter + Android SDK no Codespaces (mesmas versões do CI em .github/workflows/mobile.yml).
# Roda sozinho ao criar o codespace; pode ser executado de novo sem problema.
set -euo pipefail

FLUTTER_VERSION="3.47.8"
ANDROID_PLATFORM="android-36"
ANDROID_BUILD_TOOLS="36.0.0"
ANDROID_NDK="28.2.13676358"

FLUTTER_HOME="${FLUTTER_HOME:-$HOME/sdk/flutter}"
ANDROID_HOME="${ANDROID_HOME:-$HOME/sdk/android}"
mkdir -p "$(dirname "$FLUTTER_HOME")" "$ANDROID_HOME"

echo "==> Flutter $FLUTTER_VERSION"
if [ ! -x "$FLUTTER_HOME/bin/flutter" ]; then
  curl -fsSL "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" \
    | tar -xJ -C "$(dirname "$FLUTTER_HOME")"
fi
git config --global --add safe.directory "$FLUTTER_HOME"
export PATH="$FLUTTER_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
flutter config --no-analytics >/dev/null
flutter --version

echo "==> Android command-line tools"
if [ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]; then
  # Descobre o zip mais recente no repositório oficial do Android
  zip_name=$(curl -fsSL https://dl.google.com/android/repository/repository2-3.xml \
    | grep -oE 'commandlinetools-linux-[0-9]+_latest\.zip' | sort -V | tail -1)
  tmp=$(mktemp -d)
  curl -fsSL "https://dl.google.com/android/repository/$zip_name" -o "$tmp/tools.zip"
  unzip -q "$tmp/tools.zip" -d "$tmp"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  rm -rf "$ANDROID_HOME/cmdline-tools/latest"
  mv "$tmp/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
  rm -rf "$tmp"
fi

echo "==> Pacotes do Android SDK"
yes | sdkmanager --licenses >/dev/null || true
sdkmanager --install "platform-tools" "platforms;$ANDROID_PLATFORM" \
  "build-tools;$ANDROID_BUILD_TOOLS" "ndk;$ANDROID_NDK" >/dev/null
flutter config --android-sdk "$ANDROID_HOME" >/dev/null
yes | flutter doctor --android-licenses >/dev/null || true

echo "==> Dependências do app"
cd "$(dirname "$0")/../mobile"
flutter pub get

echo "==> Dependências do backend (para rodar os testes localmente)"
sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg fonts-dejavu-core espeak-ng >/dev/null
python3 -m pip install -q -r ../backend/requirements-dev.txt

flutter doctor
cat <<'EOF'

Pronto! Para gerar o APK:
  cd mobile && flutter build apk --release
O arquivo fica em mobile/build/app/outputs/flutter-apk/app-release.apk
(clique com o botão direito nele no Explorer → Download).
EOF
