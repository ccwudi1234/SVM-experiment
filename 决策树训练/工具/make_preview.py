# -*- coding: utf-8 -*-
"""
生成《数据集预览.xlsx》：把 UCI 蘑菇数据集的字母编码翻译成中文，方便查看。
- Sheet1 数据预览：8124 行，序号 + 类别 + 22 个中文特征
- Sheet2 字段取值说明：每个特征的取值含义
- Sheet3 数据概览：规模、类别分布、缺失值、来源
运行：python tools/make_preview.py
"""
import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "数据集" / "mushroom" / "agaricus-lepiota.data"
OUT = ROOT / "数据集" / "数据集预览.xlsx"

FEATURES = [
    "cap-shape", "cap-surface", "cap-color", "bruises", "odor",
    "gill-attachment", "gill-spacing", "gill-size", "gill-color",
    "stalk-shape", "stalk-root", "stalk-surface-above-ring",
    "stalk-surface-below-ring", "stalk-color-above-ring",
    "stalk-color-below-ring", "veil-type", "veil-color", "ring-number",
    "ring-type", "spore-print-color", "population", "habitat",
]
CN = ["菌盖形状", "菌盖表面", "菌盖颜色", "碰伤痕迹", "气味",
      "菌褶附着方式", "菌褶间距", "菌褶大小", "菌褶颜色",
      "菌柄形状", "菌柄根部形态", "菌环上方菌柄表面", "菌环下方菌柄表面",
      "菌环上方菌柄颜色", "菌环下方菌柄颜色", "菌幕类型", "菌幕颜色",
      "菌环数量", "菌环类型", "孢子印颜色", "群体密度", "生长环境"]

VALUE_MEANING = {
    "cap-shape": {"b": "钟形", "c": "圆锥形", "x": "凸起", "f": "平坦", "k": "隆起", "s": "凹陷"},
    "cap-surface": {"f": "纤维状", "g": "有沟纹", "y": "鳞片状", "s": "光滑"},
    "cap-color": {"n": "棕色", "b": "黄褐色", "c": "肉桂色", "g": "灰色", "r": "绿色",
                  "p": "粉红色", "u": "紫色", "e": "红色", "w": "白色", "y": "黄色"},
    "bruises": {"t": "有碰伤", "f": "无碰伤"},
    "odor": {"a": "杏仁味", "l": "茴香味", "c": "杂酚油味", "y": "鱼腥味", "f": "恶臭味",
             "m": "霉味", "n": "无味", "p": "刺鼻味", "s": "辛辣味"},
    "gill-attachment": {"a": "附着", "d": "向下延伸", "f": "离生", "n": "凹生"},
    "gill-spacing": {"c": "密集", "w": "紧密", "d": "稀疏"},
    "gill-size": {"b": "宽", "n": "窄"},
    "gill-color": {"k": "黑色", "n": "棕色", "b": "黄褐色", "h": "巧克力色", "g": "灰色",
                   "r": "绿色", "o": "橙色", "p": "粉红色", "u": "紫色", "e": "红色",
                   "w": "白色", "y": "黄色"},
    "stalk-shape": {"e": "增粗", "t": "渐细"},
    "stalk-root": {"b": "球状", "c": "棒状", "u": "杯状", "e": "等粗",
                   "z": "根状", "r": "带根", "?": "缺失"},
    "stalk-surface-above-ring": {"f": "纤维状", "y": "鳞片状", "k": "丝状", "s": "光滑"},
    "stalk-surface-below-ring": {"f": "纤维状", "y": "鳞片状", "k": "丝状", "s": "光滑"},
    "stalk-color-above-ring": {"n": "棕色", "b": "黄褐色", "c": "肉桂色", "g": "灰色",
                               "o": "橙色", "p": "粉红色", "e": "红色", "w": "白色", "y": "黄色"},
    "stalk-color-below-ring": {"n": "棕色", "b": "黄褐色", "c": "肉桂色", "g": "灰色",
                               "o": "橙色", "p": "粉红色", "e": "红色", "w": "白色", "y": "黄色"},
    "veil-type": {"p": "部分", "u": "全部"},
    "veil-color": {"n": "棕色", "o": "橙色", "w": "白色", "y": "黄色"},
    "ring-number": {"n": "无", "o": "1 个", "t": "2 个"},
    "ring-type": {"c": "蛛网状", "e": "易消失", "f": "张开", "l": "大",
                  "n": "无", "p": "悬垂", "s": "鞘状", "z": "环状"},
    "spore-print-color": {"k": "黑色", "n": "棕色", "b": "黄褐色", "h": "巧克力色",
                          "r": "绿色", "o": "橙色", "u": "紫色", "w": "白色", "y": "黄色"},
    "population": {"a": "大量", "c": "簇生", "n": "众多", "s": "分散", "v": "少量", "y": "孤立"},
    "habitat": {"g": "草地", "l": "落叶", "m": "草甸", "p": "小径", "u": "城镇",
                "w": "垃圾", "d": "林地"},
}
CLASS_MEANING = {"e": "可食", "p": "有毒"}

HEAD_FILL = PatternFill("solid", fgColor="2F5597")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
POISON_FILL = PatternFill("solid", fgColor="FCE4E4")
EDIBLE_FILL = PatternFill("solid", fgColor="E8F5E9")


def style_header(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(ncols)}1"


def main():
    rows = []
    with open(DATA, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(line.split(","))

    wb = Workbook()

    # ---------- Sheet1 数据预览 ----------
    ws = wb.active
    ws.title = "数据预览"
    header = ["序号", "类别"] + [f"{cn}（{en}）" for cn, en in zip(CN, FEATURES)]
    ws.append(header)
    for i, r in enumerate(rows, start=1):
        values = [i, CLASS_MEANING[r[0]]]
        for j, code in enumerate(r[1:], start=1):
            values.append(VALUE_MEANING[FEATURES[j - 1]].get(code, code))
        ws.append(values)
        fill = POISON_FILL if r[0] == "p" else EDIBLE_FILL
        ws.cell(row=i + 1, column=2).fill = fill
    style_header(ws, len(header))
    ws.column_dimensions["A"].width = 7
    ws.column_dimensions["B"].width = 8
    for c in range(3, len(header) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 15
    for row in ws.iter_rows(min_row=2, max_row=len(rows) + 1):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = BORDER
    ws.row_dimensions[1].height = 30

    # ---------- Sheet2 字段取值说明 ----------
    ws2 = wb.create_sheet("字段取值说明")
    ws2.append(["序号", "特征名", "中文含义", "取值（字母 = 含义）"])
    for i, (en, cn) in enumerate(zip(FEATURES, CN), start=1):
        pairs = VALUE_MEANING[en]
        text = "；".join(f"{k}={v}" for k, v in pairs.items())
        ws2.append([i, en, cn, text])
    ws2.append([0, "class", "类别（目标变量）", "e=可食(edible)；p=有毒(poisonous)"])
    style_header(ws2, 4)
    for c, w in zip("ABCD", [6, 26, 16, 88]):
        ws2.column_dimensions[c].width = w
    for row in ws2.iter_rows(min_row=2, max_row=ws2.max_row):
        for cell in row:
            cell.alignment = Alignment(vertical="center", wrap_text=(cell.column_letter == "D"))
            cell.border = BORDER

    # ---------- Sheet3 数据概览 ----------
    ws3 = wb.create_sheet("数据概览")
    edible = sum(1 for r in rows if r[0] == "e")
    poison = len(rows) - edible
    missing = sum(1 for r in rows if r[11] == "?")
    info = [
        ("数据集", "UCI Machine Learning Repository — Mushroom (id=73)"),
        ("样本数", f"{len(rows)} 条"),
        ("特征数", "22 个（全部为类别型特征）"),
        ("目标变量", "class：可食 edible（e）/ 有毒 poisonous（p）"),
        ("类别分布", f"可食 {edible} 条（{edible / len(rows) * 100:.1f}%）；"
                    f"有毒 {poison} 条（{poison / len(rows) * 100:.1f}%）"),
        ("缺失值", f"stalk-root 列有 {missing} 条缺失（原始数据用“?”表示，约占 {missing / len(rows) * 100:.1f}%）"),
        ("数据来源", "The Audubon Society Field Guide to North American Mushrooms (1981)"),
        ("许可协议", "CC BY 4.0"),
        ("引用", "Mushroom [Dataset]. (1981). UCI Machine Learning Repository. "
                "https://doi.org/10.24432/C5959T"),
        ("在线页面", "https://archive.ics.uci.edu/dataset/73/mushroom"),
        ("说明", "本表把原始字母编码翻译成中文；原始文件见 data/mushroom/agaricus-lepiota.data"),
    ]
    ws3.append(["项目", "内容"])
    for k, v in info:
        ws3.append([k, v])
    style_header(ws3, 2)
    ws3.column_dimensions["A"].width = 14
    ws3.column_dimensions["B"].width = 95
    for row in ws3.iter_rows(min_row=2, max_row=ws3.max_row):
        row[0].font = Font(bold=True)
        for cell in row:
            cell.alignment = Alignment(vertical="center", wrap_text=(cell.column_letter == "B"))
            cell.border = BORDER

    wb.save(OUT)
    print(f"已生成：{OUT}（{len(rows)} 行 × {len(FEATURES)} 个特征）")


if __name__ == "__main__":
    main()
