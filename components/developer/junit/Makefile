#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
# Copyright (c) 2011, 2013, Oracle and/or its affiliates. All rights reserved.
#
include ../../../make-rules/shared-macros.mk

COMPONENT_NAME=		junit
COMPONENT_VERSION=	4.11
COMPONENT_PROJECT_URL=	https://github.com/junit-team/junit
COMPONENT_REVISION=	1
COMPONENT_SRC=		$(COMPONENT_NAME)4-r$(COMPONENT_VERSION)
COMPONENT_ARCHIVE=	r$(COMPONENT_VERSION).tar.gz
COMPONENT_ARCHIVE_HASH=	\
    sha256:65c0688d4491864ac53bf50164a02fa2169e14eb10bda6730934d6749d86587d
COMPONENT_ARCHIVE_URL=  $(COMPONENT_PROJECT_URL)/archive/$(COMPONENT_ARCHIVE)
COMPONENT_BUGDB=	utility/junit

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/ant.mk
include $(WS_TOP)/make-rules/ips.mk

COMPONENT_BUILD_ARGS=

# These ARGS override what is set in build.xml
COMPONENT_BUILD_ARGS 	+= -Ddist=${PROTO_DIR}
COMPONENT_BUILD_ARGS    += -Djavadocdir=${PROTO_DIR}
COMPONENT_BUILD_ARGS    += -Dversion-status=""
COMPONENT_BUILD_TARGETS += dist

# common targets
build:		$(BUILD_32)
	
install:	build	

# Testing is run as part of the build.
# To really test AFTER you have installed the resulting package do:
# $ java -cp /usr/share/lib/java/junit.jar:/usr/share/doc/junit/samples/org \
#       junit/samples/money/MoneyTest
# ......................
# Time: 0.003
#
# OK (22 tests)
test:		$(NO_TESTS)
		
BUILD_PKG_DEPENDENCIES =        $(BUILD_TOOLS)

include $(WS_TOP)/make-rules/depend.mk
