# Arquivos para o Overleaf

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
