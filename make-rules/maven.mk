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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

MVN=/usr/bin/mvn
JAVA_LIB=usr/share/lib/java

COMPONENT_BUILD_ENV += JAVA_HOME="$(JAVA_HOME)"
# build the configured source
$(BUILD_DIR)/%/.built:	$(SOURCE_DIR)/.prep
	$(RM) -r $(@D) ; $(MKDIR) $(@D)
	$(CLONEY) $(SOURCE_DIR) $(@D)
	$(COMPONENT_PRE_BUILD_ACTION)
	(cd $(@D) ; $(ENV) $(COMPONENT_BUILD_ENV) \
		$(MVN) clean)
	$(COMPONENT_POST_BUILD_ACTION)
	$(TOUCH) $@

COMPONENT_INSTALL_ENV += JAVA_HOME="$(JAVA_HOME)"
# install the built source into a prototype area
$(BUILD_DIR)/%/.installed:	$(BUILD_DIR)/%/.built
	$(COMPONENT_PRE_INSTALL_ACTION)
	(cd $(@D) ; $(ENV) $(COMPONENT_INSTALL_ENV) \
		$(MVN) package; \
		for dir in `find . -name target`; do \
			pdir=`dirname $$dir`; \
			mkdir -p $(PROTO_DIR)/$$pdir; \
			ln -s `pwd`/$$dir $(PROTO_DIR)/$$pdir/target; \
		done)
	$(COMPONENT_POST_INSTALL_ACTION)
	$(TOUCH) $@


#		$(CP) -rp target/* $(PROTO_DIR)/$(JAVA_LIB))

clean::
	$(RM) -r $(SOURCE_DIR) $(BUILD_DIR)
