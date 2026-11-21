


    // !!! This file is generated using emlearn !!!

    #include <stdint.h>
    

static inline int32_t k12_T1_tree_0(const float *features, int32_t features_length) {
          if (features[1] < 103.500000f) {
              if (features[0] < 280.000000f) {
                  if (features[5] < 2178.000000f) {
                      if (features[0] < 44.500000f) {
                          if (features[7] < 0.750000f) {
                              if (features[0] < 12.000000f) {
                                  return 0;
                              } else {
                                  return 1;
                              }
                          } else {
                              if (features[6] < 682842.000000f) {
                                  if (features[1] < 37.000000f) {
                                      if (features[0] < 16.500000f) {
                                          if (features[8] < 0.500000f) {
                                              if (features[2] < 1.500000f) {
                                                  return 0;
                                              } else {
                                                  return 0;
                                              }
                                          } else {
                                              if (features[2] < 2671.000000f) {
                                                  return 0;
                                              } else {
                                                  return 0;
                                              }
                                          }
                                      } else {
                                          if (features[2] < 361.000000f) {
                                              return 1;
                                          } else {
                                              return 0;
                                          }
                                      }
                                  } else {
                                      if (features[1] < 62.000000f) {
                                          if (features[4] < 0.200000f) {
                                              return 1;
                                          } else {
                                              return 1;
                                          }
                                      } else {
                                          if (features[1] < 74.500000f) {
                                              if (features[7] < 1525.625000f) {
                                                  return 0;
                                              } else {
                                                  return 1;
                                              }
                                          } else {
                                              return 0;
                                          }
                                      }
                                  }
                              } else {
                                  if (features[2] < 60367646.000000f) {
                                      if (features[10] < 498.500000f) {
                                          if (features[5] < 824.000000f) {
                                              if (features[9] < 0.226476f) {
                                                  return 0;
                                              } else {
                                                  return 0;
                                              }
                                          } else {
                                              return 0;
                                          }
                                      } else {
                                          if (features[5] < 516.000000f) {
                                              return 1;
                                          } else {
                                              return 0;
                                          }
                                      }
                                  } else {
                                      return 0;
                                  }
                              }
                          }
                      } else {
                          if (features[9] < 72.727390f) {
                              return 0;
                          } else {
                              if (features[4] < 0.333333f) {
                                  return 1;
                              } else {
                                  return 1;
                              }
                          }
                      }
                  } else {
                      if (features[7] < 3403.277710f) {
                          return 1;
                      } else {
                          return 1;
                      }
                  }
              } else {
                  if (features[2] < 1182.500000f) {
                      return 1;
                  } else {
                      if (features[9] < 634.999054f) {
                          if (features[0] < 527.500000f) {
                              return 1;
                          } else {
                              return 1;
                          }
                      } else {
                          return 0;
                      }
                  }
              }
          } else {
              if (features[2] < 974431.500000f) {
                  if (features[11] < 151.360146f) {
                      return 1;
                  } else {
                      if (features[11] < 251.083336f) {
                          return 0;
                      } else {
                          return 1;
                      }
                  }
              } else {
                  if (features[1] < 318.500000f) {
                      return 0;
                  } else {
                      return 1;
                  }
              }
          }
        }
        

int32_t k12_T1_predict(const float *features, int32_t features_length) {

        int32_t votes[2] = {0,};
        int32_t _class = -1;

        _class = k12_T1_tree_0(features, features_length); votes[_class] += 1;
    
        int32_t most_voted_class = -1;
        int32_t most_voted_votes = 0;
        for (int32_t i=0; i<2; i++) {

            if (votes[i] > most_voted_votes) {
                most_voted_class = i;
                most_voted_votes = votes[i];
            }
        }
        return most_voted_class;
    }
    

int k12_T1_predict_proba(const float *features, int32_t features_length, float *out, int out_length) {

        int32_t _class = -1;

        for (int i=0; i<out_length; i++) {
            out[i] = 0.0f;
        }

        _class = k12_T1_tree_0(features, features_length); out[_class] += 1.0f;
    
        // compute mean
        for (int i=0; i<out_length; i++) {
            out[i] = out[i] / 1;
        }
        return 0;
    }
    