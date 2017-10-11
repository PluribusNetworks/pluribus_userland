INSTALL ?= /usr/gnu/bin/install

all:

install: all
	$(INSTALL) -d $(DESTDIR)/lib/svc/manifest/system
	$(INSTALL) -d $(DESTDIR)/lib/svc/method
	$(INSTALL) -d $(DESTDIR)/usr/bin
	$(INSTALL) -d $(DESTDIR)/usr/share/sysinstall
	$(INSTALL) -m 555 sysinstall $(DESTDIR)/usr/bin/sysinstall
	$(INSTALL) -m 444 sysinstall.xml $(DESTDIR)/lib/svc/manifest/system/sysinstall.xml
	$(INSTALL) -m 555 svc-sysinstall $(DESTDIR)/lib/svc/method/svc-sysinstall
	$(INSTALL) -m 555 cleanup_pkg_img $(DESTDIR)/usr/share/sysinstall/cleanup_pkg_img
	$(INSTALL) -m 555 patch_pkg_img $(DESTDIR)/usr/share/sysinstall/patch_pkg_img
	$(INSTALL) -m 555 setup_autoinstall $(DESTDIR)/usr/share/sysinstall/setup_autoinstall
	$(INSTALL) -m 444 sysinstall.conf.default $(DESTDIR)/usr/share/sysinstall/sysinstall.conf.default

ipspkg:
	rm -rf proto_install
	mkdir -p proto_install/lib/svc/manifest/system
	mkdir -p proto_install/lib/svc/method
	mkdir -p proto_install/usr/bin
	mkdir -p proto_install/usr/share/sysinstall
	ln sysinstall.xml proto_install/lib/svc/manifest/system/sysinstall.xml
	ln svc-sysinstall proto_install/lib/svc/method/svc-sysinstall
	ln sysinstall proto_install/usr/bin/sysinstall
	ln cleanup_pkg_img proto_install/usr/share/sysinstall/cleanup_pkg_img
	ln patch_pkg_img proto_install/usr/share/sysinstall/patch_pkg_img
	ln setup_autoinstall proto_install/usr/share/sysinstall/setup_autoinstall
	ln sysinstall.conf.default proto_install/usr/share/sysinstall/sysinstall.conf.default
	pkgsend generate proto_install | pkgfmt >sysinstall.p5m.1
	pkgmogrify sysinstall.p5m.1 sysinstall.mog | pkgfmt >sysinstall.p5m.2
	pkgdepend generate -md proto_install sysinstall.p5m.2 | pkgfmt >sysinstall.p5m.3
	pkgdepend resolve -m sysinstall.p5m.3
	rm -rf ips_repo
	mkdir -p ips_repo
	pkgrepo create ips_repo
	pkgrepo set -s ips_repo publisher/prefix=pluribusnetworks.com
	pkgsend publish -s $(PWD)/ips_repo -d proto_install sysinstall.p5m.3.res
