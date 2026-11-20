import pytest
from backend.drift import *
def test_same_distribution_has_zero_shift():
    a=distribution([.9]*100);assert population_stability(a,a)==0
def test_monitor_warms_up_then_detects_shift():
    monitor=DriftMonitor(distribution([.9]*100),window=10)
    for _ in range(9):assert monitor.update(.2)['drift_score'] is None
    assert monitor.update(.2)['model_drift']
def test_stationary_monitor_stays_clear():
    monitor=DriftMonitor(distribution([.9]*100),window=10)
    for _ in range(20):assert not monitor.update(.9)['model_drift']
def test_invalid_baseline_rejected():
    with pytest.raises(ValueError):DriftMonitor([0]*10)
