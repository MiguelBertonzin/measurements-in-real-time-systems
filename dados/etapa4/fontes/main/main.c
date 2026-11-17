/*
 * Etapa 4 — sistema: cargas periódicas, mutex e tráfego UART externo.
 *
 * app_main gera a entrada e envia um evento para a tarefa Huffman.
 * A tarefa acorda, codifica, decodifica, compara e devolve a conclusão.
 * Só então app_main prepara o evento seguinte: nunca há duas entradas em voo.
 * O gerador libera os eventos a cada 100 ms. Duas tarefas de carga disputam
 * o mesmo núcleo: uma usa o buffer encoded com mutex e outra ocupa a CPU.
 * O algoritmo Huffman é o mesmo da etapa 1, preservada em dados/etapa1/fontes.
 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "esp_log.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "huffman.h"

#define EXPERIMENT_STAGE 4
#define EXPERIMENT_VERSION "etapa4-uart-v1"
#define INPUT_SIZE 4096
#define ACTIVATIONS 10000
#define RANDOM_SEED UINT32_C(123456789)
/* D = 1,2 * 27034 us, obtido da coleta inicial da etapa 1.
 * É apenas critério de análise: não interrompe nem descarta execuções tardias. */
#define DEADLINE_NS UINT64_C(32440800)
#define WORKER_CORE 0
#define WORKER_PRIORITY 1
#define WORKER_STACK_BYTES 4096
#define HUFFMAN_PERIOD_MS 100
#define BUFFER_PERIOD_MS 70
#define CPU_PERIOD_MS 30
#define CPU_WORK_US 3000
#define LOAD_STACK_BYTES 3072
#define LOAD_START BIT0
#define LOAD_STOP BIT1

static const char *TAG = "huffman";
/* Buffers estáticos ficam fora da pilha das tarefas. O gerador só escreve
 * input depois de receber a conclusão, quando a tarefa não o utiliza mais. */
static huffman_workspace_t workspace;
static uint8_t input[INPUT_SIZE];
static uint8_t encoded[INPUT_SIZE];
static uint8_t decoded[INPUT_SIZE];
static uint64_t response_ns[ACTIVATIONS];

/* A fila copia esta estrutura, incluindo o instante do disparo.
 * Isso transporta o início da medição até a tarefa que atende o evento. */
typedef struct {
    uint32_t activation;
    struct timespec released_at;
} request_t;

typedef struct {
    uint32_t activation;
    uint64_t elapsed_ns;
    bool valid;
} result_t;

static QueueHandle_t events;
static QueueHandle_t completions;
/* O mutex protege um recurso realmente compartilhado: encoded é usado
 * pelo Huffman e como buffer de uma transferência simulada de periférico.
 * As tarefas não podem escrever nele simultaneamente. */
static SemaphoreHandle_t buffer_mutex;
static EventGroupHandle_t load_control;
static SemaphoreHandle_t loads_finished;
static uint32_t huffman_mutex_blocks;
static uint32_t uart_bytes;
static uint32_t uart_reads;
static uint32_t uart_checksum;
static bool uart_error;

/* A carga vem de OUTRO computador, pela mesma USB/serial usada para gravar.
 * O script envia bytes em rajadas. A UART gera interrupções de recepção e
 * esta tarefa, com prioridade 3, processa os bytes no núcleo do Huffman.
 * Não responde nem ecoa os bytes: o canal de saída fica reservado ao log. */
static void uart_load_task(void *argument)
{
    (void)argument;
    uint8_t packet[256];
    xEventGroupWaitBits(load_control, LOAD_START, pdFALSE, pdTRUE, portMAX_DELAY);
    while (!(xEventGroupGetBits(load_control) & LOAD_STOP)) {
        int count = uart_read_bytes(UART_NUM_0, packet, sizeof(packet), pdMS_TO_TICKS(20));
        if (count < 0) {
            uart_error = true;
            break;
        }
        if (count > 0) {
            uart_bytes += (uint32_t)count;
            ++uart_reads;
            for (int i = 0; i < count; ++i) {
                uart_checksum = uart_checksum * UINT32_C(33) + packet[i];
            }
        }
    }
    xSemaphoreGive(loads_finished);
    vTaskSuspend(NULL);
}

typedef struct {
    bool uses_buffer;
    uint32_t period_ms;
    uint32_t jobs;
    uint32_t late_jobs;
    volatile uint32_t checksum;
    bool clock_error;
} load_config_t;

static load_config_t buffer_load = {.uses_buffer = true, .period_ms = BUFFER_PERIOD_MS};
static load_config_t cpu_load = {.period_ms = CPU_PERIOD_MS, .checksum = 1};

/* Processamento intencionalmente ativo para a tarefa concorrente de CPU.
 * vTaskDelay aqui apenas dormiria e não produziria essa carga. A cada lote
 * de operações, verificamos o orçamento de 3 ms com o relógio monotônico.
 * checksum é volatile para impedir que o compilador elimine o cálculo.
 * A duração é de parede: interrupções podem consumir parte desse orçamento. */
static bool consume_cpu(volatile uint32_t *checksum)
{
    struct timespec start, now;
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) {
        return false;
    }
    int64_t elapsed;
    do {
        for (unsigned i = 0; i < 128; ++i) {
            *checksum = *checksum * UINT32_C(1664525) + UINT32_C(1013904223);
        }
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
            return false;
        }
        elapsed = ((int64_t)now.tv_sec - start.tv_sec) * INT64_C(1000000000)
                  + now.tv_nsec - start.tv_nsec;
    } while (elapsed < (int64_t)CPU_WORK_US * 1000);
    return true;
}

static void periodic_load_task(void *argument)
{
    load_config_t *config = argument;
    /* Todos os recursos são criados antes de liberar as tarefas de carga. */
    xEventGroupWaitBits(load_control, LOAD_START, pdFALSE, pdTRUE, portMAX_DELAY);
    TickType_t next_release = xTaskGetTickCount();
    while (!(xEventGroupGetBits(load_control) & LOAD_STOP)) {
        ++config->jobs;
        if (config->uses_buffer) {
            xSemaphoreTake(buffer_mutex, portMAX_DELAY);
            /* Transferência simulada de 128 bytes para o mesmo buffer de
             * trabalho. encode limpa os bytes que utilizará ao receber o mutex.
             * A transferência não altera a sequência de entradas do Huffman. */
            for (unsigned i = 0; i < 128; ++i) {
                encoded[i] = (uint8_t)(config->jobs + i);
                config->checksum += encoded[i];
            }
            /* Simula um periférico que ainda possui o buffer. Na maior parte
             * dos trabalhos, retém por 1 tick; a cada oitavo, por 2 ticks.
             * Dormir com o mutex é intencional neste caso de teste: produz
             * bloqueio de recurso, além da disputa de CPU da outra tarefa.
             * Com tick de 100 Hz, os ticks equivalem a 10/20 ms nominais;
             * o tempo observado depende da fase do tick e do escalonamento. */
            vTaskDelay(config->jobs % 8 == 0 ? 2 : 1);
            xSemaphoreGive(buffer_mutex);
        } else if (!consume_cpu(&config->checksum)) {
            config->clock_error = true;
            break;
        }
        /* Períodos diferentes evitam que todas as tarefas tenham sempre
         * o mesmo alinhamento. pdFALSE indica atraso no calendário periódico;
         * nenhum trabalho é descartado para esconder sobrecarga. */
        if (xTaskDelayUntil(&next_release, pdMS_TO_TICKS(config->period_ms)) == pdFALSE) {
            ++config->late_jobs;
        }
    }
    /* Sinaliza que não acessará mais o mutex/buffer/contadores. app_main
     * espera as duas confirmações antes de imprimir e liberar os recursos. */
    xSemaphoreGive(loads_finished);
    vTaskSuspend(NULL);
}

/* Mesma sequência pseudoaleatória da etapa 1. Não reiniciamos a semente
 * entre ativações: cada boot reproduz as mesmas 1000 entradas na mesma ordem. */
static uint32_t next_random(uint32_t *state)
{
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return *state;
}

static void huffman_task(void *argument)
{
    (void)argument;
    request_t request;
    for (;;) {
        /* Fica bloqueada, sem consumir CPU, até receber um evento.
         * Não é uma interrupção física: é um evento externo à tarefa,
         * simulado pelo gerador e entregue por fila do FreeRTOS. */
        if (xQueueReceive(events, &request, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        size_t bit_count = 0;
        size_t decoded_size = 0;
        struct timespec finished_at;
        result_t result = {.activation = request.activation};

        /* Uma tentativa sem espera identifica contenção real. Se o buffer
         * estiver ocupado, espera pelo mutex DENTRO do intervalo de resposta.
         * A primeira tentativa também permite contar quantas ativações bloquearam. */
        if (xSemaphoreTake(buffer_mutex, 0) != pdTRUE) {
            ++huffman_mutex_blocks;
            xSemaphoreTake(buffer_mutex, portMAX_DELAY);
        }

        /* Mesmas funções e mesma validação da etapa 1. && interrompe a
         * avaliação na primeira falha; memcmp == 0 confirma bytes idênticos. */
        bool valid = huffman_encode(&workspace, input, sizeof(input),
                                    encoded, sizeof(encoded), &bit_count) &&
                     huffman_decode(&workspace, encoded, sizeof(encoded),
                                    bit_count, decoded, sizeof(decoded),
                                    &decoded_size) &&
                     decoded_size == sizeof(input) &&
                     memcmp(input, decoded, sizeof(input)) == 0;
        xSemaphoreGive(buffer_mutex);

        /* Fim da resposta: resultado calculado e validado. A leitura vem
         * após liberar o recurso, antes do envio da conclusão. Inclui bloqueio
         * pelo mutex e preempções ocorridas enquanto a tarefa processava. */
        if (clock_gettime(CLOCK_MONOTONIC, &finished_at) == 0) {
            int64_t elapsed = ((int64_t)finished_at.tv_sec - request.released_at.tv_sec)
                              * INT64_C(1000000000)
                              + finished_at.tv_nsec - request.released_at.tv_nsec;
            result.valid = valid && elapsed >= 0;
            result.elapsed_ns = result.valid ? (uint64_t)elapsed : 0;
        }

        /* Uma conclusão por evento, mesmo em caso de erro, para o gerador
         * não continuar usando uma coleta cuja validação tenha falhado. */
        xQueueSend(completions, &result, portMAX_DELAY);
    }
}

static void print_samples(void)
{
    /* Marcadores permitem identificar o cenário e conferir se o log veio
     * inteiro. Não imprimimos durante as ativações cronometradas. */
    ESP_LOGI(TAG, "Validacao OK em todas as %d ativacoes; CSV abaixo", ACTIVATIONS);
    printf("COLETA_CSV_INICIO etapa=%d versao=%s amostras=%d\n",
           EXPERIMENT_STAGE, EXPERIMENT_VERSION, ACTIVATIONS);
    puts("ativacao,tempo_us");
    for (size_t i = 0; i < ACTIVATIONS; ++i) {
        /* Converte nanossegundos para microssegundos sem ponto flutuante.
         * As três casas decimais são formatação, não resolução do relógio. */
        printf("%u,%" PRIu64 ".%03" PRIu64 "\n", (unsigned)(i + 1),
               response_ns[i] / 1000, response_ns[i] % 1000);
        if (i % 32 == 31) {
            vTaskDelay(1);
        }
    }
    printf("COLETA_CSV_FIM etapa=%d amostras=%d\n", EXPERIMENT_STAGE, ACTIVATIONS);
    ESP_LOGI(TAG, "Fim da tarefa sob teste");
}

void app_main(void)
{
    /* Estes registros identificam o cenário antes de começar a coleta.
     * CPU e tick abaixo são valores da configuração compilada no firmware. */
    ESP_LOGI(TAG, "COLETA_INICIO etapa=%d versao=%s", EXPERIMENT_STAGE, EXPERIMENT_VERSION);
    ESP_LOGI(TAG, "Cenario: sistema; cargas da etapa 3 + trafego UART externo em rajadas");
    ESP_LOGI(TAG, "entrada_bytes=%d; semente=%" PRIu32 "; ativacoes=%d",
             INPUT_SIZE, RANDOM_SEED, ACTIVATIONS);
    ESP_LOGI(TAG, "Entrada: ASCII imprimivel [32,126], PRNG xorshift32");
    ESP_LOGI(TAG, "cpu_config_mhz=%d; tick_hz=%d; tarefa_core=%d; prioridade=%d",
             CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, CONFIG_FREERTOS_HZ,
             WORKER_CORE, WORKER_PRIORITY);
    ESP_LOGI(TAG, "deadline_fixo_us=%" PRIu64 ".%03" PRIu64,
             DEADLINE_NS / 1000, DEADLINE_NS % 1000);
    ESP_LOGI(TAG, "periodos_ms: huffman=%d; buffer=%d; cpu=%d; cpu_trabalho_us=%d",
             HUFFMAN_PERIOD_MS, BUFFER_PERIOD_MS, CPU_PERIOD_MS, CPU_WORK_US);
    ESP_LOGI(TAG, "prioridades: huffman=1; buffer=1; cpu=2; todas no core=0");
    ESP_LOGI(TAG, "buffer: 128 bytes; retencao=1 tick, 2 ticks a cada 8 trabalhos");
    ESP_LOGI(TAG, "Relogio: clock_gettime(CLOCK_MONOTONIC)");
    ESP_LOGI(TAG, "Intervalo: envio do evento + espera/mutex + Huffman + validacao + liberar mutex");
    ESP_LOGI(TAG, "UART externa: UART0, 115200 baud, tarefa prioridade=3 no core=0");
    ESP_LOGI(TAG, "Coleta longa: aproximadamente 17 minutos apos iniciar a carga externa");

    /* A ESP32 aguarda o computador: assim, gravar o firmware não começa a
     * coleta antes de abrir o script. Instalar o driver neste núcleo também
     * aloca aqui a interrupção UART. Mantemos o baud rate da console (115200).
     * O primeiro byte é a autorização de início do gerador externo. */
    if (uart_driver_install(UART_NUM_0, 4096, 0, 0, NULL, 0) != ESP_OK) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: falha ao instalar UART");
        return;
    }
    ESP_LOGI(TAG, "AGUARDANDO_CARGA_UART: execute scripts/coletar_sistema.py");
    uint8_t first_byte;
    if (uart_read_bytes(UART_NUM_0, &first_byte, 1, portMAX_DELAY) != 1) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: falha ao iniciar carga UART");
        return;
    }
    uart_bytes = 1;
    uart_checksum = first_byte;
    ESP_LOGI(TAG, "CARGA_UART_INICIADA; iniciando as 10000 ativacoes");

    /* Recursos de sincronização são criados antes da coleta. Filas de um
     * elemento e confirmação obrigatória impedem acúmulo de requisições. */
    TaskHandle_t worker = NULL;
    TaskHandle_t buffer_worker = NULL;
    TaskHandle_t cpu_worker = NULL;
    TaskHandle_t uart_worker = NULL;
    unsigned loads_created = 0;
    bool complete = false;
    events = xQueueCreate(1, sizeof(request_t));
    completions = xQueueCreate(1, sizeof(result_t));
    buffer_mutex = xSemaphoreCreateMutex();
    load_control = xEventGroupCreate();
    loads_finished = xSemaphoreCreateCounting(3, 0);
    if (!events || !completions || !buffer_mutex || !load_control || !loads_finished ||
        xTaskCreatePinnedToCore(huffman_task, "huffman_evento", WORKER_STACK_BYTES,
                                NULL, WORKER_PRIORITY, &worker, WORKER_CORE) != pdPASS) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: nao foi possivel criar filas/tarefa");
        goto cleanup;
    }
    if (xTaskCreatePinnedToCore(periodic_load_task, "carga_buffer", LOAD_STACK_BYTES,
                                &buffer_load, 1, &buffer_worker, WORKER_CORE) != pdPASS) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: falha ao criar tarefa do buffer");
        goto cleanup;
    }
    ++loads_created;
    if (xTaskCreatePinnedToCore(periodic_load_task, "carga_cpu", LOAD_STACK_BYTES,
                                &cpu_load, 2, &cpu_worker, WORKER_CORE) != pdPASS) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: falha ao criar tarefa da CPU");
        goto cleanup;
    }
    ++loads_created;

    if (xTaskCreatePinnedToCore(uart_load_task, "carga_uart", LOAD_STACK_BYTES,
                                NULL, 3, &uart_worker, WORKER_CORE) != pdPASS) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: falha ao criar tarefa UART");
        goto cleanup;
    }
    ++loads_created;

    /* Breve estabilização com as cargas já ativas, fora das amostras. */
    xEventGroupSetBits(load_control, LOAD_START);
    vTaskDelay(pdMS_TO_TICKS(100));

    uint32_t random_state = RANDOM_SEED;
    TickType_t next_release = xTaskGetTickCount();
    uint32_t late_releases = 0;
    for (uint32_t activation = 1; activation <= ACTIVATIONS; ++activation) {
        /* Prepara a próxima entrada antes da liberação periódica. */
        for (size_t i = 0; i < INPUT_SIZE; ++i) {
            input[i] = (uint8_t)(32 + next_random(&random_state) % 95);
        }
        request_t request = {.activation = activation};
        result_t result;

        /* Libera a tarefa a cada 100 ms, preservando o envio por evento da
         * etapa 2. Se houver atraso, não pula amostras nem reinicia o calendário.
         * O relógio abaixo marca o envio EFETIVO: atraso do próprio gerador
         * em relação ao calendário nominal não faz parte de tempo_us. */
        if (xTaskDelayUntil(&next_release, pdMS_TO_TICKS(HUFFMAN_PERIOD_MS)) == pdFALSE) {
            ++late_releases;
        }

        /* O início é capturado pelo EMISSOR, antes de publicar o evento.
         * Começar o relógio só dentro de huffman_task esconderia o atraso
         * de envio, escalonamento e atendimento que esta etapa quer medir. */
        if (clock_gettime(CLOCK_MONOTONIC, &request.released_at) != 0 ||
            xQueueSend(events, &request, 0) != pdTRUE ||
            xQueueReceive(completions, &result, pdMS_TO_TICKS(10000)) != pdTRUE) {
            ESP_LOGE(TAG, "COLETA_INVALIDA: falha no evento/relogio/timeout em %" PRIu32, activation);
            goto cleanup;
        }
        if (!result.valid || result.activation != activation) {
            ESP_LOGE(TAG, "COLETA_INVALIDA: validacao falhou na ativacao %" PRIu32, activation);
            goto cleanup;
        }
        response_ns[activation - 1] = result.elapsed_ns;
    }
    complete = true;

cleanup:
    /* Para as cargas de forma ordenada. START também é liberado em falhas
     * parciais de inicialização, para não deixar uma tarefa presa na barreira. */
    if (load_control) {
        xEventGroupSetBits(load_control, LOAD_START | LOAD_STOP);
    }
    for (unsigned i = 0; i < loads_created; ++i) {
        xSemaphoreTake(loads_finished, portMAX_DELAY);
    }
    if (complete && (cpu_load.clock_error || uart_error || uart_reads == 0)) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: erro na carga CPU/UART ou sem trafego externo");
        complete = false;
    }
    if (complete) {
        ESP_LOGI(TAG, "uart_bytes=%" PRIu32 "; uart_leituras=%" PRIu32 "; uart_checksum=%" PRIu32,
                 uart_bytes, uart_reads, uart_checksum);
        ESP_LOGI(TAG, "Cargas encerradas: buffer_trabalhos=%" PRIu32 "; cpu_trabalhos=%" PRIu32,
                 buffer_load.jobs, cpu_load.jobs);
        ESP_LOGI(TAG, "disputas_mutex_huffman=%" PRIu32 "; liberacoes_atrasadas=%" PRIu32,
                 huffman_mutex_blocks, late_releases);
        ESP_LOGI(TAG, "atrasos_cargas: buffer=%" PRIu32 "; cpu=%" PRIu32,
                 buffer_load.late_jobs, cpu_load.late_jobs);
        print_samples();
    }
    /* Só libera recursos depois que as tarefas deixaram de acessá-los. */
    if (buffer_worker) {
        vTaskDelete(buffer_worker);
    }
    if (cpu_worker) {
        vTaskDelete(cpu_worker);
    }
    if (uart_worker) {
        vTaskDelete(uart_worker);
    }
    if (worker) {
        vTaskDelete(worker);
    }
    if (events) {
        vQueueDelete(events);
    }
    if (completions) {
        vQueueDelete(completions);
    }
    if (buffer_mutex) {
        vSemaphoreDelete(buffer_mutex);
    }
    if (loads_finished) {
        vSemaphoreDelete(loads_finished);
    }
    if (load_control) {
        vEventGroupDelete(load_control);
    }
}
