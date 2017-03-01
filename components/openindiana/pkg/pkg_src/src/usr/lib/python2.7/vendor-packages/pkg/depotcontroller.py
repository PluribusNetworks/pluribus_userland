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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
#

import httplib
import os
import pkg.pkgsubprocess as subprocess
import pkg.server.repository as sr
import socket
import sys
import signal
import time
import urllib
import urllib2
import urlparse

class DepotStateException(Exception):

        def __init__(self, reason):
                Exception.__init__(self, reason)

class DepotController(object):

        HALTED = 0
        STARTING = 1
        RUNNING = 2

        def __init__(self, wrapper_start=None, wrapper_end="", env=None):
                self.__add_content = False
                self.__auto_port = True
                self.__cfg_file = None
                self.__debug_features = {}
                self.__depot_handle = None
                self.__depot_path = "/usr/lib/pkg.depotd"
                self.__depot_content_root = None
                self.__dir = None
                self.__disable_ops = None
                self.__exit_ready = False
                self.__file_root = None
                self.__logpath = "/tmp/depot.log"
                self.__mirror = False
                self.__output = None
                self.__port = -1
                self.__props = {}
                self.__readonly = False
                self.__rebuild = False
                self.__refresh_index = False
                self.__state = self.HALTED
                self.__writable_root = None
                self.__socket_path = None
                self.__sort_file_max_size = None
                self.__starttime = 0
                self.__wrapper_start = []
                self.__wrapper_end = wrapper_end
                self.__env = {}
                if wrapper_start:
                        self.__wrapper_start = wrapper_start
                if env:
                        self.__env = env
                return

        def get_wrapper(self):
                return self.__wrapper_start, self.__wrapper_end

        def set_wrapper(self, start, end):
                self.__wrapper_start = start
                self.__wrapper_end = end

        def unset_wrapper(self):
                self.__wrapper_start = []
                self.__wrapper_end = ""

        def set_depotd_path(self, path):
                self.__depot_path = path

        def set_depotd_content_root(self, path):
                self.__depot_content_root = path

        def get_depotd_content_root(self):
                return self.__depot_content_root

        def set_auto_port(self):
                self.__auto_port = True

        def set_port(self, port):
                self.__auto_port = False
                self.__port = port

        def get_port(self):
                return self.__port

        def clear_property(self, section, prop):
                del self.__props[section][prop]

        def set_property(self, section, prop, value):
                self.__props.setdefault(section, {})
                self.__props[section][prop] = value

        def get_property(self, section, prop):
                return self.__props.get(section, {}).get(prop)

        def set_file_root(self, f_root):
                self.__file_root = f_root

        def get_file_root(self):
                return self.__file_root

        def set_repodir(self, repodir):
                self.__dir = repodir

        def get_repodir(self):
                return self.__dir

        def get_repo(self, auto_create=False):
                return sr.Repository(auto_create=auto_create,
                    cfgpathname=self.__cfg_file, repo_root=self.__dir)

        def get_repo_url(self):
                return urlparse.urlunparse(("file", "", urllib.pathname2url(
                    self.__dir), "", "", ""))

        def set_readonly(self):
                self.__readonly = True

        def set_readwrite(self):
                self.__readonly = False

        def set_mirror(self):
                self.__mirror = True

        def unset_mirror(self):
                self.__mirror = False

        def set_rebuild(self):
                self.__rebuild = True

        def set_norebuild(self):
                self.__rebuild = False

        def set_exit_ready(self):
                self.__exit_ready = True

        def set_add_content(self):
                self.__add_content = True

        def set_logpath(self, logpath):
                self.__logpath = logpath

        def get_logpath(self):
                return self.__logpath

        def set_socket_path(self, sock_path):
                self.__socket_path = sock_path

        def get_socket_path(self):
                return self.__socket_path

        def set_refresh_index(self):
                self.__refresh_index = True

        def set_norefresh_index(self):
                self.__refresh_index = False

        def get_state(self):
                return self.__state

        def set_cfg_file(self, f):
                self.__cfg_file = f

        def get_cfg_file(self):
                return self.__cfg_file

        def get_depot_url(self):
                return "http://localhost:%d" % self.__port

        def set_writable_root(self, wr):
                self.__writable_root = wr

        def get_writable_root(self):
                return self.__writable_root

        def set_sort_file_max_size(self, sort):
                self.__sort_file_max_size = sort

        def get_sort_file_max_size(self):
                return self.__sort_file_max_size

        def set_debug_feature(self, feature):
                self.__debug_features[feature] = True

        def unset_debug_feature(self, feature):
                del self.__debug_features[feature]

        def set_disable_ops(self, ops):
                self.__disable_ops = ops

        def unset_disable_ops(self):
                self.__disable_ops = None

        def __ping_unix_socket(self):

                if not os.path.exists(self.__socket_path):
                        return False

                try:
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.connect(self.__socket_path)
                        s.close()
                except socket.error:
                        return False

                # If we connected without error, the server is listening on
                # the socket.  That's good enough for now.
                return True

        def __network_ping(self):

                if self.__socket_path:
                        return self.__ping_unix_socket()

                try:
                        repourl = urlparse.urljoin(self.get_depot_url(),
                            "versions/0")
                        urllib2.urlopen(repourl)
                except urllib2.HTTPError, e:
                        # Server returns NOT_MODIFIED if catalog is up
                        # to date
                        if e.code == httplib.NOT_MODIFIED:
                                return True
                        else:
                                return False
                except urllib2.URLError:
                        return False
                return True

        def is_alive(self):
                """ First, check that the depot process seems to be alive.
                    Then make a little HTTP request to see if the depot is
                    responsive to requests """

                if self.__depot_handle == None:
                        return False

                status = self.__depot_handle.poll()
                if status != None:
                        return False
                return self.__network_ping()

        @property
        def started(self):
                """ Return a boolean value indicating whether a depot process
                    has been started using this depotcontroller. """

                return self.__depot_handle != None

        def get_args(self):
                """ Return the equivalent command line invocation (as an
                    array) for the depot as currently configured. """

                args = []

                # The depot may fork off children of its own, so we place
                # them all together in a process group.  This allows us to
                # nuke everything later on.
                args.append("setpgrp")
                args.extend(self.__wrapper_start[:])
                args.append(self.__depot_path)
                if self.__depot_content_root:
                        args.append("--content-root")
                        args.append(self.__depot_content_root)
                if self.__port != -1:
                        args.append("-p")
                        args.append("%d" % self.__port)
                if self.__dir != None:
                        args.append("-d")
                        args.append(self.__dir)
                if self.__file_root != None:
                        args.append("--file-root=%s" % self.__file_root)
                if self.__readonly:
                        args.append("--readonly")
                if self.__rebuild:
                        args.append("--rebuild")
                if self.__mirror:
                        args.append("--mirror")
                if self.__refresh_index:
                        args.append("--refresh-index")
                if self.__add_content:
                        args.append("--add-content")
                if self.__socket_path:
                        args.append("--socket-path=%s" % self.__socket_path)
                if self.__exit_ready:
                        args.append("--exit-ready")
                if self.__cfg_file:
                        args.append("--cfg-file=%s" % self.__cfg_file)
                if self.__debug_features:
                        args.append("--debug=%s" % ",".join(
                            self.__debug_features))
                if self.__disable_ops:
                        args.append("--disable-ops=%s" % ",".join(
                            self.__disable_ops))
                for section in self.__props:
                        for prop, val in self.__props[section].iteritems():
                                args.append("--set-property=%s.%s='%s'" %
                                    (section, prop, val))
                if self.__writable_root:
                        args.append("--writable-root=%s" % self.__writable_root)

                if self.__sort_file_max_size:
                        args.append("--sort-file-max-size=%s" % self.__sort_file_max_size)

                # Always log access and error information.
                args.append("--log-access=stdout")
                args.append("--log-errors=stderr")
                args.append(self.__wrapper_end)

                return args

        def __initial_start(self):
                if self.__state != self.HALTED:
                        raise DepotStateException("Depot already starting or "
                            "running")

                # XXX what about stdin and stdout redirection?
                args = self.get_args()

                if self.__network_ping():
                        raise DepotStateException("A depot (or some " +
                            "other network process) seems to be " +
                            "running on port %d already!" % self.__port)

                self.__state = self.STARTING

                self.__output = open(self.__logpath, "w", 0)
                cmdline = " ".join(args)

                newenv = os.environ.copy()
                newenv.update(self.__env)
                self.__depot_handle = subprocess.Popen(cmdline, env=newenv,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=self.__output,
                    stderr=self.__output,
                    close_fds=True)
                if self.__depot_handle == None:
                        raise DepotStateException("Could not start Depot")
                self.__starttime = time.time()

        def start(self):
                try:
                        self.__initial_start()

                        if self.__refresh_index:
                                return

                        begintime = time.time()

                        sleeptime = 0.0
                        check_interval = 0.20
                        contact = False
                        while (time.time() - begintime) <= 40.0:
                                rc = self.__depot_handle.poll()
                                if rc is not None:
                                        raise DepotStateException("Depot exited "
                                            "unexpectedly while starting "
                                            "(exit code %d)" % rc)

                                if self.is_alive():
                                        contact = True
                                        break
                                time.sleep(check_interval)

                        if contact == False:
                                self.kill()
                                self.__state = self.HALTED
                                raise DepotStateException("Depot did not respond to "
                                    "repeated attempts to make contact")

                        self.__state = self.RUNNING
                except KeyboardInterrupt:
                        if self.__depot_handle:
                                self.kill(now=True)
                        raise

        def start_expected_fail(self, exit=2):
                try:
                        self.__initial_start()

                        sleeptime = 0.05
                        died = False
                        rc = None
                        while sleeptime <= 10.0:

                                rc = self.__depot_handle.poll()
                                if rc is not None:
                                        died = True
                                        break
                                time.sleep(sleeptime)
                                sleeptime *= 2

                        if died and rc == exit:
                                self.__state = self.HALTED
                                return True
                        else:
                                self.stop()
                                return False
                except KeyboardInterrupt:
                        if self.__depot_handle:
                                self.kill(now=True)
                        raise

        def refresh(self):
                if self.__depot_handle == None:
                        # XXX might want to remember and return saved
                        # exit status
                        return 0

                os.kill(self.__depot_handle.pid, signal.SIGUSR1)
                return self.__depot_handle.poll()

        def kill(self, now=False):
                """kill the depot; letting it live for
                a little while helps get reliable death"""

                if self.__depot_handle == None:
                        # XXX might want to remember and return saved
                        # exit status
                        return 0

                try:
                        lifetime = time.time() - self.__starttime
                        if now == False and lifetime < 1.0:
                                time.sleep(1.0 - lifetime)

                finally:
                        # By sticking in this finally: block we ensure that even
                        # if the kill gets ctrl-c'd, we'll at least take a good
                        # final whack at the depot by killing -9 its process group.
                        try:
                                os.kill(-1 * self.__depot_handle.pid, signal.SIGKILL)
                        except OSError:
                                pass
                        self.__state = self.HALTED
                        self.__depot_handle.wait()
                        self.__depot_handle = None

        def stop(self):
                if self.__state == self.HALTED:
                        raise DepotStateException("Depot already stopped")

                return self.kill()

        def wait_search(self):
                if self.__writable_root:
                        idx_tmp_dir = os.path.join(self.__writable_root,
                            "index", "TMP")
                else:
                        idx_tmp_dir = os.path.join(self.__dir, "index", "TMP")

                if not os.path.exists(idx_tmp_dir):
                        return

                begintime = time.time()

                sleeptime = 0.0
                check_interval = 0.20
                ready = False
                while (time.time() - begintime) <= 10.0:
                        if not os.path.exists(idx_tmp_dir):
                                ready = True
                                break
                        time.sleep(check_interval)

                if not ready:
                        raise DepotStateException("Depot search "
                            "readiness timeout exceeded.")


def test_func(testdir):
        dc = DepotController()
        dc.set_port(22222)
        try:
                os.mkdir(testdir)
        except OSError:
                pass

        dc.set_repodir(testdir)

        for j in range(0, 10):
                print "%4d: Starting Depot... (%s)" % (j, " ".join(dc.get_args())),
                try:
                        dc.start()
                        print " Done.    ",
                        print "... Ping ",
                        sys.stdout.flush()
                        time.sleep(0.2)
                        while dc.is_alive() == False:
                                pass
                        print "... Done.  ",

                        print "Stopping Depot...",
                        status = dc.stop()
                        if status == 0:
                                print " Done.",
                        elif status < 0:
                                print " Result: Signal %d" % (-1 * status),
                        else:
                                print " Result: Exited %d" % status,
                        print
                        f = open("/tmp/depot.log", "r")
                        print f.read()
                        f.close()
                except KeyboardInterrupt:
                        print "\nKeyboard Interrupt: Cleaning up Depots..."
                        dc.stop()
                        raise

if __name__ == "__main__":
        __testdir = "/tmp/depotcontrollertest.%d" % os.getpid()
        try:
                test_func(__testdir)
        except KeyboardInterrupt:
                pass
        os.system("rm -fr %s" % __testdir)
        print "\nDone"

