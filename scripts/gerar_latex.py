"""Exporta o relatório editável para LaTeX e monta o projeto do Overleaf.

Executar após gerar_relatorio.py para usar as tabelas atualizadas.
O ZIP inclui apenas os fontes LaTeX, as cinco figuras e as instruções.
"""
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'relatorio'


def escape(text):
    replacements = {
        '\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
        '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
        '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
        'µ': r'\ensuremath{\mu}', '×': r'\ensuremath{\times}',
        '·': r'\textperiodcentered{}',
        '∈': r'\ensuremath{\in}', '−': r'\ensuremath{-}',
        '≤': r'\ensuremath{\leq}', '≥': r'\ensuremath{\geq}',
        '…': r'\ldots{}', '–': '--', '—': '---', '“': '``', '”': "''",
    }
    return ''.join(replacements.get(char, char) for char in text)


def inline(text):
    parts = re.split(r'(\*\*.*?\*\*|https://\S+|`[^`]+`|(?:scripts|dados|analises|relatorio)/[\w./-]+)', text)
    result = []
    for part in parts:
        if part.startswith('**'):
            result.append(r'\textbf{' + inline(part[2:-2]) + '}')
        elif part.startswith('https://'):
            result.append(r'\url{' + part + '}')
        elif part.startswith('`'):
            result.append(r'\texttt{' + escape(part[1:-1]) + '}')
        elif re.match(r'(?:scripts|dados|analises|relatorio)/', part):
            result.append(r'\path{' + part + '}')
        else:
            result.append(escape(part))
    return ''.join(result)


def convert(source):
    output = ['% Conteúdo do relatório. Preencher o RA na identificação abaixo.']
    figures = []
    table_count = 0
    for block in source.strip().split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if block == '<!-- pagina -->':
            output.append(r'\clearpage')
        elif block.startswith('<!-- pagina -->\n'):
            output.append(r'\clearpage')
            heading = block.split('\n', 1)[1]
            assert heading.startswith('## '), heading
            output.append(r'\section*{' + inline(heading[3:]) + '}')
        elif block.startswith('|'):
            matrix = [[cell.strip() for cell in line.strip('|').split('|')]
                      for line in block.splitlines()]
            header, body = matrix[0], matrix[2:]
            assert all(len(row) == len(header) for row in body)
            columns = ' '.join('Y' for _ in header)
            table = [r'\begingroup', r'\fontsize{6.7}{8.8}\selectfont',
                     r'\setlength{\tabcolsep}{3pt}', r'\renewcommand{\arraystretch}{1.25}',
                     r'\noindent\begin{tabularx}{\linewidth}{@{}' + columns + '@{}}',
                     r'\toprule', r'\rowcolor{cabecalho}',
                     ' & '.join(r'\textbf{' + inline(c) + '}' for c in header) + r' \\',
                     r'\midrule']
            table.extend(' & '.join(inline(c) for c in row) + r' \\' for row in body)
            table.extend([r'\bottomrule', r'\end{tabularx}', r'\par\endgroup\vspace{5pt}'])
            output.append('\n'.join(table))
            table_count += 1
        elif block.startswith('!['):
            match = re.fullmatch(r'!\[(.*?)\]\((.*?)\)', block, re.S)
            assert match, block
            caption, path = match.groups()
            path = str(Path(path).with_suffix('.pdf')).replace('\\', '/')
            assert (REPORT / path).is_file(), path
            figures.append(path)
            output.append('\n'.join([
                r'\noindent\includegraphics[width=\linewidth]{' + path + '}',
                r'\par\vspace{3pt}',
                r'{\sffamily\fontsize{7.5}{10}\selectfont ' + inline(caption) + r'\par}',
                r'\vspace{7pt}',
            ]))
        elif block.startswith('### '):
            output.append(r'\subsection*{' + inline(block[4:]) + '}')
        elif block.startswith('## '):
            output.append(r'\section*{' + inline(block[3:]) + '}')
        elif block.startswith('# '):
            output.append(r'{\sffamily\bfseries\color{titulo}\fontsize{17}{21}\selectfont '
                          + inline(block[2:]) + r'\par}\vspace{9pt}')
        else:
            output.append(inline(block.replace('\n', ' ')) + '\n\\par')
    assert table_count == 5, table_count
    assert len(figures) == 5, figures
    assert sum(r'\clearpage' in block for block in output) == 7
    return '\n\n'.join(output) + '\n', figures


PREAMBLE = r'''% Arquivo principal: compilar main.tex com pdfLaTeX no Overleaf.
\documentclass[9pt,a4paper]{extarticle}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[brazil]{babel}
\usepackage{lmodern}
\usepackage[left=38pt,right=38pt,top=40pt,bottom=37pt,footskip=20pt]{geometry}
\usepackage{graphicx}
\usepackage[table]{xcolor}
\usepackage{array,tabularx,booktabs}
\usepackage{amsmath,amssymb}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{microtype}
\usepackage{xurl}
\usepackage[unicode,hidelinks]{hyperref}

\definecolor{titulo}{HTML}{153D52}
\definecolor{cabecalho}{HTML}{E4EDF2}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\setlength{\emergencystretch}{2em}
\titleformat{\section}{\sffamily\bfseries\color{titulo}\fontsize{11.5}{15}\selectfont}{}{0pt}{}
\titleformat{\subsection}{\sffamily\bfseries\fontsize{9.8}{13}\selectfont}{}{0pt}{}
\titlespacing*{\section}{0pt}{6pt}{8pt}
\titlespacing*{\subsection}{0pt}{4pt}{5pt}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[L]{\sffamily\fontsize{7}{9}\selectfont UNIVALI \textperiodcentered{} Sistemas em Tempo Real \textperiodcentered{} Atividade complementar M3}
\fancyfoot[R]{\sffamily\fontsize{7}{9}\selectfont\thepage}
\hypersetup{pdftitle={Quanto o teste enxerga do pior caso? -- Huffman na ESP32},pdfauthor={Miguel Bertonzin}}

\begin{document}
\fontsize{9}{12}\selectfont
\input{conteudo.tex}
\end{document}
'''

INSTRUCTIONS = '''# Arquivos para o Overleaf

Importar `Overleaf_Miguel_STR.zip` como projeto e compilar `main.tex` com pdfLaTeX.
O texto e as tabelas ficam em `conteudo.tex`; a identificação tem o campo do RA.
As cinco figuras em PDF ficam em `figuras/`.

Para gerar novamente a partir das análises, executar na raiz do repositório:

```powershell
python scripts/gerar_relatorio.py
python scripts/gerar_latex.py
```

A geração substitui `main.tex`, `conteudo.tex` e o ZIP. Guarde separadamente as
alterações feitas no Overleaf antes de gerar novamente.
'''


def main():
    source = (REPORT/'RELATORIO_EDITAVEL.md').read_text(encoding='utf-8')
    content, figures = convert(source)
    for name, text in [('main.tex', PREAMBLE), ('conteudo.tex', content), ('OVERLEAF.md', INSTRUCTIONS)]:
        (REPORT/name).write_text(text, encoding='utf-8', newline='\n')
    package = REPORT/'Overleaf_Miguel_STR.zip'
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ['main.tex', 'conteudo.tex', 'OVERLEAF.md', *figures]:
            archive.write(REPORT/name, name)
    print(f'LaTeX e projeto Overleaf gerados: {package}')


if __name__ == '__main__':
    main()
