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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../../Makefile.lib

SUBDIRS=	autogen \
		bootvars \
		fw \
		loader

.PARALLEL:	$(SUBRDIRS)

all:=		TARGET=	all
check:=		TARGET= check
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install
install_h:=	TARGET= install_h
lint:=		TARGET= lint

all check clean clobber install install_h lint: $(SUBDIRS)

PYMODS=	__init__.py 

PYCMODS=	$(PYMODS:%.py=%.pyc)
ROOTPYMODS=	$(PYMODS:%=$(ROOTPYTHONVENDORBOOTMGMTBKND)/%)
ROOTPYCMODS=	$(PYCMODS:%=$(ROOTPYTHONVENDORBOOTMGMTBKND)/%)

CLOBBERFILES	= $(PYCMODS) 
CLEANFILES	= $(CLOBBERFILES)

%.pyc : %.py
	$(RM) $@
	$(PYTHON) -mpy_compile $<
	@[ $(<)c = $@ ] || $(MV) $(<)c $@


all:	$(SUBDIRS) $(PYCMODS)

$(ROOTPYTHONVENDORBOOTMGMTBKND): $(ROOTPYTHONVENDORBOOTMGMT) 
$(ROOTPYTHONVENDORBOOTMGMT) : $(ROOTPYTHONVENDOR)

$(ROOTPYMODS)  : $(ROOTPYTHONVENDORBOOTMGMTBKND)
$(ROOTPYCMODS) : $(ROOTPYTHONVENDORBOOTMGMTBKND) $(PYCMODS)

install: all $(ROOTPYMODS) $(ROOTPYCMODS) $(SUBDIRS)

install_h:

$(SUBDIRS): FRC
	cd $@; pwd; $(MAKE) $(TARGET)

FRC:

include ../../Makefile.targ
