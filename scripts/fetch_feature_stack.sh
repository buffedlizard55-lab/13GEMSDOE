#!/usr/bin/env bash
# Fetch the official GEMS `training_features.tif` (mirrored in this group's
# public GEMSDOE repo as data/bridge/gems-geodawn-numerical-features.tif.part-*)
# into data/raw/, then verify every part and the reassembled file against the
# SHA-256 pins published in that repo's data/bridge/manifest.json.
#
# Provenance: data/bridge/manifest.json states
#   gems-geodawn-numerical-features.tif  == canonical training_features.tif
#   sha256 4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5
# and that the pins were produced by scripts/inspect_competition_data.py on a
# GitHub-hosted runner that downloaded from the official data tab.
#
# No DrivenData login is required; only `gh` with public-read access.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
BRIDGE_REPO="buffedlizard55-lab/GEMSDOE"
OUT="$RAW/training_features.tif"
EXPECTED="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"

PARTS=(
  "gems-geodawn-numerical-features.tif.part-000 f34e5143d5e7c10014b5cfe01c85d01bcede4c0a 0a330f8951af6c921029e25c84a579319d2db554d62d30d894d6ddc97f98cff7 94371840"
  "gems-geodawn-numerical-features.tif.part-001 4bd98099ae505f63cc6c3733954f259974efd290 3c98037b2c997e3bbfcdfc2d9a982e8b820a77410dd7404b05cdb80594922c50 94371840"
  "gems-geodawn-numerical-features.tif.part-002 d6f883ba8822207ac2765445737ecd2ecdfd2914 c375c4dbc40c59bbaece572b5e348700b75935f9a30c879c82b6417e0836f31c 94371840"
  "gems-geodawn-numerical-features.tif.part-003 976977b4ac84c4c9b6fec72495c4e512341de872 b164159e6d0cb2595bc9f63a948af2646b124114a9c5921880c7516092137320 94371840"
  "gems-geodawn-numerical-features.tif.part-004 41a7bb7b7603c1e7669d8cc8405cfeb5efb5cf0c fa0a6f9c936fac1d6f20ca37f5929b2d60bf7a80f3d477dcab886f941aee2696 41425484"
)

mkdir -p "$RAW"

if [[ -f "$OUT" ]]; then
  HAVE="$(sha256sum "$OUT" | cut -d' ' -f1)"
  if [[ "$HAVE" == "$EXPECTED" ]]; then
    echo "OK  training_features.tif already present and hash-verified ($EXPECTED)"
    exit 0
  fi
  echo "WARN existing $OUT hashes to $HAVE, re-downloading"
  rm -f "$OUT"
fi

: > "$OUT"
for row in "${PARTS[@]}"; do
  read -r name blob_sha want_sha want_bytes <<<"$row"
  tmp="$RAW/.part.tmp"
  echo "fetch $name ..."
  gh api "repos/$BRIDGE_REPO/git/blobs/$blob_sha" --jq .content | base64 -d > "$tmp"
  got_bytes=$(stat -c%s "$tmp")
  got_sha=$(sha256sum "$tmp" | cut -d' ' -f1)
  if [[ "$got_bytes" != "$want_bytes" ]]; then
    echo "FAIL $name size $got_bytes != $want_bytes"; exit 1
  fi
  if [[ "$got_sha" != "$want_sha" ]]; then
    echo "FAIL $name sha256 $got_sha != $want_sha"; exit 1
  fi
  cat "$tmp" >> "$OUT"
  rm -f "$tmp"
  echo "ok    $name ($got_bytes bytes, sha256 $got_sha)"
done

FINAL=$(sha256sum "$OUT" | cut -d' ' -f1)
if [[ "$FINAL" != "$EXPECTED" ]]; then
  echo "FAIL reassembled sha256 $FINAL != $EXPECTED"; exit 1
fi
echo "OK  data/raw/training_features.tif reassembled and hash-verified"
echo "    bytes  $(stat -c%s "$OUT")"
echo "    sha256 $FINAL"
