"""按现有证据整理报告与分析措辞；不重新训练，不重建图表。"""
from pathlib import Path
import re

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '实验报告/决策树实验报告-分析完善版.docx'


def rewrite(paragraph, text):
    """保留段落与首个文本运行的格式。"""
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ''
    else:
        paragraph.add_run(text)


def polish(doc):
    # 在讨论前展示两组对照，移动原始XML节点以保留表格与样式。
    paragraphs = doc.paragraphs
    discussion = next(p for p in paragraphs if p.text == '6.10 结果讨论')
    first = next(p for p in paragraphs if p.text.startswith('7.4 编码'))
    stop = next(p for p in paragraphs if p.text.startswith('7.6 从疑问'))
    current = first._p
    while current is not stop._p:
        following = current.getnext()
        discussion._p.addprevious(current)
        current = following

    # 讨论使用条件判断和具体数字，不编写学习经历。
    points = [
        '（1）我不会把100%直接理解成模型没有问题。当前测试集有2438条样本，重复核查没有发现跨集合相同记录，30次划分中29次满分。这些结果支持数据中的分类规则比较容易学习。我的结论只限于这份数据和这些划分，真实环境中的识别能力还没有得到验证。',
        '（2）在干净数据上，我倾向于选择序数编码的信息熵树作为本实验的主要解释模型。它与基尼树的测试准确率相同，叶节点却从20个减少到14个，便于逐条查看规则。这个选择依据是当前模型规模，而不是认定信息熵总比基尼指数好，也没有据此声称推理更快。',
        '（3）如果训练标签不可靠，我更倾向于随机森林。相同10%标签翻转位置下，基尼树和信息熵树的平均准确率约为85.82%和86.46%，随机森林约为99.54%。这组对照比干净数据上共同达到100%更能区分模型。但噪声是人为翻转标签构造的，不能替代对现实错误来源的验证。',
        '（4）表11同时列出默认阈值和验证集所选阈值在测试集上的总代价与漏判数。代价比是实验设定。实际应用中的阈值还取决于错误损失与实际样本分布。',
    ]
    for paragraph in list(doc.paragraphs):
        text = paragraph.text
        if text == '6.10 结果讨论':
            rewrite(paragraph, '6.12 结果讨论与模型取舍')
        elif text.startswith('7.4 编码'):
            rewrite(paragraph, '6.10 编码与模型复杂度对照')
        elif text.startswith('7.5 相同噪声'):
            rewrite(paragraph, '6.11 相同噪声位置下的鲁棒性对照')
        elif text == '综合 6.1–6.9 的结果，可以归纳为以下六点。':
            rewrite(paragraph, '结合基础实验和两组补充对照，我对结果作如下判断。')
        elif text.startswith(tuple(f'（{i}）' for i in range(1, 7))):
            # 只修改旧结果讨论中的编号段落。
            previous = paragraph._p.getprevious()
            in_discussion = False
            while previous is not None:
                content = ''.join(previous.itertext())
                if '6.12 结果讨论与模型取舍' in content:
                    in_discussion = True
                    break
                if previous.tag.endswith('}p') and '七、选做内容' in content:
                    break
                previous = previous.getprevious()
            if in_discussion:
                number = int(text[1])
                if number <= 4:
                    rewrite(paragraph, points[number-1])
                else:
                    paragraph._p.getparent().remove(paragraph._p)
        elif text.startswith('但两棵树在规模上存在明显差异'):
            rewrite(paragraph, '两棵完整树深度均为7，基尼树有20个叶节点，信息熵树有14个。当前划分下信息熵树更小，这是实际结果；不同准则为什么产生不同结构，还取决于具体特征分布和候选划分。不能仅凭这一例把“树更小”归结为信息熵准则的普遍优势。')
        elif text.startswith('结果分析：自己实现的 ID3'):
            rewrite(paragraph, '多路ID3有29个节点、24个叶节点，简化增益率树有26个节点、20个叶节点，两者测试准确率均为100%。增益率会用分裂信息归一化信息增益，但当前节点数差异并不能证明它在所有数据上都能避免ID3的多值偏好。比较二叉树与多路树时还要考虑分支形式；不能只按节点总数判定算法优劣。')
        elif text.startswith('7.6 从疑问'):
            rewrite(paragraph, '7.4 实现边界与核实方法')
        elif text.startswith('首先核查100%'):
            rewrite(paragraph, '核查分成三步：检查样本重复，改变数据划分，再加入标签噪声。三种检查分别对应数据重叠、划分偶然性和训练标签扰动；它们能发现部分问题，不能代替全部泄漏检查。具体结果与模型选择见6.12。')
        elif text.startswith('其次核查阈值'):
            rewrite(paragraph, '阈值实验将选择与评价分开：训练部分内部的验证集负责选择阈值，冻结后在测试集评价，所有概率恰好等于阈值的样本统一判为有毒。这样可以避免在测试集上挑出最优结果后再报告同一结果。')
        elif text.startswith('7.4与7.5补充'):
            paragraph._p.getparent().remove(paragraph._p)
        elif text.startswith('7.7 一条'):
            rewrite(paragraph, '7.5 一条实际预测路径')
        elif text.startswith('根节点计算核对：'):
            rewrite(paragraph, '根节点计算核对：下表给出训练集odor各取值的类别计数，下一段给出按信息熵公式计算的中间值，便于检查信息增益与增益率。')
        elif text.startswith('数值核对：'):
            rewrite(paragraph, '训练集共5686条。H(D)=0.999071；odor只有n分支同时含两类样本，该分支2485条，其中可食2397条、有毒88条，其余分支均为纯节点。因此H(D|odor)=(2485/5686)×H(2397/2485,88/2485)=0.096519。信息增益为0.902552；分裂信息为2.301773，增益率为0.392112。这里各分支必须按样本比例加权，不能直接把分支熵相加。')

    # 更新交叉引用与导读，不改公式、图片或表格数据。
    for paragraph in doc.paragraphs:
        text = paragraph.text
        new = text.replace('6.10 对全部结果做统一讨论', '6.10–6.11补充编码与噪声对照，6.12统一讨论')
        new = new.replace('最后统一讨论（6.10）', '随后补充两组对照并统一讨论（6.10–6.12）')
        new = new.replace('7.5节同位置', '6.11节同位置').replace('7.5节', '6.11节')
        new = new.replace('详细交叉验证对照见7.3与7.4', '详细选参流程见7.3，结果对照见6.10')
        new = new.replace('基于以上结论，第七节给出三项选做内容的具体实现与验证，第八节列出全部提交文件。', '第七节给出多路树实现、计算核对和预测路径，第八节列出复现材料。')
        new = new.replace('还自己实现了 ID3 与 简化C4.5', '项目实现了ID3与简化C4.5')
        new = new.replace('决策树实验报告-修正版.docx', OUTPUT.name)
        if new != text:
            rewrite(paragraph, new)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if '决策树实验报告-修正版.docx' in paragraph.text:
                        rewrite(paragraph, paragraph.text.replace('决策树实验报告-修正版.docx', OUTPUT.name))
    table_numbers = {13: 15, 14: 16, 15: 13, 16: 14}
    for paragraph in doc.paragraphs:
        text = paragraph.text
        new = re.sub(r"表\s*(13|14|15|16)(?![0-9])",
                     lambda match: "表 " + str(table_numbers[int(match[1])]), text)
        if new != text:
            rewrite(paragraph, new)
    return doc


if __name__ == '__main__':
    source = ROOT / '实验报告/决策树实验报告-修正版.docx'
    document = polish(Document(source))
    document.save(OUTPUT)
    print(OUTPUT)
