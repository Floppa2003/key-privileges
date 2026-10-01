#!/usr/bin/env bash
# Install only into this directory. No sudo, no system service, no API key.
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
  echo 'This reproducible CPU package targets Linux x86_64 (for example ubuntu-24.04).' >&2; exit 2;
}
for tool in python3 curl tar zstd; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 2; }
done
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -p 'test_*.py' -v
mkdir -p .tools .cache setup-logs
archive=.tools/ollama-linux-amd64-0.34.4.tar.zst
sha=c238986e61d40c0cc5f4a9b9e40b9eea104350b77efa34741fc134e105cb9533
if [[ ! -f "$archive" ]]; then
  curl --fail --location --max-time 600 \
    https://github.com/ollama/ollama/releases/download/v0.34.4/ollama-linux-amd64.tar.zst \
    -o "$archive.part"
  mv "$archive.part" "$archive"
fi
printf '%s  %s\n' "$sha" "$archive" | sha256sum --check -
mkdir -p .tools/ollama
tar --zstd -xf "$archive" -C .tools/ollama
.venv/bin/python - <<'PY'
from pathlib import Path
import os
import subprocess
import benchmark as b
binary=b.ROOT/'.tools/ollama/bin/ollama'
with b.Server(binary,b.ROOT/'setup-logs/ollama.log') as server:
    response=server.client.get(b.BASE+'/api/tags',timeout=10)
    response.raise_for_status()
    model=os.environ.get('OLLAMA_MODEL', b.old.MODEL)
    matches=[m for m in response.json().get('models',[]) if m.get('name')==model]
    if not matches:
        with (b.ROOT/'setup-logs/model-pull.log').open('wb') as log:
            subprocess.run([str(binary),'pull',model],env=b.process_env(),
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
    b.old.save(b.ROOT/'setup-logs/runtime.json',b.check_runtime(server, model=model))
print('Setup verified. No document inference performed.')
PY
