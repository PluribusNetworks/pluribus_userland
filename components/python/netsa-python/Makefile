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

COMPONENT_NAME=		netsa-python
COMPONENT_VERSION=	1.5
COMPONENT_PROJECT_URL=	https://tools.netsa.cert.org/
COMPONENT_SRC=		$(COMPONENT_NAME)-$(COMPONENT_VERSION)
COMPONENT_ARCHIVE=	$(COMPONENT_SRC).tar.gz
COMPONENT_ARCHIVE_HASH=	\
    sha256:122b2b9107087438f4bab35b4041b7069dbc04ab3aa5b6d95501d2194f47c109
COMPONENT_ARCHIVE_URL=	$(COMPONENT_PROJECT_URL)netsa-python/download.html
COMPONENT_BUGDB=	netsa-python

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/setup.py.mk
include $(WS_TOP)/make-rules/ips.mk

IPS_COMPONENT_VERSION = 1.5
PATCH_LEVEL = 0

# to make sure that the docs get installed in the right place.
PYTHON_DATA = /usr

# common targets
build:		$(BUILD_32)

install:	$(INSTALL_32)

test:		$(NO_TESTS)

BUILD_PKG_DEPENDENCIES =	$(BUILD_TOOLS)

include $(WS_TOP)/make-rules/depend.mk
