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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
# AI multicast DNS (mdns) software library makefile
#

LIBRARY	= libaimdns

OBJECTS	= libaimdns.o

CPYTHONLIBS = libaimdns.so

PRIVHDRS =

EXPHDRS =

HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../../Makefile.lib

PYVERSION=python2.7
PYINCLUDE=-I/usr/include/$(PYVERSION)

SRCDIR		= ..
INCLUDE		 = $(PYINCLUDE) \
		   -I$(ROOTINCADMIN)

CPPFLAGS       += $(INCLUDE) -D$(ARCH)
CFLAGS		+= $(DEBUG_CFLAGS) -Xa $(CPPFLAGS)

static:

dynamic: $(CPYTHONLIB)

all: dynamic

install_h:

include ../../Makefile.targ
