/*
 * Etapa 2 — teste comportamental, com um evento simulado por vez.
 *
 * app_main gera a entrada e envia um evento para a tarefa Huffman.
 * A tarefa acorda, codifica, decodifica, compara e devolve a conclusão.
 * Só então app_main prepara o evento seguinte: nunca há duas entradas em voo.
 * O algoritmo Huffman é o mesmo da etapa 1, preservada em dados/etapa1/fontes.
 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "huffman.h"

#define EXPERIMENT_STAGE 2
#define EXPERIMENT_VERSION "etapa2-evento-v1"
#define INPUT_SIZE 4096
#define ACTIVATIONS 1000
#define RANDOM_SEED UINT32_C(123456789)
/* D = 1,2 * 27034 us, obtido da coleta inicial da etapa 1.
 * É apenas critério de análise: não interrompe nem descarta execuções tardias. */
#define DEADLINE_NS UINT64_C(32440800)
#define WORKER_CORE 0
#define WORKER_PRIORITY 1
#define WORKER_STACK_BYTES 4096

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

        /* Mesmas funções e mesma validação da etapa 1. && interrompe a
         * avaliação na primeira falha; memcmp == 0 confirma bytes idênticos. */
        bool valid = huffman_encode(&workspace, input, sizeof(input),
                                    encoded, sizeof(encoded), &bit_count) &&
                     huffman_decode(&workspace, encoded, sizeof(encoded),
                                    bit_count, decoded, sizeof(decoded),
                                    &decoded_size) &&
                     decoded_size == sizeof(input) &&
                     memcmp(input, decoded, sizeof(input)) == 0;

        /* Fim da resposta: resultado calculado e validado. A leitura vem
         * antes do envio da conclusão, que fica fora do intervalo medido. */
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
    ESP_LOGI(TAG, "Cenario: comportamental; evento simulado por fila; um por vez");
    ESP_LOGI(TAG, "entrada_bytes=%d; semente=%" PRIu32 "; ativacoes=%d",
             INPUT_SIZE, RANDOM_SEED, ACTIVATIONS);
    ESP_LOGI(TAG, "Entrada: ASCII imprimivel [32,126], PRNG xorshift32");
    ESP_LOGI(TAG, "cpu_config_mhz=%d; tick_hz=%d; tarefa_core=%d; prioridade=%d",
             CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, CONFIG_FREERTOS_HZ,
             WORKER_CORE, WORKER_PRIORITY);
    ESP_LOGI(TAG, "deadline_fixo_us=%" PRIu64 ".%03" PRIu64,
             DEADLINE_NS / 1000, DEADLINE_NS % 1000);
    ESP_LOGI(TAG, "Relogio: clock_gettime(CLOCK_MONOTONIC)");
    ESP_LOGI(TAG, "Intervalo: envio do evento + espera + Huffman + decodificacao + comparacao");
    ESP_LOGI(TAG, "Aguarde aproximadamente 40 segundos; dados serao impressos ao final");

    /* Recursos de sincronização são criados antes da coleta. Filas de um
     * elemento e confirmação obrigatória impedem acúmulo de requisições. */
    TaskHandle_t worker = NULL;
    events = xQueueCreate(1, sizeof(request_t));
    completions = xQueueCreate(1, sizeof(result_t));
    if (!events || !completions ||
        xTaskCreatePinnedToCore(huffman_task, "huffman_evento", WORKER_STACK_BYTES,
                                NULL, WORKER_PRIORITY, &worker, WORKER_CORE) != pdPASS) {
        ESP_LOGE(TAG, "COLETA_INVALIDA: nao foi possivel criar filas/tarefa");
        goto cleanup;
    }

    uint32_t random_state = RANDOM_SEED;
    for (uint32_t activation = 1; activation <= ACTIVATIONS; ++activation) {
        /* Geração da entrada e espera entre eventos ficam fora da medição. */
        for (size_t i = 0; i < INPUT_SIZE; ++i) {
            input[i] = (uint8_t)(32 + next_random(&random_state) % 95);
        }
        request_t request = {.activation = activation};
        result_t result;

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
        /* Um tick permite executar a idle task entre as ativações.
         * Com tick_hz=100, um tick corresponde a 10 ms nominais. */
        vTaskDelay(1);
    }
    print_samples();

cleanup:
    /* Primeiro remove a tarefa bloqueada, depois as filas que ela utiliza. */
    if (worker) {
        vTaskDelete(worker);
    }
    if (events) {
        vQueueDelete(events);
    }
    if (completions) {
        vQueueDelete(completions);
    }
}
