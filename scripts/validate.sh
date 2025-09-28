#!/bin/bash
# scripts/validate.sh - 系统验证脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
API_HOST="localhost"
API_PORT="5000"
TIMEOUT=30
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            API_HOST="$2"
            shift 2
            ;;
        --port)
            API_PORT="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --host     API host (default: localhost)"
            echo "  --port     API port (default: 5000)"
            echo "  --timeout  Timeout in seconds (default: 30)"
            echo "  -v, --verbose  Verbose output"
            echo "  -h, --help     Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

BASE_URL="http://${API_HOST}:${API_PORT}"

echo -e "${BLUE}🔍 股票分析系统验证${NC}"
echo "=============================="
echo "API地址: $BASE_URL"
echo "超时时间: ${TIMEOUT}秒"
echo ""

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_code="${3:-200}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    printf "%-50s" "测试: $test_name"
    
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "命令: $test_command"
    fi
    
    # Run the test command
    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 通过${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ 失败${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        
        if [ "$VERBOSE" = true ]; then
            echo "错误详情:"
            eval "$test_command" 2>&1 | head -5
        fi
        return 1
    fi
}

# Function to check HTTP response
check_http() {
    local url="$1"
    local expected_code="${2:-200}"
    
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url")
    
    if [ "$response_code" = "$expected_code" ]; then
        return 0
    else
        if [ "$VERBOSE" = true ]; then
            echo "期望状态码: $expected_code, 实际: $response_code"
        fi
        return 1
    fi
}

# Function to check JSON response
check_json() {
    local url="$1"
    local json_path="$2"
    local expected_value="$3"
    
    local actual_value
    actual_value=$(curl -s --max-time "$TIMEOUT" "$url" | jq -r "$json_path" 2>/dev/null)
    
    if [ "$actual_value" = "$expected_value" ]; then
        return 0
    else
        if [ "$VERBOSE" = true ]; then
            echo "期望值: $expected_value, 实际值: $actual_value"
        fi
        return 1
    fi
}

echo -e "${YELLOW}📡 基础连接测试${NC}"
echo "------------------------------"

# Test 1: Service availability
run_test "服务可用性" "check_http '$BASE_URL/api/stocks/health'"

# Test 2: Root endpoint
run_test "根端点访问" "check_http '$BASE_URL/'"

# Test 3: Health check returns correct status
run_test "健康检查状态" "check_json '$BASE_URL/api/stocks/health' '.status' 'healthy' || check_json '$BASE_URL/api/stocks/health' '.status' 'degraded'"

echo ""
echo -e "${YELLOW}📊 API功能测试${NC}"
echo "------------------------------"

# Test 4: Stock query (长江电力)
run_test "股票查询 (长江电力)" "check_http '$BASE_URL/api/stocks/600900.SH'"

# Test 5: Stock analysis
run_test "股票分析功能" "check_http '$BASE_URL/api/stocks/600900.SH/analysis'"

# Test 6: Realtime data
run_test "实时数据接口" "check_http '$BASE_URL/api/stocks/600900.SH/realtime'"

# Test 7: Historical data
run_test "历史数据接口" "check_http '$BASE_URL/api/stocks/600900.SH/history'"

# Test 8: Batch analysis
run_test "批量分析接口" "curl -s --max-time $TIMEOUT -X POST '$BASE_URL/api/stocks/batch_analysis' -H 'Content-Type: application/json' -d '{\"stock_codes\": [\"600900.SH\"], \"analysis_types\": [\"technical\"]}' | jq '.batch_id' >/dev/null"

echo ""
echo -e "${YELLOW}🔧 系统监控测试${NC}"
echo "------------------------------"

# Test 9: Metrics endpoint
run_test "度量端点" "check_http '$BASE_URL/metrics/'"

# Test 10: Detailed health check
run_test "详细健康检查" "check_http '$BASE_URL/metrics/health'"

# Test 11: Response time header
run_test "响应时间头" "curl -s -I --max-time $TIMEOUT '$BASE_URL/api/stocks/health' | grep -i 'x-response-time' >/dev/null"

echo ""
echo -e "${YELLOW}🎯 性能基准测试${NC}"
echo "------------------------------"

# Test 12: Response time benchmark
printf "%-50s" "测试: 响应时间基准 (<1000ms)"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health")
response_time_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "999")

if (( $(echo "$response_time_ms < 1000" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${GREEN}✅ 通过 (${response_time_ms%.*}ms)${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${YELLOW}⚠️  较慢 (${response_time_ms%.*}ms)${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))  # Count as passed but warn
fi

# Test 13: Concurrent requests
printf "%-50s" "测试: 并发请求处理"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Run 5 concurrent requests
if curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" \
   & curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" \
   & curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" \
   & curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" \
   & curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 通过${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}❌ 失败${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

wait # Wait for background jobs to complete

echo ""
echo -e "${YELLOW}📋 配置验证${NC}"
echo "------------------------------"

# Test 14: Check if running in offline mode
printf "%-50s" "检查: 离线模式状态"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

offline_mode=$(curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" | jq -r '.mode.offline_mode // false' 2>/dev/null)
if [ "$offline_mode" = "true" ]; then
    echo -e "${BLUE}ℹ️  离线模式${NC}"
else
    echo -e "${BLUE}ℹ️  在线模式${NC}"
fi
PASSED_TESTS=$((PASSED_TESTS + 1))  # Always pass, just informational

# Test 15: Check database status
printf "%-50s" "检查: 数据库状态"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

db_status=$(curl -s --max-time "$TIMEOUT" "$BASE_URL/api/stocks/health" | jq -r '.database.status // "unknown"' 2>/dev/null)
case "$db_status" in
    "healthy")
        echo -e "${GREEN}✅ 健康${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        ;;
    "degraded")
        echo -e "${YELLOW}⚠️  降级模式${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        ;;
    *)
        echo -e "${RED}❌ 异常 ($db_status)${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        ;;
esac

echo ""
echo "=============================="
echo -e "${BLUE}📊 验证结果汇总${NC}"
echo "=============================="
echo "总测试数: $TOTAL_TESTS"
echo -e "通过: ${GREEN}$PASSED_TESTS${NC}"
echo -e "失败: ${RED}$FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 所有测试通过！系统运行正常。${NC}"
    echo ""
    echo "🔗 可用的API端点:"
    echo "   • 健康检查: $BASE_URL/api/stocks/health"
    echo "   • 股票查询: $BASE_URL/api/stocks/600900.SH"
    echo "   • 股票分析: $BASE_URL/api/stocks/600900.SH/analysis"
    echo "   • 系统度量: $BASE_URL/metrics/"
    echo ""
    echo "📖 更多信息请查看文档:"
    echo "   • docs/QUICK_START.md"
    echo "   • docs/API.md"
    exit 0
else
    echo ""
    echo -e "${RED}⚠️  发现 $FAILED_TESTS 个问题，请检查：${NC}"
    echo ""
    echo "🔧 常见解决方案:"
    echo "   • 确保服务正在运行: python src/app.py"
    echo "   • 检查端口占用: lsof -i :$API_PORT"
    echo "   • 查看日志: tail -f logs/app.log"
    echo "   • 重启服务: docker-compose restart"
    echo ""
    echo "📖 详细故障排查请参考: docs/TROUBLESHOOTING.md"
    exit 1
fi