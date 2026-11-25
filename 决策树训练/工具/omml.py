# -*- coding: utf-8 -*-
"""把公式写成 Word 原生公式（OMML，Office Math Markup Language）。

python-docx 不支持公式，这里直接拼 OMML 节点，插入到段落里，
这样生成的 .docx 在 Word 里是"可编辑的公式对象"，可以正常缩放、复制到 LaTeX。

常用构件：
    mr(text)            普通数学文本（默认斜体；sty="p" 表示正体）
    frac(num, den)      分式
    sub(base, sub)      下标
    sup(base, sup)      上标
    nary(chr, sub, sup, body)   求和/连乘等大运算符
    delim(elems)        圆括号
    iadd(parent, elems) 追加子元素
"""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _el(tag: str):
    """创建 m: 命名空间下的空元素。"""
    return OxmlElement(tag)


def mr(text: str, sty: str | None = None, bold: bool = False):
    """数学文本。sty='p' 表示正体（函数名、中文、数字标记用），默认斜体（变量用）。"""
    run = _el("m:r")
    rpr = _el("m:rPr")
    if sty:
        s = _el("m:sty")
        s.set(qn("m:val"), sty)
        rpr.append(s)
    run.append(rpr)
    t = _el("m:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    return run


def _container(tag: str, elems):
    box = _el(tag)
    for e in elems:
        box.append(e)
    return box


def frac(num, den):
    f = _el("m:f")
    f.append(_container("m:num", num))
    f.append(_container("m:den", den))
    return f


def sub(base, sub_elems):
    s = _el("m:sSub")
    s.append(_container("m:e", base))
    s.append(_container("m:sub", sub_elems))
    return s


def inline_p_k():
    """行内变量 p_k"""
    return [sub([mr("p")], [mr("k")])]


def inline_D_v():
    """行内变量 |D_v|"""
    return [mr("|"), sub([mr("D")], [mr("v")]), mr("|")]


def inline_H_A():
    """行内变量 H_A(D)"""
    return [sub([mr("H")], [mr("A")]), mr("(D)")]


def sup(base, sup_elems):
    s = _el("m:sSup")
    s.append(_container("m:e", base))
    s.append(_container("m:sup", sup_elems))
    return s


def subsup(base, sub_elems, sup_elems):
    s = _el("m:sSubSup")
    s.append(_container("m:e", base))
    s.append(_container("m:sub", sub_elems))
    s.append(_container("m:sup", sup_elems))
    return s


def delim(elems, beg="(", end=")"):
    d = _el("m:d")
    dpr = _el("m:dPr")
    b = _el("m:begChr")
    b.set(qn("m:val"), beg)
    e = _el("m:endChr")
    e.set(qn("m:val"), end)
    dpr.append(b)
    dpr.append(e)
    d.append(dpr)
    d.append(_container("m:e", elems))
    return d


def nary(char: str, sub_elems=None, sup_elems=None, body=None):
    """大运算符，如求和 ∑_{v}、∑_{k=1}^{K}。

    注意：LibreOffice 会把空的 m:sup 渲染成占位方块，所以没有上限时
    用空格占位并令 limLoc="sub"，只显示下标。
    """
    n = _el("m:nary")
    pr = _el("m:naryPr")
    c = _el("m:chr")
    c.set(qn("m:val"), char)
    pr.append(c)
    lim = _el("m:limLoc")
    lim.set(qn("m:val"), "subSup" if sup_elems else "sub")
    pr.append(lim)
    if not sup_elems:
        hidden = _el("m:supHide")
        hidden.set(qn("m:val"), "1")
        pr.append(hidden)
    n.append(pr)
    n.append(_container("m:sub", sub_elems if sub_elems is not None else [mr(" ")]))
    n.append(_container("m:sup", sup_elems if sup_elems else [mr(" ")]))
    n.append(_container("m:e", body or []))
    return n


def log2(arg):
    """log₂(·)：log 为正体，2 作下标。"""
    return [sub([mr("log", sty="p")], [mr("2", sty="p")]), mr(" "), *arg]


def add_equation(paragraph, elements):
    """把一个公式（元素列表）作为 Word 公式对象放进段落，居中显示。"""
    para = _el("m:oMathPara")
    pr = _el("m:oMathParaPr")
    jc = _el("m:jc")
    jc.set(qn("m:val"), "center")
    pr.append(jc)
    para.append(pr)
    omath = _el("m:oMath")
    for e in elements:
        omath.append(e)
    para.append(omath)
    paragraph._p.append(para)


# ----------------------------------------------------------------------
# 具体公式：与报告"二、实验原理"中的公式一一对应
# ----------------------------------------------------------------------
def eq_entropy():
    """H(D) = -Σ_{k=1}^{K} p_k log2 p_k"""
    return [
        mr("H(D) = −"),
        nary("∑", [mr("k=1")], [mr("K")],
             [sub([mr("p")], [mr("k")]), mr(" "), *log2([sub([mr("p")], [mr("k")])])]),
    ]


def eq_info_gain():
    """g(D,A) = H(D) - H(D|A) = H(D) - Σ_v (|D_v|/|D|) H(D_v)"""
    dv = [mr("|"), sub([mr("D")], [mr("v")]), mr("|")]
    d_abs = [mr("|D|")]
    return [
        mr("g(D,A) = H(D) − H(D|A) = H(D) − "),
        nary("∑", [mr("v")], [],
             [frac(dv, d_abs), mr("H("), sub([mr("D")], [mr("v")]), mr(")")]),
    ]


def eq_gain_ratio():
    """g_R(D,A) = g(D,A) / H_A(D)"""
    ratio = frac([mr("g(D,A)")], [sub([mr("H")], [mr("A")]), mr("(D)")])
    return [sub([mr("g")], [mr("R")]), mr("(D,A) = "), ratio]


def eq_split_info():
    """H_A(D) = -Σ_v p_v log2 p_v ，p_v = |D_v|/|D|"""
    pv = sub([mr("p")], [mr("v")])
    dv = [mr("|"), sub([mr("D")], [mr("v")]), mr("|")]
    return [
        sub([mr("H")], [mr("A")]), mr("(D) = "),
        mr("−"),
        nary("∑", [mr("v")], [], [pv, mr(" "), *log2([sub([mr("p")], [mr("v")])])]),
        mr("，    "),
        sub([mr("p")], [mr("v")]), mr(" = "), frac(dv, [mr("|D|")]),
    ]


def eq_gini():
    """Gini(D) = 1 - Σ_k p_k² ；Gini(D,A) = Σ_v (|D_v|/|D|) Gini(D_v)"""
    dv = [mr("|"), sub([mr("D")], [mr("v")]), mr("|")]
    d_abs = [mr("|D|")]
    return [
        mr("Gini(D) = 1 − "),
        nary("∑", [mr("k=1")], [mr("K")],
             [sup([sub([mr("p")], [mr("k")])], [mr("2")])]),
        mr("，    "),
        mr("Gini(D,A) = "),
        nary("∑", [mr("v")], [],
             [frac(dv, d_abs), mr("Gini("), sub([mr("D")], [mr("v")]), mr(")")]),
    ]


def eq_accuracy_precision():
    """Acc = (TP+TN)/N，P = TP/(TP+FP)"""
    return [
        mr("Acc = ", sty="p"), frac([mr("TP + TN")], [mr("N")]),
        mr("，    ", sty="p"),
        mr("P = ", sty="p"), frac([mr("TP")], [mr("TP + FP")]),
    ]


def eq_recall_f1():
    """R = TP/(TP+FN)，F1 = 2PR/(P+R)"""
    return [
        mr("R = ", sty="p"), frac([mr("TP")], [mr("TP + FN")]),
        mr("，    ", sty="p"),
        mr("F1 = ", sty="p"), frac([mr("2PR")], [mr("P + R")]),
    ]
