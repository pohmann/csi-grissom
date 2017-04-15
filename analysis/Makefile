# ---------------------- settings ---------------------- #
CPPFLAGS=-std=c++11 -g -O3 -Wall -Werror
SVPA_LIB_DIR ?= /p/csi/public/tools/symbolicautomata/install/SVPAlib
# ------------------------------------------------------ #

# ------- computed ------- #
SVPA_INSTALL_DIR=$(dir $(abspath $(lastword $(MAKEFILE_LIST))))/SVPAServer
# ------------------------ #

all: csi-grissom

SvpaExecutionSolver.py: SvpaExecutionSolver.py.in
	sed -e 's|@SVPA_LIB@|$(SVPA_LIB_DIR)|g' -e 's|@SVPA_INSTALL@|$(SVPA_INSTALL_DIR)|g' $^ >| $@

SVPAServer/stamp:
	@$(MAKE) --directory=$(@D) SVPAServer.jar

csi-grissom: grissom.py SVPAServer/stamp SvpaExecutionSolver.py
	cp grissom.py $@
	chmod ugo+x $@

test: csi-grissom
	@$(MAKE) --directory=$@

clean:
	rm -f csi-grissom SVPAServer/stamp SvpaExecutionSolver.py
	@$(MAKE) --directory=SVPAServer clean
