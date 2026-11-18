# Huffman na ESP32

Sistemas em Tempo Real · UNIVALI.

Medições de Huffman em quatro etapas: tarefa isolada, evento, tarefas concorrentes
e sistema com tráfego UART. São 1.000 ativações nas etapas 1–3 e 10.000 na etapa 4,
com deadline fixo de 32.440,8 µs. ESP32-D0WD-V3, CPU de 160 MHz e tick de 100 Hz.


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

