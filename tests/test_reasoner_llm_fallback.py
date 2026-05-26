from soc_agent.reasoners.critic import LLMCritic
from soc_agent.reasoners.investigator import LLMInvestigator
from soc_agent.reasoners.playbook import LLMPlaybookGenerator
from soc_agent.reasoning import LLMClientError


class FailingClient:
    """complete 一律丟 LLMClientError，模擬 live 呼叫失敗。"""

    def complete(self, *, system, prompt):
        raise LLMClientError("boom")


def test_investigator_falls_back_on_llmclienterror():
    inv = LLMInvestigator(client=FailingClient()).assess({"severity": "high"})
    assert inv.verdict == "true_positive"  # rule-based fallback


def test_playbook_falls_back_on_llmclienterror():
    pb = LLMPlaybookGenerator(client=FailingClient()).generate({})
    assert pb.model_dump().keys() == {"containment", "eradication", "recovery"}


def test_critic_falls_back_on_llmclienterror():
    c = LLMCritic(client=FailingClient()).review({"critique_iterations": 0})
    assert c.complete is False  # deterministic fallback, first pass incomplete
