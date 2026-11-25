#!/bin/bash
# Sign KeyStow.app. Usage: installer/mac_sign.sh path/to/KeyStow.app evidence-dir
#
# With the MAC_SIGNING_P12 (base64) and MAC_SIGNING_PASSWORD secrets, the app is
# signed with KeyStow's own long-lived self-signed certificate. Every release
# then has the same code identity, so macOS can keep the Accessibility
# permission across updates instead of treating each update as a new app.
# It is not an Apple Developer ID: macOS still asks for confirmation on first
# open. Without the secrets (for example in a pull request from a fork), the
# app is ad-hoc signed as before.
set -euo pipefail
app="$1"
evidence="$2"
mkdir -p "$evidence"
identity="-"
keychain=""
cleanup() {
  if [ -n "$keychain" ]; then security delete-keychain "$keychain" >/dev/null 2>&1 || true; fi
  rm -f "${RUNNER_TEMP:-/tmp}/keystow-signing.p12"
}
trap cleanup EXIT

if [ -n "${MAC_SIGNING_P12:-}" ] && [ -n "${MAC_SIGNING_PASSWORD:-}" ]; then
  keychain="${RUNNER_TEMP:-/tmp}/keystow-signing.keychain-db"
  keychain_password="$(uuidgen)"
  security create-keychain -p "$keychain_password" "$keychain"
  security set-keychain-settings -lut 3600 "$keychain"
  security unlock-keychain -p "$keychain_password" "$keychain"
  printf '%s' "$MAC_SIGNING_P12" | base64 --decode > "${RUNNER_TEMP:-/tmp}/keystow-signing.p12"
  security import "${RUNNER_TEMP:-/tmp}/keystow-signing.p12" -k "$keychain" -P "$MAC_SIGNING_PASSWORD" \
    -T /usr/bin/codesign >/dev/null
  security set-key-partition-list -S apple-tool:,apple: -s -k "$keychain_password" "$keychain" >/dev/null
  # Put the temporary keychain first in the search list so codesign finds the key.
  existing=$(security list-keychains -d user | tr -d '"')
  # shellcheck disable=SC2086
  security list-keychains -d user -s "$keychain" $existing
  # The certificate is self-signed, so it is listed without -v (untrusted).
  identity=$(security find-identity -p codesigning "$keychain" | awk '/KeyStow Mac Code Signing/ {print $2; exit}')
  [ -n "$identity" ] || { echo "KeyStow signing identity not found in the imported certificate"; exit 1; }
  echo "Signing with KeyStow's certificate $identity" | tee "$evidence/signing-identity.txt"
else
  if [ "${REQUIRE_SIGNING:-false}" = true ]; then
    # A release must carry KeyStow's stable identity; an ad-hoc release would
    # make every Mac user re-allow Accessibility again.
    echo "Release build without the MAC_SIGNING_P12 / MAC_SIGNING_PASSWORD secrets; refusing to ad-hoc sign"
    exit 1
  fi
  echo "No signing secrets: ad-hoc signature (Accessibility must be re-added after updates)" \
    | tee "$evidence/signing-identity.txt"
fi

codesign --force --deep --sign "$identity" --preserve-metadata=entitlements "$app"
codesign --verify --deep --strict --verbose=2 "$app" 2>&1 | tee "$evidence/app-signature-verify.txt"
codesign -d --verbose=4 "$app" 2>&1 | tee "$evidence/app-signature-details.txt"
codesign -d -r- "$app" 2>&1 | tee "$evidence/designated-requirement.txt"
if [ "$identity" != "-" ]; then
  # A stable identity means the requirement names this certificate (for a
  # self-signed certificate macOS writes "certificate root"; the root is the
  # certificate itself) and the bundle ID, not one build's hash.
  fingerprint=$(printf '%s' "$identity" | tr 'A-F' 'a-f')
  grep -Eq "identifier \"com\.keystow\.app\" and certificate (leaf|root) = H\"$fingerprint\"" \
    "$evidence/designated-requirement.txt" || {
    echo "The designated requirement does not name KeyStow's certificate ($fingerprint)"; exit 1; }
fi
