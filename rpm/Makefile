TOPDIR=$(shell readlink -e ../dist)
YUM_LABS=../../yum-labs

all:
	$(MAKE) -sC $(YUM_LABS) clean
	$(MAKE) build-centos7 build-centos8

build-centos%:
	docker-compose run --rm centos$*
	mkdir -p $(YUM_LABS)/rpms/CentOS$*-x86_64
	cp -f $(shell readlink -e $(TOPDIR)/last_build.rpm) $(YUM_LABS)/rpms/CentOS$*-x86_64/

push:
	$(MAKE) -sC $(YUM_LABS) push createrepos clean
