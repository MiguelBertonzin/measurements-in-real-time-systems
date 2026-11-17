# Huffman na ESP32

Miguel Bertonzin · Sistemas em Tempo Real · UNIVALI.

[Relatório em PDF](relatorio/Relatorio_Individual_Miguel_STR.pdf) ·
[Projeto Overleaf](relatorio/Overleaf_Miguel_STR.zip) ·
[Resultados](analises/tabela_sintese.csv) ·
[Gráficos](analises/graficos_completos.pdf)

Medições de Huffman em quatro etapas: tarefa isolada, evento, tarefas concorrentes
e sistema com tráfego UART. São 1.000 ativações nas etapas 1–3 e 10.000 na etapa 4,
com deadline fixo de 32.440,8 µs. ESP32-D0WD-V3, CPU de 160 MHz e tick de 100 Hz.

Os CSV, logs e fontes de cada etapa estão em `dados/`. As estatísticas, perdas
de prazo, janelas (m,k) e gráficos estão em `analises/`.

## Reproduzir as análises

Na raiz do projeto, com Python 3.11:

```powershell
python -m venv .venv-analise
.\.venv-analise\Scripts\python.exe -m pip install -r requirements-relatorio.txt
.\.venv-analise\Scripts\python.exe scripts/analisar_coletas.py
.\.venv-analise\Scripts\python.exe scripts/verificar_analises.py
.\.venv-analise\Scripts\python.exe scripts/gerar_relatorio.py
.\.venv-analise\Scripts\python.exe -m unittest discover -s tests -p test_metricas.py -v
```

O texto do relatório fica em `relatorio/texto_base.md`; o RA ainda precisa ser preenchido.
Para recompilar uma etapa, copiar `dados/etapaN/fontes` para uma pasta separada
e executar `idf.py build` no terminal ESP-IDF. A etapa 4 também precisa do coletor
`scripts/coletar_sistema.py` para gerar o tráfego UART.

As coletas estão concluídas. Novas medições devem ser salvas em outra pasta.
A análise confere os logs e seus hashes. O prefixo de boot da etapa 2 está
preservado e documentado no relatório. HWM e (m,k) descrevem as amostras observadas.
