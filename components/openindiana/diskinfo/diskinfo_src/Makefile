INSTALL ?= /usr/gnu/bin/install

all:
	gcc -o diskinfo -L/usr/lib/fm -R/usr/lib/fm -ldiskmgt -lnvpair -ltopo diskinfo.c

install: all
	$(INSTALL) -d $(DESTDIR)/usr/bin
	$(INSTALL) -m 555 diskinfo $(DESTDIR)/usr/bin/diskinfo

