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
# Copyright (c) 2013, Oracle and/or its affiliates. All rights reserved.
#
include ../../../make-rules/shared-macros.mk
include ../illumos-gate/version-macros.mk

COMPONENT_NAME=         name
COMPONENT_VERSION=      1.1
COMPONENT_SUMMARY=      Enable Pluribus OS Name in /etc/release file
COMPONENT_PROJECT_URL=  http://www.pluribusnetworks.com/
COMPONENT_CLASSIFICATION=       System/Core
COMPONENT_SRC=          $(COMPONENT_NAME)-$(COMPONENT_VERSION)

include $(WS_TOP)/make-rules/prep.mk
include $(WS_TOP)/make-rules/ips.mk

build:
	pwd
	mkdir -p $(COMPONENT_SRC)
	mkdir -p $(BUILD_DIR)/prototype/$(MACH)/etc
	echo "Pluribus Networks Netvisor(TM) OS" > $(BUILD_DIR)/prototype/$(MACH)/etc/release
	echo "Illumos BUILD $(ONNV_BUILDNUM)" > $(BUILD_DIR)/prototype/$(MACH)/etc/illumos-release
	mkdir -p $(BUILD_DIR)/prototype/$(MACH)/etc/profile.d
	echo "PATH=/usr/bin:/usr/sbin:/sbin" > $(BUILD_DIR)/prototype/$(MACH)/etc/profile.d/def_env.sh
	echo "export PATH" >> $(BUILD_DIR)/prototype/$(MACH)/etc/profile.d/def_env.sh

install:

test:

clean::
	$(RM) -r $(BUILD_DIR)

