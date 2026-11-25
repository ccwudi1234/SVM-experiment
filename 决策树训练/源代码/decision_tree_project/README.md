# 决策树实验项目

机器学习课程实验：**决策树（ID3 / C4.5 / CART）+ 随机森林**，数据集为 UCI Mushroom（蘑菇分类），
8124 条样本、22 个类别特征、二分类（可食 / 有毒）。

项目按「**数据 → 模型 → 评估 → 可视化 → 主流程**」分层，每个文件只做一件事，
便于阅读、修改和答辩时讲解。

## 目录结构

```
decision_tree_project/
├── main.py                     主程序：按顺序调用各模块完成整个实验
├── requirements.txt            依赖版本
├── README.md                   本说明
├── src/
│   ├── config.py               全局配置：路径查找、列名、随机种子、两种策略
│   ├── data_loader.py          ① 数据：读取 → 缺失值处理 → 编码 → 划分
│   ├── metrics.py              ③ 评估：准确率 / 精确率 / 召回率 / F1 / 混淆矩阵
│   ├── visualization.py        ④ 可视化：全部图表（含扩展实验图）
│   ├── models/                 ② 模型：不同模型分文件存放
│   │   ├── decision_tree.py    决策树（gini=基尼指数 / entropy=信息熵）
│   │   ├── random_forest.py    随机森林（含 OOB 曲线、特征重要性）
│   │   └── handwritten_tree.py 选做：自己编写的 ID3 / C4.5（多路分裂）
│   └── experiments/            ⑤ 扩展实验：难度梯度、代价敏感、结构稳定性、划分比例
└── （图表输出到工作区根目录的 图表/：图片、results.json、树规则文本）
```

## 快速运行

```bash
# 在工作区根目录（本目录的上一级）执行
python 源代码/decision_tree_project/main.py

# 数据不在默认位置时，显式指定
python 源代码/decision_tree_project/main.py --data 数据集/mushroom/agaricus-lepiota.data
```

程序会依次打印：数据概况 → 两种策略结果 → 随机森林结果 → 剪枝实验 → 选做实现 → 扩展实验 → 汇总表格，
所有图表保存到工作区根目录的 `图表/`。

## 模块职责对照

| 模块 | 负责什么 | 对应实验要求 |
| --- | --- | --- |
| `src/data_loader.py` | 读取数据、缺失值当独立类别、序数编码、7:3 分层划分 | 数据收集与预处理 |
| `src/models/decision_tree.py` | 两种特征选择策略：`criterion='gini'`（CART 基尼指数）和 `criterion='entropy'`（信息增益/ID3 思路）；限深树、剪枝参数树 | 要求 2：两种特征选择策略 |
| `src/models/random_forest.py` | 随机森林训练、OOB 准确率曲线、特征重要性排序 | 要求 3：随机森林预测 |
| `src/models/handwritten_tree.py` | 自己实现 ID3（信息增益）与 C4.5（信息增益率），多路分裂，并导出规则 | 选做：自己编写决策树 |
| `src/metrics.py` | 统一计算准确率、精确率、召回率、F1、混淆矩阵 | 要求 4：结果分析与评估 |
| `src/visualization.py` | 决策树图、混淆矩阵、特征重要性、OOB 曲线、深度曲线、剪枝曲线、扩展实验图 | 要求 2、3 的可视化 |
| `src/experiments/` | 难度梯度（学习曲线/特征子集/标签噪声）、代价敏感与阈值扫描、结构稳定性（30 次重划分）、划分比例实验 | 扩展：模型鲁棒性与代价分析 |
| `src/config.py` | 路径自动查找、列名、随机种子等常量 | —— |

## 输出文件（图表/）

| 文件 | 内容 |
| --- | --- |
| `tree_gini.png` / `tree_entropy.png` | 两种策略的决策树图（前 2 层，便于阅读） |
| `full_tree_gini.png` / `full_tree_entropy.png` | 完整决策树高清大图（不截断深度，可放大查看） |
| `confusion_matrices.png` | 两种策略在测试集上的混淆矩阵 |
| `feature_importance.png` | 决策树 vs 随机森林特征重要性对比 |
| `rf_single_tree.png` | 随机森林中的一棵树 |
| `rf_oob_curve.png` | OOB 准确率随树数量的变化 |
| `depth_curve.png` | 树深-准确率曲线（过拟合分析） |
| `pruning.png` | 后剪枝 `ccp_alpha` 与准确率 |
| `tree_rules_gini.txt` / `tree_rules_entropy.txt` | 完整决策树的判定规则文本 |
| `handwritten_rules.txt` | 自己编写的 ID3 决策树的规则片段 |
| `difficulty.png` / `cost_sensitive.png` | 难度梯度实验 / 代价敏感与阈值分析 |
| `stability.png` / `split_ratio.png` | 树结构稳定性 / 不同划分比例的准确率 |
| `results.json` | 全部指标与绘图数据 |

## 数据来源

- 数据集：UCI Machine Learning Repository — **Mushroom**（id=73），文件位于 `数据集/mushroom/`
- 许可：CC BY 4.0
- 引用：`Mushroom [Dataset]. (1981). UCI Machine Learning Repository. https://doi.org/10.24432/C5959T`
- 原始文件：`agaricus-lepiota.data`（无表头，23 列，`?` 表示缺失）

## 环境要求

Python 3.10+，依赖见 `requirements.txt`：

```
numpy>=1.24
pandas>=2.0
scikit-learn>=1.0
matplotlib>=3.6
```

## 本轮核实与改进

- 深度与剪枝曲线的后一个分数是训练集内部验证准确率，不再是测试准确率。
- 代价敏感曲线来自验证集；阈值冻结后，best/default 字段记录测试集结果，validation_best 记录验证选择结果。
- 手写 C4.5 为直接最大化增益率的简化实现，默认限深8，未实现完整筛选与剪枝。
- 运行 `python 工具/refine_experiments.py`：在每折独立拟合编码器的五折交叉验证中选择深度和剪枝参数，生成编码对照、同位置噪声对照与样本决策路径。
- 新增结果在 `图表/refined_results.json`，解释与本人补充问题在 `实验报告/实验改进与思考记录.md`。
- 新版报告为 `实验报告/决策树实验报告-改进版.docx`，保留原版。运行 `python 工具/build_report.py` 生成；`工具/render_word_local.py` 使用已安装的 Word 只读导出并渲染预览（预览输出到系统临时目录）。

完整运行顺序、阈值边界规则及提交说明见根目录 `复现说明.md`；当前报告为 `实验报告/决策树实验报告-分析完善版.docx`。主程序CV已统一为每折拟合编码器的五折分层流程。
