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

COMPONENT_NAME=		maven
COMPONENT_VERSION=	3.5.0
COMPONENT_PROJECT_URL=	https://maven.apache.org/
COMPONENT_REVISION=	0
COMPONENT_SRC=		apache-$(COMPONENT_NAME)-$(COMPONENT_VERSION)
COMPONENT_ARCHIVE=	$(COMPONENT_SRC)-bin.tar.gz
COMPONENT_ARCHIVE_HASH=	\
    sha256:beb91419245395bd69a4a6edad5ca3ec1a8b64e41457672dc687c173a495f034
COMPONENT_ARCHIVE_URL=  http://www-eu.apache.org/dist/maven/maven-3/$(COMPONENT_VERSION)/binaries/$(COMPONENT_ARCHIVE)
COMPONENT_BUGDB=	development/maven

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/ips.mk

$(SOURCE_DIR)/build/$(MACH)/.installed:
	@$(MKDIR) $(PROTO_DIR)/usr/maven
	@$(CP) -RP $(COMPONENT_SRC)/* $(PROTO_DIR)/usr/maven
	@$(GSED) -i '/cygwin=false;/i if [ -z "$$JAVA_HOME" ]; then JAVA_HOME=$(JAVA_HOME); export JAVA_HOME; fi'  $(PROTO_DIR)/usr/maven/bin/mvn 
	@$(MKDIR) $(@D)
	@$(TOUCH) $@

build:  prep

install:        build   $(SOURCE_DIR)/build/$(MACH)/.installed

clean::
	$(RM) -r $(SOURCE_DIR) $(BUILD_DIR)

include $(WS_TOP)/make-rules/depend.mk
