#\!/bin/bash
# package.sh - Create portable package for deployment

VERSION=${1:-$(date +%Y%m%d-%H%M%S)}
PACKAGE_NAME="stock-analysis-${VERSION}"

echo "Creating package: ${PACKAGE_NAME}.tar.gz"

tar -czf "${PACKAGE_NAME}.tar.gz" \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='.env' \
    Dockerfile \
    docker-compose.prod.yml \
    build.sh \
    deploy.sh \
    .env.example \
    DEPLOYMENT.md \
    README.md \
    requirements.txt \
    src/ \
    config/ \
    frontend/

echo "✅ Package created: ${PACKAGE_NAME}.tar.gz"
echo "Size: $(du -h ${PACKAGE_NAME}.tar.gz | cut -f1)"
echo ""
echo "To deploy on another server:"
echo "  1. scp ${PACKAGE_NAME}.tar.gz user@server:/path/"
echo "  2. ssh user@server"
echo "  3. tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  4. cd stock && ./deploy.sh"
