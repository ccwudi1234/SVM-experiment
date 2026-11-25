"""使用已安装的 Word 导出 PDF 并渲染预览，不修改源文档。"""
import argparse
from pathlib import Path

import pymupdf as fitz
import win32com.client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('document', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    source = args.document.resolve()
    target = args.output_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    pdf = target / (source.stem + '.pdf')
    word = win32com.client.DispatchEx('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    document = None
    try:
        document = word.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False)
        document.Repaginate()
        document.ExportAsFixedFormat(str(pdf), 17)
    finally:
        if document is not None:
            document.Close(False)
        word.Quit()
    with fitz.open(pdf) as rendered:
        for number, page in enumerate(rendered, 1):
            page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4)).save(str(target / f'page-{number:02}.png'))
        print(f'Pages: {len(rendered)}; previews: {target}')


if __name__ == '__main__':
    main()
