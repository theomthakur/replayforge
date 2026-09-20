import argparse
import yfinance as yf

from .optimizers.mean_variance import MeanVarianceOptimizer
from .optimizers.min_variance import MinVarianceOptimizer
from .optimizers.max_sharpe import MaxSharpeOptimizer
from .optimizers.risk_parity import RiskParityOptimizer
from .optimizers.black_litterman import BlackLittermanOptimizer
from .optimizers.max_diversification import MaxDiversificationOptimizer

from .covariance.shrinkage import ShrinkageCovariance
from .constraints.long_only import LongOnlyConstraint
from .constraints.position_limits import PositionLimitsConstraint

from .backtest.rolling import RollingBacktest
from .backtest.costs import TransactionCosts
from .backtest.engine import BacktestEngine
from .evals.metrics import PerformanceMetrics


def download_data():
    """Download standard US equity universe data (DJIA proxy)."""
    tickers = ['AAPL', 'MSFT', 'JPM', 'V', 'JNJ', 'WMT', 'PG', 'UNH', 'HD', 'CVX']
    data = yf.download(tickers, start="2015-01-01", end="2023-12-31")['Close']
    returns = data.pct_change().dropna()
    return returns


def main():
    parser = argparse.ArgumentParser(description='Portfolio Optimization Backtest')
    parser.add_argument('--optimizer', type=str, default='max_sharpe',
                        choices=['mean_variance', 'min_variance', 'max_sharpe',
                                 'risk_parity', 'black_litterman', 'max_diversification'],
                        help='Optimizer to use')
    args = parser.parse_args()

    print("Downloading data for US Equities...")
    returns = download_data()

    print("Setting up constraints...")
    constraints = [
        LongOnlyConstraint(),
        PositionLimitsConstraint(max_weight=0.30)
    ]

    print(f"Initializing {args.optimizer} optimizer...")
    if args.optimizer == 'mean_variance':
        opt = MeanVarianceOptimizer(target_return=0.10/252, constraints=constraints)
    elif args.optimizer == 'min_variance':
        opt = MinVarianceOptimizer(constraints=constraints)
    elif args.optimizer == 'max_sharpe':
        opt = MaxSharpeOptimizer(risk_free_rate=0.0, constraints=constraints)
    elif args.optimizer == 'risk_parity':
        opt = RiskParityOptimizer(constraints=constraints)
    elif args.optimizer == 'black_litterman':
        opt = BlackLittermanOptimizer(target_return=0.10/252, constraints=constraints)
    elif args.optimizer == 'max_diversification':
        opt = MaxDiversificationOptimizer(constraints=constraints)

    cov_est = ShrinkageCovariance()
    rolling = RollingBacktest(lookback_periods=36, rebalance_freq='ME')
    costs = TransactionCosts(bps=0.0010, impact_coeff=0.0)

    engine = BacktestEngine(
        returns=returns,
        optimizer=opt,
        cov_estimator=cov_est,
        rolling_backtest=rolling,
        tx_costs=costs
    )

    print("Running backtest...")
    results = engine.run()

    port_returns = results['returns']
    weights = results['weights']

    print("\\n--- Backtest Results ---")
    print(f"Annualized Return: {PerformanceMetrics.annualized_return(port_returns):.2%}")
    print(f"Annualized Vol:    {PerformanceMetrics.annualized_volatility(port_returns):.2%}")
    print(f"Sharpe Ratio:      {PerformanceMetrics.sharpe_ratio(port_returns):.2f}")
    print(f"Max Drawdown:      {PerformanceMetrics.max_drawdown(port_returns):.2%}")
    print(f"Average Eff N:     {PerformanceMetrics.average_effective_n(weights):.2f}")


if __name__ == '__main__':
    main()
