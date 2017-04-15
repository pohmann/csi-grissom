ifeq ($(strip $(SVPA_LIB_DIR)),)
SVPA_LIB_DIR=/p/csi/public/tools/symbolicautomata/install/SVPAlib
endif

all: clean run

svpaserver/SVPAServer.class: svpaserver/SVPAServer.java $(SVPA_LIB_DIR)/target/SVPAlib-1.0.jar
	javac -cp .:$(SVPA_LIB_DIR)/target/SVPAlib-1.0.jar:$(SVPA_LIB_DIR)/lib/guava-18.0.jar:$(SVPA_LIB_DIR)/lib/commons-lang3-3.4.jar svpaserver/SVPAServer.java

SVPAServer.jar: svpaserver/SVPAServer.class
	rm -f manifest.mf
	printf "Main-Class: svpaserver.SVPAServer\n" >> manifest.mf
	printf "Class-Path: $(SVPA_LIB_DIR)/target/SVPAlib-1.0.jar $(SVPA_LIB_DIR)/lib/guava-18.0.jar $(SVPA_LIB_DIR)/lib/commons-lang3-3.4.jar\n" >> manifest.mf
	jar cmf manifest.mf $@ $^
	rm -f manifest.mf

run: SVPAServer.jar
	java -jar SVPAServer.jar

clean:
	rm -f svpaserver/SVPAServer.class manifest.mf SVPAServer.jar

.DELETE_ON_ERROR:
