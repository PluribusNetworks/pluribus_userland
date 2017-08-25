#!/usr/bin/python
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

# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

#
# This file is installed into
# usr/lib/python2.7/vendor-packages/solaris_install/auto_install/ directory
# and lets the Python interpreter know that this directory contains valid
# Python modules which can be imported using following command:
# from solaris_install.auto_install.<module_name> import <object>
#

"""Init module for the Automated Installer package"""

from solaris_install.data_object.cache import DataObjectCache
import ai_instance

# AI TransferFiles checkpoint name
TRANSFER_FILES_CHECKPOINT = "transfer-ai-files"

# Register local Data Objects, use relative module reference.
DataObjectCache.register_class(ai_instance)

__all__ = []
