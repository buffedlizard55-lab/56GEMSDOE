#!/bin/bash
# Mirrors every GEMSDOE* repo in the buffedlizard55-lab account that contains TIFs (sparse, blobless).
# Mirror every raster (.tif/.zip-free) committed under any GEMSDOE* repo of buffedlizard55-lab (sparse, blobless clone)
mkdir -p ${1:-/tmp/gems/registry} && cd ${1:-/tmp/gems/registry}
names=$(gh repo list buffedlizard55-lab --limit 200 --json name -q '.[].name' | grep -i gems)
for r in $names; do
  if [ -d "$r" ]; then continue; fi
  n=$(gh api "repos/buffedlizard55-lab/$r/git/trees/HEAD?recursive=1" -q '[.tree[] | select(.path|endswith(".tif"))] | length' 2>/dev/null)
  if [ -z "$n" ] || [ "$n" = "0" ]; then echo "$r tif=0"; continue; fi
  timeout 400 git clone -q --depth 1 --filter=blob:none --sparse https://github.com/buffedlizard55-lab/$r.git $r >/dev/null 2>&1 || { echo "$r CLONE_FAIL"; continue; }
  git -C $r sparse-checkout set --no-cone '*.tif' >/dev/null 2>&1
  git -C $r checkout -q 2>/dev/null
  echo "$r tif=$n files=$(find $r -name '*.tif' | wc -l)"
done
echo DONE
