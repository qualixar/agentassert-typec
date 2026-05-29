
from agentassert_typec_core.monitor.drift import DriftTracker


class TestDriftTracker:
    def test_initial_jsd_is_zero(self):
        dt = DriftTracker(window=10)
        assert dt.current_jsd() == 0.0

    def test_jsd_between_zero_and_one(self):
        dt = DriftTracker(window=5)
        for i in range(20):
            dt.update(tool=f"tool_{i % 4}")
        jsd = dt.current_jsd()
        assert 0.0 <= jsd <= 1.0

    def test_baseline_freezes(self):
        dt = DriftTracker(window=5)
        for i in range(5):
            dt.update(tool="Read")
        assert dt._baseline_counts is not None

    def test_window_eviction(self):
        dt = DriftTracker(window=3)
        tools = ["A", "B", "C", "D"]
        for tool in tools:
            dt.update(tool=tool)
        assert len(dt._call_sequence) == 3
        assert list(dt._call_sequence) == ["B", "C", "D"]

    def test_same_distribution_zero_jsd(self):
        dt = DriftTracker(window=5)
        for i in range(10):
            dt.update(tool="Read")
        jsd = dt.current_jsd()
        assert jsd < 0.01

    def test_different_distribution_positive_jsd(self):
        dt = DriftTracker(window=5)
        for i in range(5):
            dt.update(tool="Read")
        for i in range(5):
            dt.update(tool="Write")
        jsd = dt.current_jsd()
        assert jsd > 0.0

    def test_report(self):
        dt = DriftTracker(window=5)
        for i in range(10):
            dt.update(tool="Read")
        report = dt.report()
        assert report.current_jsd < 0.01
        assert report.window_size == 5
