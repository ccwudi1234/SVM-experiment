# -*- coding: utf-8 -*-
"""
根据实验模板生成《决策树实验报告-修正版.docx》
- 读取 outputs/results.json 与 outputs/*.png
- 保留模板封面与八节标题样式，正文用宋体小四、1.5 倍行距
运行（用带 python-docx 的 Python）：
    python tools/build_report.py
"""
import csv
import json
import platform
from collections import Counter
from math import log2
from sklearn.model_selection import train_test_split
from importlib.metadata import version
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

import omml
from polish_report import polish

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "模板与要求" / "实验报告模板2026.docx"
OUTPUT_DOCX = ROOT / "实验报告" / "决策树实验报告-复现核查版.docx"
OUT_DIR = ROOT / "图表"
RES = json.loads((OUT_DIR / "results.json").read_text(encoding="utf-8"))

FIG = {k: str(OUT_DIR / f"{k}.png") for k in RES["figures"]}
T = RES["tables"]
REFINED = json.loads((OUT_DIR / "refined_results.json").read_text(encoding="utf-8"))

# 手写 ID3 / 简化C4.5 的结果（根节点特征与得分也记录在 results.json 里）
_hand_id3 = T["handwritten"]["手写ID3(信息增益)"]
_hand_c45 = T["handwritten"]["手写C4.5(信息增益率)"]
HAND = {
    "id3": {
        "nodes": _hand_id3["nodes"],
        "leaves": _hand_id3["leaves"],
        "top": _hand_id3["top_split_scores"][0][0],
        "score": _hand_id3["top_split_scores"][0][1],
    },
    "c45": {
        "nodes": _hand_c45["nodes"],
        "leaves": _hand_c45["leaves"],
        "top": _hand_c45["top_split_scores"][0][0],
        "score": _hand_c45["top_split_scores"][0][1],
    },
}

CN_TABLE_HEAD = ["特征名", "中文含义", "取值个数"]
FEATURE_CN = {
    "cap-shape": "菌盖形状",
    "cap-surface": "菌盖表面",
    "cap-color": "菌盖颜色",
    "bruises": "碰伤痕迹",
    "odor": "气味",
    "gill-attachment": "菌褶附着方式",
    "gill-spacing": "菌褶间距",
    "gill-size": "菌褶大小",
    "gill-color": "菌褶颜色",
    "stalk-shape": "菌柄形状",
    "stalk-root": "菌柄根部形态（含缺失）",
    "stalk-surface-above-ring": "菌环上方菌柄表面",
    "stalk-surface-below-ring": "菌环下方菌柄表面",
    "stalk-color-above-ring": "菌环上方菌柄颜色",
    "stalk-color-below-ring": "菌环下方菌柄颜色",
    "veil-type": "菌幕类型",
    "veil-color": "菌幕颜色",
    "ring-number": "菌环数量",
    "ring-type": "菌环类型",
    "spore-print-color": "孢子印颜色",
    "population": "群体密度",
    "habitat": "生长环境",
}


def value_counts_of_features():
    """从原始数据统计每个特征的取值个数（含缺失 '?'）。"""
    path = ROOT / "数据集" / "mushroom" / "agaricus-lepiota.data"
    with open(path, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split(",") for line in f if line.strip()]
    n_cols = len(rows[0])
    counts = {}
    for j in range(1, n_cols):
        counts[j] = len({r[j] for r in rows})
    return counts


def set_run(run, size=12, bold=False, font="宋体"):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font)
    rfonts.set(qn("w:ascii"), font if font != "宋体" else "Times New Roman")
    rfonts.set(qn("w:hAnsi"), font if font != "宋体" else "Times New Roman")


def new_after(ref_el, doc):
    """在 ref_el 之后插入空段落，返回 Paragraph。"""
    p = doc.add_paragraph()
    ref_el.addnext(p._p)
    return p


def after_table(table, doc):
    p = doc.add_paragraph()
    table._tbl.addnext(p._p)
    return p


def table_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    # 按 OOXML 顺序插在 tblLayout / tblCellMar / tblLook 之前
    anchor = None
    for tag in ("w:tblLayout", "w:tblCellMar", "w:tblLook", "w:shd"):
        anchor = tblPr.find(qn(tag))
        if anchor is not None:
            break
    if anchor is not None:
        anchor.addprevious(borders)
    else:
        tblPr.append(borders)


def shade(cell, color="D9E2F3"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


class Builder:
    def __init__(self, doc):
        self.doc = doc
        self.cursor = None       # 当前插入位置（Paragraph）
        self.fig_no = 0
        self.tab_no = 0

    # ---------- 基本块 ----------
    def body(self, text, indent=True, size=12, space_after=4, line=1.5, bold=False,
             align=None):
        p = new_after(self.cursor._p, self.doc)
        pf = p.paragraph_format
        pf.first_line_indent = Pt(size * 2) if indent else None
        pf.line_spacing = line
        pf.space_after = Pt(space_after)
        if align is not None:
            p.alignment = align
        run = p.add_run(text)
        set_run(run, size=size, bold=bold)
        self.cursor = p
        return p

    def sub(self, text):
        p = self.body(text, indent=False, size=12, bold=True,
                      space_after=3, line=1.5)
        p.paragraph_format.keep_with_next = True
        return p

    def equation(self, elements, space_before=4, space_after=4):
        """插入一条 Word 原生公式（OMML），居中显示。"""
        p = new_after(self.cursor._p, self.doc)
        pf = p.paragraph_format
        pf.first_line_indent = None
        pf.line_spacing = 1.2
        pf.space_before = Pt(space_before)
        pf.space_after = Pt(space_after)
        omml.add_equation(p, elements)
        self.cursor = p
        return p

    def body_rich(self, parts, indent=True, space_after=4, line=1.5):
        """正文里混排行内公式：parts 的元素为 ("text", 文字) 或 ("math", 公式元素列表)。"""
        p = new_after(self.cursor._p, self.doc)
        pf = p.paragraph_format
        pf.first_line_indent = Pt(24) if indent else None
        pf.line_spacing = line
        pf.space_after = Pt(space_after)
        for kind, value in parts:
            if kind == "text":
                run = p.add_run(value)
                set_run(run, size=12)
            else:
                math = OxmlElement("m:oMath")
                for e in value:
                    math.append(e)
                p._p.append(math)
        self.cursor = p
        return p

    def code(self, text):
        p = new_after(self.cursor._p, self.doc)
        pf = p.paragraph_format
        pf.first_line_indent = None
        pf.line_spacing = 1.1
        pf.space_after = Pt(6)
        pf.left_indent = Pt(18)
        for i, line in enumerate(text.split("\n")):
            if i:
                p.add_run().add_break()
            run = p.add_run(line)
            set_run(run, size=9, font="Consolas")
        self.cursor = p
        return p

    def caption(self, text, before=4, after=8, keep_next=False):
        p = new_after(self.cursor._p, self.doc)
        pf = p.paragraph_format
        pf.first_line_indent = None
        pf.line_spacing = 1.0
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.keep_with_next = keep_next
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        set_run(run, size=10.5)
        self.cursor = p
        return p

    def image(self, key, width=6.0, caption=None):
        path = FIG[key]
        p = new_after(self.cursor._p, self.doc)
        pf = p.paragraph_format
        pf.first_line_indent = None
        pf.line_spacing = 1.0
        pf.space_before = Pt(6)
        pf.space_after = Pt(2)
        pf.keep_with_next = True       # 图与图题不分页
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(path, width=Inches(width))
        self.cursor = p
        if caption:
            self.fig_no += 1
            self.caption(f"图 {self.fig_no}  {caption}")
        return p

    def table(self, rows, caption=None, widths=None, font_size=9.5,
              first_col_left=False):
        if caption:
            self.tab_no += 1
            self.caption(f"表 {self.tab_no}  {caption}", before=8, after=2, keep_next=True)
        n_rows, n_cols = len(rows), len(rows[0])
        if widths is None:
            widths = [6.0 / n_cols] * n_cols
        total = sum(widths)
        if total > 6.1:                      # 不超过正文宽度
            widths = [w * 6.1 / total for w in widths]
        t = self.doc.add_table(rows=n_rows, cols=n_cols)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        table_borders(t)
        tbl = t._tbl
        grid = tbl.tblGrid
        for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
            gc.set(qn("w:w"), str(int(w * 1440)))
        self.cursor._p.addnext(t._tbl)
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.width = Inches(widths[j])
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.first_line_indent = None
                p.alignment = (WD_ALIGN_PARAGRAPH.LEFT if (first_col_left and j == 0)
                               else WD_ALIGN_PARAGRAPH.CENTER)
                run = p.add_run(str(val))
                set_run(run, size=font_size, bold=(i == 0))
                if i == 0:
                    shade(cell)
        # 表头跨页重复、行内不拆分
        for i, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            cant = OxmlElement("w:cantSplit")
            trPr.append(cant)
            if i == 0:
                trPr.append(OxmlElement("w:tblHeader"))
        p_after = after_table(t, self.doc)
        p_after.paragraph_format.space_after = Pt(4)
        p_after.paragraph_format.line_spacing = 1.0
        self.cursor = p_after
        return t


# ----------------------------------------------------------------------
# 报告正文内容
# ----------------------------------------------------------------------
def fill_title(p):
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = None
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.page_break_before = True
    run = p.add_run("实验一  决策树实验")
    set_run(run, size=16, bold=True, font="黑体")


def prepare_doc(doc):
    """统一正文宽度、清掉模板多余空段落、填标题。"""
    doc.styles["Normal"].paragraph_format.right_indent = Pt(0)
    doc.styles["Normal"].paragraph_format.left_indent = Pt(0)
    title_p = doc.paragraphs[18]
    # 封面标题之前的多余空段落（否则会多出一张空白页）
    for p in [q for q in doc.paragraphs[14:18] if not q.text.strip()]:
        p._element.getparent().remove(p._element)
    # 标题之后的空段落与示例文字
    seen_title = False
    for p in list(doc.paragraphs):
        if p._element is title_p._element:
            seen_title = True
            continue
        if seen_title:
            text = p.text.strip()
            if not text or text.startswith("编写本次实验目的"):
                p._element.getparent().remove(p._element)
    fill_title(title_p)


def section(doc, title):
    for p in doc.paragraphs:
        if p.text.strip() == title:
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            return p
    raise KeyError(title)


def main():
    doc = Document(str(TEMPLATE))
    prepare_doc(doc)
    b = Builder(doc)

    # ================= 一、实验目的 =================
    b.cursor = section(doc, "一、实验目的")
    for text in [
        "1. 理解并掌握决策树的基本原理，包括特征选择、决策树生成与决策树剪枝三个步骤；",
        "2. 掌握 ID3（信息增益）、简化C4.5（信息增益率）、CART（基尼指数）三种常用决策树算法的特征选择思想与区别；",
        "3. 掌握随机森林的集成学习原理，理解 Bootstrap 抽样与随机特征子空间对模型泛化能力的提升；",
        "4. 熟练使用 Python 与 scikit-learn 完成数据预处理、模型训练、预测、评估与可视化；",
        "5. 通过两种特征选择策略的对比实验，分析决策树结构差异，并讨论过拟合、剪枝与模型可解释性；",
        "6. 通过自己实现决策树的建树过程，加深对特征选择、递归划分与停止条件的理解；",
        "7. 通过划分比例（含 9:1）、难度梯度、代价敏感、结构稳定性四组扩展实验，检验模型鲁棒性并给出划分比例与分类阈值的建议。",
    ]:
        b.body(text, space_after=2)
    b.body("上述目标在报告中的对应关系为：第二、三、四节分别给出原理、数据与环境；第五节说明实验流程；"
           "第六节先完成两种策略对比、随机森林与剪枝等必做内容（6.1–6.5），再用四组扩展实验检验模型可信度"
           "（6.6–6.9），最后统一讨论（6.10）；第七、八节为选做内容与附件。")

    # ================= 二、实验原理 =================
    b.cursor = section(doc, "二、实验原理")
    b.body("（1）决策树模型。决策树（Decision Tree）是一种基于特征对实例进行分类的有监督学习方法，"
           "由根节点、内部节点、叶节点和有向边构成：内部节点表示对某个特征的判断，叶节点表示分类结果。"
           "其学习过程是一个递归过程：从根节点开始，选择最优特征把训练集划分为若干子集；若子集已基本正确分类，"
           "则构造叶节点，否则对子集继续选择新的最优特征递归划分，直至满足停止条件。"
           "因此决策树学习通常包括特征选择、决策树生成和决策树修剪三个步骤。")
    b.body("（2）特征选择策略。特征选择的目标是选出使划分后子集“纯度”提升最大的特征，常用三种度量：")
    b.body("① 信息熵与信息增益（ID3）。信息熵度量样本集合的不确定性，定义为：", indent=False)
    b.equation(omml.eq_entropy())
    b.body_rich([("text", "其中 "), ("math", omml.inline_p_k()),
                 ("text", " 为第 k 类样本所占比例，K 为类别数。特征 A 对数据集 D 的信息增益定义为划分前后熵的差值：")],
                indent=False)
    b.equation(omml.eq_info_gain())
    b.body_rich([("text", "其中 "), ("math", omml.inline_D_v()),
                 ("text", " 为特征 A 取第 v 个值的样本子集。ID3 选择信息增益最大的特征进行划分，"
                          "其缺点是偏向取值较多的特征。")],
                indent=False)
    b.body("② 信息增益率（简化C4.5）。为克服信息增益偏向多值特征的缺点，简化C4.5 以信息增益率作为准则：", indent=False)
    b.equation(omml.eq_gain_ratio())
    b.body_rich([("text", "其中 "), ("math", omml.inline_H_A()),
                 ("text", " 称为特征 A 对数据集 D 的分裂信息，计算方式为：")], indent=False)
    b.equation(omml.eq_split_info())
    b.body("完整C4.5通常先筛选信息增益，再比较增益率；本实验简化实现直接最大化增益率，不含该筛选和剪枝。", indent=False)
    b.body("③ 基尼指数（CART）。基尼指数表示从数据集中随机抽取两个样本、其类别不一致的概率：", indent=False)
    b.equation(omml.eq_gini())
    b.body("CART 选择使划分后基尼指数最小的特征及其切分点，生成二叉树。", indent=False)
    b.body("（3）随机森林。随机森林在 Bagging 基础上进一步引入随机特征选择：对训练集做 T 次有放回抽样，"
           "每次用抽样得到的子集训练一棵决策树，且每次节点分裂时只在随机选取的一部分特征中选择最优划分；"
           "预测时由 T 棵树投票决定类别。随机森林通过降低方差来抑制单棵决策树的过拟合，"
           "并可用袋外样本（OOB）估计泛化误差。")
    b.body("（4）剪枝。决策树容易过拟合，需要通过剪枝控制模型复杂度。预剪枝在生成过程中提前停止（如限制最大深度 "
           "max_depth、限制叶节点最少样本数 min_samples_leaf）；后剪枝先生成完整树，再按代价复杂度"
           "（cost-complexity pruning，参数 ccp_alpha）自底向上剪去分支。")
    b.body("（5）评价指标。设 TP、FP、TN、FN 分别表示真正例、假正例、真负例、假负例，"
           "N 为样本总数，P、R 分别为精确率与召回率，则各指标定义为：")
    b.equation(omml.eq_accuracy_precision())
    b.equation(omml.eq_recall_f1())
    b.body("本实验中“有毒”为正类，漏判（有毒误判为可食）属于 FN，后果严重，"
           "因此除了准确率之外，还需要重点关注有毒类的召回率。"
           "以上就是本实验涉及的全部原理与指标定义，下面依次说明数据、环境与实验流程。")

    # ================= 三、实验数据收集 =================
    b.cursor = section(doc, "三、实验数据收集")
    b.body("在明确了原理与评价指标之后，先说明实验数据的来源与特点。"
           "本实验采用 UCI Machine Learning Repository 的蘑菇分类数据集（Mushroom, id=73）。"
           "该数据集包含 8124 条样本，每条样本描述一朵蘑菇的 22 个外形特征（如菌盖形状、表面、颜色、气味、"
           "菌褶颜色与间距、菌柄形态、孢子印颜色、生长环境等），标签为“可食（edible）”或“有毒（poisonous）”，"
           "数据来源于《The Audubon Society Field Guide to North American Mushrooms》(1981)，"
           "许可证为 CC BY 4.0，引用格式见文末参考文献[1]。")
    b.body("数据中 stalk-root（菌柄根部）列存在缺失，用“?”标记，共 2480 条（约占 30.5%）。"
           "由于缺失比例较高，删除该列或删除整行都会损失大量信息，本实验将缺失值视为一个独立的取值“missing”参与建模，"
           "这是一种显式缺失值处理策略，不能据此认为所有决策树都可直接处理缺失。数据集概况如表 1 所示（训练集 5686 条、测试集 2438 条，"
           "按 7:3 分层抽样划分）。")
    rows = [["项目", "数值"],
            ["样本总数", "8124"],
            ["特征数", "22（全部为类别型特征）"],
            ["可食样本（edible）", f"{T['data_summary']['class_counts']['edible']}（51.8%）"],
            ["有毒样本（poisonous）", f"{T['data_summary']['class_counts']['poisonous']}（48.2%）"],
            ["缺失值", "stalk-root 列 2480 条（30.5%）"],
            ["训练集 / 测试集", "5686 / 2438（7:3 分层抽样）"]]
    b.table(rows, caption="Mushroom 数据集概况", widths=[2.2, 3.6], first_col_left=True)
    b.body("22 个特征的名称、含义及取值个数见表 2。")
    vc = value_counts_of_features()
    frows = [CN_TABLE_HEAD]
    for j, name in enumerate(
        ["cap-shape", "cap-surface", "cap-color", "bruises", "odor", "gill-attachment",
         "gill-spacing", "gill-size", "gill-color", "stalk-shape", "stalk-root",
         "stalk-surface-above-ring", "stalk-surface-below-ring",
         "stalk-color-above-ring", "stalk-color-below-ring", "veil-type", "veil-color",
         "ring-number", "ring-type", "spore-print-color", "population", "habitat"], start=1):
        frows.append([name, FEATURE_CN[name], str(vc[j])])
    b.table(frows, caption="Mushroom 数据集特征说明", widths=[1.9, 3.2, 0.8], font_size=9)

    # ================= 四、实验环境 =================
    b.cursor = section(doc, "四、实验环境")
    b.body("数据确定后，需要搭建实验环境。实验在 Windows 11 操作系统上完成，使用 Anaconda 提供的 Python 环境，"
           "主要依赖 scikit-learn、pandas、numpy 与 matplotlib。具体版本见表 3。")
    rows = [["项目", "版本 / 说明"],
            ["操作系统", "Windows 11 (64 位)"],
            ["编程语言", f"Python {platform.python_version()}"],
            ["机器学习库", f"scikit-learn {version('scikit-learn')}"],
            ["数据处理", f"pandas {version('pandas')}、numpy {version('numpy')}"],
            ["绘图", f"matplotlib {version('matplotlib')}"],
            ["开发方式", "Python 脚本 + 终端运行"]]
    b.table(rows, caption="实验环境", widths=[2.2, 3.6], first_col_left=True)

    # ================= 五、实验步骤 =================
    b.cursor = section(doc, "五、实验步骤")
    b.body("按照“数据 → 模型 → 评估 → 扩展验证”的顺序，整个实验分为以下十步：步骤 1–8 完成数据准备、"
           "两种特征选择策略、随机森林与剪枝等必做内容，步骤 9 完成选做内容，步骤 10 为四组扩展实验。")
    steps = [
        "1. 数据读取：用 pandas 读取 agaricus-lepiota.data（无表头，按 UCI 官方文档补 23 个列名），"
        "把“?”作为缺失类别missing处理，标签 edible→0、poisonous→1。",
        "2. 数据预处理（先按第3步划分，仅在训练部分拟合编码器）：scikit-learn 的决策树只接受数值输入，因此 22 个类别特征用 OrdinalEncoder 编码为整数"
        "（作为基线；阈值分裂受类别编码顺序影响，另与独热编码进行对照），缺失值作为独立类别保留；"
        "画图时再把编码值换算回原始类别（见图 2、图 3 与表 5）。",
        "3. 数据集划分：按 7:3 分层抽样，得到训练集 5686 条、测试集 2438 条，保证两类样本比例一致。",
        "4. 策略一（CART·基尼指数）：DecisionTreeClassifier(criterion='gini') 训练，在训练集、测试集上预测，"
        "计算准确率、精确率、召回率、F1 与混淆矩阵，并做 5 折交叉验证。",
        "5. 策略二（信息熵/信息增益）：DecisionTreeClassifier(criterion='entropy') 重复上述过程。",
        "6. 可视化：用 plot_tree 绘制另行训练的两棵限深决策树（max_depth=2），用 imshow 绘制混淆矩阵对比图，"
        "绘制两种策略与随机森林的特征重要性对比图。",
        "7. 随机森林：RandomForestClassifier(n_estimators=100) 训练与预测，计算指标与 OOB 准确率，"
        "绘制森林中单棵树、特征重要性、OOB 准确率随树数量变化曲线。",
        "8. 过拟合与剪枝：遍历 max_depth=1~15 记录训练/内部验证准确率；遍历 ccp_alpha 做后剪枝，比较叶节点数与准确率变化。",
        "9. 选做：自己编写 ID3 / 简化C4.5 决策树（信息增益、信息增益率），在相同划分上训练评估，并与 scikit-learn 结果对比。",
        "10. 扩展实验：训练/测试划分比例对比（9:1~5:5）、难度梯度（学习曲线/特征子集/标签噪声）、"
        "代价敏感与阈值扫描、结构稳定性（30 次重划分）。",
    ]
    for s in steps:
        b.body(s, space_after=2)
    b.body("核心代码如下（完整工程见附件 decision_tree_project/，按数据、模型、评估、可视化分模块）：", indent=True)
    b.code("""# 两种特征选择策略
tree_gini    = DecisionTreeClassifier(criterion='gini',    random_state=42).fit(X_tr, y_tr)
tree_entropy = DecisionTreeClassifier(criterion='entropy', random_state=42).fit(X_tr, y_tr)

# 随机森林
rf = RandomForestClassifier(n_estimators=100, oob_score=True, random_state=42).fit(X_tr, y_tr)

# 决策树可视化
plot_tree(tree_gini, feature_names=FEATS, class_names=CLASS_NAMES, filled=True, rounded=True)

# 后剪枝：代价复杂度
pruned = DecisionTreeClassifier(ccp_alpha=0.02, random_state=42).fit(X_tr, y_tr)""")

    # ================= 六、实验结果分析 =================
    b.cursor = section(doc, "六、实验结果分析")
    b.body("本章按“先必做、再扩展、后讨论”的顺序组织：6.1–6.5 给出必做内容的实验结果，"
           "6.6–6.9 用四组扩展实验（划分比例、难度梯度、代价敏感、结构稳定性）检验模型的可信度，6.10 对全部结果做统一讨论。"
           "最终分类指标在测试集（2438条）计算；深度与剪枝曲线使用内部验证集，阈值曲线使用验证集，交叉验证只使用训练部分。")

    b.sub("6.1 两种特征选择策略的预测结果")
    b.body("按 7:3 划分后，两种特征选择策略在训练集与测试集上的结果见表 4。"
           "两种策略的测试准确率、精确率、召回率、F1 均为 1.0000，五折分层交叉验证（每折独立拟合编码器）均为1.0000，混淆矩阵中没有任何误判。"
           "这表明当前划分下两类样本容易由特征区分，当前测试中未观察到错误，但不能据此排除所有噪声或分布变化。")
    rows = [["特征选择策略", "训练准确率", "测试准确率", "精确率macro", "召回率macro", "F1 macro", "树深/叶节点"],
            ["基尼指数（CART）", "1.0000", "1.0000", "1.0000", "1.0000", "1.0000",
             f"{T['tree_gini']['depth']} / {T['tree_gini']['leaves']}"],
            ["信息熵（ID3 思路）", "1.0000", "1.0000", "1.0000", "1.0000", "1.0000",
             f"{T['tree_entropy']['depth']} / {T['tree_entropy']['leaves']}"]]
    b.table(rows, caption="两种特征选择策略的分类结果", font_size=9,
            widths=[1.55, 0.85, 0.85, 0.75, 0.75, 0.7, 1.0])
    b.image("confusion_matrices", width=5.6,
            caption="基尼树、信息熵树与随机森林在测试集上的混淆矩阵")
    b.body("从混淆矩阵看，测试集 2438 条样本全部预测正确：可食 1263 条、有毒 1175 条均无误判。"
           "对“有毒”类而言，召回率为 1.0，即没有出现“有毒被误判为可食”的严重漏判，这在食品安全场景中是最重要的指标。")

    b.sub("6.2 决策树结构对比")
    b.body("两棵决策树（为便于观察，均另行训练为max_depth=2，完整树的判定规则见附件 tree_rules_*.txt）分别如图 2、图 3 所示。"
           "可以看到：两种策略生成的根节点分裂特征相同，"
           "都是gill-color，但阈值和类别集合不同，并非完全相同的判断；后续分裂也使用 "
           "population、spore-print-color、stalk-root、gill-size 等特征，与领域经验相符。")
    b.body("说明：scikit-learn 的决策树只接受数值输入，类别特征先被编码成整数（0、1、2……），"
           "所以程序原始输出的分裂条件是“gill-color <= 3.50”这样的数字阈值。为便于阅读，"
           "可视化模块按“编码值 → 原始取值”的顺序把阈值换算回了类别集合：图中“gill-color ∈ {b,e,g,h}”"
           "表示菌褶颜色属于 b、e、g、h 中的一种，“是/否”分别表示满足/不满足该条件。"
           "图中出现的关键条件与中文含义对照见表 5。")
    b.image("tree_gini", width=5.7, caption="基尼指数（CART）决策树（max_depth=2）")
    b.image("tree_entropy", width=5.7, caption="信息熵（ID3 思路）决策树（max_depth=2）")
    rows = [["图中条件", "含义（原始类别取值）"],
            ["gill-color ∈ {b,e,g,h}", "菌褶颜色属于 b=黄褐、e=红、g=灰、h=巧克力色"],
            ["population ∈ {a,c,n,s}", "群体密度属于 a=大量、c=簇生、n=众多、s=分散"],
            ["spore-print-color ∈ {b,h}", "孢子印颜色为 b=黄褐、h=巧克力色"],
            ["gill-color ∈ {b}", "菌褶颜色为 b=黄褐"],
            ["odor ∈ {a,c,f}", "气味为 a=杏仁味、c=杂酚油味、f=恶臭味"],
            ["stalk-root ∈ {b,c,e,missing}", "菌柄根部形态为 b=球状、c=棒状、e=等粗或缺失"]]
    b.table(rows, caption="决策树图中条件与中文含义对照", widths=[2.4, 3.6],
            font_size=9, first_col_left=True)
    b.body(f"但两棵树在规模上存在明显差异：基尼树共有 {T['tree_gini']['leaves']} 个叶节点，"
           f"而信息熵树只有 {T['tree_entropy']['leaves']} 个叶节点（两者深度均为 {T['tree_gini']['depth']}）。"
           "信息熵准则对“划分后子集更纯”更敏感，倾向于选择能一次把样本分得更纯的特征，因此生成的分支更少、"
           "树结构更紧凑；基尼指数计算的是随机误分类概率，更关注“多数类”的纯度。"
           "在当前测试集两者准确率相同，信息熵树规模更小；尚未测量推理速度或直接评价可解释性。")

    b.sub("6.3 特征重要性分析")
    b.body("图 4 给出了两种决策树与随机森林的特征重要性对比（取随机森林重要性前 10 的特征）。"
           "单棵决策树的重要性高度集中：基尼树的 gill-color 一个特征就贡献约 33%，"
           "加上 spore-print-color、population 后前三个特征累计约 70%，说明少数特征即可决定分类结果。"
           "随机森林的重要性则明显分散：odor（气味）最高约 19%，gill-color 约 12%、gill-size 约 11%、"
           "spore-print-color 约 11%，这是因为随机森林每次分裂只在随机特征子集中选择，重要性被“分摊”到更多特征上。")
    b.image("feature_importance", width=5.7,
            caption="决策树与随机森林的特征重要性对比（随机森林前 10 个特征）")
    b.body("重要性排名靠前的 odor、gill-color、gill-size、spore-print-color 都是蘑菇鉴别中常用的形态特征，"
           "说明模型学到的规律与领域知识一致，模型具有较好的可解释性。")

    b.sub("6.4 随机森林结果")
    b.body(f"随机森林（100 棵树）在测试集上同样达到 1.0000 的准确率，OOB 准确率为 {T['random_forest']['oob_score']:.4f}，"
           "两种评价在当前数据上结果一致，不等于验证了所有分布下的估计可靠性。图 5 显示 OOB 准确率随树数量的变化：树数量很少时OOB准确率偏低，且部分样本没有袋外预测，估计不可靠；"
           "随着树数量增加逐渐接近1.0，说明该数据上随机森林不需要很多棵树就能收敛。"
           "图 6 是森林中第一棵树（仅展示前 1 层，括号表示未展开的子树），可以看出单棵树的结构与前面两棵树有较大差异——"
           "这正是 Bootstrap 抽样与随机特征带来的多样性，再通过投票集成降低方差。")
    b.image("rf_oob_curve", width=4.9, caption="随机森林 OOB 准确率随树数量的变化")
    b.image("rf_single_tree", width=5.4, caption="随机森林中的一棵决策树（仅展示前 1 层）")
    rows = [["指标", "数值"],
            ["树的数量", "100"],
            ["测试集准确率", "1.0000"],
            ["精确率（macro）", "1.0000"],
            ["召回率（macro）", "1.0000"],
            ["F1（macro）", "1.0000"],
            ["OOB 准确率", "1.0000"]]
    b.table(rows, caption="随机森林在测试集上的表现", widths=[2.4, 3.4], first_col_left=True)

    b.sub("6.5 过拟合与剪枝分析")
    b.body("为了考察决策树复杂度对泛化的影响，分别做了预剪枝（限制树深）与后剪枝（代价复杂度）实验，结果见表 7、表 8"
           "和图 7、图 8。")
    rows = [["max_depth", "训练准确率", "验证准确率"]]
    for d, tr, te in T["depth_curve"]:
        rows.append([str(d), f"{tr:.4f}", f"{te:.4f}"])
    b.table(rows, caption="预剪枝：不同树深下的准确率", widths=[1.4, 2.2, 2.2])
    b.image("depth_curve", width=5.2, caption="树深与准确率的关系")
    b.body("本节曲线仅使用训练集内部验证集，不用测试结果选深度。训练与验证准确率同步上升只说明当前划分未观察到明显过拟合，不能证明深树在所有数据上都不会过拟合。")
    rows = [["ccp_alpha", "叶节点数", "训练准确率", "验证准确率"]]
    for a, leaves, tr, te in T["pruning"]:
        rows.append([f"{a:g}", str(leaves), f"{tr:.4f}", f"{te:.4f}"])
    b.table(rows, caption="后剪枝：不同 ccp_alpha 下的准确率", widths=[1.4, 1.4, 1.8, 1.8])
    b.image("pruning", width=5.2, caption="后剪枝强度 ccp_alpha 与准确率的关系")
    b.body("剪枝应在验证或交叉验证中选择强度，再在独立测试集上评价。精度相近时可结合叶节点数选择较简单的模型；详细交叉验证对照见7.3与7.4。")

    # ---------- 6.6 划分比例 ----------
    ext = T["extensions"]
    split = ext["split_ratio"]
    b.sub("6.6 训练与测试划分比例对照")
    b.body("主实验预先采用 7:3 的分层划分。下列重复划分用于探索模型对划分比例的敏感度。"
           f"把测试集比例从 10%（9:1）逐步增加到 50%（5:5），每种比例重复 {split['seeds']} 次不同随机划分，"
           "每次只在该次训练集拟合编码器，比较决策树与随机森林的测试准确率及其波动，结果如图 9 所示。")
    b.image("split_ratio", width=5.8,
            caption="不同训练/测试划分比例下的准确率（含 9:1，虚线为本实验采用的 7:3）")
    rows = [["测试集比例", "训练/测试条数", "决策树测试准确率", "随机森林测试准确率", "1 条误判的影响"],
            *[[f"{r[0]:.0%}", f"{r[1]} / {r[2]}",
               f"{r[4]:.4f} ± {r[5]:.4f}", f"{r[6]:.4f} ± {r[7]:.4f}", f"{r[8]:.3f}%"]
              for r in split["ratios"]]]
    b.table(rows, caption="不同划分比例下的测试准确率", font_size=9)
    b.body("分析：（1）五种比例下两种模型的测试准确率都 ≥ 0.9990、方差极小，说明本实验结论对划分比例不敏感；"
           "（2）但测试集越小，评估“粒度”越粗：9:1 时测试集有 813 条，1 条误判就会让准确率下降 0.12%，"
           "而 7:3 时为 0.04%，因此小测试集对单条误判更敏感，但本次9:1的重复实验标准差为0，不能声称已观察到更大波动；"
           "（3）另一方面，训练集并非越大越好——6.7 的难度梯度实验将说明只用 5% 训练样本也能达到 98% 以上，"
           "本数据对训练量并不敏感；（4）综合“训练量够用”和“测试集足够大且稳定”两点，"
           "7:3（5686 / 2438）是合适的折中：9:1虽然训练数据更多，但测试样本较少，"
           "主实验及固定划分对照均沿用预先设定的 7:3。")

    # ---------- 6.7 难度梯度 ----------
    diff = ext["difficulty"]
    b.sub("6.7 难度梯度实验：模型到底学到了什么")
    b.body("划分比例确定后，还有一个更根本的问题：6.1–6.5 中各模型在本数据上几乎完美，"
           "“完美”究竟是因为模型学到了规律，还是因为数据过于简单？为此设计难度梯度实验："
           "分别减少训练样本（5%~100%）、只保留重要性前 k 个特征、以及在训练标签中注入噪声，"
           "观察测试准确率如何变化，结果如图 10 所示。")
    b.image("difficulty", width=6.1,
            caption="难度梯度实验（左：学习曲线；中：特征子集；右：标签噪声）")
    lc = diff["learning_curve"]
    noise = {int(round(r[0] * 100)): r[1] for r in diff["noise"]}
    full_k, full_k_acc = max(diff["feature_subset"], key=lambda row: row[1])
    rows = [["实验设定", "测试准确率"],
            [f"训练集只用 5%（约 {int(5686 * 0.05)} 条）", f"{lc[0][3]:.4f}"],
            ["训练集 20%", f"{lc[2][3]:.4f}"],
            ["训练集 100%", f"{lc[-1][3]:.4f}"],
            [f"只保留重要性前 {full_k} 个特征（共 22 个）", f"{full_k_acc:.4f}"],
            ["训练集标签噪声 5%", f"{noise[5]:.4f}"],
            ["训练集标签噪声 10%", f"{noise[10]:.4f}"],
            ["训练集标签噪声 20%", f"{noise[20]:.4f}"],
            ["训练集标签噪声 30%", f"{noise[30]:.4f}"]]
    b.table(rows, caption="难度梯度实验关键结果", widths=[3.2, 2.0], first_col_left=True)
    b.body(f"分析：（1）训练集只用 5%（约 {int(5686 * 0.05)} 条）时测试准确率仍有 {lc[0][3]:.4f}，"
           "说明少量样本就能学到主要判别规则，这也从侧面支持了 6.6 中“训练量不是关键”的判断；"
           f"（2）按训练集重要性排序，保留前 {full_k} 个特征时，首次达到该曲线的最高平均测试准确率 {full_k_acc:.4f}。"
           "这条曲线仅用于探索，正式选择特征数量需在验证集进行。"
           "（3）训练标签噪声越高、测试准确率越低，"
           f"噪声 10% 时降到 {noise[10]:.4f}、30% 时降到 {noise[30]:.4f}，准确率随噪声增加而下降，不应假定严格线性关系，"
           "说明模型受训练标签影响，但不能单凭这一现象证明没有记忆训练样本；"
           "（4）这些现象支持数据可分性较强，但噪声实验本身不足以排除所有形式的数据泄漏或过拟合。")

    # ---------- 6.8 代价敏感 ----------
    cost = ext["cost_sensitive"]
    b.sub("6.8 代价敏感与阈值分析")
    b.body("6.7 说明模型确实学到了规律；但在实际应用中，两类错误的后果并不对等。"
           "蘑菇识别中，“有毒判成可食”（漏判 FN）的代价远高于“可食判成有毒”（误判 FP）。"
           f"干净数据上模型分类准确率很高（准确率 {cost['clean_accuracy']:.4f}），不利于观察阈值取舍；"
           f"因此给训练集注入 {cost['noise']:.0%} 标签噪声，构造一个不完美的随机森林"
           f"（测试准确率 {cost['noisy_accuracy']:.4f}），再扫描分类阈值，结果如图 11 所示。")
    b.image("cost_sensitive", width=6.1,
            caption="代价敏感分析（左：阈值-总代价；右：阈值-精确率/召回率）")
    rows = [["漏判:误判代价", "默认阈值 0.5 的代价", "验证选定阈值", "测试代价", "漏判数", "误判数", "有毒类召回率"]]
    for r in cost["cost_ratios"]:
        best = cost["best"][str(r)]
        rows.append([f"{r}:1", f"{cost['default'][str(r)]['cost']:.0f}",
                     f"{best['threshold']:.2f}", f"{best['cost']:.0f}",
                     str(best["fn"]), str(best["fp"]), f"{best['recall']:.4f}"])
    b.table(rows, caption="验证集选择阈值后的测试结果", font_size=9)
    b.body("阈值在训练部分内部的验证集上选择，表中代价、漏判和误判来自独立测试集。验证集最优阈值不一定降低测试代价；应按实际结果判断，不把零漏判当作安全保证。")

    stab = ext["stability"]
    b.sub("6.9 树结构稳定性分析")
    b.body(f"6.7、6.8 考察的是预测性能，而决策树的可解释性依赖于树结构本身是否稳定。"
           f"同一份数据、同一套参数，只改变随机划分（共 {stab['seeds']} 次），观察树结构是否稳定，结果如图 12 所示。")
    b.image("stability", width=6.1,
            caption="结构稳定性（左：根节点特征；中：叶节点数；右：重要性标准差对比）")
    rows = [["统计量", "数值"],
            ["叶节点数", f"{stab['leaves_mean']:.1f} ± {stab['leaves_std']:.1f}"
                          f"（{stab['leaves_min']}~{stab['leaves_max']}）"],
            ["树深", f"{stab['depth_min']}~{stab['depth_max']}（众数 {stab['depth_mode']}）"],
            ["根节点特征", f"{stab['root_top']}（{stab['root_top_ratio']:.0%} 的划分）"],
            ["前 3 特征集合 Jaccard（单树）", f"{stab['top3_jaccard_tree']:.2f}"],
            ["前 3 特征集合 Jaccard（随机森林）", f"{stab['top3_jaccard_rf']:.2f}"],
            ["特征重要性标准差（单树）", f"{stab['importance_std_tree']:.4f}"],
            ["特征重要性标准差（随机森林）", f"{stab['importance_std_rf']:.4f}"]]
    b.table(rows, caption="30 次随机划分下的树结构统计", widths=[3.2, 2.6], first_col_left=True)
    b.body(f"分析：单棵树的结构比直觉更稳定——{stab['seeds']} 次划分中叶节点数集中在 "
           f"{stab['leaves_mean']:.1f}±{stab['leaves_std']:.1f}，根节点 {stab['root_top_ratio']:.0%} 选择 "
           f"{stab['root_top']}，前 3 个重要特征的集合完全一致（Jaccard={stab['top3_jaccard_tree']:.2f}）。"
           f"但随机森林的特征重要性前 3 反而不稳定（Jaccard≈{stab['top3_jaccard_rf']:.2f}），"
           "可能与随机特征抽样及相近重要性特征的排名交换有关，本实验没有单独验证这一原因。"
           "这提醒我们：单棵树的“可解释性”来自稳定的树结构，而集成模型的重要性排名需要多次重采样才能可靠比较。")

    b.sub("6.10 结果讨论")
    b.body("综合 6.1–6.9 的结果，可以归纳为以下六点。")
    b.body("（1）两种特征选择策略在本数据上的分类能力相同（均 100%），但生成的树规模不同：信息熵树更紧凑（14 叶 vs 20 叶）。"
           "当前结果支持比较结构规模，不能仅凭单次划分推出信息熵普遍更好或推理更快。")
    b.body("（2）随机森林与单棵决策树精度相同，但稳定性应根据具体指标判断：当前单树前三特征集合比森林更稳定，"
           "而森林通过多棵树的投票降低了方差，但不能据此直接断言其特征排序更稳定。7.5节同位置标签噪声实验进一步显示，在本实验条件下，"
           "随机森林准确率更高。")
    b.body("（3）本数据集几乎所有模型（决策树、随机森林、手写分类树）都能达到接近 100% 的准确率，"
           "说明它适合作为“算法正确性验证”和“可解释性分析”的教学案例，而不适合比较模型优劣。"
           "若要比较不同模型，需要引入噪声、减少特征或使用更难的数据集。")
    b.body("（4）从应用角度看，本实验模型对“有毒”类的召回率为 1.0，即不存在漏判，仅表示当前测试样本上未观察到漏判，不能保证实际使用安全。"
           "如果模型存在漏判，应通过调整类别权重、调整阈值等方式提高有毒类的召回率。")

    b.body("（5）难度梯度实验表明模型确实学到了规律：5% 训练样本即可达 98.56%，"
           "标签噪声增加时准确率下降，且 6 个特征就足以达到 100%；"
           "代价敏感分析进一步说明，阈值必须先在验证集选定，再检查测试代价是否降低，不能保证漏判为零。")
    b.body("（6）稳定性与划分比例实验表明：模型在重复划分下表现较稳定；"
           "单棵决策树的结构在 30 次重采样下高度稳定，但其前三特征集合保持一致，"
           "集成模型的重要性排名需要多次重采样才可靠。")
    b.body("基于以上结论，第七节给出三项选做内容的具体实现与验证，第八节列出全部提交文件。")

    # ================= 七、选做内容 =================
    b.cursor = section(doc, "七、选做内容")
    b.body("在完成必做内容与四组扩展实验之后，本节给出三项选做内容的实现与结果：7.1 自己编写决策树，"
           "7.2 决策树可视化，7.3 决策树剪枝。三项内容分别侧重算法内部实现、模型可解释性与模型复杂度控制，"
           "与前文的实验结论相互补充。")

    b.sub("7.1 自己编写 ID3 / 简化C4.5 决策树")
    b.body("为了理解决策树的内部过程，除调用 scikit-learn 外，还自己实现了 ID3 与 简化C4.5 两棵决策树，不依赖现成的树模型"
           "（代码见 源代码/decision_tree_project/src/models/handwritten_tree.py）。实现要点：")
    b.body("① 递归建树：在每个节点上计算所有可用特征的信息增益（ID3）或信息增益率（简化C4.5），"
           "选择得分最高的特征，按该特征的每个取值做多路划分；", indent=False)
    b.body("② 停止条件：子集样本全部同一类、特征用尽、达到最大深度或最大增益为 0 时，生成叶节点并取多数类；",
           indent=False)
    b.body("③ 预测：测试样本从根节点沿取值向下走；若出现训练时没见过的取值，返回该节点保存的多数类作为兜底。",
           indent=False)
    b.body(f"根节点分析：自己实现的 ID3 按信息增益选到 {HAND['id3']['top']}（信息增益 {HAND['id3']['score']:.4f}），"
           f"自己实现的 简化C4.5 按信息增益率同样选到 {HAND['c45']['top']}（增益率 {HAND['c45']['score']:.4f}）。"
           "这与 scikit-learn 两棵树都以 gill-color 作为根节点不同——scikit-learn 的 CART 是"
           "“阈值二分裂”，而手写 ID3/简化C4.5 一次就把 odor 的 9 个取值分成 9 个分支，"
           "多路分裂下 odor 的判别力最集中，所以根节点选择不同。")
    rows = [["手写算法", "特征选择准则", "节点数", "叶节点数", "测试准确率"],
            ["ID3", "信息增益最大", str(HAND["id3"]["nodes"]), str(HAND["id3"]["leaves"]), "1.0000"],
            ["简化C4.5", "信息增益率最大", str(HAND["c45"]["nodes"]), str(HAND["c45"]["leaves"]), "1.0000"]]
    b.table(rows, caption="自己编写的 ID3 / 简化C4.5 决策树结果", font_size=9.5)
    b.body("结果分析：自己实现的 ID3 得到 29 个节点、24 个叶节点，简化C4.5 得到 26 个节点、20 个叶节点，"
           "两者测试准确率均为 100%。简化C4.5 的树比 ID3 更小，原因是信息增益率用分裂信息对"
           "“取值多的特征”做了惩罚，避免了 ID3 偏向选择分支过多特征的缺陷。"
           "与 scikit-learn 的结果相比（基尼树 20 个叶节点、信息熵树 14 个叶节点），"
           "自己实现的树规模略大，但两者的分裂方式不同（CART 是二分裂、多路分裂实现），"
           "树规模不能直接比较。这也说明：决策树的最终结构由“特征选择准则 + 分裂方式”共同决定，"
           "在类别可完全区分的数据上，不同实现的预测能力是一致的。")

    b.body("根节点计算核对：下表只使用训练集，供独立手算信息增益与增益率。计数来自数据，不代表已经由本人完成手算。")
    with open(ROOT / "数据集/mushroom/agaricus-lepiota.data", encoding="utf-8") as handle:
        raw_rows = list(csv.reader(handle))
    train_rows, _ = train_test_split(raw_rows, test_size=0.3, random_state=42,
                                    stratify=[r[0] for r in raw_rows])
    counts = Counter((r[5], r[0]) for r in train_rows)
    rows = [["odor原始取值", "可食e", "有毒p", "合计"]]
    conditional = split_entropy = 0.0
    n = len(train_rows)
    for value in sorted({r[5] for r in train_rows}):
        edible, poison = counts[value, "e"], counts[value, "p"]
        total = edible + poison
        entropy = -sum((c / total) * log2(c / total) for c in (edible, poison) if c)
        conditional += total / n * entropy
        split_entropy -= total / n * log2(total / n)
        rows.append([value, str(edible), str(poison), str(total)])
    b.table(rows, caption="训练集odor各取值的类别计数", font_size=9)
    total_poison = sum(r[0] == "p" for r in train_rows)
    probability = total_poison / n
    base_entropy = -probability * log2(probability) - (1-probability) * log2(1-probability)
    b.body(f"数值核对：H(D)={base_entropy:.6f}，H(D|odor)={conditional:.6f}，分裂信息={split_entropy:.6f}。信息增益={base_entropy-conditional:.6f}，增益率={(base_entropy-conditional)/split_entropy:.6f}。手算时应说明权重来自各分支样本数，不能只把各分支熵直接相加。")

    b.sub("7.2 决策树可视化")
    b.body("决策树的图在前文结果分析中已经出现过：图 2、图 3 为另行训练的max_depth=2两棵树，图 6 为森林中的一棵树，"
           "它们的共同特点是节点信息清晰、便于讲解。本节补充未截断的完整树绘制：每个节点标出划分条件、"
           "基尼/熵值、样本数、各类样本数与预测类别，并用大画布输出高清图（图 13、图 14）；同时用 export_text "
           "把完整判定规则导出为文本（运行程序后在 图表/tree_rules_*.txt 中生成），可以逐条阅读。"
           "可以看到，两棵完整树在前几层结构相似、深层分支差别较大，这与 6.2 的结论一致——"
           "决策树的可解释性正是来自这种可直接阅读、可逐条核对的树结构。")
    b.body("为了看清整棵树的结构，程序还会输出未截断的完整决策树（高分辨率大图）。图 13 为基尼指数决策树的完整结构"
           "（7 层、20 个叶节点），图 14 为信息熵决策树的完整结构（7 层、14 个叶节点），"
           "每个节点都标出了划分条件、基尼/熵值、样本数、各类样本数及预测类别；"
           "由于节点较多，建议放大查看，高清原图见“图表”文件夹中的 full_tree_gini.png 与 full_tree_entropy.png。")
    b.image("full_tree_gini", width=6.1,
            caption="完整决策树（CART·基尼指数，深度 7、20 个叶节点）")
    b.image("full_tree_entropy", width=6.1,
            caption="完整决策树（信息熵，深度 7、14 个叶节点）")

    b.sub("7.3 决策树剪枝")
    b.body("深度和剪枝曲线使用训练部分内部验证集；最终对照使用五折分层交叉验证，并在每折内部拟合编码器。深度候选为3、5、7及不限深，ccp_alpha候选为0、0.001、0.005。测试集不参与选择。这里的选择结果仅适用于该候选网格。")
    b.sub("7.4 编码与模型复杂度对照")
    rows = [["编码", "准则", "CV准确率", "测试准确率", "深度上限/α", "叶节点", "节点数"]]
    for r in REFINED["comparison"]:
        rows.append([r["encoding"], r["criterion"], f"{r['cv']:.5f}", f"{r['test']:.5f}", f"{r['params']['tree__max_depth']}/{r['params']['tree__ccp_alpha']}", str(r["leaves"]), str(r["nodes"])])
    b.table(rows, caption="交叉验证选参后的编码与复杂度对照", font_size=9)
    b.body("序数编码下两棵树都达到100%，但信息熵树只有14个叶节点，基尼树为20个。因此本实验中区分模型的依据转为结构规模。独热编码下树更小，但测试准确率略降；不能仅凭这一划分断言一种编码普遍更好。原始22个特征经独热编码后变为多个二元列，树深和节点数应结合表示方式解释。")
    b.sub("7.5 相同噪声位置下的鲁棒性对照")
    rows = [["标签噪声", "Gini均值±标准差", "Entropy均值±标准差", "随机森林均值±标准差"]]
    for r in REFINED["noise"]:
        rows.append([f"{r['ratio']:.0%}"] + [f"{r['scores'][k]['mean']:.4f} ± {r['scores'][k]['std']:.4f}" for k in ("gini", "entropy", "forest")])
    b.table(rows, caption="固定划分下五次相同噪声位置的模型对照", font_size=9)
    b.body("每次重复让三个模型使用完全相同的被翻转标签位置，测试标签始终不变。10%训练标签噪声下，两种单树准确率约86%，随机森林约99.5%，支持森林在本实验条件下更抗标签噪声。这里的标准差反映固定划分下噪声位置及模型种子的变化，不是跨数据划分的置信区间。")
    b.sub("7.6 从疑问到证据的核实过程")
    b.body("首先核查100%是否可能来自重复样本。核查脚本发现完全重复记录和当前跨训练测试集合相同特征记录均为0；30次划分中29次满分，最低约99.84%。这些证据支持模型容易学到此数据中的分类规则，但不能证明真实场景零风险，也不能排除其他分布上的性能下降。")
    b.body("其次核查阈值调节是否真的有效。旧流程在测试集找最低代价，再用同一批样本报告收益，混合了选择与评价。本轮改为验证集选择、测试集评价。FN代价为10时，阈值0.46使测试总代价由57降到33，但仍有2次漏判。因此应保留有条件的收益结论，放弃零漏判保证。")
    b.body("最后检查算法名称是否与实现相符。sklearn的entropy仍是二叉阈值树；手写简化C4.5只实现直接最大化增益率，没有完整的信息增益候选筛选和剪枝，默认最大深度为8。比较时必须说明这些限制。")
    b.body("7.4与7.5补充了前述讨论的证据：序数编码信息熵树较小，噪声下森林准确率较高，而阈值调节只降低代价、不保证零漏判。个人模型取舍仍需结合这些条件说明。")
    b.sub("7.7 一条实际预测路径")
    sample = REFINED["sample"]
    b.body(f"取当前测试集第一条样本，真实类别为{sample['actual']}、预测为{sample['predicted']}（0可食，1有毒）。以下路径来自序数编码基尼树实际遍历，不是人为构造的示例。")
    rows = [["特征", "原始取值", "编码", "阈值", "分支"]]
    for r in sample["route"]:
        rows.append([r["feature"], r["value"], str(r["encoded"]), str(r["threshold"]), "左" if r["branch"] == "left" else "右"])
    b.table(rows, caption="测试样本沿基尼树的判断过程", font_size=9)
    b.body("左分支对应编码值小于等于阈值，右分支对应大于阈值。例如编码0进入阈值3.5的左分支，只是类别映射后的判断，不能解释为颜色本身有大小顺序。完整路径可与树规则文本逐项核对。")

    # ================= 八、附件 =================
    b.cursor = section(doc, "八、附件（代码和数据文件名称）")
    b.body("为便于复现和检查，主要提交文件如下。补充对照运行 python 工具/refine_experiments.py，结果存于图表/refined_results.json；核查运行 python 工具/check_100_percent.py。报告运行 python 工具/build_report.py。")
    rows = [["文件名", "说明"],
            ["源代码/decision_tree_project/main.py", "主程序：按顺序调用各模块完成整个实验"],
            ["源代码/decision_tree_project/src/data_loader.py", "数据模块：读取、缺失值处理、编码、划分"],
            ["源代码/decision_tree_project/src/models/decision_tree.py", "模型模块：决策树（基尼指数 / 信息熵两种策略）、限深与剪枝训练"],
            ["源代码/decision_tree_project/src/models/random_forest.py", "模型模块：随机森林、OOB 曲线、特征重要性"],
            ["源代码/decision_tree_project/src/models/handwritten_tree.py", "自己编写的 ID3 / 简化C4.5（信息增益 / 信息增益率，多路分裂）"],
            ["源代码/decision_tree_project/src/metrics.py", "评估模块：准确率、精确率、召回率、F1、混淆矩阵"],
            ["源代码/decision_tree_project/src/visualization.py", "可视化模块：决策树图、混淆矩阵、特征重要性等全部图表"],
            ["源代码/decision_tree_project/src/experiments/", "扩展实验模块：难度梯度、代价敏感、结构稳定性、划分比例"],
            ["源代码/decision_tree_project/src/config.py", "配置模块：路径查找、列名、随机种子"],
            ["数据集/mushroom/agaricus-lepiota.data", "蘑菇数据集原始文件（UCI，8124 条 × 23 列）"],
            ["数据集/mushroom/agaricus-lepiota.names", "数据集字段说明"],
            [f"实验报告/{OUTPUT_DOCX.name}", "本实验报告"]]
    b.table(rows, caption="提交文件清单", widths=[2.9, 3.0], font_size=9, first_col_left=True)
    b.body("运行 python 源代码/decision_tree_project/main.py 会自动在 图表/ 目录下生成"
           "本报告中的 14 张图表（混淆矩阵、两棵决策树、两棵完整决策树、特征重要性、随机森林单树、OOB 曲线、深度曲线、剪枝曲线、划分比例、难度梯度、代价敏感、结构稳定性）、"
           "全部指标文件 results.json，以及两棵决策树的完整判定规则 tree_rules_*.txt。")

    # ================= 参考文献 =================
    p = new_after(b.cursor._p, doc)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("参考文献")
    set_run(run, size=12, bold=True)
    b.cursor = p
    refs = [
        "[1] Mushroom [Dataset]. (1981). UCI Machine Learning Repository. https://doi.org/10.24432/C5959T.",
        "[2] 周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.",
        "[3] Pedregosa F, et al. Scikit-learn: Machine Learning in Python[J]. Journal of Machine Learning Research, 2011, 12: 2825-2830.",
        "[4] Breiman L. Random Forests[J]. Machine Learning, 2001, 45(1): 5-32.",
        "[5] 和鲸社区. 蘑菇分类数据集（UCI Machine Learning）[DS/OL]. https://www.heywhale.com/mw/dataset/5a4c87653616537d65c7cdcc.",
    ]
    for r in refs:
        p = new_after(b.cursor._p, doc)
        p.paragraph_format.first_line_indent = None
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(r)
        set_run(run, size=10.5)
        b.cursor = p

    polish(doc)
    for table in doc.tables:
        if len(table.rows) <= 8:
            for row in table.rows[:-1]:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.keep_with_next = True
    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(OUTPUT_DOCX))
        print("已生成：", OUTPUT_DOCX)
    except PermissionError:
        alt = OUTPUT_DOCX.with_name(OUTPUT_DOCX.stem + "-最新.docx")
        doc.save(str(alt))
        print("目标文件正被占用，已保存到：", alt)


if __name__ == "__main__":
    main()
