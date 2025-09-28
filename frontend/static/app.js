// frontend/static/app.js - Frontend application logic
class StockAnalysisApp {
    constructor() {
        this.apiBaseUrl = 'http://localhost:5000/api/stocks';
        this.currentStock = null;
        this.currentChart = null;
        this.theme = localStorage.getItem('theme') || 'light';
        
        this.initializeApp();
        this.bindEvents();
        this.applyTheme();
    }
    
    initializeApp() {
        console.log('Initializing Stock Analysis System...');
        this.showToast('系统初始化完成', 'success');
    }
    
    bindEvents() {
        // Search functionality
        document.getElementById('search-btn').addEventListener('click', () => {
            const query = document.getElementById('stock-search').value.trim();
            if (query) {
                this.searchStock(query);
            }
        });
        
        // Enter key for search
        document.getElementById('stock-search').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = e.target.value.trim();
                if (query) {
                    this.searchStock(query);
                }
            }
        });
        
        // Theme toggle
        document.getElementById('theme-toggle').addEventListener('click', () => {
            this.toggleTheme();
        });
        
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            if (this.currentStock) {
                this.loadStockInfo(this.currentStock);
            }
        });
        
        // Generate recommendation
        document.getElementById('generate-recommendation').addEventListener('click', () => {
            if (this.currentStock) {
                this.generateRecommendation(this.currentStock);
            }
        });
        
        // Chart period buttons
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                
                if (this.currentStock) {
                    this.loadPriceChart(this.currentStock, e.target.dataset.period);
                }
            });
        });
        
        // Scanner toggle
        document.getElementById('toggle-scanner').addEventListener('click', () => {
            const controls = document.getElementById('scanner-controls');
            controls.style.display = controls.style.display === 'none' ? 'grid' : 'none';
        });
        
        // Scanner execution
        document.getElementById('scan-stocks').addEventListener('click', () => {
            this.executeStockScan();
        });
    }
    
    async searchStock(query) {
        this.showLoading(true);
        
        try {
            let stockCode = query.toUpperCase();
            
            // Check if already has exchange suffix
            if (/\.(SH|SZ|HK)$/.test(stockCode)) {
                // Already formatted
            } else if (/^[0-9]{1,5}$/.test(stockCode)) {
                // Pure numeric code - try to determine exchange
                if (stockCode.startsWith('60') || stockCode.startsWith('68') || stockCode.startsWith('90')) {
                    stockCode += '.SH';
                } else if (stockCode.startsWith('00') || stockCode.startsWith('30') || stockCode.startsWith('20')) {
                    stockCode += '.SZ';
                } else if (stockCode.length <= 4) {
                    // Assume HK stock for short codes
                    stockCode += '.HK';
                } else {
                    this.showToast('无法识别股票代码格式，请手动添加后缀（如：000001.SZ, 700.HK）', 'warning');
                    this.showLoading(false);
                    return;
                }
            } else {
                this.showToast('请输入正确的股票代码格式（如：000001.SZ, 700.HK）', 'warning');
                this.showLoading(false);
                return;
            }
            
            await this.loadStockInfo(stockCode);
            this.currentStock = stockCode;
            
        } catch (error) {
            this.showToast('搜索失败：' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    async loadStockInfo(stockCode) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${stockCode}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('股票不存在');
                }
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.displayStockInfo(data);
            
            // Load related data
            await Promise.all([
                this.loadPriceChart(stockCode, '1M'),
                this.loadFactorAnalysis(stockCode)
            ]);
            
            if (data.recommendation) {
                this.displayRecommendation(data.recommendation);
            }
            
        } catch (error) {
            this.showToast('加载股票信息失败：' + error.message, 'error');
        }
    }
    
    displayStockInfo(data) {
        const content = document.getElementById('stock-info-content');
        const changeClass = data.change_pct >= 0 ? 'price-positive' : 'price-negative';
        const changeSign = data.change_pct >= 0 ? '+' : '';
        
        content.innerHTML = `
            <div class="stock-info">
                <div class="stock-basic-info">
                    <h3>${data.name} (${data.code})</h3>
                    <div class="info-item">
                        <span class="info-label">交易所:</span>
                        <span class="info-value">${data.exchange}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">行业:</span>
                        <span class="info-value">${data.industry || '未知'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">市值:</span>
                        <span class="info-value">${this.formatNumber(data.market_cap, '亿')}</span>
                    </div>
                </div>
                <div class="stock-price-info">
                    <div class="info-item">
                        <span class="info-label">当前价格:</span>
                        <span class="info-value ${changeClass}">¥${data.current_price?.toFixed(2) || 'N/A'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">涨跌幅:</span>
                        <span class="info-value ${changeClass}">${changeSign}${data.change_pct?.toFixed(2) || 'N/A'}%</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">成交量:</span>
                        <span class="info-value">${this.formatNumber(data.volume, '万')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">更新时间:</span>
                        <span class="info-value">${data.last_updated ? new Date(data.last_updated).toLocaleString() : 'N/A'}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    async loadPriceChart(stockCode, period = '1M') {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${stockCode}/timeline?range=${period}`);
            const data = await response.json();
            
            if (data.data && data.data.length > 0) {
                this.renderChart(data.data);
            }
        } catch (error) {
            console.error('Failed to load chart data:', error);
        }
    }
    
    renderChart(priceData) {
        const canvas = document.getElementById('chart-canvas');
        const ctx = canvas.getContext('2d');
        
        // Destroy existing chart
        if (this.currentChart) {
            this.currentChart.destroy();
        }
        
        const labels = priceData.map(d => new Date(d.timestamp).toLocaleDateString());
        const prices = priceData.map(d => d.close);
        const volumes = priceData.map(d => d.volume);
        
        this.currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '收盘价',
                        data: prices,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        yAxisID: 'y'
                    },
                    {
                        label: '成交量',
                        data: volumes,
                        type: 'bar',
                        backgroundColor: 'rgba(100, 116, 139, 0.3)',
                        borderColor: 'rgba(100, 116, 139, 0.5)',
                        borderWidth: 1,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.datasetIndex === 0) {
                                    return `价格: ¥${context.parsed.y.toFixed(2)}`;
                                } else {
                                    return `成交量: ${(context.parsed.y / 10000).toFixed(1)}万`;
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '日期'
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: '价格 (¥)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: '成交量'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }
    
    async generateRecommendation(stockCode) {
        this.showLoading(true);
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/recommend/${stockCode}`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`生成建议失败 (${response.status})`);
            }
            
            const recommendation = await response.json();
            this.displayRecommendation(recommendation);
            this.showToast('投资建议已更新', 'success');
            
        } catch (error) {
            this.showToast('生成建议失败：' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    displayRecommendation(recommendation) {
        const content = document.getElementById('recommendation-content');
        const actionText = {
            'buy': '买入',
            'hold': '观望',
            'sell': '回避'
        };
        
        content.innerHTML = `
            <div class="recommendation">
                <div class="recommendation-action ${recommendation.action}">
                    ${actionText[recommendation.action] || recommendation.action}
                </div>
                <div class="confidence-container">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span>置信度</span>
                        <span>${(recommendation.confidence * 100).toFixed(1)}%</span>
                    </div>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${recommendation.confidence * 100}%"></div>
                    </div>
                </div>
                <div class="reasoning">
                    ${recommendation.reasoning || '暂无详细分析'}
                </div>
                <div style="margin-top: 15px; font-size: 12px; color: var(--text-secondary);">
                    生成时间: ${new Date(recommendation.timestamp).toLocaleString()}
                </div>
            </div>
        `;
    }
    
    async loadFactorAnalysis(stockCode) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${stockCode}/factors`);
            
            if (response.ok) {
                const data = await response.json();
                this.displayFactorAnalysis(data.features);
            }
        } catch (error) {
            console.error('Failed to load factor analysis:', error);
        }
    }
    
    displayFactorAnalysis(features) {
        const content = document.getElementById('factors-content');
        
        if (!features) {
            content.innerHTML = '<p class="placeholder">暂无因子分析数据</p>';
            return;
        }
        
        const factorItems = Object.entries(features).map(([key, value]) => {
            const displayName = this.getFactorDisplayName(key);
            const valueClass = this.getFactorValueClass(key, value);
            const formattedValue = this.formatFactorValue(key, value);
            
            return `
                <div class="factor-item">
                    <span class="factor-name">${displayName}</span>
                    <span class="factor-value ${valueClass}">${formattedValue}</span>
                </div>
            `;
        }).join('');
        
        content.innerHTML = `<div class="factors-list">${factorItems}</div>`;
    }
    
    async executeStockScan() {
        this.showLoading(true);
        
        try {
            const industry = document.getElementById('industry-filter').value;
            const minPrice = document.getElementById('min-price').value;
            const maxPrice = document.getElementById('max-price').value;
            const action = document.getElementById('action-filter').value;
            
            const params = new URLSearchParams();
            if (industry) params.append('industry', industry);
            if (minPrice) params.append('min_price', minPrice);
            if (maxPrice) params.append('max_price', maxPrice);
            if (action) params.append('action', action);
            params.append('limit', '20');
            
            const response = await fetch(`${this.apiBaseUrl}/scan?${params}`);
            const data = await response.json();
            
            this.displayScanResults(data.stocks);
            this.showToast(`找到 ${data.total_found} 只股票`, 'success');
            
        } catch (error) {
            this.showToast('筛选失败：' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    displayScanResults(stocks) {
        const container = document.getElementById('scanner-results');
        
        if (!stocks || stocks.length === 0) {
            container.innerHTML = '<p class="placeholder">未找到符合条件的股票</p>';
            return;
        }
        
        const resultsHtml = stocks.map(stock => {
            const changeClass = stock.change_pct >= 0 ? 'price-positive' : 'price-negative';
            const changeSign = stock.change_pct >= 0 ? '+' : '';
            const actionText = {
                'buy': '买入',
                'hold': '观望',
                'sell': '回避'
            };
            
            return `
                <div class="stock-result" onclick="app.searchStock('${stock.code}')">
                    <div class="stock-name-code">
                        <div class="stock-name">${stock.name}</div>
                        <div class="stock-code">${stock.code}</div>
                    </div>
                    <div>${stock.industry || 'N/A'}</div>
                    <div>¥${stock.current_price?.toFixed(2) || 'N/A'}</div>
                    <div class="${changeClass}">${changeSign}${stock.change_pct?.toFixed(2) || 'N/A'}%</div>
                    <div>${stock.recommendation ? actionText[stock.recommendation.action] || stock.recommendation.action : 'N/A'}</div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = resultsHtml;
    }
    
    // Utility methods
    getFactorDisplayName(key) {
        const names = {
            'price_momentum_5d': '5日动量',
            'price_momentum_20d': '20日动量',
            'ma_5_ratio': '5日均线比',
            'ma_20_ratio': '20日均线比',
            'rsi': 'RSI指标',
            'macd': 'MACD',
            'bb_position': '布林带位置',
            'volume_ratio': '量比',
            'volatility': '波动率',
            'avg_volume': '平均成交量',
            'price_std': '价格标准差'
        };
        return names[key] || key;
    }
    
    getFactorValueClass(key, value) {
        if (key.includes('momentum') || key === 'change_pct') {
            return value >= 0 ? 'factor-positive' : 'factor-negative';
        }
        return '';
    }
    
    formatFactorValue(key, value) {
        if (typeof value !== 'number') return 'N/A';
        
        if (key.includes('ratio') || key.includes('position')) {
            return value.toFixed(3);
        } else if (key.includes('momentum') || key === 'change_pct') {
            return value.toFixed(2) + '%';
        } else if (key === 'avg_volume') {
            return this.formatNumber(value, '万');
        } else {
            return value.toFixed(2);
        }
    }
    
    formatNumber(num, unit = '') {
        if (!num) return 'N/A';
        
        if (unit === '万') {
            return (num / 10000).toFixed(1) + '万';
        } else if (unit === '亿') {
            return (num / 100000000).toFixed(2) + '亿';
        }
        
        return num.toLocaleString();
    }
    
    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme();
        localStorage.setItem('theme', this.theme);
    }
    
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        const icon = document.querySelector('#theme-toggle i');
        icon.className = this.theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
    }
    
    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        overlay.style.display = show ? 'flex' : 'none';
    }
    
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div>${message}</div>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new StockAnalysisApp();
});