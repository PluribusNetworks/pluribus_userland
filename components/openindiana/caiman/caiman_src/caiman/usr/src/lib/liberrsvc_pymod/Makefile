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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

SUBDIRS		= $(MACH)
SUBDIRS		+= $(MACH64)

all :=          TARGET= all
clean :=        TARGET= clean
clobber :=      TARGET= clobber
install :=      TARGET= install
lint :=         TARGET= lint

include ../Makefile.lib

all clean clobber install lint: $(SUBDIRS)

PYMODS		= errsvc.py \
		liberrsvc.py

PYCMODS		= $(PYMODS:%.py=%.pyc)

CLOBBERFILES	= $(PYCMODS) liberrsvc_wrap.c liberrsvc.py
CLEANFILES	= $(CLOBBERFILES)

PRIVHDRS	=
EXPHDRS		=
HDRS		= $(EXPHDRS) $(PRIVHDRS)


python:
	$(PYTHON) -m compileall -l $(@D)

all:		$(HDRS) .WAIT python $(SUBDIRS)

install_h:

install:	all .WAIT $(SUBDIRS) .WAIT \
		$(ROOTPYTHONVENDOR) \
		$(ROOTPYTHONVENDORINSTALL) \
		$(ROOTPYTHONVENDORINSTALLMODS) \
		$(ROOTPYTHONVENDORINSTALLCMODS)

lint:		lint_SRCS

liberrsvc_wrap.c liberrsvc.py:
	swig -python liberrsvc.i

$(SUBDIRS):	liberrsvc_wrap.c liberrsvc.py FRC
	cd $@; pwd; $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ
