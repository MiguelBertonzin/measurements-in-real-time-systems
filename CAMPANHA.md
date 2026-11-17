# Registro das coletas

Miguel Bertonzin — ESP32-D0WD-V3, revisão 3.1, MAC 1c:69:20:31:5e:e8.
CPU: 160 MHz. Tick: 100 Hz. Entrada: 4.096 bytes. Semente: 123456789.
Deadline: 1,2 × HWM da etapa 1 = 32.440,8 µs.

| Etapa | Ativações | HWM (µs) | Perdas com D fixo |
| --- | ---: | ---: | ---: |
| Tarefa isolada | 1.000 | 27.034 | 0 |
| Evento | 1.000 | 27.148 | 0 |
| Intertarefas | 1.000 | 39.962 | 179 |
| Sistema com UART | 10.000 | 40.304 | 1.786 |

As quatro coletas foram validadas. Os arquivos de cada etapa ficam em `dados/etapaN`.
Na etapa 2, o log original contém um prefixo de boot de 33.340 bytes; a execução
completa está em `log_validado.txt`, sem excluir amostras. Na etapa 4, a placa
registrou 1.342.958 bytes recebidos pela UART.

Análises A–D, gráficos e relatório concluídos. Falta preencher o RA no relatório.
