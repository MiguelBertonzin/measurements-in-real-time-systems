# Arquivos para o Overleaf

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
