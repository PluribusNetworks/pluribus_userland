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
# Copyright 2013 Adam Stevko. All rights reserved.
# Copyright 2014 Alexander Pyhalov. All rights reserved.
#

include ../../../make-rules/shared-macros.mk

COMPONENT_NAME=		sysding
COMPONENT_SRC=		$(COMPONENT_NAME)
COMPONENT_VERSION=	0.5.11
COMPONENT_LICENSE=	CDDL
COMPONENT_LICENSE_FILE=	$(COMPONENT_NAME).license
COMPONENT_PROJECT_URL=	http://openindiana.org
COMPONENT_CLASSIFICATION=	"System/Administration and Configuration"
COMPONENT_FMRI=	service/management/sysding

COMPONENT_REVISION=$(shell cd $(COMPONENT_SRC); git rev-list HEAD --count)

COMPONENT_SUMMARY=	Simple tool for initial system configuration

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/justmake.mk

include $(WS_TOP)/make-rules/ips.mk

$(SOURCE_DIR)/.downloaded: $(ARCHIVES:%=$(USERLAND_ARCHIVES)%)
	@[ -d $(SOURCE_DIR) ] || cp -rp sysding_src $(SOURCE_DIR)

COMPONENT_BUILD_TARGETS = all

$(SOURCE_DIR)/.prep: $(SOURCE_DIR)/.downloaded Makefile

build: $(BUILD_32)

install: $(INSTALL_32)

download:: $(SOURCE_DIR)/.downloaded

