/* Agreement with sklearn + latency for one exported tree.
 * Build: cc -O2 -DTIER=T1 -include models/k12_T1.h check.c -o check_T1
 * Run from this folder after `python src/s06_export_c.py`.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define NF 12
#define CAT2(a, b) a##b
#define CAT(a, b) CAT2(a, b)
#define STR2(x) #x
#define STR(x) STR2(x)
#define PREDICT CAT(CAT(k12_, TIER), _predict)

int main(void) {
    FILE *f = fopen("X.bin", "rb");
    if (!f) { fprintf(stderr, "X.bin missing: run src/s06_export_c.py first\n"); return 1; }
    fseek(f, 0, SEEK_END); long n = ftell(f) / (long)(sizeof(float) * NF); rewind(f);
    float *X = malloc(sizeof(float) * NF * n); int32_t *Y = malloc(sizeof(int32_t) * n);
    if (fread(X, sizeof(float), NF * n, f) != (size_t)(NF * n)) return 1; fclose(f);
    f = fopen("y_" STR(TIER) ".bin", "rb");
    if (!f || fread(Y, sizeof(int32_t), n, f) != (size_t)n) return 1; fclose(f);

    long same = 0;
    for (long i = 0; i < n; i++) same += (PREDICT(&X[i * NF], NF) == Y[i]);

    struct timespec a, b; long s = 0; int R = 200;
    clock_gettime(CLOCK_MONOTONIC, &a);
    for (int r = 0; r < R; r++) for (long i = 0; i < n; i++) s += PREDICT(&X[i * NF], NF);
    clock_gettime(CLOCK_MONOTONIC, &b);
    double ns = ((b.tv_sec - a.tv_sec) * 1e9 + (b.tv_nsec - a.tv_nsec)) / (double)R / n;
    printf("%s: agree %ld/%ld (%.2f%%)  ns_per_flow %.1f  (checksum %ld)\n",
           STR(TIER), same, n, 100.0 * same / n, ns, s);
    return 0;
}
