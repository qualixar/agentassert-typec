
from agentassert_typec_core.monitor.violation_log import ViolationLog


class TestViolationLog:
    def test_record_hard(self):
        vl = ViolationLog()
        vl.record("tool_blocklist", "PreAction", "rm", "dangerous tool")
        assert len(vl.all_violations()) == 1
        v = vl.all_violations()[0]
        assert v["name"] == "tool_blocklist"
        assert v["kind"] == "hard"

    def test_record_soft(self):
        vl = ViolationLog()
        vl.record_soft("context_budget", "ContextWindow", "context", "too many tokens")
        assert len(vl.all_violations()) == 1
        v = vl.all_violations()[0]
        assert v["kind"] == "soft"

    def test_maxlen_enforced(self):
        vl = ViolationLog(maxlen=5)
        for i in range(10):
            vl.record(f"test_{i}", "PreAction", "tool", "reason")
        assert len(vl.all_violations()) == 5

    def test_thread_safe(self):
        import threading

        vl = ViolationLog(maxlen=1000)
        errors = []

        def record_many():
            try:
                for i in range(100):
                    vl.record(f"test_{i}", "PreAction", "tool", "reason")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(vl.all_violations()) == 1000
