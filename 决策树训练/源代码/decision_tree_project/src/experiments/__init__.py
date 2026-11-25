# -*- coding: utf-8 -*-
"""扩展实验包：划分比例、难度梯度、代价敏感、结构稳定性。

这四个实验都属于"模型可信度/鲁棒性"分析，用来回应一个问题：
本数据集上几乎所有模型都接近 100%，那么模型到底是学到了规律，还是数据太简单？

顺序上先做划分比例实验——因为它是实验设置的前提（为什么选 7:3），
再依次检验数据难度、错误代价和结构稳定性。
"""
from . import cost_sensitive, difficulty, split_ratio, stability


def run_all(X, y, feature_names, output_dir):
    """依次运行四个扩展实验，返回结果字典（同时把图保存到 output_dir）。"""
    results = {}
    results["split_ratio"] = split_ratio.run(X, y, output_dir)
    results["difficulty"] = difficulty.run(X, y, output_dir)
    results["cost_sensitive"] = cost_sensitive.run(X, y, output_dir)
    results["stability"] = stability.run(X, y, feature_names, output_dir)
    return results
