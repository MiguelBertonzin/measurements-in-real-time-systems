#include "huffman.h"

#include <limits.h>
#include <string.h>

/* Huffman atribui códigos menores aos símbolos mais frequentes, em geral.
 * A árvore é formada unindo repetidamente as duas árvores de menor frequência.
 * Ir à esquerda representa 0; ir à direita representa 1. Somente as folhas
 * representam símbolos, então nenhum código completo é prefixo de outro.
 * Isso permite decodificar o fluxo sem separadores entre os caracteres. */

/* Busca a raiz de menor frequência entre os primeiros count nós.
 * parent == -1 identifica árvores ainda disponíveis para combinação.
 * excluded impede selecionar o mesmo nó como os dois filhos.
 * A busca é linear: prioriza simplicidade para o alfabeto de até 256 bytes. */
static int16_t smallest_root(const huffman_workspace_t *w, int count,
                             int16_t excluded)
{
    int16_t best = -1; /* Sentinela: nenhum candidato escolhido ainda. */
    for (int16_t i = 0; i < count; ++i) {
        if (i != excluded && w->nodes[i].parent == -1 &&
            (best == -1 || w->nodes[i].frequency < w->nodes[best].frequency)) {
            /* Como a comparação usa <, empates preservam o primeiro índice. */
            best = i;
        }
    }
    return best;
}

/* Liga um bit em um buffer previamente zerado. Bits zero não exigem escrita.
 * position/8 escolhe o byte e position%8 escolhe a posição dentro dele.
 * Usamos primeiro o bit mais significativo: posições 0, 1, ... usam 7, 6, ...
 * Exemplo: position=9 aponta para o segundo byte, no bit de número 6. */
static void write_bit(uint8_t *bytes, size_t position, uint8_t bit)
{
    if (bit) {
        bytes[position / 8] |= (uint8_t)(1U << (7 - position % 8));
    }
}

/* Inverso da localização usada em write_bit: desloca o bit desejado até
 * a posição zero e usa & 1 para remover os demais bits, retornando 0 ou 1. */
static uint8_t read_bit(const uint8_t *bytes, size_t position)
{
    return (bytes[position / 8] >> (7 - position % 8)) & 1U;
}

bool huffman_encode(huffman_workspace_t *w,
                    const uint8_t *input, size_t input_size,
                    uint8_t *encoded, size_t encoded_capacity,
                    size_t *bit_count)
{
    /* 1. Valida os ponteiros e o tamanho: as frequências usam uint32_t.
     * Os ponteiros devem existir inclusive para uma entrada vazia. */
    if (!w || !input || !encoded || !bit_count || input_size > UINT32_MAX) {
        return false;
    }
    *bit_count = 0;
    /* Descarta a árvore e os códigos da ativação anterior. O zero inicial
     * também é necessário para write_bit, que só liga bits de valor 1. */
    memset(w, 0, sizeof(*w));
    w->root = -1;
    /* 2. Conta quantas vezes cada valor de byte aparece na entrada. */
    for (size_t i = 0; i < input_size; ++i) {
        ++w->frequencies[input[i]];
    }

    /* 3. Cria uma folha para cada símbolo presente. Símbolos ausentes não
     * precisam participar da árvore. count também é o próximo índice livre. */
    int count = 0;
    for (int symbol = 0; symbol < HUFFMAN_SYMBOLS; ++symbol) {
        if (w->frequencies[symbol] != 0) {
            w->nodes[count++] = (huffman_node_t) {
                .frequency = w->frequencies[symbol],
                .left = -1, .right = -1, .parent = -1, .symbol = symbol,
            };
        }
    }
    const int leaves = count;
    if (count == 0) {
        /* Entrada vazia: sucesso com zero bits e sem árvore. */
        return true;
    }

    /* 4. Une as duas menores raízes sob um novo pai cuja frequência é a soma.
     * Cada união reduz em uma a quantidade de árvores disponíveis; ao final
     * resta uma única árvore. Empates têm resultado determinístico. */
    for (int remaining = leaves; remaining > 1; --remaining) {
        int16_t left = smallest_root(w, count, -1);
        int16_t right = smallest_root(w, count, left);
        w->nodes[count] = (huffman_node_t) {
            .frequency = w->nodes[left].frequency + w->nodes[right].frequency,
            .left = left, .right = right, .parent = -1, .symbol = -1,
        };
        /* Marca os filhos como ocupados: não serão selecionados novamente
         * como raízes. O novo pai permanece disponível para a próxima união. */
        w->nodes[left].parent = count;
        w->nodes[right].parent = count;
        ++count;
    }
    w->root = count - 1; /* O último nó criado é a raiz final. */

    /* 5. Monta a tabela de códigos, percorrendo cada folha até a raiz. */
    size_t total_bits = 0;
    for (int leaf = 0; leaf < leaves; ++leaf) {
        /* Ao subir da folha até a raiz, os bits aparecem na ordem inversa
         * da necessária para codificar. Este vetor guarda esse caminho. */
        uint8_t reversed[HUFFMAN_SYMBOLS - 1];
        unsigned length = 0;
        int16_t current = leaf;
        while (w->nodes[current].parent != -1) {
            int16_t parent = w->nodes[current].parent;
            /* Comparação verdadeira vira 1 (filho direito), falsa vira 0. */
            reversed[length++] = w->nodes[parent].right == current;
            current = parent;
        }
        unsigned symbol = (unsigned)w->nodes[leaf].symbol;
        if (length == 0) { /* Entrada com apenas um simbolo: codigo 0. */
            /* A própria raiz é uma folha: atribuímos um bit por ocorrência
             * para que o fluxo ainda informe quantas repetições existem. */
            reversed[length++] = 0;
        }
        w->lengths[symbol] = (uint8_t)length;
        /* Inverte o caminho para obter a sequência da raiz até a folha. */
        for (unsigned bit = 0; bit < length; ++bit) {
            write_bit(w->codes[symbol], bit, reversed[length - bit - 1]);
        }
        /* O símbolo contribui frequência * comprimento para o fluxo.
         * Testamos antes da multiplicação para evitar overflow em size_t. */
        if (w->frequencies[symbol] > (SIZE_MAX - total_bits) / length) {
            return false;
        }
        total_bits += (size_t)w->frequencies[symbol] * length;
    }
    /* 6. Arredonda para cima: 9 bits, por exemplo, precisam de 2 bytes.
     * Verifica a capacidade antes de escrever no buffer do chamador. */
    size_t bytes = total_bits / 8 + (total_bits % 8 != 0);
    if (bytes > encoded_capacity) {
        return false;
    }
    /* Os bits finais que não pertencem ao fluxo ficam zerados; bit_count
     * permite que o decodificador ignore esse preenchimento. */
    memset(encoded, 0, bytes);
    size_t position = 0;
    /* 7. Substitui cada byte da entrada pelo seu código na tabela,
     * concatenando todos os códigos em um único fluxo de bits. */
    for (size_t i = 0; i < input_size; ++i) {
        unsigned symbol = input[i];
        for (unsigned bit = 0; bit < w->lengths[symbol]; ++bit) {
            write_bit(encoded, position++, read_bit(w->codes[symbol], bit));
        }
    }
    *bit_count = total_bits; /* Devolve o tamanho exato pelo ponteiro. */
    return true;
}

bool huffman_decode(const huffman_workspace_t *w,
                    const uint8_t *encoded, size_t encoded_size,
                    size_t bit_count, uint8_t *decoded,
                    size_t decoded_capacity, size_t *decoded_size)
{
    /* Confere argumentos e se todos os bits informados cabem na entrada.
     * Usa divisão e resto para arredondar, sem multiplicar encoded_size por 8. */
    if (!w || !encoded || !decoded || !decoded_size ||
        bit_count / 8 + (bit_count % 8 != 0) > encoded_size) {
        return false;
    }
    *decoded_size = 0;
    if (w->root == -1) {
        /* Uma árvore vazia só é compatível com um fluxo vazio. */
        return bit_count == 0;
    }
    if (w->root < 0 || w->root >= HUFFMAN_MAX_NODES) {
        return false;
    }
    /* Começa na raiz e consome os bits na mesma ordem usada na codificação. */
    int16_t current = w->root;
    for (size_t bit = 0; bit < bit_count; ++bit) {
        uint8_t value = read_bit(encoded, bit);
        if (w->nodes[w->root].symbol >= 0) {
            /* Caso especial: só há um símbolo. Cada zero representa uma
             * ocorrência dele; não existem filhos para percorrer. */
            if (value != 0) {
                return false;
            }
        } else {
            /* Operador ?: escolhe o filho direito para 1 e esquerdo para 0. */
            current = value ? w->nodes[current].right : w->nodes[current].left;
            if (current < 0 || current >= HUFFMAN_MAX_NODES) {
                return false;
            }
        }
        if (w->nodes[current].symbol >= 0) {
            /* Chegar a uma folha conclui um caractere. Antes de gravá-lo,
             * garante que há espaço no buffer de saída. */
            if (*decoded_size >= decoded_capacity) {
                return false;
            }
            /* Escreve na posição atual e depois incrementa o total recuperado. */
            decoded[(*decoded_size)++] = (uint8_t)w->nodes[current].symbol;
            /* O próximo código sempre começa novamente na raiz. */
            current = w->root;
        }
    }
    /* Se os bits acabaram no meio de um caminho, faltou parte de um código.
     * Terminar na raiz indica que o último símbolo foi concluído. A igualdade
     * com a entrada original ainda será verificada por quem chamou a função. */
    return current == w->root;
}
