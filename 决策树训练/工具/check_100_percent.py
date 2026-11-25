# -*- coding: utf-8 -*-
"""核查"100% 准确率"是否可靠（一次性诊断脚本，不进提交包）。

检查四件事：
  1. 数据集里有没有重复样本；训练集/测试集之间会不会重复（会不会"背答案"）
  2. 换不同的随机划分种子，100% 是否稳定（单次划分是否为运气）
  3. 只用少数几个特征，准确率是否依然很高（说明学到的是规则而不是死记）
  4. 给训练集标签加噪声，模型是否跟着退化（说明模型真的在学习）
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

COLS = ["class"] + [f"f{i}" for i in range(1, 23)]
df = pd.read_csv("数据集/mushroom/agaricus-lepiota.data", header=None, names=COLS)
df = df.replace("?", np.nan)
X = df[COLS[1:]].fillna("missing").astype(str)
y = (df["class"] == "p").astype(int).to_numpy()
keys = X.apply(lambda r: "|".join(r), axis=1)

# ---------- 1. 重复样本检查 ----------
dup = int(df.duplicated().sum())
idx_tr, idx_te = train_test_split(
    np.arange(len(y)), test_size=0.3, random_state=42, stratify=y
)
cross = set(keys.iloc[idx_tr]) & set(keys.iloc[idx_te])
print(f"1) 整行完全重复的样本数：{dup}")
print(f"   训练集与测试集之间重复的行数（跨集合“背答案”）：{len(cross)}")


def split(seed):
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=seed, stratify=y
    )
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    return enc.fit_transform(Xtr), enc.transform(Xte), ytr, yte


# ---------- 2. 不同随机划分的稳定性 ----------
accs = []
for seed in range(30):
    Xtr, Xte, ytr, yte = split(seed)
    accs.append(DecisionTreeClassifier(random_state=42).fit(Xtr, ytr).score(Xte, yte))
print(f"2) 30 种随机划分的测试准确率：最小 {min(accs):.4f}，"
      f"平均 {np.mean(accs):.4f}，最大 {max(accs):.4f}，"
      f"达到 100% 的划分次数 {sum(a == 1.0 for a in accs)}/30")

# ---------- 3. 只用少数特征 ----------
Xtr, Xte, ytr, yte = split(42)
base = DecisionTreeClassifier(random_state=42).fit(Xtr, ytr)
top = np.argsort(base.feature_importances_)[::-1][:3]
for k in (1, 2, 3):
    cols = top[:k]
    acc = DecisionTreeClassifier(random_state=42).fit(Xtr[:, cols], ytr).score(Xte[:, cols], yte)
    names = "、".join(f"f{int(c) + 1}" for c in cols)
    print(f"3) 只用重要性前 {k} 个特征（{names}）：测试准确率 {acc:.4f}")

# ---------- 4. 训练标签加噪声 ----------
rng = np.random.default_rng(0)
for ratio in (0.05, 0.10, 0.20):
    y_noisy = ytr.copy()
    idx = rng.choice(len(y_noisy), size=int(len(y_noisy) * ratio), replace=False)
    y_noisy[idx] = 1 - y_noisy[idx]
    acc = DecisionTreeClassifier(random_state=42).fit(Xtr, y_noisy).score(Xte, yte)
    print(f"4) 训练集 {ratio:.0%} 的标签被随机打乱后，测试准确率 {acc:.4f}（原始 1.0000）")
