/*
 * Ponto de entrada do experimento na ESP32.
 * Fluxo de cada ativação:
 * gerar entrada -> iniciar relógio -> codificar -> decodificar -> comparar
 * -> encerrar relógio -> guardar duração -> ceder a CPU.
 */
#include <inttypes.h> /* PRIu32/PRIu64: formatos portáveis para printf. */
#include <stdio.h>
#include <string.h>
#include <time.h>     /* struct timespec, clock_gettime e CLOCK_MONOTONIC. */

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "huffman.h"

/* Parâmetros que devem constar no relatório. UINT32_C cria uma constante
 * inteira de 32 bits sem sinal, compatível com o gerador abaixo. */
#define INPUT_SIZE 4096 /* Quantidade de caracteres em cada entrada. */
#define ACTIVATIONS 1000 /* Quantas vezes a tarefa será medida. */
#define RANDOM_SEED UINT32_C(123456789) /* Deve ser diferente de zero. */

/* TAG identifica as mensagens do programa no monitor serial. */
static const char *TAG = "huffman";
/* static mantém estes dados durante toda a execução, fora da pilha da tarefa.
 * O workspace contém a árvore e a tabela de códigos. Os outros buffers guardam
 * a entrada original, os bits comprimidos e os caracteres recuperados.
 * A entrada é tratada pelo tamanho: não precisa terminar com '\0'. */
static huffman_workspace_t workspace;
static uint8_t input[INPUT_SIZE];
static uint8_t encoded[INPUT_SIZE];
static uint8_t decoded[INPUT_SIZE];
static uint64_t response_ns[ACTIVATIONS]; /* Uma duração em ns por ativação. */

/* Gerador pseudoaleatório xorshift32. O ponteiro permite atualizar o estado
 * do chamador a cada chamada. ^= combina por XOR; << e >> deslocam os bits.
 * Uma mesma semente não nula reproduz a sequência, inclusive após um reset.
 * Não é um gerador para criptografia; aqui serve para reproduzir as entradas. */
static uint32_t next_random(uint32_t *state)
{
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return *state;
}

void app_main(void)
{
    /* O ESP-IDF chama app_main após inicializar o sistema e o FreeRTOS.
     * Os logs registram como esta coleta foi configurada. */
    ESP_LOGI(TAG, "Item 3: Huffman com codificacao, decodificacao e comparacao");
    ESP_LOGI(TAG, "entrada_bytes=%d; semente=%" PRIu32 "; ativacoes=%d",
             INPUT_SIZE, RANDOM_SEED, ACTIVATIONS);
    ESP_LOGI(TAG, "Entrada: ASCII imprimivel [32,126], PRNG xorshift32");
    ESP_LOGI(TAG, "Relogio: clock_gettime(CLOCK_MONOTONIC)");
    ESP_LOGI(TAG, "Intervalo: construir arvore + codificar + decodificar + comparar");

    uint32_t random_state = RANDOM_SEED;
    /* Cada passagem deste laço representa uma ativação da tarefa sob teste. */
    for (size_t activation = 0; activation < ACTIVATIONS; ++activation) {
        /* % 95 produz valores de 0 a 94; somar 32 limita a entrada ao ASCII
         * imprimível, de espaço (32) a ~ (126). A geração não é cronometrada.
         * O estado avança entre ativações, sem reiniciar a semente. */
        for (size_t i = 0; i < INPUT_SIZE; ++i) {
            input[i] = (uint8_t)(32 + next_random(&random_state) % 95);
        }

        /* timespec separa segundos (tv_sec) e nanossegundos (tv_nsec).
         * bit_count e decoded_size recebem resultados pelas funções. */
        struct timespec start, end;
        size_t bit_count = 0;
        size_t decoded_size = 0;
        /* Relógio monotônico mede intervalos sem depender da hora civil.
         * Retorno diferente de zero indica falha na leitura. */
        if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) {
            ESP_LOGE(TAG, "Falha ao ler o relogio no inicio");
            return;
        }
        /* && avalia da esquerda para a direita e para na primeira falha:
         * 1. Constrói a árvore e escreve o fluxo comprimido.
         * 2. Recupera a entrada usando a árvore preservada no workspace.
         * 3. Confere a quantidade de bytes recuperados.
         * 4. memcmp retorna zero se todos os bytes forem iguais.
         * Assim, o intervalo inclui codificação, decodificação e validação. */
        bool valid = huffman_encode(&workspace, input, sizeof(input),
                                    encoded, sizeof(encoded), &bit_count) &&
                     huffman_decode(&workspace, encoded, sizeof(encoded),
                                    bit_count, decoded, sizeof(decoded),
                                    &decoded_size) &&
                     decoded_size == sizeof(input) &&
                     memcmp(input, decoded, sizeof(input)) == 0;
        if (clock_gettime(CLOCK_MONOTONIC, &end) != 0) {
            ESP_LOGE(TAG, "Falha ao ler o relogio no fim");
            return;
        }
        /* Uma saída incorreta invalida a coleta: não será reportada como
         * uma execução válida apenas por ter terminado rapidamente. */
        if (!valid) {
            ESP_LOGE(TAG, "Validacao falhou na ativacao %u; coleta interrompida",
                     (unsigned)(activation + 1));
            return;
        }
        /* Converte a diferença de segundos para ns e soma a diferença de ns.
         * Funciona também quando a medição atravessa a virada de um segundo.
         * O cálculo intermediário é assinado porque end.tv_nsec pode ser
         * menor que start.tv_nsec, mesmo com duração total positiva. */
        int64_t elapsed = ((int64_t)end.tv_sec - start.tv_sec) * INT64_C(1000000000)
                          + end.tv_nsec - start.tv_nsec;
        response_ns[activation] = (uint64_t)elapsed;
        /* Bloqueia por um tick do FreeRTOS (não necessariamente 1 ms).
         * Permite executar a idle task, que atende o watchdog. Esta espera
         * ocorre depois da leitura final, fora do intervalo medido. */
        vTaskDelay(1);
    }

    /* Só imprime após todas as medições. A transmissão serial durante a
     * coleta poderia interferir no tempo das ativações seguintes. */
    ESP_LOGI(TAG, "Validacao OK em todas as %d ativacoes; CSV abaixo", ACTIVATIONS);
    puts("ativacao,tempo_us");
    for (size_t i = 0; i < ACTIVATIONS; ++i) {
        /* Converte ns para µs sem usar ponto flutuante: /1000 é a parte
         * inteira; %1000 fornece três casas decimais, completadas por zeros.
         * Essas casas não significam que o relógio tenha resolução de 1 ns.
         * i + 1 numera as ativações a partir de 1 no CSV. */
        printf("%u,%" PRIu64 ".%03" PRIu64 "\n", (unsigned)(i + 1),
               response_ns[i] / 1000, response_ns[i] % 1000);
        if (i % 32 == 31) {
            /* Cede a CPU também durante a impressão de cada grupo de 32. */
            vTaskDelay(1);
        }
    }
    ESP_LOGI(TAG, "Fim da tarefa sob teste");
}
