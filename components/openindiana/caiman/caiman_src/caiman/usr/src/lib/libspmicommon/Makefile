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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#
# SPMI common library makefile
#

include ../Makefile.lib

SUBDIRS=        $(MACH)
$(BUILD64)SUBDIRS += $(MACH64)

all :=          TARGET= all
clean :=        TARGET= clean
clobber :=      TARGET= clobber
install :=      TARGET= install
lint :=         TARGET= lint

.KEEP_STATE:

all clean clobber install lint: $(SUBDIRS)

PRIVHDRS	= \
	spmicommon_lib.h \
	common_strings.h \
	common_linklist_in.h \
	common_process_control_in.h
EXPHDRS		= spmicommon_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

SRCDIR		= ..

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBCOMMON

.KEEP_STATE:

all clean clobber install lint: $(SUBDIRS)

install:	all .WAIT $(SUBDIRS) .WAIT msgs .WAIT $(INSTMSGS)

install_test:	all .WAIT $(SUBDIRS) .WAIT $(INSTMSGS)

install_h:	$(ROOTUSRINCLEXP)

msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${SRCS} ${HDRS}
	@echo "Making messages file ${MSG_DOMAIN}.po"
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -s \
			-c "i18n:" - >/dev/null 2>&1
 
lint:  ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

install_h:      $(EXPHDRS:%=$(ROOTINC)/%)

check: $(CHECKHDRS)

$(SUBDIRS):     FRC
	@cd $@; pwd; $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ
