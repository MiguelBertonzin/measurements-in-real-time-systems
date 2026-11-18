# Huffman na ESP32

Sistemas em Tempo Real · UNIVALI · Miguel Bertonzin

Medições de Huffman em quatro etapas: tarefa isolada, evento, tarefas concorrentes
e sistema com tráfego UART. A campanha reúne 13.000 ativações e usa um deadline
fixo de 32.440,8 µs. A placa é uma ESP32-D0WD-V3 a 160 MHz, com tick de 100 Hz.

## Reproduzir as análises

Na raiz do projeto, em um ambiente Python 3.11 com pip:

```sh
python -m pip install -r requirements-analise.txt
python scripts/analisar_coletas.py
python scripts/verificar_analises.py
python -m unittest discover -s tests -p test_metricas.py -v
```

O primeiro script de análise gera tabelas, gráficos e janelas em [analises/](analises/).
A verificação compara esses resultados com os CSVs e os logs da campanha.
A cobertura original está em [dados/cobertura/](dados/cobertura/). Para medi-la
novamente, execute `python scripts/medir_cobertura.py` com GCC e gcov disponíveis.

## Compilar e executar na ESP32

[DEMONSTRAÇÃO.txt](DEMONSTRA%C3%87%C3%83O.txt) descreve a compilação e a coleta
com ESP-IDF. Cada etapa tem seu próprio `main.c` e `sdkconfig` em
`dados/etapaN/fontes/`. O projeto na raiz corresponde à etapa 4.

Os CSVs de medição e seus logs ficam em [dados/](dados/). A configuração
e o resumo da campanha estão em [CAMPANHA.md](CAMPANHA.md). O relatório
em PDF acompanha o pacote de entrega.
