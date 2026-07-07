"""
全球资产配置再平衡策略 - 多ETF回测系统
支持全球股票和债券多种标的组合
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# ========== ETF 配置 ==========
ETF_UNIVERSE = {
    # 股票类 - 美国
    'VTI': {'name': 'Vanguard美股总市场', 'type': 'stock', 'region': 'US', 'fee': 0.03},
    'VOO': {'name': 'Vanguard标普500', 'type': 'stock', 'region': 'US', 'fee': 0.03},
    'QQQ': {'name': '纳斯达克100', 'type': 'stock', 'region': 'US', 'fee': 0.20},
    
    # 股票类 - 国际
    'VXUS': {'name': 'Vanguard国际股票', 'type': 'stock', 'region': 'Intl', 'fee': 0.08},
    'VEA': {'name': 'Vanguard发达市场', 'type': 'stock', 'region': 'Developed', 'fee': 0.05},
    'VWO': {'name': 'Vanguard新兴市场', 'type': 'stock', 'region': 'Emerging', 'fee': 0.10},
    
    # 股票类 - 全球
    'VT': {'name': 'Vanguard全球股票', 'type': 'stock', 'region': 'Global', 'fee': 0.07},
    
    # 债券类 - 美国
    'BND': {'name': 'Vanguard全美债券', 'type': 'bond', 'region': 'US', 'fee': 0.03},
    'TLT': {'name': 'iShares 20年+国债', 'type': 'bond', 'region': 'US', 'duration': 'long', 'fee': 0.15},
    'IEF': {'name': 'iShares 7-10年国债', 'type': 'bond', 'region': 'US', 'duration': 'medium', 'fee': 0.15},
    'BIL': {'name': 'SPDR 1-3月国债', 'type': 'bond', 'region': 'US', 'duration': 'short', 'fee': 0.14},
    
    # 债券类 - 国际
    'BNDX': {'name': 'Vanguard国际债券', 'type': 'bond', 'region': 'Intl', 'fee': 0.08},
    'VWOB': {'name': 'Vanguard新兴市场债', 'type': 'bond', 'region': 'Emerging', 'fee': 0.15},
    
    # 通胀保护
    'TIP': {'name': 'iShares通胀保护债', 'type': 'bond', 'region': 'US', 'inflation': True, 'fee': 0.19},
}


# ========== 预设组合配置 ==========
PORTFOLIO_PRESETS = {
    'global_balanced': {
        'name': '全球平衡组合',
        'stocks': {'VT': 1.0},
        'bonds': {'BND': 0.7, 'BNDX': 0.3},
    },
    'us_focused': {
        'name': '美股专注组合',
        'stocks': {'VTI': 0.6, 'VXUS': 0.4},
        'bonds': {'BND': 0.8, 'TLT': 0.2},
    },
    'diversified': {
        'name': '高度分散组合',
        'stocks': {'VTI': 0.4, 'VEA': 0.3, 'VWO': 0.2, 'VXUS': 0.1},
        'bonds': {'BND': 0.5, 'BNDX': 0.3, 'TLT': 0.15, 'TIP': 0.05},
    },
    'conservative_bond': {
        'name': '保守债券组合',
        'stocks': {'VT': 1.0},
        'bonds': {'BND': 0.4, 'TLT': 0.3, 'BNDX': 0.2, 'TIP': 0.1},
    },
    'growth_stock': {
        'name': '成长股票组合',
        'stocks': {'VOO': 0.5, 'QQQ': 0.3, 'VXUS': 0.2},
        'bonds': {'BND': 0.6, 'IEF': 0.4},
    },
}


class DataManager:
    """ETF数据管理器"""
    
    def __init__(self, start_date='2005-01-01', end_date='2025-01-01'):
        self.start_date = start_date
        self.end_date = end_date
        self.data_cache = {}
        
    def download_data(self, symbols: List[str]) -> pd.DataFrame:
        """下载ETF数据"""
        print(f"\n📊 下载ETF数据 ({self.start_date} 至 {self.end_date})...")
        
        all_data = {}
        for symbol in symbols:
            if symbol in self.data_cache:
                all_data[symbol] = self.data_cache[symbol]
                continue
                
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=self.start_date, end=self.end_date)
                if not df.empty:
                    all_data[symbol] = df['Close']
                    self.data_cache[symbol] = df['Close']
                    print(f"  ✅ {symbol}: {len(df)}天")
                else:
                    print(f"  ❌ {symbol}: 无数据")
            except Exception as e:
                print(f"  ❌ {symbol}: {e}")
        
        prices = pd.DataFrame(all_data).dropna()
        print(f"\n✅ 数据准备完成: {len(prices)}个交易日")
        return prices
    
    def create_composite_index(self, prices: pd.DataFrame, 
                               weights: Dict[str, float]) -> pd.Series:
        """创建加权组合指数"""
        available = [s for s in weights.keys() if s in prices.columns]
        if not available:
            return None
        
        # 归一化权重
        total_weight = sum(weights[s] for s in available)
        normalized_weights = {s: weights[s]/total_weight for s in available}
        
        # 计算加权价格
        composite = pd.Series(0, index=prices.index)
        for symbol, weight in normalized_weights.items():
            normalized_price = prices[symbol] / prices[symbol].iloc[0]
            composite += normalized_price * weight
        
        return composite * 100  # 基准100


class PortfolioBuilder:
    """组合构建器"""
    
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
        
    def build_portfolio(self, preset_name: str, 
                       stock_alloc: float = 0.6) -> Tuple[pd.Series, pd.Series]:
        """构建股债组合"""
        if preset_name not in PORTFOLIO_PRESETS:
            raise ValueError(f"未知组合: {preset_name}")
        
        preset = PORTFOLIO_PRESETS[preset_name]
        
        # 获取所有需要的ETF
        all_etfs = list(preset['stocks'].keys()) + list(preset['bonds'].keys())
        prices = self.dm.download_data(all_etfs)
        
        # 构建股票组合
        stock_index = self.dm.create_composite_index(prices, preset['stocks'])
        
        # 构建债券组合
        bond_index = self.dm.create_composite_index(prices, preset['bonds'])
        
        return stock_index, bond_index, prices


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_value=100000):
        self.initial_value = initial_value
        
    def run_backtest(self, stock_prices: pd.Series, bond_prices: pd.Series,
                    stock_target: float, threshold: float = None,
                    rebalance_freq: str = 'buy_hold') -> Dict:
        """运行回测"""
        bond_target = 1 - stock_target
        
        # 初始化持仓
        stock_shares = (self.initial_value * stock_target) / stock_prices.iloc[0]
        bond_shares = (self.initial_value * bond_target) / bond_prices.iloc[0]
        
        portfolio_values = []
        stock_weights = []
        rebalance_count = 0
        
        for i in range(len(stock_prices)):
            # 计算当前价值
            stock_val = stock_shares * stock_prices.iloc[i]
            bond_val = bond_shares * bond_prices.iloc[i]
            total_val = stock_val + bond_val
            
            current_weight = stock_val / total_val if total_val > 0 else stock_target
            stock_weights.append(current_weight)
            
            # 检查再平衡
            need_rebalance = False
            if i == 0:
                need_rebalance = True
            elif rebalance_freq == 'buy_hold':
                need_rebalance = False
            elif threshold and abs(current_weight - stock_target) > threshold:
                need_rebalance = True
            elif rebalance_freq == 'yearly':
                if i > 0 and stock_prices.index[i].year != stock_prices.index[i-1].year:
                    need_rebalance = True
            
            if need_rebalance:
                stock_shares = (total_val * stock_target) / stock_prices.iloc[i]
                bond_shares = (total_val * bond_target) / bond_prices.iloc[i]
                rebalance_count += 1
            
            portfolio_values.append(total_val)
        
        # 计算指标
        portfolio_series = pd.Series(portfolio_values, index=stock_prices.index)
        daily_returns = portfolio_series.pct_change().dropna()
        
        total_return = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) - 1
        years = len(daily_returns) / 252
        annual_return = (1 + total_return) ** (1/years) - 1
        annual_vol = daily_returns.std() * np.sqrt(252)
        
        # 下行波动（索提诺比率用）
        downside_returns = daily_returns[daily_returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        
        # 夏普比率
        sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0
        
        # 索提诺比率
        sortino = (annual_return - 0.02) / downside_vol if downside_vol > 0 else 0
        
        # 最大回撤
        cummax = portfolio_series.cummax()
        drawdown = (portfolio_series - cummax) / cummax
        max_dd = drawdown.min()
        
        # 卡玛比率
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0
        
        return {
            'portfolio_value': portfolio_series,
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'downside_volatility': downside_vol,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_dd,
            'calmar_ratio': calmar,
            'rebalance_count': rebalance_count,
            'stock_weights': pd.Series(stock_weights, index=stock_prices.index),
            'drawdown': drawdown,
        }


class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self, backtest_engine: BacktestEngine):
        self.engine = backtest_engine
        
    def grid_search(self, stock_prices: pd.Series, bond_prices: pd.Series,
                   stock_allocs: List[float], thresholds: List[float]) -> pd.DataFrame:
        """网格搜索最优参数"""
        results = []
        
        total = len(stock_allocs) * len(thresholds)
        count = 0
        
        for alloc in stock_allocs:
            for threshold in thresholds:
                count += 1
                print(f"  测试 {count}/{total}: 股票{alloc*100:.0f}% 阈值{threshold*100:.0f}%", end='\r')
                
                result = self.engine.run_backtest(
                    stock_prices, bond_prices, 
                    alloc, threshold
                )
                
                results.append({
                    'stock_alloc': alloc,
                    'threshold': threshold,
                    'annual_return': result['annual_return'],
                    'volatility': result['annual_volatility'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'sortino_ratio': result['sortino_ratio'],
                    'max_drawdown': result['max_drawdown'],
                    'calmar_ratio': result['calmar_ratio'],
                    'rebalance_count': result['rebalance_count'],
                    'total_return': result['total_return'],
                })
        
        print(f"\n  ✅ 完成 {total} 组参数测试")
        return pd.DataFrame(results)
    
    def find_best_params(self, results_df: pd.DataFrame, metric='sharpe_ratio') -> Dict:
        """找出最优参数"""
        if metric not in results_df.columns:
            raise ValueError(f"未知指标: {metric}")
        
        best_idx = results_df[metric].idxmax()
        best = results_df.loc[best_idx]
        
        return {
            'metric': metric,
            'stock_alloc': best['stock_alloc'],
            'threshold': best['threshold'],
            'value': best[metric],
            'details': best.to_dict()
        }


def run_full_analysis():
    """运行完整分析"""
    print("=" * 80)
    print("🚀 全球资产配置再平衡策略 - 20年回测")
    print("=" * 80)
    
    # 初始化组件
    dm = DataManager()
    pb = PortfolioBuilder(dm)
    engine = BacktestEngine()
    optimizer = ParameterOptimizer(engine)
    
    # 所有测试结果
    all_results = {}
    
    # 测试每个预设组合
    for preset_key, preset_config in PORTFOLIO_PRESETS.items():
        print(f"\n{'=' * 80}")
        print(f"📊 测试组合: {preset_config['name']}")
        print(f"{'=' * 80}")
        
        # 构建组合
        try:
            stock_idx, bond_idx, prices = pb.build_portfolio(preset_key)
            if stock_idx is None or bond_idx is None:
                print(f"  ⚠️ 数据不足，跳过")
                continue
        except Exception as e:
            print(f"  ❌ 构建失败: {e}")
            continue
        
        # 参数网格
        stock_allocs = [0.4, 0.5, 0.6, 0.7, 0.8]
        thresholds = [0.03, 0.05, 0.10, 0.15, 0.20]
        
        # 网格搜索
        print(f"\n🔍 参数网格搜索 ({len(stock_allocs)} × {len(thresholds)} = {len(stock_allocs)*len(thresholds)} 组合)...")
        results_df = optimizer.grid_search(stock_idx, bond_idx, stock_allocs, thresholds)
        
        all_results[preset_key] = results_df
        
        # 找出最优
        print(f"\n🏆 最优参数组合:")
        for metric in ['sharpe_ratio', 'calmar_ratio', 'annual_return']:
            best = optimizer.find_best_params(results_df, metric)
            print(f"  • 最高{metric}: 股票{best['stock_alloc']*100:.0f}% 阈值{best['threshold']*100:.0f}% = {best['value']:.3f}")
    
    return all_results


if __name__ == "__main__":
    results = run_full_analysis()
    print("\n" + "=" * 80)
    print("✅ 分析完成!")
    print("=" * 80)
