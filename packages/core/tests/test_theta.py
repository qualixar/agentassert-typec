
from agentassert_typec_core.monitor.theta import ThetaScorer


class TestThetaScorer:
    def test_default_theta_is_one(self):
        scorer = ThetaScorer()
        assert scorer.compute() == 1.0

    def test_apply_penalty_reduces_score(self):
        scorer = ThetaScorer()
        scorer.apply_penalty(0.3)
        assert scorer.compute() < 1.0
        assert scorer.compute() == 0.7

    def test_compute_clamps_to_zero(self):
        scorer = ThetaScorer()
        scorer.apply_penalty(5.0)
        assert scorer.compute() == 0.0

    def test_compute_clamps_to_one(self):
        scorer = ThetaScorer()
        scorer.record_compliance(1.0, 1.0)
        assert scorer.compute() == 1.0

    def test_violations_reduce_score(self):
        scorer = ThetaScorer()
        scorer.record_violation()
        scorer.record_violation()
        theta = scorer.compute()
        assert theta < 1.0

    def test_compliance_affects_score(self):
        scorer = ThetaScorer()
        scorer.record_compliance(0.5, 0.5)
        theta = scorer.compute()
        assert theta < 1.0

    def test_recovery_success_improves_score(self):
        scorer = ThetaScorer()
        scorer.record_recovery(True)
        theta = scorer.compute()
        assert theta == 1.0

    def test_multiple_penalties(self):
        scorer = ThetaScorer()
        scorer.apply_penalty(0.1)
        scorer.apply_penalty(0.1)
        scorer.apply_penalty(0.1)
        assert scorer.compute() == 0.7
