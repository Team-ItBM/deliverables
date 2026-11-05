#!/usr/bin/env bash
# Pushes the image for this commit unless the immutable tag already exists.
# ECR tags are immutable, so a rerun of the same commit must reuse the image
# instead of pushing a new build to the same tag. Any error other than "image
# not found" stops the deploy.
#
# Required env: REPOSITORY, TAG, IMAGE. Writes image=<ref> to GITHUB_OUTPUT.
set -euo pipefail

if result=$(aws ecr describe-images --repository-name "$REPOSITORY" --image-ids "imageTag=$TAG" \
              --query 'imageDetails[0].imageDigest' --output text 2>&1); then
  echo "Reusing existing image $TAG ($result)"
elif grep -q ImageNotFoundException <<<"$result"; then
  docker buildx build \
    --platform linux/arm64 \
    --build-arg SKIP_WEB=1 \
    --tag "$IMAGE" \
    --push \
    .
else
  echo "$result" >&2
  exit 1
fi
echo "image=$IMAGE" >> "$GITHUB_OUTPUT"
