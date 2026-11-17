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
    parts = re.split(r'(\*\*.*?\*\*|https://\S+|`[^`]+`|\b2\^(?:32|64)\b|(?:scripts|dados|analises|relatorio)/[\w./-]+)', text)
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
        elif re.fullmatch(r'2\^(32|64)', part):
            result.append(r'\ensuremath{2^{' + part[2:] + '}}')
        else:
            result.append(escape(part))
    return ''.join(result)


def convert(source):
    output = ['% Conteúdo do relatório. Preencher o RA na identificação abaixo.']
    figures = []
    table_count = 0
    # A identificação fica na capa; o corpo começa na primeira seção numerada.
    source = source[source.index('## 1. '):]
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
            output.append(r'\section{' + inline(re.sub(r'^\d+\.\s*', '', heading[3:])) + '}')
        elif block.startswith('|'):
            matrix = [[cell.strip() for cell in line.strip('|').split('|')]
                      for line in block.splitlines()]
            header, body = matrix[0], matrix[2:]
            assert all(len(row) == len(header) for row in body)
            columns = ' '.join('Y' for _ in header)
            table = [r'\begingroup', r'\fontsize{7}{9}\selectfont',
                     r'\setlength{\tabcolsep}{1.5pt}', r'\renewcommand{\arraystretch}{1.15}',
                     r'\noindent\begin{tabularx}{\linewidth}{@{}' + columns + '@{}}',
                     r'\toprule',
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
                r'{\noindent\fontsize{8}{10}\selectfont ' + inline(caption) + r'\par}',
                r'\vspace{7pt}',
            ]))
        elif block.startswith('### '):
            title = block[4:]
            command = r'\subsection' if re.match(r'^\d+\.\d+ ', title) else r'\subsection*'
            title = re.sub(r'^\d+\.\d+\s*', '', title)
            output.append(command + '{' + inline(title) + '}')
        elif block.startswith('## '):
            output.append(r'\section{' + inline(re.sub(r'^\d+\.\s*', '', block[3:])) + '}')
        elif block.startswith('# '):
            output.append(r'{\sffamily\bfseries\color{titulo}\fontsize{17}{21}\selectfont '
                          + inline(block[2:]) + r'\par}\vspace{9pt}')
        else:
            output.append(inline(block.replace('\n', ' ')) + '\n\\par')
    assert table_count == 5, table_count
    assert len(figures) == 5, figures
    assert sum(r'\clearpage' in block for block in output) == 6
    return '\n\n'.join(output) + '\n', figures


PREAMBLE = r'''% Arquivo principal: compilar main.tex com pdfLaTeX no Overleaf.
% Estilo da M2: capa institucional, Latin Modern, títulos pretos e recuo.
% Corpo compacto e sem sumário separado para respeitar as oito páginas da M3.
\documentclass[12pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[brazil]{babel}
\usepackage{lmodern}
\usepackage[left=30mm,right=20mm,top=25mm,bottom=25mm,footskip=12mm]{geometry}
\usepackage{graphicx}
\usepackage[table]{xcolor}
\usepackage{array,tabularx,booktabs}
\usepackage{amsmath,amssymb}
\usepackage{titlesec}
\usepackage{indentfirst}
\usepackage{microtype}
\usepackage{xurl}
\usepackage[unicode,hidelinks]{hyperref}

\definecolor{institucional}{HTML}{174586}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\setlength{\parindent}{1.25cm}
\setlength{\parskip}{3pt}
\setlength{\emergencystretch}{2em}
\titleformat{\section}{\bfseries\fontsize{14}{17}\selectfont}{\thesection}{0.8em}{}
\titleformat{\subsection}{\bfseries\fontsize{11}{13}\selectfont}{\thesubsection}{0.8em}{}
\titlespacing*{\section}{0pt}{7pt}{7pt}
\titlespacing*{\subsection}{0pt}{5pt}{4pt}
\pagestyle{plain}
\hypersetup{pdftitle={Quanto o teste enxerga do pior caso? -- Huffman na ESP32},pdfauthor={Miguel Bertonzin}}

\begin{document}
\hypersetup{pageanchor=false}
\input{capa.tex}
\hypersetup{pageanchor=true}
\fontsize{11}{13}\selectfont
\input{conteudo.tex}
\end{document}
'''

INSTRUCTIONS = '''# Arquivos para o Overleaf

Importar `Overleaf_Miguel_STR.zip` como projeto e compilar `main.tex` com pdfLaTeX.
O texto e as tabelas ficam em `conteudo.tex`; o RA fica em `capa.tex`.
As cinco figuras em PDF ficam em `figuras/`.

O estilo segue a M2: capa institucional, fonte Latin Modern, títulos numerados,
parágrafos com recuo e paginação central. O corpo foi compactado para 11 pt,
sem sumário separado: são oito páginas físicas, incluindo a capa, conforme a M3.

Para gerar novamente a partir das análises, executar na raiz do repositório:

```powershell
python scripts/gerar_relatorio.py
```

A geração usa `texto_base.md` e substitui os três arquivos `.tex` e o ZIP.
Com Tectonic disponível, também compila o PDF; caso contrário, compilar no Overleaf.
Guarde separadamente as
alterações feitas no Overleaf antes de gerar novamente.
'''


def main():
    source = (REPORT/'RELATORIO_EDITAVEL.md').read_text(encoding='utf-8')
    content, figures = convert(source)
    student = re.search(r'\*\*Acadêmico:\*\* (.*)', source)[1].rstrip('.')
    professors = re.search(r'\*\*Professores:\*\* (.*)', source)[1].rstrip('.')
    repository = re.search(r'\*\*Repositório:\*\* (https://\S+)', source)[1]
    cover = r'''% Identificação do trabalho individual.
\begin{titlepage}
\centering
{\color{institucional}\bfseries\fontsize{24.88}{30}\selectfont UNIVALI\par}
\vspace{10pt}
Universidade do Vale do Itajaí\\
Escola Politécnica\\
Engenharia de Computação\\
Sistemas em Tempo Real
\vfill
{\bfseries\fontsize{17.28}{21}\selectfont ATIVIDADE COMPLEMENTAR M3\\
QUANTO O TESTE ENXERGA DO PIOR CASO?\par}
\vspace{14pt}
{\fontsize{14.4}{18}\selectfont Codificação de Huffman na ESP32:\\
tempo de resposta e análise (m,k)-firme\par}
\vfill
\textbf{Acadêmico}\\
''' + inline(student).replace(' --- RA:', r'\\ RA:') + r'''
\vspace{20pt}

\textbf{Professores}\\
''' + inline(professors).replace(' e Felipe', r'\\ Felipe') + r'''
\vspace{20pt}

{\fontsize{9}{12}\selectfont\textbf{Repositório}\\
\url{''' + repository + r'''}\par}
\vfill
Itajaí -- SC\\
2026
\end{titlepage}
'''
    for name, text in [('main.tex', PREAMBLE), ('capa.tex', cover), ('conteudo.tex', content), ('OVERLEAF.md', INSTRUCTIONS)]:
        (REPORT/name).write_text(text, encoding='utf-8', newline='\n')
    package = REPORT/'Overleaf_Miguel_STR.zip'
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ['main.tex', 'capa.tex', 'conteudo.tex', 'OVERLEAF.md', *figures]:
            archive.write(REPORT/name, name)
    print(f'LaTeX e projeto Overleaf gerados: {package}')


if __name__ == '__main__':
    main()
