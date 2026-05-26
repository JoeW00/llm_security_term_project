import json

from soc_agent.reasoners.critic import DeterministicCritic, LLMCritic
from soc_agent.reasoning import CritiqueModel

PASSING = json.dumps(
    {"complete": True, "scores": {"coverage": 5, "executability": 4, "safety": 5}, "issues": []}
)
FAILING = json.dumps(
    {
        "complete": True,  # the LLM claims complete, but a low score must override to incomplete
        "scores": {"coverage": 2, "executability": 4, "safety": 5},
        "issues": ["containment too vague"],
    }
)


class StubClient:
    def __init__(self, response):
        self._response = response

    def complete(self, *, system, prompt):
        return self._response


def test_deterministic_incomplete_first_pass():
    c = DeterministicCritic().review({"critique_iterations": 0})
    assert c.complete is False
    assert c.issues  # has at least one issue


def test_deterministic_complete_second_pass():
    c = DeterministicCritic().review({"critique_iterations": 1})
    assert c.complete is True


def test_llm_critic_complete_when_all_scores_pass():
    c = LLMCritic(client=StubClient(PASSING)).review({"playbook": {"containment": ["x"]}})
    assert isinstance(c, CritiqueModel)
    assert c.complete is True


def test_llm_critic_threshold_overrides_complete_flag():
    c = LLMCritic(client=StubClient(FAILING)).review({"playbook": {}})
    assert c.complete is False
    assert "containment too vague" in c.issues


def test_llm_critic_falls_back_on_malformed():
    c = LLMCritic(client=StubClient("nonsense")).review({"critique_iterations": 0})
    assert c.complete is False
