/* Compiled alone to measure the code size of one tree: cc -Os -c -DTIER=T1 -include models/k12_T1.h model_only.c */
#define CAT2(a, b) a##b
#define CAT(a, b) CAT2(a, b)
int predict_one(const float *f) { return CAT(CAT(k12_, TIER), _predict)(f, 12); }
