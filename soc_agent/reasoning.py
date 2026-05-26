"""推理邊界：研判 / 劇本 / 批判的契約、Pydantic 結果模型與 LLM 輸出解析。

三個推理器節點透過此處的 Protocol 取得已驗證結果。正式環境注入雲端 LLM 後端，
測試注入替身，裸呼叫退回確定性預設（見 `soc_agent/reasoners/`）。
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from soc_agent.state import IncidentState, Verdict


class LLMClientError(Exception):
    """LLMClient.complete 的失敗：呼叫或回應解析出錯（網路 / SDK / 空回應等）。

    LLMClient 實作在任何失敗時丟此例外，呼叫端（reasoner）據此退回確定性預設。
    """


class Investigation(BaseModel):
    """研判結果：真偽判定 + 信心度 + 理由。"""

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class PlaybookModel(BaseModel):
    """三階段處置劇本。"""

    containment: list[str]
    eradication: list[str]
    recovery: list[str]


class RubricScores(BaseModel):
    """劇本品質評分（各維度 0–5）。"""

    coverage: int = Field(ge=0, le=5)
    executability: int = Field(ge=0, le=5)
    safety: int = Field(ge=0, le=5)


class CritiqueModel(BaseModel):
    """批判結果：是否完整 + rubric 分數 + 待改 issues。"""

    complete: bool
    scores: RubricScores
    issues: list[str] = Field(default_factory=list)


@runtime_checkable
class LLMClient(Protocol):
    """最小 LLM 介面：吃 system/prompt，回傳模型輸出文字。"""

    def complete(self, *, system: str, prompt: str) -> str: ...


@runtime_checkable
class Investigator(Protocol):
    """研判推理器：讀唯讀 state，回傳已驗證 Investigation。"""

    def assess(self, state: IncidentState) -> Investigation: ...


@runtime_checkable
class PlaybookGenerator(Protocol):
    """劇本推理器：讀唯讀 state，回傳已驗證 PlaybookModel。"""

    def generate(self, state: IncidentState) -> PlaybookModel: ...


@runtime_checkable
class Critic(Protocol):
    """批判推理器：讀唯讀 state，回傳已驗證 CritiqueModel。"""

    def review(self, state: IncidentState) -> CritiqueModel: ...


def parse_json[T: BaseModel](text: str, model: type[T]) -> T:
    """解析 LLM 輸出文字為已驗證模型。

    失敗（非 JSON、缺鍵、值越界等）拋 ValueError 系例外（`json.JSONDecodeError`
    與 Pydantic `ValidationError` 皆為 ValueError 子類），由呼叫端決定退路。
    """
    return model.model_validate(json.loads(text))
