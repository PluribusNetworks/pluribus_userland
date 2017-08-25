#
# This file and its contents are supplied under the terms of the
# Common Development and Distribution License ("CDDL)". You may
# only use this file in accordance with the terms of the CDDL.
#
# A full copy of the text of the CDDL should have accompanied this
# source. A copy of the CDDL is also available via the Internet at
# http://www.illumos.org/license/CDDL.
#

#
# Copyright 2013, Andrzej Szeszo
# Copyright 2016, Adam Stevko
#

include ../../../make-rules/shared-macros.mk
include ../illumos-gate/version-macros.mk

COMPONENT_NAME=		caiman
COMPONENT_SRC=		$(COMPONENT_NAME)
PUB_SUFFIX=		.pluribusnetworks.com

DMAKE=/usr/bin/dmake
FETCH=$(WS_TOOLS)/userland-fetch
SOURCE_DIR=$(COMPONENT_DIR)/caiman

DEBUG=no

COMPONENT_REVISION=$(shell cd $(COMPONENT_SRC); git rev-list HEAD --count)

$(SOURCE_DIR)/.downloaded: 
	/usr/bin/cp -rp@ $(COMPONENT_DIR)/caiman_src/caiman $(COMPONENT_DIR)

download:: $(SOURCE_DIR)/.downloaded

prep::

build install: $(BUILD_DIR)/$(MACH)/.built

#
# Use -W for nightly to avoid warnings making nightly.sh fail.
# We have to do a bunch of sed to tweak the Makefile for our
# environment and our older version of Pkg tools.
# OmniOS uses new Pkg.
#
$(BUILD_DIR)/$(MACH)/.built: $(SOURCE_DIR)/.downloaded
	mkdir -p $(BUILD_DIR)/$(MACH)
	(cd $(SOURCE_DIR); \
	 echo "-------- toplevel build --------"; \
	 export CODEMGR_WS=$(SOURCE_DIR); \
	 export ON_CLOSED_BINS="/opt/onbld/closed"; \
	 cp usr/src/tools/env/omnios.sh . || exit 1; \
	 $(GSED) -i -e 's@CODEMGR_WS=.*@CODEMGR_WS="$(SOURCE_DIR)"@' omnios.sh || exit 1; \
	 echo "PKGPUBLISHER_REDIST=$(PUBLISHER)$(PUB_SUFFIX); export PKGPUBLISHER_REDIST;" >> omnios.sh; \
	 echo "PKGVERS_BRANCH=0.144; export PKGVERS_BRANCH;" >> omnios.sh; \
	 $(GSED) -i -e 's@i386/python2.7@i86/python2.7@' usr/src/Makefile.master|| exit 1; \
	 $(GSED) -i -e 's@add-publisher \$$@set-property publisher/prefix=$$@' usr/src/pkg/Makefile; \
	 $(GSED) -i -e 's@set publisher@set-property publisher@' usr/src/pkg/Makefile; \
	 $(GSED) -i -e 's@pkgfmt \-c@pkgfmt@' usr/src/pkg/Makefile; \
	 $(GSED) -i -e 's@\-T \\\*\.py@@' usr/src/pkg/Makefile; \
	 /opt/onbld/bin/nightly -W omnios.sh || exit 1)
	$(TOUCH) $@

$(BUILD_DIR)/$(MACH)/.published: $(BUILD_DIR)/$(MACH)/.built
	(cd $(SOURCE_DIR); \
	 echo "-------- Rebuilding repository metadata --------"; \
	 pkgrepo -s file://$(SOURCE_DIR)/packages/i386/nightly-nd/repo.redist rebuild || exit 1; \
	 echo "-------- Re-publishing caiman pkgs to $(WS_REPO) --------"; \
	 $(RM) -r $(@D)/pkgrecv.dir; \
	 $(MKDIR) $(@D)/pkgrecv.dir; \
	 pkgrecv -s file://$(SOURCE_DIR)/packages/i386/nightly-nd/repo.redist -d $(@D)/pkgrecv.dir 'pkg:/*' || exit1; \
	 for pkg in $$(echo $(@D)/pkgrecv.dir/*/*); do \
		echo "Re-publishing $$pkg ..."; \
		pkgsend -s file://$(WS_REPO) publish --fmri-in-manifest --no-index \
			--no-catalog -d $$pkg $$pkg/manifest || exit 1; \
	 done; \
	 pkgrepo -s file://$(WS_REPO) rebuild)
	$(TOUCH) $@

.NOTPARALLEL:

publish: $(BUILD_DIR)/$(MACH)/.published

clean::
	$(RM) -r $(BUILD_DIR)

