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

#
# Copyright (c) 2012, 2013, Oracle and/or its affiliates. All rights reserved.
#

include ../../../make-rules/shared-macros.mk

COMPONENT_NAME=		bcel
COMPONENT_VERSION=	6.0
COMPONENT_REVISION=	0
COMPONENT_PROJECT_URL=	https://commons.apache.org/proper/commons-bcel/
COMPONENT_SRC=		commons-bcel-BCEL_6_0
COMPONENT_ARCHIVE=	BCEL_6_0.tar.gz
COMPONENT_ARCHIVE_HASH=	\
    sha256:5a98e2e6cb0f858a53c2467a084304564fcea45db24142a33c99d1df5dccc628
COMPONENT_ARCHIVE_URL=	https://github.com/apache/commons-bcel/archive/$(COMPONENT_ARCHIVE)
COMPONENT_BUGDB=	java-class/bcel

# Use version of Java defined in ../../make-rules/shared-macros.mk
PATH=$(JAVA_HOME)/bin:/usr/bin

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/maven.mk
include $(WS_TOP)/make-rules/ips.mk

# common targets
build:          $(BUILD_32)

install:        $(INSTALL_32)

include $(WS_TOP)/make-rules/depend.mk
