# Rodar uma etapa na apresentação

O módulo `huffman.c` é o mesmo nos quatro cenários. Cada etapa tem uma versão
de `main.c` com sua instrumentação e cargas, preservada em `dados/etapaN/fontes`.
A pasta `main` da raiz contém a etapa 4. Rodar o botão de build nessa pasta
compila a etapa 4; o menuconfig não escolhe o cenário.

| Etapa | O que demonstra | Ativações | Duração aproximada |
| --- | --- | ---: | --- |
| 1 | Huffman isolado, com validação | 1.000 | 40 s |
| 2 | Atendimento de um evento por vez | 1.000 | 40 s |
| 3 | Tarefas periódicas, CPU, buffer e mutex | 1.000 | 1 min 40 s |
| 4 | Etapa 3 mais carga UART gerada pelo computador | 10.000 | 16 min 40 s |

Esses tempos não incluem compilação, gravação e transmissão final do CSV.
As medições aparecem ao final; silêncio durante a execução é esperado.

Abra o **terminal ESP-IDF** no VS Code. Se aparecer `.venv-analise`, use o Python
do ESP-IDF explicitamente na preparação, conforme o comando abaixo. Para rodar
`idf.py` e os coletores, use o terminal ESP-IDF com o ambiente dele ativo.

```powershell
cd C:\Users\Migue\M3_STR
& 'C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe' scripts/preparar_demonstracao.py --etapa 2
```

Troque `2` por `1`, `3` ou `4`. O script imprime o comando `cd` da pasta criada
e os comandos seguintes. Ele copia os fontes e a configuração daquele cenário;
não muda os arquivos de medição do relatório. Cada preparação cria outra pasta.

Para as etapas 1–3, depois do `cd` impresso:

```powershell
idf.py -p COM7 build flash monitor
```

Para salvar uma execução, saia do monitor com Ctrl+] e rode o comando de captura
impresso pelo preparador. Ele reinicia a placa e salva a execução seguinte em
`dados/etapaN/tentativas` da pasta de demonstração.

Para a etapa 4, depois do `cd` impresso:

```powershell
idf.py -p COM7 build flash
python scripts/coletar_sistema.py --porta COM7
```

O coletor da etapa 4 gera o tráfego UART e salva o log. Mantenha o monitor fechado
para liberar a COM7. Só abrir o monitor não executa a carga externa necessária.
Troque COM7 se a placa estiver em outra porta.

O botão Build, Flash and Monitor também serve para as etapas 1–3 se a pasta de
demonstração for aberta como projeto no VS Code. Na etapa 4, use Build/Flash e
o coletor; o monitor deve ficar fechado.

Os experimentos A–D têm outra função: A mede cobertura com os testes no computador;
B analisa o máximo acumulado; C compara margens; D recalcula perdas e janelas com
outros deadlines. B, C e D usam os CSV salvos e não exigem mudar o firmware.
Na raiz, `python scripts/analisar_coletas.py` reproduz as análises dos dados da
campanha; `python scripts/medir_cobertura.py` refaz a cobertura com GCC/gcov.

Uma nova execução pode produzir outros tempos. Apresente-a como demonstração:
os valores do relatório continuam ligados às coletas originais preservadas.
