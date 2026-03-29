"""
Batch test runner - runs tests file by file to reduce memory usage.

Usage:
    python run_tests.py              # Run all unit tests
    python run_tests.py phase1       # Run Phase 1 tests only
    python run_tests.py phase2       # Run Phase 2 tests only
    python run_tests.py e2e          # Run E2E tests (requires running server)
    python run_tests.py <filename>   # Run single test file
"""

import subprocess
import sys
import time
from pathlib import Path

# Test files grouped by phase
PHASE1_TESTS = [
    "tests/unit/test_settings.py",
    "tests/unit/test_constants.py",
    "tests/unit/test_exceptions.py",
    "tests/unit/test_exchanges.py",
    "tests/unit/test_models.py",
    "tests/unit/test_logger.py",
    "tests/unit/test_events.py",
]

PHASE2_TESTS = [
    "tests/unit/test_providers_base.py",
    "tests/unit/test_providers_binance_conn.py",
    "tests/unit/test_providers_binance_data.py",
    "tests/unit/test_normalizer_normalize.py",
    "tests/unit/test_normalizer_cache.py",
    "tests/unit/test_normalizer_init.py",
    "tests/unit/test_ws_basic.py",
    "tests/unit/test_ws_streaming.py",
    "tests/unit/test_rest_init.py",
    "tests/unit/test_rest_funding.py",
    "tests/unit/test_hist_basic.py",
    "tests/unit/test_hist_load.py",
    "tests/unit/test_collector_lifecycle.py",
    "tests/unit/test_collector_methods.py",
]

PHASE3_TESTS = [
    "tests/unit/test_ind_trend.py",
    "tests/unit/test_ind_momentum.py",
    "tests/unit/test_ind_volatility.py",
    "tests/unit/test_ind_volume.py",
    "tests/unit/test_ind_pipeline.py",
    "tests/unit/test_strat_base.py",
    "tests/unit/test_strat_momentum.py",
    "tests/unit/test_strat_mean_reversion.py",
    "tests/unit/test_strat_volume.py",
    "tests/unit/test_strat_smc_detect.py",
    "tests/unit/test_strat_smc_eval.py",
    "tests/unit/test_strat_funding.py",
    "tests/unit/test_regime.py",
    "tests/unit/test_aggregator_calc.py",
    "tests/unit/test_aggregator_flow.py",
    "tests/unit/test_phase3_integration.py",
]

PHASE4_TESTS = [
    "tests/unit/test_position_sizer.py",
    "tests/unit/test_stop_loss.py",
    "tests/unit/test_circuit_breaker_state.py",
    "tests/unit/test_circuit_breaker_triggers.py",
    "tests/unit/test_portfolio_risk.py",
    "tests/unit/test_portfolio_tracking.py",
    "tests/unit/test_risk_evaluator.py",
    "tests/unit/test_phase4_integration.py",
]

PHASE5_TESTS = [
    "tests/unit/test_feature_engineer.py",
    "tests/unit/test_feature_scaler.py",
    "tests/unit/test_ml_base.py",
    "tests/unit/test_xgboost_model.py",
    "tests/unit/test_regime_model.py",
    "tests/unit/test_anomaly_model.py",
    "tests/unit/test_onnx_predictor.py",
    "tests/unit/test_ml_enhancer.py",
    "tests/unit/test_trainer.py",
    "tests/unit/test_phase5_integration.py",
]

PHASE6_TESTS = [
    "tests/unit/test_order_manager.py",
    "tests/unit/test_paper_trader.py",
    "tests/unit/test_position_tracker.py",
    "tests/unit/test_executor.py",
    "tests/unit/test_live_trader.py",
    "tests/unit/test_phase6_integration.py",
]

PHASE7_TESTS = [
    "tests/unit/test_bt_metrics.py",
    "tests/unit/test_bt_simulator.py",
    "tests/unit/test_bt_engine.py",
    "tests/unit/test_bt_walkforward.py",
    "tests/unit/test_bt_montecarlo.py",
    "tests/unit/test_bt_optimizer.py",
    "tests/unit/test_bt_report.py",
    "tests/unit/test_phase7_integration.py",
]

PHASE8_TESTS = [
    "tests/unit/test_api_auth.py",
    "tests/unit/test_api_schemas.py",
    "tests/unit/test_api_deps.py",
    "tests/unit/test_api_main.py",
    "tests/unit/test_api_signals.py",
    "tests/unit/test_api_orders.py",
    "tests/unit/test_api_positions.py",
    "tests/unit/test_api_bot.py",
    "tests/unit/test_api_backtest.py",
    "tests/unit/test_api_settings.py",
    "tests/unit/test_api_websocket.py",
    "tests/unit/test_api_system.py",
    "tests/unit/test_phase8_integration.py",
]

PHASE10_TESTS = [
    "tests/unit/test_bot_service.py",
    "tests/unit/test_api_candles.py",
    "tests/unit/test_api_markets.py",
    "tests/unit/test_api_indicators.py",
]

# E2E tests -- require a running server at localhost:8000
# Run separately with: python run_tests.py e2e
E2E_TESTS = [
    "tests/e2e/test_server_health.py",
    "tests/e2e/test_api_crud.py",
    "tests/e2e/test_backtest_e2e.py",
]

PYTHON = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")


def run_test_file(test_file: str) -> tuple[bool, int, int]:
    """Run a single test file and return (success, passed, failed)."""
    result = subprocess.run(
        [PYTHON, "-m", "pytest", test_file, "-v", "--tb=short", "-q"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent),
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    passed = failed = 0
    for line in result.stdout.splitlines():
        if "passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed" and i > 0:
                    try:
                        passed = int(parts[i - 1])
                    except ValueError:
                        pass
                if p == "failed" and i > 0:
                    try:
                        failed = int(parts[i - 1])
                    except ValueError:
                        pass
    return result.returncode == 0, passed, failed


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "phase1":
        test_files = PHASE1_TESTS
    elif arg == "phase2":
        test_files = PHASE2_TESTS
    elif arg == "phase3":
        test_files = PHASE3_TESTS
    elif arg == "phase4":
        test_files = PHASE4_TESTS
    elif arg == "phase5":
        test_files = PHASE5_TESTS
    elif arg == "phase6":
        test_files = PHASE6_TESTS
    elif arg == "phase7":
        test_files = PHASE7_TESTS
    elif arg == "phase8":
        test_files = PHASE8_TESTS
    elif arg == "phase10":
        test_files = PHASE10_TESTS
    elif arg == "e2e":
        test_files = E2E_TESTS
    elif arg == "all":
        test_files = PHASE1_TESTS + PHASE2_TESTS + PHASE3_TESTS + PHASE4_TESTS + PHASE5_TESTS + PHASE6_TESTS + PHASE7_TESTS + PHASE8_TESTS + PHASE10_TESTS
    else:
        test_files = [arg]

    total_passed = 0
    total_failed = 0
    failed_files = []

    print(f"{'='*60}")
    print(f"  CryptoQuant Engine - Batch Test Runner")
    print(f"  Running {len(test_files)} test file(s)")
    print(f"{'='*60}\n")

    start = time.time()

    for i, test_file in enumerate(test_files, 1):
        name = Path(test_file).stem
        print(f"\n--- [{i}/{len(test_files)}] {name} ---")
        success, passed, failed = run_test_file(test_file)
        total_passed += passed
        total_failed += failed
        if not success:
            failed_files.append(test_file)

    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"  RESULTS: {total_passed} passed, {total_failed} failed ({elapsed:.1f}s)")
    if failed_files:
        print(f"  FAILED FILES:")
        for f in failed_files:
            print(f"    - {f}")
    else:
        print(f"  ALL TESTS PASSED")
    print(f"{'='*60}")

    sys.exit(1 if failed_files else 0)


if __name__ == "__main__":
    main()
