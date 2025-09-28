#!/bin/bash
# scripts/build.sh - 构建脚本支持不同场景

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
BUILD_TYPE="full"
PLATFORM="linux/amd64"
TAG="stock-analysis"
PUSH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            BUILD_TYPE="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --type     Build type: full, minimal (default: full)"
            echo "  --platform Target platform (default: linux/amd64)"
            echo "  --tag      Docker image tag (default: stock-analysis)"
            echo "  --push     Push image after build"
            echo "  -h, --help Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

echo "🏗️  Building Docker image..."
echo "Build type: $BUILD_TYPE"
echo "Platform: $PLATFORM"
echo "Tag: $TAG"

# Build based on type
case $BUILD_TYPE in
    full)
        echo "📦 Building full image with ML dependencies..."
        docker build \
            --platform "$PLATFORM" \
            --build-arg INSTALL_ML=true \
            -f build/docker/Dockerfile \
            -t "$TAG:latest" \
            -t "$TAG:full" \
            .
        ;;
    minimal)
        echo "📦 Building minimal image..."
        docker build \
            --platform "$PLATFORM" \
            -f build/docker/Dockerfile.minimal \
            -t "$TAG:minimal" \
            .
        ;;
    both)
        echo "📦 Building both images..."
        # Full image
        docker build \
            --platform "$PLATFORM" \
            --build-arg INSTALL_ML=true \
            -f build/docker/Dockerfile \
            -t "$TAG:latest" \
            -t "$TAG:full" \
            .
        # Minimal image
        docker build \
            --platform "$PLATFORM" \
            -f build/docker/Dockerfile.minimal \
            -t "$TAG:minimal" \
            .
        ;;
    *)
        echo "❌ Unknown build type: $BUILD_TYPE"
        echo "Available types: full, minimal, both"
        exit 1
        ;;
esac

# Show image sizes
echo "📊 Image sizes:"
docker images | grep "$TAG" | head -5

# Push if requested
if [ "$PUSH" = true ]; then
    echo "🚀 Pushing images..."
    if [ "$BUILD_TYPE" = "both" ]; then
        docker push "$TAG:latest"
        docker push "$TAG:full"
        docker push "$TAG:minimal"
    elif [ "$BUILD_TYPE" = "minimal" ]; then
        docker push "$TAG:minimal"
    else
        docker push "$TAG:latest"
        docker push "$TAG:full"
    fi
fi

echo "✅ Build completed successfully!"