#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
image="mlids-secure-docker-m2-ci:${GITHUB_SHA:-local}"
container="mlids-secure-docker-m2-smoke-$$"
port="${CONTAINER_SMOKE_PORT:-18080}"

cleanup() {
    docker rm --force "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build --pull --tag "$image" "$repo_root"
docker run --detach \
    --name "$container" \
    --publish "127.0.0.1:${port}:8000" \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --cpus=1 \
    --memory=512m \
    --pids-limit=128 \
    "$image" >/dev/null

ready=false
for _ in $(seq 1 30); do
    if curl --silent --show-error --fail --max-time 3 "http://127.0.0.1:${port}/health" >/dev/null; then
        ready=true
        break
    fi
    sleep 1
done

if [[ "$ready" != true ]]; then
    docker logs "$container"
    exit 1
fi

python3 - "$repo_root/samples/sample_flow.json" "$port" <<'PY'
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sample = json.loads(Path(sys.argv[1]).read_text())
port = sys.argv[2]


def post(body):
    request = Request(
        f"http://127.0.0.1:{port}/predict",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


status, body = post(sample)
assert status == 200
assert body == {"prediction": "ATTACK", "class": 1, "confidence": 1.0}

status, body = post({})
assert status == 422
assert body["detail"]["message"] == "Feature map must contain exactly the stored model features"
PY
