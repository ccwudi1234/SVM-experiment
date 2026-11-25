"""重新核实评估流程，并生成可追溯的报告补充。运行：python 工具/refine_experiments.py。"""
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '源代码' / 'decision_tree_project'))
from src import data_loader
from src.config import FEATURES, resolve_data_path
from src.experiments.cost_sensitive import threshold_curve


def main():
    X, y = data_loader.prepare(data_loader.load_raw(resolve_data_path(None)))
    train, test, yt, ye = data_loader.split(X, y)
    cv = StratifiedKFold(5, shuffle=True, random_state=42)
    rows = []
    for encoding in ('ordinal', 'onehot'):
        for criterion in ('gini', 'entropy'):
            encoder = (OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
                       if encoding == 'ordinal' else OneHotEncoder(handle_unknown='ignore'))
            pipe = Pipeline([('encode', encoder), ('tree', DecisionTreeClassifier(random_state=42, criterion=criterion))])
            search = GridSearchCV(pipe, {'tree__max_depth': [3, 5, 7, None],
                                        'tree__ccp_alpha': [0, .001, .005]}, cv=cv)
            start = perf_counter()
            search.fit(train, yt)
            elapsed = perf_counter() - start
            tree = search.best_estimator_.named_steps['tree']
            rows.append(dict(encoding=encoding, criterion=criterion, params=search.best_params_,
                             cv=float(search.best_score_), test=float(search.score(test, ye)),
                             depth=tree.get_depth(), leaves=int(tree.get_n_leaves()),
                             nodes=int(tree.tree_.node_count), search_seconds=elapsed))
    enc = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
    a, b = enc.fit_transform(train), enc.transform(test)
    noise = []
    for ratio in (0, .05, .1, .2):
        scores = {'gini': [], 'entropy': [], 'forest': []}
        for seed in range(5):
            noisy = yt.copy()
            idx = np.random.default_rng(seed).choice(len(yt), int(len(yt)*ratio), replace=False)
            noisy[idx] = 1 - noisy[idx]
            models = {'gini': DecisionTreeClassifier(random_state=seed),
                      'entropy': DecisionTreeClassifier(criterion='entropy', random_state=seed),
                      'forest': RandomForestClassifier(n_estimators=100, random_state=seed)}
            for name, model in models.items():
                scores[name].append(float(model.fit(a, noisy).score(b, ye)))
        noise.append(dict(ratio=ratio, scores={k: dict(mean=float(np.mean(v)), std=float(np.std(v)), values=v) for k,v in scores.items()}))
    model = DecisionTreeClassifier(random_state=42).fit(a, yt)
    path = model.decision_path(b[:1]).indices
    route = []
    for node in path:
        j = model.tree_.feature[node]
        if j >= 0:
            route.append(dict(feature=FEATURES[j], value=str(test.iloc[0,j]),
                              encoded=float(b[0,j]), threshold=float(model.tree_.threshold[node]),
                              branch='left' if b[0,j] <= model.tree_.threshold[node] else 'right'))
    result = dict(comparison=rows, noise=noise, cost=None,
                  sample=dict(actual=int(ye[0]), predicted=int(model.predict(b[:1])[0]), route=route))
    # 阈值实验用原始顺序，确保与主程序划分一致。
    result['cost'] = threshold_curve(enc.transform(X), y)
    (ROOT/'图表'/'refined_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=lambda v: v.item()), encoding='utf-8')
    lines = ['# 决策树实验核实与改进记录', '',
             '本轮关注三个问题：100% 是否可信；同样准确时模型复杂度如何；阈值收益能否在独立测试集保持。', '',
             '## 编码与交叉验证选参', '',
             '每折独立拟合编码器，五折分层交叉验证只使用训练集。测试集不参与参数选择。运行耗时为完整搜索耗时，不能当作单次训练耗时。', '',
             '|编码|准则|CV|测试|深度|叶节点|节点数|搜索秒数|', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"|{r['encoding']}|{r['criterion']}|{r['cv']:.5f}|{r['test']:.5f}|{r['depth']}|{r['leaves']}|{r['nodes']}|{r['search_seconds']:.2f}|")
    lines += ['', '类别数值编码会限制可选的二分方式，因此不能说类别排列不影响结果。准确率相近时，应继续比较结构，而不是仅凭满分指标判定算法优劣。', '', '## 相同噪声条件下的对照', '', '固定同一训练与测试划分，五次重复只改变噪声位置和模型种子；标准差不代表跨数据划分的不确定性。', '', '|训练标签噪声|Gini 均值±标准差|Entropy 均值±标准差|随机森林 均值±标准差|', '|---|---|---|---|']
    for r in noise:
        lines.append('|' + str(r['ratio']) + '|' + '|'.join(f"{r['scores'][k]['mean']:.5f} ± {r['scores'][k]['std']:.5f}" for k in ('gini','entropy','forest')) + '|')
    lines += ['', '## 验证集选阈值与测试集评价', '', '训练部分再留出25%作验证。曲线属于验证集；以下代价属于冻结阈值后的测试集。降低阈值是否改善测试结果必须根据下表判断，不能预设一定改善。', '', '|FN代价|验证选定阈值|默认测试代价|选定阈值测试代价|测试FN|测试FP|', '|---|---|---|---|---|---|']
    for k, v in result['cost']['best'].items():
        lines.append(f"|{k}|{v['threshold']}|{result['cost']['default'][k]['cost']}|{v['cost']}|{v['fn']}|{v['fp']}|")
    lines += ['', '## 一个样本的实际决策路径', '', f"标签规定：0可食、1有毒。真实类别 {result['sample']['actual']}，预测类别 {result['sample']['predicted']}。"]
    for r in route:
        lines.append(f"- {r['feature']} 原始值 {r['value']}，编码 {r['encoded']}，与阈值 {r['threshold']} 比较后走 {r['branch']} 分支。")
    lines += ['', '## 思考线索与本人补充', '',
              '已验证的线索：原核查脚本检查到完整重复和跨集合重复均为0，30次划分中29次满分。因此单次100%有数据支持，但不等于真实环境零风险。',
              '方法上的修正：原先直接在测试集寻找最低代价阈值，会高估选参收益。本轮把选择与评价分开，接受测试结果可能没有改善。',
              '算法边界：sklearn entropy树属于二叉阈值树；手写C4.5仅直接最大化增益率，未实现完整候选筛选与剪枝，手写树默认限深8。',
              '待本人补充：查看编码对照后，你更愿意采用哪种编码？请结合表中的节点数与准确率写出理由。',
              '待本人补充：沿上述路径手算一处分裂，说明为什么当前取值进入这个分支；不要把编码大小解释成颜色或气味的自然顺序。',
              '待本人补充：你原来如何理解100%？本轮哪条证据改变或保留了你的判断？只有符合本人经历时才写成第一人称。',
              '', '本记录可用于修订报告，旧版Word中的固定阈值和剪枝数字不能直接沿用。']
    (ROOT/'实验报告'/'实验改进与思考记录.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == '__main__':
    main()
