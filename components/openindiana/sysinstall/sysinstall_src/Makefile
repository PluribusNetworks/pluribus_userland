INSTALL ?= /usr/gnu/bin/install

all:

install: all
	$(INSTALL) -d $(DESTDIR)/lib/svc/manifest/system
	$(INSTALL) -d $(DESTDIR)/lib/svc/method
	$(INSTALL) -m 444 sysinstall.xml $(DESTDIR)/lib/svc/manifest/network
	$(INSTALL) -m 555 sysinstall $(DESTDIR)/lib/svc/method/sysinstall

ipspkg:
	rm -rf proto_install
	mkdir -p proto_install/lib/svc/manifest/network
	mkdir -p proto_install/lib/svc/method
	ln sysinstall.xml proto_install/lib/svc/manifest/system/sysinstall.xml
	ln sysinstall proto_install/lib/svc/method/sysinstall
	pkgsend generate proto_install | pkgfmt >sysinstall.p5m.1
	pkgmogrify sysinstall.p5m.1 sysinstall.mog | pkgfmt >sysinstall.p5m.2
	pkgdepend generate -md proto_install sysinstall.p5m.2 | pkgfmt >sysinstall.p5m.3
	pkgdepend resolve -m sysinstall.p5m.3
	rm -rf ips_repo
	mkdir -p ips_repo
	pkgrepo create ips_repo
	pkgrepo set -s ips_repo publisher/prefix=pluribusnetworks.com
	pkgsend publish -s $(PWD)/ips_repo -d proto_install sysinstall.p5m.3.res
