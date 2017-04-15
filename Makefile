TOP_DIR := $(shell pwd)

ifndef CSI_CC
	CSI_CC=$(shell which csi-cc)
	CSI_CC_BAD=$(shell which csi-cc 1> /dev/null 2> /dev/null; echo $$?)
else
	CSI_CC_BAD=0
endif

all: analysis/stamp do-csi-analysis

analysis/stamp:
ifndef SVPA_LIB_DIR
	@(>&2 echo "error: No SVPA_LIB_DIR specified.  Provide SVPA_LIB_DIR=/symbolicautomata/path to make.")
	@exit 1
else
	@$(MAKE) -C analysis test SVPA_LIB_DIR=$(SVPA_LIB_DIR) FIRST_SOLVER=FSA SECOND_SOLVER=UTL
	touch $@
endif

.SECONDEXPANSION:
do-csi-analysis: frontend/$$@.in analysis/stamp
ifneq "$(CSI_CC_BAD)" "0"
	@(>&2 echo "error: Could not find csi-cc.  Provide CSI_CC=/path/to/csi/cc to make.")
	@exit 1
else
	sed -e 's|@TOP_DIR@|$(TOP_DIR)|' -e 's|@CSI_CC_DIR@|$(shell dirname $(shell dirname $(shell readlink -f $(CSI_CC))))|' $< >| $@
	chmod u+x $@
endif

clean:
	@$(MAKE) -C analysis clean
	rm -f analysis/stamp do-csi-analysis
