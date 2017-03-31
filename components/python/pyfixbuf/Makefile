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
# Copyright 2017 Pluribus Networks Inc.
#

include ../../../make-rules/shared-macros.mk

COMPONENT_NAME=		pyfixbuf
COMPONENT_VERSION=	0.2.1
COMPONENT_PROJECT_URL=	https://tools.netsa.cert.org/
COMPONENT_SRC=		$(COMPONENT_NAME)-$(COMPONENT_VERSION)
COMPONENT_ARCHIVE=	$(COMPONENT_SRC).tar.gz
COMPONENT_ARCHIVE_HASH=	\
    sha256:8d1ff4c94d6af36c3ad7597e3ee1e779740d9b7e3d01cb00e1d4551f34154b0f
COMPONENT_ARCHIVE_URL=	$(COMPONENT_PROJECT_URL)pyfixbuf/download.html
COMPONENT_BUGDB=	pyfixbuf

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/setup.py.mk
include $(WS_TOP)/make-rules/ips.mk

IPS_COMPONENT_VERSION = 1.5
PATCH_LEVEL = 1

# to make sure that the docs get installed in the right place.
PYTHON_DATA = /usr

# common targets
build:		$(BUILD_32)

install:	$(INSTALL_32)

test:		$(NO_TESTS)

BUILD_PKG_DEPENDENCIES =	$(BUILD_TOOLS)

include $(WS_TOP)/make-rules/depend.mk
