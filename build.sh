#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-ocr-server}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"

cd "$(dirname "$0")"

echo "=== Building ${IMAGE_NAME}:${IMAGE_TAG} ==="
docker build \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  -f "${DOCKERFILE}" \
  .

echo ""
echo "=== Build complete ==="
echo "Run:"
echo "  docker run --rm -p 8000:8000 \\"
echo "    -e MINIO_ENDPOINT=your-minio:9000 \\"
echo "    -e MINIO_ACCESS_KEY=... \\"
echo "    -e MINIO_SECRET_KEY=... \\"
echo "    -e VLM_SERVER_URL=http://your-vlm:8021 \\"
echo "    ${IMAGE_NAME}:${IMAGE_TAG}"
