/* Testes executados no computador: não medem o desempenho da ESP32.
 * assert interrompe o programa se a expressão for falsa, apontando a falha.
 * Compile sem NDEBUG para manter as verificações habilitadas. */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "huffman.h"

/* Buffers maiores permitem montar distribuições especiais de frequência. */
static huffman_workspace_t workspace;
static uint8_t input[65536];
static uint8_t encoded[65536];
static uint8_t decoded[65536];

/* Entradas inválidas exercitam os caminhos de erro sem mudar o algoritmo.
 * A corrupção da árvore é intencional e restrita a estes testes no computador. */
static void invalid_inputs(void)
{
    size_t bits = 0, recovered = 0;
    assert(!huffman_encode(NULL, input, 1, encoded, sizeof(encoded), &bits));
    assert(!huffman_encode(&workspace, NULL, 1, encoded, sizeof(encoded), &bits));
    assert(!huffman_encode(&workspace, input, 1, NULL, sizeof(encoded), &bits));
    assert(!huffman_encode(&workspace, input, 1, encoded, sizeof(encoded), NULL));
#if SIZE_MAX > UINT32_MAX
    /* Rejeitado antes de ler a entrada; não aloca nem acessa 4 GiB. */
    assert(!huffman_encode(&workspace, input, (size_t)UINT32_MAX + 1,
                           encoded, sizeof(encoded), &bits));
#endif
    assert(!huffman_decode(NULL, encoded, 1, 1, decoded, sizeof(decoded), &recovered));
    assert(!huffman_decode(&workspace, NULL, 1, 1, decoded, sizeof(decoded), &recovered));
    assert(!huffman_decode(&workspace, encoded, 1, 1, NULL, sizeof(decoded), &recovered));
    assert(!huffman_decode(&workspace, encoded, 1, 1, decoded, sizeof(decoded), NULL));

    assert(huffman_encode(&workspace, input, 0, encoded, sizeof(encoded), &bits));
    assert(!huffman_decode(&workspace, encoded, 1, 1, decoded, sizeof(decoded), &recovered));
    workspace.root = -2;
    assert(!huffman_decode(&workspace, encoded, 1, 1, decoded, sizeof(decoded), &recovered));
    workspace.root = HUFFMAN_MAX_NODES;
    assert(!huffman_decode(&workspace, encoded, 1, 1, decoded, sizeof(decoded), &recovered));

    input[0] = 'A';
    assert(huffman_encode(&workspace, input, 1, encoded, sizeof(encoded), &bits));
    encoded[0] = 0x80; /* Um símbolo único só aceita o código 0, nunca 1. */
    assert(!huffman_decode(&workspace, encoded, 1, bits, decoded, sizeof(decoded), &recovered));

    input[1] = 'B';
    assert(huffman_encode(&workspace, input, 2, encoded, sizeof(encoded), &bits));
    encoded[0] = 0;
    workspace.nodes[workspace.root].left = -1;
    assert(!huffman_decode(&workspace, encoded, 1, bits, decoded, sizeof(decoded), &recovered));
    workspace.nodes[workspace.root].left = HUFFMAN_MAX_NODES;
    assert(!huffman_decode(&workspace, encoded, 1, bits, decoded, sizeof(decoded), &recovered));
}

/* Uma "ida e volta": comprime e recupera os primeiros size bytes de input. */
static void round_trip(size_t size)
{
    size_t bits, recovered;
    assert(huffman_encode(&workspace, input, size, encoded, sizeof(encoded), &bits));
    size_t bytes = bits / 8 + (bits % 8 != 0); /* Arredondamento para cima. */
    assert(huffman_decode(&workspace, encoded, bytes, bits,
                          decoded, sizeof(decoded), &recovered));
    /* Corretude exige tanto o tamanho quanto o conteúdo original. */
    assert(recovered == size);
    assert(memcmp(input, decoded, size) == 0);
    if (size != 0) {
        /* Provoca falhas controladas para conferir a proteção dos buffers:
         * saída comprimida sem espaço, saída recuperada curta e entrada
         * comprimida truncada em um byte. Recria o workspace após a falha. */
        assert(!huffman_encode(&workspace, input, size, encoded, 0, &bits));
        assert(huffman_encode(&workspace, input, size, encoded, sizeof(encoded), &bits));
        assert(!huffman_decode(&workspace, encoded, bytes, bits,
                               decoded, size - 1, &recovered));
        assert(!huffman_decode(&workspace, encoded, bytes - 1, bits,
                               decoded, sizeof(decoded), &recovered));
    }
}

int main(void)
{
    invalid_inputs();
    /* Vetor conhecido: com empate, A recebe 0 e B recebe 1. ABBA vira 0110.
     * Confere os bits independentemente da decodificação de ida e volta. */
    memcpy(input, "ABBA", 4);
    size_t bits = 0, recovered = 0;
    assert(huffman_encode(&workspace, input, 4, encoded, sizeof(encoded), &bits));
    assert(bits == 4 && encoded[0] == 0x60);
    /* Três símbolos geram ao menos um código de dois bits. Cortar esse
     * código ao meio deve falhar mesmo se o byte que o contém estiver presente. */
    memcpy(input, "ABC", 3);
    assert(huffman_encode(&workspace, input, 3, encoded, sizeof(encoded), &bits));
    assert(workspace.lengths['A'] == 2);
    assert(!huffman_decode(&workspace, encoded, 1, 1, decoded, sizeof(decoded), &recovered));
    memset(input, 0, sizeof(input));
    /* Arrays static começam zerados: o segundo caso contém um byte zero. */
    round_trip(0);
    round_trip(1);
    /* Um único símbolo distinto exercita a raiz que também é uma folha. */
    memset(input, 'A', sizeof(input));
    round_trip(4096);
    assert(workspace.lengths['A'] == 1);

    for (size_t i = 0; i < sizeof(input); ++i) {
        /* A conversão para uint8_t repete a sequência de 0 a 255. */
        input[i] = (uint8_t)i;
    }
    round_trip(sizeof(input)); /* Inclui zero e todos os 256 simbolos. */
    for (unsigned i = 0; i < HUFFMAN_SYMBOLS; ++i) {
        /* Com frequências iguais para 256 símbolos, cada código tem 8 bits. */
        assert(workspace.lengths[i] == 8);
    }

    /* Frequencias Fibonacci exercitam codigos maiores que um byte. */
    size_t size = 0;
    unsigned previous = 1, frequency = 1;
    for (unsigned symbol = 0; symbol < 20; ++symbol) {
        /* Acrescenta frequency repetições do símbolo, depois avança Fibonacci. */
        memset(input + size, (int)symbol, frequency);
        size += frequency;
        unsigned next = previous + frequency;
        previous = frequency;
        frequency = next;
    }
    round_trip(size);
    assert(workspace.lengths[0] > 8);

    /* Repete o mesmo gerador e parâmetros da tarefa para validar a sequência
     * completa de 1000 entradas utilizada no experimento padrão. */
    uint32_t state = 123456789;
    for (unsigned run = 0; run < 1000; ++run) {
        for (size_t i = 0; i < 4096; ++i) {
            state ^= state << 13;
            state ^= state >> 17;
            state ^= state << 5;
            input[i] = (uint8_t)(32 + state % 95);
        }
        round_trip(4096);
    }
    puts("OK: entradas vazia, unica, repetida, 256 simbolos, codigos longos,");
    puts("argumentos invalidos, arvore corrompida, vetor conhecido, fluxo truncado,");
    puts("limites dos buffers e 1000 entradas pseudoaleatorias validadas.");
    return 0;
}
