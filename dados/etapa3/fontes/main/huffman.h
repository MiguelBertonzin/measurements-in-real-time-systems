/* Interface compartilhada pelo programa da ESP32 e pelo teste no computador.
 * A proteção abaixo evita definir os tipos duas vezes se o cabeçalho for
 * incluído mais de uma vez no mesmo arquivo de compilação. */
#ifndef HUFFMAN_H
#define HUFFMAN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Um byte pode ter 256 valores diferentes, inclusive zero.
 * Uma árvore binária completa com L folhas tem 2*L - 1 nós.
 * Com até 256 folhas, um caminho pode ter até 255 bits: 32 bytes bastam. */
#define HUFFMAN_SYMBOLS 256
#define HUFFMAN_MAX_NODES (2 * HUFFMAN_SYMBOLS - 1)
#define HUFFMAN_CODE_BYTES 32 /* Ate 255 bits por codigo. */

typedef struct {
    uint32_t frequency; /* Ocorrências do símbolo ou soma das frequências filhas. */
    int16_t left;       /* Índice do filho esquerdo em nodes; -1 se não existir. */
    int16_t right;      /* Índice do filho direito; representa o bit 1. */
    int16_t parent;     /* Índice do pai; -1 para uma raiz ainda não combinada. */
    int16_t symbol;     /* Byte de 0 a 255 nas folhas; -1 nos nós internos. */
} huffman_node_t;

/* Memória de trabalho reutilizada entre ativações. Não há malloc/free.
 * Usar um workspace por tarefa concorrente e mantê-lo fora da pilha pequena
 * do app_main. Os índices ligam os nós sem precisar alocar ponteiros. */
typedef struct {
    huffman_node_t nodes[HUFFMAN_MAX_NODES]; /* Folhas e nós internos da árvore. */
    uint32_t frequencies[HUFFMAN_SYMBOLS];  /* Histograma dos bytes da entrada. */
    uint8_t codes[HUFFMAN_SYMBOLS][HUFFMAN_CODE_BYTES]; /* Bits de cada código. */
    uint8_t lengths[HUFFMAN_SYMBOLS]; /* Quantidade de bits válidos por código. */
    int16_t root; /* Índice da raiz final; -1 representa entrada vazia. */
} huffman_workspace_t;

/* Codifica input_size bytes de input em encoded.
 * encoded_capacity é a capacidade disponível em bytes, enquanto *bit_count
 * recebe a quantidade exata de bits produzidos, sem os bits de preenchimento.
 * Retorna true em caso de sucesso, false para argumentos/capacidade inválidos.
 * A árvore fica no workspace e deve ser preservada até a decodificação.
 * O fluxo não contém um cabeçalho com a árvore: não é um arquivo independente.
 * Entrada e saída precisam ocupar buffers separados. */
bool huffman_encode(huffman_workspace_t *workspace,
                    const uint8_t *input, size_t input_size,
                    uint8_t *encoded, size_t encoded_capacity,
                    size_t *bit_count);

/* Decodifica apenas bit_count bits usando a árvore criada por encode.
 * encoded_size e decoded_capacity são limites dos buffers, em bytes.
 * *decoded_size recebe quantos bytes foram recuperados. O chamador compara
 * esse tamanho e o conteúdo com a entrada para confirmar a corretude.
 * O workspace deve vir de uma codificação bem-sucedida e não ser alterado.
 * O retorno false sinaliza dados inconsistentes ou capacidade insuficiente. */
bool huffman_decode(const huffman_workspace_t *workspace,
                    const uint8_t *encoded, size_t encoded_size,
                    size_t bit_count, uint8_t *decoded,
                    size_t decoded_capacity, size_t *decoded_size);

#endif
