"""评估指标计算"""
from typing import List, Dict, Any
from collections import defaultdict


def compute_task_classification_metrics(results: List[Dict]) -> Dict:
    """按 task_type 计算分类 accuracy"""
    total = 0
    correct = 0
    per_type = defaultdict(lambda: {"total": 0, "correct": 0})
    confusion_matrix = defaultdict(lambda: defaultdict(int))  # expected -> predicted -> count

    for r in results:
        expected = r.get("expected_task_type")
        predicted = r.get("predicted_task_type")
        if expected is None:
            continue

        total += 1
        per_type[expected]["total"] += 1
        confusion_matrix[expected][predicted] += 1

        if expected == predicted:
            correct += 1
            per_type[expected]["correct"] += 1

    return {
        "overall_accuracy": correct / total if total else 0,
        "total": total,
        "correct": correct,
        "per_type_accuracy": {
            t: {
                "accuracy": v["correct"] / v["total"] if v["total"] else 0,
                "total": v["total"],
                "correct": v["correct"],
            }
            for t, v in per_type.items()
        },
        "confusion_matrix": {
            e: dict(p) for e, p in confusion_matrix.items()
        },
    }


def compute_entity_resolution_metrics(results: List[Dict]) -> Dict:
    """评估重名消歧的准确性"""
    relevant = [r for r in results if r.get("expected_ambiguity_reason")]
    if not relevant:
        return {"note": "No ambiguity test cases"}

    reason_correct = 0
    candidates_correct = 0

    for r in relevant:
        if r.get("predicted_ambiguity_reason") == r.get("expected_ambiguity_reason"):
            reason_correct += 1

        expected_count = r.get("expected_candidates_count")
        actual_count = r.get("actual_candidates_count")
        if expected_count is not None and expected_count == actual_count:
            candidates_correct += 1

    return {
        "total": len(relevant),
        "ambiguity_reason_accuracy": reason_correct / len(relevant),
        "candidates_count_accuracy": candidates_correct / len(relevant) if any(
            r.get("expected_candidates_count") for r in relevant) else None,
    }


def compute_semantic_retrieval_metrics(results: List[Dict]) -> Dict:
    """评估 semantic search 召回质量"""
    relevant = [r for r in results if
                r.get("category", "").startswith("retrieval_") or r.get("category", "").startswith("semantic_")]
    if not relevant:
        return {"note": "No semantic test cases"}

    # 1. Top-1 subfield 匹配率
    subfield_match_count = 0
    subfield_match_total = 0

    # 2. Top-1 score 分布
    top1_scores = []

    # 3. 低置信度召回的识别
    low_confidence_count = 0

    for r in relevant:
        top1_score = r.get("predicted_top1_score")
        if top1_score is not None:
            top1_scores.append(top1_score)
            if top1_score < 0.75:
                low_confidence_count += 1

        expected_subfields = r.get("expected_relevant_subfields")
        predicted_subfields = r.get("predicted_top1_subfield")
        if expected_subfields and predicted_subfields:
            subfield_match_total += 1
            if predicted_subfields in expected_subfields:
                subfield_match_count += 1

    return {
        "total_semantic_queries": len(relevant),
        "top1_subfield_match_rate": subfield_match_count / subfield_match_total if subfield_match_total else None,
        "subfield_match_total": subfield_match_total,
        "average_top1_score": sum(top1_scores) / len(top1_scores) if top1_scores else None,
        "min_top1_score": min(top1_scores) if top1_scores else None,
        "max_top1_score": max(top1_scores) if top1_scores else None,
        "low_confidence_count": low_confidence_count,
    }


def compute_latency_metrics(results: List[Dict]) -> Dict:
    """耗时统计"""
    by_category = defaultdict(list)
    for r in results:
        elapsed = r.get("elapsed_ms")
        if elapsed is None:
            continue
        category = r.get("category", "unknown")
        by_category[category].append(elapsed)

    def pct(arr, p):
        if not arr:
            return None
        s = sorted(arr)
        idx = int(len(s) * p / 100)
        return s[min(idx, len(s) - 1)]

    all_elapsed = [r.get("elapsed_ms") for r in results if r.get("elapsed_ms") is not None]

    return {
        "overall": {
            "count": len(all_elapsed),
            "avg_ms": sum(all_elapsed) / len(all_elapsed) if all_elapsed else 0,
            "p50_ms": pct(all_elapsed, 50),
            "p95_ms": pct(all_elapsed, 95),
            "min_ms": min(all_elapsed) if all_elapsed else 0,
            "max_ms": max(all_elapsed) if all_elapsed else 0,
        },
        "by_category": {
            cat: {
                "count": len(arr),
                "avg_ms": sum(arr) / len(arr),
                "p95_ms": pct(arr, 95),
            }
            for cat, arr in by_category.items()
        },
    }