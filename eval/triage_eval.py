"""分流分類器評估：Accuracy / per-class F1 / macro-F1 / 混淆矩陣（純 Python）。

`evaluate` 對任一符合 Classifier 介面的物件計分；`ablation` 並列多個分類器，
產出微調本地 vs 雲端零樣本的比較。指標計算純 Python、無外部依賴、可離線測試。
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from soc_agent.classifier import Classifier


@dataclass
class Metrics:
    """單一目標欄位（alert_type 或 severity）的評估結果。"""

    accuracy: float
    macro_f1: float
    per_class_f1: dict[str, float]
    confusion: dict[str, dict[str, int]]


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """讀取 JSONL 標註留出集：每行一個 {'alert': {...}, 'expected': {...}}。"""
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _f1_per_class(confusion: dict[str, dict[str, int]], labels: list[str]) -> dict[str, float]:
    """由混淆矩陣計算每類 F1。"""
    f1s: dict[str, float] = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels) - tp
        fn = sum(confusion[label][other] for other in labels) - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        denom = precision + recall
        f1s[label] = (2 * precision * recall / denom) if denom else 0.0
    return f1s


def evaluate(classifier: Classifier, records: list[dict[str, Any]], target: str) -> Metrics:
    """對 target 欄位（'alert_type' 或 'severity'）計分。"""
    raw_confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    labels: set[str] = set()
    correct = 0
    for rec in records:
        expected = rec["expected"][target]
        predicted = getattr(classifier.classify(rec["alert"]), target)
        labels.update((expected, predicted))
        raw_confusion[expected][predicted] += 1
        if expected == predicted:
            correct += 1

    label_list = sorted(labels)
    confusion = {a: {b: raw_confusion[a][b] for b in label_list} for a in label_list}
    per_class = _f1_per_class(confusion, label_list)
    macro_f1 = sum(per_class.values()) / len(per_class) if per_class else 0.0
    accuracy = correct / len(records) if records else 0.0
    return Metrics(
        accuracy=accuracy, macro_f1=macro_f1, per_class_f1=per_class, confusion=confusion
    )


def ablation(
    classifiers: dict[str, Classifier],
    records: list[dict[str, Any]],
    target: str,
) -> dict[str, Metrics]:
    """對每個具名分類器跑 evaluate，回傳 name -> Metrics 的並列結果。"""
    return {name: evaluate(clf, records, target) for name, clf in classifiers.items()}
