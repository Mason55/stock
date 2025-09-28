#!/bin/bash
# deploy.sh - Deployment script for stock analysis system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
COMPOSE_FILE=${1:-docker-compose.prod.yml}
ENV_FILE=${2:-.env}

echo -e "${BLUE}🚀 Stock Analysis System Deployment${NC}"
echo "============================================"

# Check if environment file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  Environment file not found: $ENV_FILE${NC}"
    echo "Creating from template..."
    cp .env.example "$ENV_FILE"
    echo -e "${RED}❗ Please edit $ENV_FILE with your configuration before deployment${NC}"
    exit 1
fi

# Check if docker-compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ Compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Pre-deployment checks...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All dependencies found${NC}"

# Build images if needed
echo -e "${YELLOW}🔨 Building images...${NC}"
if docker compose version &> /dev/null; then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
else
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
fi

# Deploy
echo -e "${YELLOW}🚀 Starting deployment...${NC}"
if docker compose version &> /dev/null; then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
else
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
fi

echo -e "${GREEN}✅ Deployment completed!${NC}"
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
if docker compose version &> /dev/null; then
    docker compose -f "$COMPOSE_FILE" ps
else
    docker-compose -f "$COMPOSE_FILE" ps
fi

echo ""
echo -e "${GREEN}🎉 Stock Analysis System is now running!${NC}"
echo "Access the application at: http://localhost:5000"
echo ""
echo "Useful commands:"
echo "  View logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "  Stop: docker-compose -f $COMPOSE_FILE down"
echo "  Restart: docker-compose -f $COMPOSE_FILE restart"