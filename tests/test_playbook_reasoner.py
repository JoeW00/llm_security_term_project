import json

from soc_agent.reasoners.playbook import LLMPlaybookGenerator, TemplatePlaybookGenerator
from soc_agent.reasoning import PlaybookModel

VALID = json.dumps(
    {"containment": ["isolate host"], "eradication": ["reset creds"], "recovery": ["restore"]}
)


class StubClient:
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def complete(self, *, system, prompt):
        self.last_call = {"system": system, "prompt": prompt}
        return self._response


def test_template_generator_three_phases():
    pb = TemplatePlaybookGenerator().generate({})
    assert pb.model_dump().keys() == {"containment", "eradication", "recovery"}


def test_llm_generator_returns_validated_playbook():
    pb = LLMPlaybookGenerator(client=StubClient(VALID)).generate({"verdict": "true_positive"})
    assert isinstance(pb, PlaybookModel)
    assert pb.containment == ["isolate host"]


def test_llm_generator_feeds_critique_issues_into_prompt():
    client = StubClient(VALID)
    state = {
        "verdict": "true_positive",
        "critique": {"issues": ["add eradication step", "cite IOC"]},
    }
    LLMPlaybookGenerator(client=client).generate(state)
    prompt = client.last_call["prompt"]
    assert "add eradication step" in prompt
    assert "cite IOC" in prompt


def test_llm_generator_falls_back_on_malformed():
    pb = LLMPlaybookGenerator(client=StubClient("not json")).generate({})
    assert pb.model_dump().keys() == {"containment", "eradication", "recovery"}
