#!/usr/bin/env python3
# test_query.py - 测试查询长江电力
import os
import sys
sys.path.append('.')

def test_chanjiang_power():
    """测试查询长江电力"""
    try:
        # 设置环境变量
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        # 导入并创建应用
        from src.app import create_app
        
        app = create_app()
        
        # 创建测试客户端
        with app.test_client() as client:
            print("=" * 50)
            print("🔍 查询长江电力 (600900.SH)")
            print("=" * 50)
            
            # 1. 健康检查
            print("\n1. 系统健康检查:")
            response = client.get('/api/stocks/health')
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"系统状态: {data.get('status', 'unknown')}")
                print(f"数据库状态: {data.get('database', 'unknown')}")
            
            # 2. 查询长江电力基本信息
            print("\n2. 长江电力基本信息:")
            response = client.get('/api/stocks/600900.SH')
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"股票代码: {data.get('code')}")
                print(f"公司名称: {data.get('name')}")
                print(f"所属行业: {data.get('industry')}")
                print(f"交易所: {data.get('exchange')}")
            else:
                print(f"查询失败: {response.get_json()}")
            
            # 3. 获取综合分析
            print("\n3. 长江电力综合分析:")
            response = client.get('/api/stocks/600900.SH/analysis')
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"股票代码: {data.get('stock_code')}")
                print(f"公司名称: {data.get('company_name')}")
                print(f"当前价格: {data.get('current_price')}")
                
                if 'technical_analysis' in data:
                    tech = data['technical_analysis']
                    print(f"技术分析趋势: {tech.get('overall_trend')}")
                    print(f"趋势强度: {tech.get('trend_strength')}")
                
                if 'recommendation' in data:
                    rec = data['recommendation']
                    print(f"投资建议: {rec.get('action')}")
                    print(f"风险等级: {rec.get('risk_level')}")
                    print(f"评分: {rec.get('score')}")
            else:
                print(f"分析失败: {response.get_json()}")
            
            # 4. 获取实时数据
            print("\n4. 长江电力实时数据:")
            response = client.get('/api/stocks/600900.SH/realtime')
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"当前价格: {data.get('current_price')}")
                print(f"价格变动: {data.get('price_change')}")
                print(f"成交量: {data.get('volume')}")
                print(f"市场状态: {data.get('market_status')}")
            else:
                print(f"实时数据获取失败: {response.get_json()}")
            
            # 5. 批量分析测试
            print("\n5. 批量分析测试 (长江电力 + 招商银行):")
            response = client.post('/api/stocks/batch_analysis', 
                                 json={
                                     'stock_codes': ['600900.SH', '600036.SH'],
                                     'analysis_types': ['technical']
                                 })
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"批次ID: {data.get('batch_id')}")
                print(f"总股票数: {data.get('total_stocks')}")
                print(f"成功分析: {data.get('completed')}")
                print(f"分析结果:")
                for result in data.get('results', []):
                    if result.get('status') == 'success':
                        print(f"  - {result.get('stock_code')}: {result.get('company_name')}")
                    else:
                        print(f"  - {result.get('stock_code')}: 分析失败")
            else:
                print(f"批量分析失败: {response.get_json()}")
    
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chanjiang_power()