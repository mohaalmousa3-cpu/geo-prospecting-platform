#!/usr/bin/env bash
# Regenerate Pydantic + TS types and the packaged schema copy from packages/schemas.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=packages/schemas/geo-contracts.schema.json
MODELS=packages/pycommon/src/geo_common/models
cp "$SRC" "$MODELS/geo-contracts.schema.json"
uv run datamodel-codegen --input "$SRC" --input-file-type jsonschema \
  --output "$MODELS/_generated.py" --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 --use-standard-collections --use-union-operator \
  --disable-timestamp --use-double-quotes --field-constraints \
  --use-annotated --custom-file-header '# Generated from packages/schemas by scripts/gen_schemas.sh. DO NOT EDIT.'
if [ -d apps/frontend/node_modules/json-schema-to-typescript ]; then
  mkdir -p apps/frontend/src/types
  (cd apps/frontend && npx --no-install json2ts -i ../../"$SRC" -o src/types/contracts.ts \
     --additionalProperties false --bannerComment '/* Generated from packages/schemas. DO NOT EDIT. */')
fi
