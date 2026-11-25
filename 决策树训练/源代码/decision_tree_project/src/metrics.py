# -*- coding: utf-8 -*-
"""评价指标计算。

实验要求里明确要计算"准确率、精度（精确率）、召回率"，
这里统一封装，保证所有模型用同一套口径。
"""
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


def metric_row(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """计算一行指标（正类 = 有毒）。"""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro")),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro")),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "precision_poison": float(precision_score(y_true, y_pred, pos_label=1)),
        "recall_poison": float(recall_score(y_true, y_pred, pos_label=1)),
        "f1_poison": float(f1_score(y_true, y_pred, pos_label=1)),
    }


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> list[list[int]]:
    """混淆矩阵 [行=真实, 列=预测]。"""
    return confusion_matrix(y_true, y_pred).tolist()


def summary_table(rows: list[tuple]) -> str:
    """把多个模型的结果排版成控制台表格。

    rows 的每一项为 (模型名, 准确率, 精确率, 召回率, F1)。
    """
    header = f"{'模型':<24}{'准确率':>8}{'精确率':>8}{'召回率':>8}{'F1':>8}"
    lines = [header, "-" * len(header)]
    for name, acc, precision, recall, f1 in rows:
        lines.append(f"{name:<24}{acc:>8.4f}{precision:>8.4f}{recall:>8.4f}{f1:>8.4f}")
    return "\n".join(lines)
