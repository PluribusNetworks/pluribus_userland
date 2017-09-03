INSTALL ?= /usr/gnu/bin/install

all:

install: all
	$(INSTALL) -d $(DESTDIR)/lib/svc/manifest/system
	$(INSTALL) -d $(DESTDIR)/lib/svc/method
	$(INSTALL) -d $(DESTDIR)/usr/bin
	$(INSTALL) -m 555 sysinstall $(DESTDIR)/usr/bin/sysinstall
	$(INSTALL) -m 444 sysinstall.xml $(DESTDIR)/lib/svc/manifest/system/sysinstall.xml
	$(INSTALL) -m 555 svc-sysinstall $(DESTDIR)/lib/svc/method/svc-sysinstall

ipspkg:
	rm -rf proto_install
	mkdir -p proto_install/lib/svc/manifest/system
	mkdir -p proto_install/lib/svc/method
	mkdir -p proto_install/usr/bin
	ln sysinstall.xml proto_install/lib/svc/manifest/system/sysinstall.xml
	ln svc-sysinstall proto_install/lib/svc/method/svc-sysinstall
	ln sysinstall proto_install/usr/bin/sysinstall
	pkgsend generate proto_install | pkgfmt >sysinstall.p5m.1
	pkgmogrify sysinstall.p5m.1 sysinstall.mog | pkgfmt >sysinstall.p5m.2
	pkgdepend generate -md proto_install sysinstall.p5m.2 | pkgfmt >sysinstall.p5m.3
	pkgdepend resolve -m sysinstall.p5m.3
	rm -rf ips_repo
	mkdir -p ips_repo
	pkgrepo create ips_repo
	pkgrepo set -s ips_repo publisher/prefix=pluribusnetworks.com
	pkgsend publish -s $(PWD)/ips_repo -d proto_install sysinstall.p5m.3.res
