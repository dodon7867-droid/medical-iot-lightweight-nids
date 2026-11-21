CC ?= cc
EMLEARN_INC := $(shell python3 -c "import emlearn; print(emlearn.includedir)")
TIERS := T1 T2 T3

.PHONY: check size clean

check: $(TIERS:%=check_%)
	@for t in $(TIERS); do ./check_$$t; done

check_%: check.c models/k12_%.h
	$(CC) -O2 -I$(EMLEARN_INC) -DTIER=$* -include models/k12_$*.h check.c -o $@

size: $(TIERS:%=size_%.o)
	size $^

size_%.o: model_only.c models/k12_%.h
	$(CC) -Os -c -I$(EMLEARN_INC) -DTIER=$* -include models/k12_$*.h model_only.c -o $@

clean:
	rm -f check_T* size_T*.o
