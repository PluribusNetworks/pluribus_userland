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

#
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""module describing a directory packaging object

This module contains the DirectoryAction class, which represents a
directory-type packaging object."""

import errno
import generic
import os
import pkg.portable as portable
import pkg.actions
import pkg.client.api_errors as apx
import stat

class DirectoryAction(generic.Action):
        """Class representing a directory-type packaging object."""

        __slots__ = []

        name = "dir"
        key_attr = "path"
        globally_unique = True

        def __init__(self, data=None, **attrs):
                generic.Action.__init__(self, data, **attrs)
                if "path" in self.attrs:
                        self.attrs["path"] = self.attrs["path"].lstrip(
                            os.path.sep)
                        if not self.attrs["path"]:
                                raise pkg.actions.InvalidActionError(
                                    str(self), _("Empty path attribute"))

        def compare(self, other):
                return cmp(self.attrs["path"], other.attrs["path"])

        def directory_references(self):
                return [os.path.normpath(self.attrs["path"])]

        def install(self, pkgplan, orig):
                """Client-side method that installs a directory."""

                mode = None
                try:
                        mode = int(self.attrs.get("mode", None), 8)
                except (TypeError, ValueError):
                        # Mode isn't valid, so let validate raise a more
                        # informative error.
                        self.validate(fmri=pkgplan.destination_fmri)

                omode = oowner = ogroup = None
                owner, group = self.get_fsobj_uid_gid(pkgplan,
                        pkgplan.destination_fmri)
                if orig:
                        try:
                                omode = int(orig.attrs.get("mode", None), 8)
                        except (TypeError, ValueError):
                                # Mode isn't valid, so let validate raise a more
                                # informative error.
                                orig.validate(fmri=pkgplan.origin_fmri)
                        oowner, ogroup = orig.get_fsobj_uid_gid(pkgplan,
                            pkgplan.origin_fmri)

                path = os.path.normpath(os.path.sep.join((
                    pkgplan.image.get_root(), self.attrs["path"])))

                # Don't allow installation through symlinks.
                self.fsobj_checkpath(pkgplan, path)

                # XXX Hack!  (See below comment.)
                if not portable.is_admin():
                        mode |= stat.S_IWUSR

                if not orig:
                        try:
                                self.makedirs(path, mode=mode,
                                    fmri=pkgplan.destination_fmri)
                        except OSError, e:
                                if e.filename != path:
                                        # makedirs failed for some component
                                        # of the path.
                                        raise

                                fs = os.lstat(path)
                                fs_mode = stat.S_IFMT(fs.st_mode)
                                if e.errno == errno.EROFS:
                                        # Treat EROFS like EEXIST if both are
                                        # applicable, since we'll end up with
                                        # EROFS instead.
                                        if stat.S_ISDIR(fs_mode):
                                                return
                                        raise
                                elif e.errno != errno.EEXIST:
                                        raise

                                if stat.S_ISLNK(fs_mode):
                                        # User has replaced directory with a
                                        # link, or a package has been poorly
                                        # implemented.  It isn't safe to
                                        # simply re-create the directory as
                                        # that won't restore the files that
                                        # are supposed to be contained within.
                                        err_txt = _("Unable to create "
                                            "directory %s; it has been "
                                            "replaced with a link.  To "
                                            "continue, please remove the "
                                            "link or restore the directory "
                                            "to its original location and "
                                            "try again.") % path
                                        raise apx.ActionExecutionError(
                                            self, details=err_txt, error=e,
                                            fmri=pkgplan.destination_fmri)
                                elif stat.S_ISREG(fs_mode):
                                        # User has replaced directory with a
                                        # file, or a package has been poorly
                                        # implemented.  Salvage what's there,
                                        # and drive on.
                                        pkgplan.image.salvage(path)
                                        os.mkdir(path, mode)
                                elif stat.S_ISDIR(fs_mode):
                                        # The directory already exists, but
                                        # ensure that the mode matches what's
                                        # expected.
                                        os.chmod(path, mode)

                # The downside of chmodding the directory is that as a non-root
                # user, if we set perms u-w, we won't be able to put anything in
                # it, which is often not what we want at install time.  We save
                # the chmods for the postinstall phase, but it's always possible
                # that a later package install will want to place something in
                # this directory and then be unable to.  So perhaps we need to
                # (in all action types) chmod the parent directory to u+w on
                # failure, and chmod it back aftwards.  The trick is to
                # recognize failure due to missing file_dac_write in contrast to
                # other failures.  Or can we require that everyone simply have
                # file_dac_write who wants to use the tools.  Probably not.
                elif mode != omode:
                        os.chmod(path, mode)

                if not orig or oowner != owner or ogroup != group:
                        try:
                                portable.chown(path, owner, group)
                        except OSError, e:
                                if e.errno != errno.EPERM and \
                                    e.errno != errno.ENOSYS:
                                        raise

        def verify(self, img, **args):
                """Returns a tuple of lists of the form (errors, warnings,
                info).  The error list will be empty if the action has been
                correctly installed in the given image."""

                lstat, errors, warnings, info, abort = \
                    self.verify_fsobj_common(img, stat.S_IFDIR)
                return errors, warnings, info

        def remove(self, pkgplan):
                path = os.path.normpath(os.path.sep.join(
                    (pkgplan.image.get_root(), self.attrs["path"])))
                try:
                        os.rmdir(path)
                except OSError, e:
                        if e.errno == errno.ENOENT:
                                pass
                        elif e.errno in (errno.EEXIST, errno.ENOTEMPTY):
                                # Cannot remove directory since it's
                                # not empty.
                                pkgplan.image.salvage(path)
                        elif e.errno == errno.ENOTDIR:
                                # Either the user or another package has changed
                                # this directory into a link or file.  Salvage
                                # what's there and drive on.
                                pkgplan.image.salvage(path)
                        elif e.errno == errno.EBUSY and os.path.ismount(path):
                                # User has replaced directory with mountpoint,
                                # or a package has been poorly implemented.
                                err_txt = _("Unable to remove %s; it is in use "
                                    "as a mountpoint.  To continue, please "
                                    "unmount the filesystem at the target "
                                    "location and try again.") % path
                                raise apx.ActionExecutionError(self,
                                    details=err_txt, error=e,
                                    fmri=pkgplan.origin_fmri)
                        elif e.errno == errno.EBUSY:
                                # os.path.ismount() is broken for lofs
                                # filesystems, so give a more generic
                                # error.
                                err_txt = _("Unable to remove %s; it is in use "
                                    "by the system, another process, or as a "
                                    "mountpoint.") % path
                                raise apx.ActionExecutionError(self,
                                    details=err_txt, error=e,
                                    fmri=pkgplan.origin_fmri)
                        elif e.errno != errno.EACCES: # this happens on Windows
                                raise

        def generate_indices(self):
                """Generates the indices needed by the search dictionary.  See
                generic.py for a more detailed explanation."""

                return [
                    ("directory", "basename",
                    os.path.basename(self.attrs["path"].rstrip(os.path.sep)),
                    None),
                    ("directory", "path", os.path.sep + self.attrs["path"],
                    None)
                ]

        def validate(self, fmri=None):
                """Performs additional validation of action attributes that
                for performance or other reasons cannot or should not be done
                during Action object creation.  An ActionError exception (or
                subclass of) will be raised if any attributes are not valid.
                This is primarily intended for use during publication or during
                error handling to provide additional diagonostics.

                'fmri' is an optional package FMRI (object or string) indicating
                what package contained this action."""

                return self.validate_fsobj_common(fmri=fmri)
