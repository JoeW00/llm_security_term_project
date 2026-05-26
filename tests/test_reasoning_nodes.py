"""Task 5 TDD：驗證 investigate/playbook/critique 節點可注入推理器，反思迴圈正常收斂。"""

from soc_agent import nodes
from soc_agent.graph import build_graph
from soc_agent.reasoning import CritiqueModel, Investigation, PlaybookModel, RubricScores

HIGH = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force",
    "indicators": ["203.0.113.45"],
    "raw": {},
}


class FakeInvestigator:
    def assess(self, state):
        return Investigation(verdict="false_positive", confidence=0.1, rationale="fake")


class FakePlaybookGenerator:
    """記錄每次 generate 收到的 critique issues，用來驗證回饋有進迴圈。"""

    def __init__(self):
        self.seen_issues = []

    def generate(self, state):
        self.seen_issues.append(list(state.get("critique", {}).get("issues", [])))
        return PlaybookModel(containment=["c"], eradication=["e"], recovery=["r"])


class ScriptedCritic:
    """前 N 次回不完整（附 issues），其後回完整。"""

    def __init__(self, fail_times):
        self._fail_times = fail_times
        self.calls = 0

    def review(self, state):
        self.calls += 1
        if self.calls <= self._fail_times:
            return CritiqueModel(
                complete=False,
                scores=RubricScores(coverage=2, executability=2, safety=3),
                issues=["add eradication step"],
            )
        return CritiqueModel(
            complete=True, scores=RubricScores(coverage=5, executability=5, safety=5), issues=[]
        )


def test_investigate_uses_injected_investigator():
    out = nodes.investigate({"severity": "high"}, investigator=FakeInvestigator())
    assert out["verdict"] == "false_positive"
    assert out["confidence"] == 0.1
    assert out["rationale"] == "fake"


def test_investigate_default_rule_based_writes_rationale():
    out = nodes.investigate({"severity": "high"})
    assert out["verdict"] == "true_positive"
    assert "rationale" in out


def test_playbook_uses_injected_generator():
    gen = FakePlaybookGenerator()
    out = nodes.playbook({"verdict": "true_positive"}, generator=gen)
    assert set(out["playbook"]) == {"containment", "eradication", "recovery"}


def test_critique_uses_injected_critic_and_increments():
    out = nodes.critique({"critique_iterations": 0}, critic=ScriptedCritic(fail_times=0))
    assert out["critique_iterations"] == 1
    assert out["critique"]["complete"] is True


def test_build_graph_closed_reflection_loop():
    gen = FakePlaybookGenerator()
    critic = ScriptedCritic(fail_times=1)  # incomplete once, then complete -> loops once
    graph = build_graph(playbook_gen=gen, critic=critic)
    result = graph.invoke({"alert": HIGH, "critique_iterations": 0})
    assert critic.calls == 2
    assert len(gen.seen_issues) == 2
    assert gen.seen_issues[1] == ["add eradication step"]
    assert result["final_report"] is not None


def test_build_graph_loop_caps_at_max_iterations():
    from soc_agent.state import MAX_CRITIQUE_ITERATIONS

    never_complete = ScriptedCritic(fail_times=99)
    graph = build_graph(critic=never_complete)
    result = graph.invoke({"alert": HIGH, "critique_iterations": 0})
    assert result["critique_iterations"] == MAX_CRITIQUE_ITERATIONS
