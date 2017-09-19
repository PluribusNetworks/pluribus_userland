#
# This file and its contents are supplied under the terms of the
# Common Development and Distribution License ("CDDL"), version 1.0.
# You may only use this file in accordance with the terms of version
# 1.0 of the CDDL.
#
# A full copy of the text of the CDDL should have accompanied this
# source.  A copy of the CDDL is also available via the Internet at
# http://www.illumos.org/license/CDDL.
#

#
# Copyright 2016 Alexander Pyhalov
#

include ../../make-rules/shared-macros.mk

COMPONENT_NAME= libproxy

COMPONENT_VERSION= 0.4.6
COMPONENT_REVISION= 1
COMPONENT_SUMMARY= Libproxy is a library that provides automatic proxy configuration management
COMPONENT_SRC= $(COMPONENT_NAME)-$(COMPONENT_NAME)-$(COMPONENT_VERSION)
COMPONENT_ARCHIVE= $(COMPONENT_NAME)-$(COMPONENT_VERSION).tar.gz
COMPONENT_ARCHIVE_HASH= \
  sha256:9c9f9e3dc93653ffc5df5d63659ef891d47f2adbee1e975685772a8c0f355828
COMPONENT_ARCHIVE_URL= \
  https://github.com/$(COMPONENT_NAME)/$(COMPONENT_NAME)/archive/$(COMPONENT_ARCHIVE)
COMPONENT_PROJECT_URL = http://code.google.com/p/libproxy/

include $(WS_MAKE_RULES)/prep.mk
include $(WS_MAKE_RULES)/configure.mk
include $(WS_MAKE_RULES)/ips.mk

COMPONENT_PRE_CONFIGURE_ACTION =        ($(CLONEY) $(SOURCE_DIR) $(@D); \
	rm $(@D)/cmake/paths.cmk; cp $(SOURCE_DIR)/cmake/paths.cmk $(@D)/cmake; \
	rm $(@D)/libmodman/test/CMakeLists.txt; cp $(SOURCE_DIR)/libmodman/test/CMakeLists.txt $(@D)/libmodman/test/; \
	rm $(@D)/libproxy/url.cpp; cp $(SOURCE_DIR)/libproxy/url.cpp $(@D)/libproxy/; \
	rm $(@D)/libproxy/modules/config_gnome.cpp; cp $(SOURCE_DIR)/libproxy/modules/config_gnome.cpp  $(@D)/libproxy/modules/; \
	cd $(@D); $(GSED) 's@bin @bin$${BIN_SUFFIX} @' -i cmake/paths.cmk; \
	$(GSED) 's@libexec @libexec$${LIBEXEC_SUFFIX} @' -i cmake/paths.cmk; \
	$(GSED) 's@NOT WIN32 AND NOT APPLE@NOT WIN32 AND NOT APPLE AND NOT SUNOS@' -i libmodman/test/CMakeLists.txt; \
	$(GSED) '/\#include <cstdlib>/a \#include <unistd.h>' -i libproxy/url.cpp; \
	$(GSED) '/\#include <signal.h>/a \#include <string.h>' -i libproxy/modules/config_gnome.cpp)

CFLAGS+= -D__EXTENSIONS__
CMAKE= cmake

CMAKE_BINSUFFIX.32 =
CMAKE_BINSUFFIX.64 =$(MACH64)
CMAKE_LIBSUFFIX.32 =
CMAKE_LIBSUFFIX.64 =$(MACH64)

CMAKE_OPTIONS+= -DCMAKE_C_COMPILER=$(CC)
CMAKE_OPTIONS+= -DCMAKE_CXX_COMPILER=$(CXX)
CMAKE_OPTIONS+= -DCMAKE_C_FLAGS="$(CFLAGS)"
CMAKE_OPTIONS+= -DCMAKE_CXX_FLAGS="$(CFLAGS)"

CMAKE_OPTIONS+= -DCMAKE_INSTALL_PREFIX=$(CONFIGURE_PREFIX)
CMAKE_OPTIONS+= -DBIN_SUFFIX=$(CMAKE_BINSUFFIX.$(BITS))
CMAKE_OPTIONS+= -DLIB_SUFFIX=$(CMAKE_LIBSUFFIX.$(BITS))
CMAKE_OPTIONS+= -DLIBEXEC_SUFFIX=$(CMAKE_LIBSUFFIX.$(BITS))
CMAKE_OPTIONS+= -DSUNOS=TRUE
CMAKE_OPTIONS+= -DCMAKE_SHARED_LINKER_FLAGS="-lsocket -lnsl"
CMAKE_OPTIONS+= -DCMAKE_EXE_LINKER_FLAGS="-lsocket -lnsl"

# gcc invocation in some link.txt file is missing -m$(BITS) parameter
# and it makes 64-bit build to fail, this is a quick hack to make it build
# for now, cmake build system needs a proper fix

COMPONENT_POST_CONFIGURE_ACTION.32=
COMPONENT_POST_CONFIGURE_ACTION.64= find $(@D) -type f -name link.txt \
	-exec perl -pi -e 's/gcc\ \ -fPIC/\/gcc\ -m64\ -fPIC/' {} \;
COMPONENT_POST_CONFIGURE_ACTION=$(COMPONENT_POST_CONFIGURE_ACTION.$(BITS))

CONFIGURE_ENV    += XGETTEXT=/usr/gnu/bin/xgettext
CONFIGURE_ENV    += MSGFMT=/usr/gnu/bin/msgfmt
CONFIGURE_ENV    += PERL=$(PERL)
CONFIGURE_ENV    += PYTHON="$(PYTHON)"
CONFIGURE_ENV    += am_cv_python_pythondir="$(PYTHON_VENDOR_PACKAGES)"
CONFIGURE_ENV    += am_cv_python_pyexecdir="$(PYTHON_VENDOR_PACKAGES)"

#COMPONENT_INSTALL_ENV+= GCONF_DISABLE_MAKEFILE_SCHEMA_INSTALL=1

$(BUILD_DIR)/%/.configured:	$(SOURCE_DIR)/.prep
	($(RM) -rf $(@D) ; $(MKDIR) $(@D))
	$(COMPONENT_PRE_CONFIGURE_ACTION)
	(cd $(@D) ; $(ENV) $(CONFIGURE_ENV) $(CMAKE) $(CMAKE_OPTIONS) ./)
	$(COMPONENT_POST_CONFIGURE_ACTION)
	$(TOUCH) $@

build: $(BUILD_32_and_64)

install: $(INSTALL_32_and_64)

REQUIRED_PACKAGES += library/libproxy
REQUIRED_PACKAGES += system/library
REQUIRED_PACKAGES += runtime/python-27
REQUIRED_PACKAGES += x11/library/libx11
REQUIRED_PACKAGES += x11/library/libxmu
