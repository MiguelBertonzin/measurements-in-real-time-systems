# Cobertura do algoritmo — experimento A

Medição real com GCC/gcov no computador Windows, separada da coleta temporal
na ESP32. Escopo: `main/huffman.c`. O módulo não foi alterado para aumentar a
cobertura; foram acrescentados casos de teste em `tests/test_huffman.c`.

- Linhas executadas: **98,89% (89 de 90)**.
- Desvios tomados ao menos uma vez: **98,75% (79 de 80)**.
- Desvios executados: **100%**. Isso significa que as decisões foram atingidas,
  não que todos os seus resultados foram tomados. A métrica de cobertura de
  desvios que será usada no relatório é **98,75%**.

O único resultado não exercitado é o retorno de erro por overflow de
`total_bits`, na proteção anterior a `frequencia * comprimento`. Na compilação
de teste de 64 bits, a entrada aceita tem no máximo `UINT32_MAX` bytes e cada
código tem no máximo 255 bits: mesmo esse limite conservador cabe em `size_t`
de 64 bits. Portanto, esse erro não é alcançável por entradas válidas nessa
plataforma. Na campanha com 4096 bytes, também não há risco de esse total
ultrapassar `size_t` de 32 bits. Não foram removidos os testes de proteção.

O enunciado permite justificar a impossibilidade de atingir 100%. Não será
alegado que 100% de linhas, desvios ou caminhos foram cobertos. O HWM inicial
da ESP32 continua sendo 27034 us, observado em outra compilação, sem cobertura.
Não houve marco de 100% a associar a esse HWM; a comparação entre etapas deve
explicitar essa limitação.

Os testes incluem round-trip de entradas especiais e aleatórias, vetor
conhecido ABBA -> 0110, códigos longos, fluxo truncado, argumentos inválidos,
buffers insuficientes e corrupção controlada de índices da árvore. Os casos
de corrupção exercitam defesas; não representam a carga temporal da campanha.

Reprodução, na raiz do projeto:

```text
python scripts/medir_cobertura.py
```

Pode-se informar `--gcc CAMINHO_DO_GCC`. Evidências: `execucao.txt`,
`huffman.c.gcov`, `resumo.json` e cópias dos fontes em `fontes/`.
