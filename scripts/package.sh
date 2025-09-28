#!/bin/bash
# scripts/package.sh - 打包离线安装wheel

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
BUILD_TYPE="base"
WHEELS_DIR="wheels"
PLATFORM=$(python -c "import sysconfig; print(sysconfig.get_platform())")

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            BUILD_TYPE="$2"
            shift 2
            ;;
        --output)
            WHEELS_DIR="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --type     Package type: base, ml, dev, minimal (default: base)"
            echo "  --output   Output directory (default: wheels)"
            echo "  --platform Target platform (default: current)"
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

# Create output directory
mkdir -p "$WHEELS_DIR"

echo "📦 Packaging wheels for offline installation..."
echo "Package type: $BUILD_TYPE"
echo "Output directory: $WHEELS_DIR"
echo "Platform: $PLATFORM"

# Select requirements file
case $BUILD_TYPE in
    base)
        REQ_FILE="requirements-base.txt"
        ;;
    ml)
        REQ_FILE="requirements-ml.txt"
        ;;
    dev)
        REQ_FILE="requirements-dev.txt"
        ;;
    minimal)
        REQ_FILE="requirements-minimal.txt"
        ;;
    full)
        REQ_FILE="requirements.txt"
        ;;
    *)
        echo "❌ Unknown package type: $BUILD_TYPE"
        echo "Available types: base, ml, dev, minimal, full"
        exit 1
        ;;
esac

# Check if requirements file exists
if [ ! -f "$REQ_FILE" ]; then
    echo "❌ Requirements file not found: $REQ_FILE"
    exit 1
fi

echo "📋 Using requirements file: $REQ_FILE"

# Download wheels
echo "⬇️  Downloading wheels..."
pip wheel \
    -r "$REQ_FILE" \
    -c constraints.txt \
    -w "$WHEELS_DIR" \
    --platform "$PLATFORM" \
    --no-deps || true  # Continue even if some wheels fail

# Also create platform-independent wheels when possible
echo "⬇️  Downloading platform-independent wheels..."
pip wheel \
    -r "$REQ_FILE" \
    -c constraints.txt \
    -w "$WHEELS_DIR" \
    --no-deps || true

# Create install script
cat > "$WHEELS_DIR/install.sh" << EOF
#!/bin/bash
# Offline installation script
# Usage: ./install.sh [--upgrade]

UPGRADE=""
if [ "\$1" = "--upgrade" ]; then
    UPGRADE="--upgrade"
fi

echo "📦 Installing from local wheels..."
pip install \$UPGRADE --no-index --find-links . -r ../$REQ_FILE -c ../constraints.txt

echo "✅ Installation completed!"
EOF

chmod +x "$WHEELS_DIR/install.sh"

# Create requirements for wheel installation
cp "$REQ_FILE" "$WHEELS_DIR/"
cp constraints.txt "$WHEELS_DIR/"

# Show summary
echo "📊 Package summary:"
echo "Total wheels: $(ls -1 "$WHEELS_DIR"/*.whl 2>/dev/null | wc -l)"
echo "Total size: $(du -sh "$WHEELS_DIR" | cut -f1)"
echo ""
echo "🚀 To install offline:"
echo "  cd $WHEELS_DIR"
echo "  ./install.sh"
echo ""
echo "✅ Packaging completed successfully!"