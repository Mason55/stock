#!/bin/bash
# build.sh - Build and package script for stock analysis system

set -e

echo "🚀 Starting build process..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
IMAGE_NAME="stock-analysis"
VERSION=${1:-latest}
REGISTRY=${REGISTRY:-}

echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:${VERSION} .

if [ ! -z "$REGISTRY" ]; then
    echo -e "${YELLOW}Tagging image for registry...${NC}"
    docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${IMAGE_NAME}:${VERSION}
fi

echo -e "${GREEN}✅ Build completed successfully!${NC}"
echo "Image: ${IMAGE_NAME}:${VERSION}"

if [ ! -z "$REGISTRY" ]; then
    echo "Registry image: ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
    
    read -p "Push to registry? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Pushing to registry...${NC}"
        docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}
        echo -e "${GREEN}✅ Push completed!${NC}"
    fi
fi

echo -e "${GREEN}🎉 Build process completed!${NC}"