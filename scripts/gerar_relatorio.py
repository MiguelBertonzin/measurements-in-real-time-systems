"""Monta o relatório de oito páginas a partir do texto e das coletas preservadas.

Editar relatorio/texto_base.md para revisar o texto e preencher os RAs.
Tabelas e figuras são reconstruídas a partir dos resultados e dos CSV.
"""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv
import json
import re
from html import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image

from analisar_coletas import load, FIXED_D
from metricas import analyze, compact

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "relatorio"
FIG = OUT / "figuras"
LABELS = ["1. Tarefa", "2. Comportamental", "3. Intertarefas", "4. Sistema"]
D = FIXED_D / 1000


def br(value, digits=0):
    # Arredondamento decimal convencional, inclusive médias terminadas em 0,0005.
    number = Decimal(str(value)).quantize(Decimal(10) ** -digits, rounding=ROUND_HALF_UP)
    return f"{number:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def mdtable(header, data):
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in [header, ["---"] * len(header), *data])


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=220)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


def figures(times):
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
                         "legend.fontsize": 7, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 3.65), layout="constrained")
    for s, ax in enumerate(axes.flat, 1):
        y = times[s] / 1000  # ns -> us
        ax.hist(y / 1000, bins=45, color="#236885", log=True)
        ax.axvline(max(y) / 1000, color="#b43832", lw=1.1, label="HWM")
        ax.axvline(D / 1000, color="#d88500", ls="--", lw=1.1, label="D")
        ax.set(title=LABELS[s-1], xlabel="Resposta (ms)", ylabel="Contagem (log)")
        ax.set_ylim(bottom=0.8)
        ax.legend(loc="upper right")
        if s <= 2:
            ax.set_xlim(26.7, 33)
            detail = ax.inset_axes([.27, .29, .43, .58])
            detail.hist(y / 1000, bins=30, color="#236885", log=True)
            detail.axvline(max(y) / 1000, color="#b43832", lw=.8)
            detail.set_title("Detalhe (ms)", fontsize=7)
            detail.tick_params(labelsize=6)
            detail.set_ylim(bottom=.8)
    save(fig, "histogramas")

    fig, axes = plt.subplots(4, 1, figsize=(7.4, 4.35), sharey=True, layout="constrained")
    for s, ax in enumerate(axes, 1):
        y = times[s] / 1e6
        x = np.arange(1, len(y)+1)
        lost = times[s] > FIXED_D
        ax.scatter(x, y, s=1.1, color="#236885", rasterized=True)
        ax.scatter(x[lost], y[lost], s=2, color="#b43832", rasterized=True)
        ax.axhline(D / 1000, color="#d88500", ls="--", lw=.8)
        ax.set(xlim=(1, len(y)), ylim=(26, 42), ylabel="R (ms)")
        ax.text(.012, .78, LABELS[s-1], transform=ax.transAxes, fontsize=8)
        if s >= 3:
            detail = ax.inset_axes([.66, .34, .32, .59])
            detail.scatter(x[:100], y[:100], s=1.7, color="#236885")
            detail.axhline(D / 1000, color="#d88500", ls="--", lw=.6)
            detail.set(xlim=(1, 100), ylim=(26, 42), xticks=[1,50,100], yticks=[27,40])
            detail.tick_params(labelsize=5.5, pad=1)
        ax.grid(axis="y", alpha=.15)
    axes[-1].set_xlabel("Número da ativação")
    save(fig, "temporais")

    fig, axes = plt.subplots(4, 3, figsize=(7.4, 4.6), sharey="col", layout="constrained")
    for s in range(1, 5):
        lost = (times[s] > FIXED_D).astype(int)
        for col, k in enumerate((10,20,50)):
            counts = np.convolve(lost, np.ones(k, dtype=int), mode="valid")
            ax = axes[s-1, col]
            ax.plot(np.arange(1, len(counts)+1), counts, lw=.55, color="#236885")
            ax.set_ylim(-.2, {10:3.4,20:4.5,50:11}[k])
            ax.set_xlim(1,len(counts))
            if s == 1: ax.set_title(f"k = {k}")
            if col == 0: ax.set_ylabel(f"Etapa {s}\nPerdas")
            if s == 4: ax.set_xlabel("Início da janela")
            ax.grid(alpha=.18)
    save(fig, "janelas")

    y = times[4] / 1000
    hwm = np.maximum.accumulate(y)
    fig, axes = plt.subplots(1,2,figsize=(7.4,1.55),layout="constrained")
    axes[0].plot(np.arange(1,len(y)+1),hwm/1000,color="#236885",lw=1)
    axes[0].set(xscale="log", ylabel="HWM (ms)",xlabel="Amostras (log)", title="Etapa 4: todos os prefixos")
    axes[1].plot(np.arange(100,len(y)+1),hwm[99:]/1000,color="#236885",lw=1)
    axes[1].set(xlabel="Amostras",ylabel="HWM (ms)",title="Ampliação após 100 amostras")
    for pos in np.flatnonzero(np.diff(hwm)>0)+2:
        if pos<100:
            continue
        axes[1].plot(pos,hwm[pos-1]/1000,"o",ms=3,color="#b43832")
        axes[1].annotate(str(pos),(pos,hwm[pos-1]/1000),xytext=(5,-12),textcoords="offset points",fontsize=7)
    for ax in axes: ax.grid(alpha=.2)
    save(fig,"convergencia")

    fig, axes = plt.subplots(3,2,figsize=(7.4,2.65),layout="constrained",sharey=True)
    summary=json.loads((ROOT/'analises/resultados.json').read_text(encoding='utf-8'))
    first=summary['1']['hwm_100_us']; last=summary['4']['hwm_99_us']
    for row, deadline in enumerate((first,(first+last)/2,last)):
        for col,s in enumerate((3,4)):
            lost = (times[s] > deadline*1000).astype(int)
            counts=np.convolve(lost,np.ones(20,dtype=int),mode="valid")
            ax=axes[row,col]
            ax.plot(np.arange(1,len(counts)+1),counts,color="#236885",lw=.5)
            ax.set(ylim=(-.3,14),xlim=(1,len(counts)))
            if row==0: ax.set_title(f"Etapa {s}")
            if col==0: ax.set_ylabel(f"D={br(deadline)}\nPerdas")
            if row==2: ax.set_xlabel("Início da janela de 20")
            ax.grid(alpha=.15)
    save(fig,"alternativos")


def tables(results):
    summary=[]; losses=[]
    coverage=json.loads((ROOT/'dados/cobertura/resumo.json').read_text(encoding='utf-8'))
    for s in range(1,5):
        r=results[str(s)]
        summary.append([LABELS[s-1],f"{br(coverage['linhas_percentual'],2)} / {br(coverage['desvios_tomados_percentual'],2)}",br(r['minimo_us']),br(r['media_us'],3),
                        br(r['hwm_100_us']),br(r['hwm_99_us']),br(r['percentual_no_prazo'],2),
                        r['skip_factor'] or '—',*[f"({r['janelas'][str(k)]['m']},{k})" for k in (10,20,50)]])
        losses.append([s,br(r['n']),br(r['perdas']),br(r['percentual_no_prazo'],2),
                       br(r['perdas_isoladas']),r['quantidade_rajadas'],r['maior_sequencia_perdas'],r['skip_factor'] or '—'])
    alternatives=[]
    for r in rows(ROOT/'analises/experimento_d/resumo.csv'):
        alternatives.append([r['etapa'],br(r['deadline_us'],1 if '.' in r['deadline_us'] and not r['deadline_us'].endswith('.0') else 0),
                             br(r['percentual_no_prazo'],2),r['skip_factor'] or '—',
                             *[f"({r[f'm_k{k}']},{k})" for k in (10,20,50)],
                             '/'.join(r[x] for x in ('perdas_isoladas','quantidade_rajadas','maior_rajada'))])
    return {
        'sintese':mdtable(['Etapa','Cob. L/D (%)','Mín.','Média','HWM100','HWM99','Prazo (%)','S','k=10','k=20','k=50'],summary),
        'perdas':mdtable(['Etapa','N','Perdas','Prazo (%)','Isoladas','Rajadas','Maior seq.','S'],losses),
        'convergencia':mdtable(['N','10','20','100','1.000','10.000'],
            [['HWM (µs)',*[br(r['hwm_us']) for r in rows(ROOT/'analises/convergencia_marcos.csv')]]]),
        'margens':mdtable(['Margem','Limite (µs)','HWM4 − limite (µs)','Primeira etapa insuficiente'],
            [[r['margem_percentual']+'%',br(r['limite_us'],1),br(results['4']['hwm_100_us']-float(r['limite_us']),1),
              r['primeira_etapa_insuficiente'] or 'Nenhuma observada'] for r in rows(ROOT/'analises/margens_seguranca.csv')]),
        'alternativos':mdtable(['Etapa','D (µs)','Prazo (%)','S','k=10','k=20','k=50','I/R/M'],alternatives),
    }


def inline(text):
    safe=escape(text)
    safe=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',safe)
    safe=re.sub(r'(https://[^\s<]+)',r'<link href="\1" color="#185a7d">\1</link>',safe)
    return safe


def pdf(text):
    fonts=Path(matplotlib.get_data_path())/'fonts/ttf'
    for name,filename in [('Body','DejaVuSerif.ttf'),('BodyBold','DejaVuSerif-Bold.ttf'),('Sans','DejaVuSans.ttf'),('SansBold','DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(fonts/filename)))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')
    pdfmetrics.registerFontFamily('Sans',normal='Sans',bold='SansBold',italic='Sans',boldItalic='SansBold')
    styles={
        'p':ParagraphStyle('p',fontName='Body',fontSize=9,leading=12,spaceAfter=5,alignment=TA_JUSTIFY),
        'h1':ParagraphStyle('h1',fontName='SansBold',fontSize=17,leading=21,spaceAfter=9,textColor=colors.HexColor('#153d52')),
        'h2':ParagraphStyle('h2',fontName='SansBold',fontSize=11.5,leading=15,spaceBefore=6,spaceAfter=8,textColor=colors.HexColor('#153d52')),
        'h3':ParagraphStyle('h3',fontName='SansBold',fontSize=9.8,leading=13,spaceBefore=4,spaceAfter=5),
        'caption':ParagraphStyle('caption',fontName='Sans',fontSize=7.5,leading=10,spaceAfter=7),
        'cell':ParagraphStyle('cell',fontName='Sans',fontSize=6.7,leading=8.8),
    }
    path=OUT/'Relatorio_Individual_Miguel_STR.pdf'
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=38,leftMargin=38,topMargin=40,bottomMargin=37,
                          title='Quanto o teste enxerga do pior caso? — Huffman na ESP32',
                          author='Miguel Bertonzin')
    story=[]
    for block in text.replace('<!-- pagina -->', '\n\n<!-- pagina -->\n\n').split('\n\n'):
        block=block.strip()
        if not block: continue
        if block=='<!-- pagina -->': story.append(PageBreak()); continue
        if block.startswith('!['):
            match=re.fullmatch(r'!\[(.+)\]\((.+)\)',block)
            image=Image(str(OUT/match[2]))
            image.drawHeight*=doc.width/image.drawWidth
            image.drawWidth=doc.width
            story.extend([image,Spacer(1,4),Paragraph(inline(match[1]),styles['caption'])]); continue
        if block.startswith('|'):
            matrix=[[c.strip() for c in line.strip('|').split('|')] for line in block.splitlines()]
            matrix.pop(1)
            cells=[[Paragraph(inline(c),styles['cell']) for c in row] for row in matrix]
            if len(matrix[0])==11:
                weights=[1.13,1.29,.82,1.17,.91,.91,.89,.32,.9,.9,.9]
            else: weights=[1]*len(matrix[0])
            widths=[doc.width*w/sum(weights) for w in weights]
            table=Table(cells,colWidths=widths,hAlign='LEFT',repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf2')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7f8')]),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),3),
                ('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
                ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#8da6b4'))]))
            story.extend([table,Spacer(1,7)]);continue
        key='p'
        for marker,style in [('### ','h3'),('## ','h2'),('# ','h1')]:
            if block.startswith(marker): key=style;block=block[len(marker):];break
        story.append(Paragraph(inline(block.replace('\n',' ')),styles[key]))
    def footer(canvas,document):
        canvas.setFont('Sans',7)
        canvas.setFillColor(colors.HexColor('#53636c'))
        canvas.drawString(38,22,'UNIVALI · Sistemas em Tempo Real · Atividade complementar M3')
        canvas.drawRightString(A4[0]-38,22,str(document.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    reader=PdfReader(path)
    count=len(reader.pages)
    print(f'PDF: {path}\nPáginas: {count}')
    if count!=8:
        for i,page in enumerate(reader.pages,1):
            print(i,page.extract_text()[:95].replace('\n',' | '))
        raise RuntimeError('Revisar diagramação: esperado relatório com oito páginas.')


def main():
    OUT.mkdir(exist_ok=True);FIG.mkdir(exist_ok=True)
    results=json.loads((ROOT/'analises/resultados.json').read_text(encoding='utf-8'))
    times={}
    for s in range(1,5):
        values,_=load(s)  # Confere CSV, sequência, log e hash antes de publicar números.
        current=json.loads(json.dumps(compact(analyze(values,FIXED_D))))
        if current!=results[str(s)]:
            raise ValueError(f'Resultados desatualizados na etapa {s}; repetir análise.')
        times[s]=np.array(values,dtype=np.int64)
    figures(times)
    text=(OUT/'texto_base.md').read_text(encoding='utf-8')
    for name,content in tables(results).items():text=text.replace('{{'+name+'}}',content)
    if '{{' in text:raise ValueError('Marcador de tabela não preenchido.')
    (OUT/'RELATORIO_EDITAVEL.md').write_text(text,encoding='utf-8')
    pdf(text)


if __name__=='__main__':main()
