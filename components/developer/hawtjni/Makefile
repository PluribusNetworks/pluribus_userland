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

COMPONENT_NAME=		hawtjni
COMPONENT_VERSION=	1.15
COMPONENT_REVISION=	0
COMPONENT_PROJECT_URL=	http://fusesource.github.io/hawtjni/
COMPONENT_ARCHIVE_SRC=	$(COMPONENT_NAME)-project-$(COMPONENT_VERSION)
COMPONENT_SRC=		$(COMPONENT_NAME)-$(COMPONENT_NAME)-project-$(COMPONENT_VERSION)
COMPONENT_ARCHIVE=	$(COMPONENT_ARCHIVE_SRC).tar.gz
COMPONENT_ARCHIVE_HASH=	\
    sha256:cf6825ff1f0c1497bd17fafac5e67f89bd7242e2d79dd0fdd606d62cc6690eaf
COMPONENT_ARCHIVE_URL=	https://github.com/fusesource/hawtjni/archive/$(COMPONENT_ARCHIVE)
COMPONENT_BUGDB=	java-class/hawtjni

# Use version of Java defined in ../../make-rules/shared-macros.mk
PATH=$(JAVA_HOME)/bin:/usr/bin

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/maven.mk
include $(WS_TOP)/make-rules/ips.mk

#COMPONENT_PREP_ACTION = ($(GSED) -i 's@! /bin/sh@!/bin/sh@' $(COMPONENT_SRC)/hawtjni-example/target/native-build/configure)
COMPONENT_PREP_ACTION = (cat $(@D)/maven-hawtjni-plugin/src/main/resources/project-template/autogen.sh | gawk '/^[   ]+auto_reconf/ { \
		print $0; \
		print " /usr/gnu/bin/sed -i \"s@! /bin/sh@!/bin/sh@\" ./configure"; next; } \
	{ print $0 }' > autogen.sh.new; \
	cp autogen.sh.new $(@D)/maven-hawtjni-plugin/src/main/resources/project-template/autogen.sh; \
	$(GSED) -i "s@{\"./autogen.sh@{\"sh\", \"./autogen.sh@" $(@D)/maven-hawtjni-plugin/src/main/java/org/fusesource/hawtjni/maven/BuildMojo.java; \
	$(GSED) -i "s@{\"./configure@{\"sh\", \"./configure@" $(@D)/maven-hawtjni-plugin/src/main/java/org/fusesource/hawtjni/maven/BuildMojo.java; \
	$(GSED) -i "s@{\"./autogen.sh@{\"sh\", \"./autogen.sh@" $(@D)/maven-hawtjni-plugin/src/main/java/org/fusesource/hawtjni/maven/GenerateMojo.java; \
	$(GSED) -i "s@{\"./configure@{\"sh\", \"./configure@" $(@D)/maven-hawtjni-plugin/src/main/java/org/fusesource/hawtjni/maven/GenerateMojo.java)

#COMPONENT_PRE_INSTALL_ACTION = (if [ ! -h /bin/sh.hawt_bash ]; then mv /bin/sh /bin/sh.hawt_bash; ln -s /bin/bash /bin/sh; fi)
#COMPONENT_POST_INSTALL_ACTION = (if [ -h /bin/sh.hawt_bash ]; then rm -f /bin/sh; mv /bin/sh.hawt_bash /bin/sh; fi)


# common targets
build:          $(BUILD_32)

install:        $(INSTALL_32)

include $(WS_TOP)/make-rules/depend.mk
