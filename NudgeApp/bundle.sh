#!/bin/bash
set -e
cd "$(dirname "$0")"

SDK=$(xcrun --show-sdk-path)
SOURCES="Sources/Nudge/DaemonController.swift Sources/Nudge/NudgeApp.swift"
OUT_DIR=".build"
APP="Nudge.app"

mkdir -p "$OUT_DIR"

OVERLAY="$(pwd)/fix-modulemap.yaml"

echo "Compiling..."
swiftc \
  -target arm64-apple-macosx13.0 \
  -sdk "$SDK" \
  -vfsoverlay "$OVERLAY" \
  -framework SwiftUI \
  -framework AppKit \
  -framework ServiceManagement \
  -parse-as-library \
  $SOURCES \
  -o "$OUT_DIR/Nudge"

echo "Assembling app bundle..."
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"
cp "$OUT_DIR/Nudge" "$APP/Contents/MacOS/"
cp Info.plist "$APP/Contents/"
[ -f AppIcon.icns ] && cp AppIcon.icns "$APP/Contents/Resources/"
[ -f MenuBarIcon.png ] && cp MenuBarIcon.png "$APP/Contents/Resources/"
[ -f MenuBarIcon@2x.png ] && cp "MenuBarIcon@2x.png" "$APP/Contents/Resources/"

echo "Signing..."
codesign --force --sign - --entitlements Nudge.entitlements "$APP"

echo ""
echo "Built: $(pwd)/$APP"
echo ""
echo "Install with:"
echo "  cp -r $APP /Applications/"
