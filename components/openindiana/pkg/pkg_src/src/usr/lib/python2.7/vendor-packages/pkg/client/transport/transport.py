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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#

import cStringIO
import errno
import httplib
import os
import statvfs
import tempfile
import urllib
import urlparse
import zlib

import pkg.catalog as catalog
import pkg.client.api_errors as apx
import pkg.client.imageconfig as imageconfig
import pkg.client.publisher as publisher
import pkg.client.transport.engine as engine
import pkg.client.transport.exception as tx
import pkg.client.transport.mdetect as mdetect
import pkg.client.transport.repo as trepo
import pkg.client.transport.stats as tstats
import pkg.file_layout.file_manager as fm
import pkg.fmri
import pkg.manifest as manifest
import pkg.misc as misc
import pkg.nrlock as nrlock
import pkg.p5i as p5i
import pkg.portable as portable
import pkg.updatelog as updatelog

from pkg.actions import ActionError
from pkg.client import global_settings
logger = global_settings.logger

class TransportCfg(object):
        """Contains configuration needed by the transport for proper
        operations.  Clients must create one of these objects, and then pass
        it to a transport instance when it is initialized.  This is the base
        class."""

        def gen_publishers(self):
                raise NotImplementedError

        def get_policy(self, policy_name):
                raise NotImplementedError

        def get_publisher(self, publisher_name):
                raise NotImplementedError

        cached_download_dir = property(None, None, None, 
            "Absolute pathname to directory of cached, completed downloads.")

        incoming_download_dir = property(None, None, None,
            "Absolute pathname to directory of in-progress downloads.")

        pkgdir = property(None, None, None,
            "Absolute pathname to pkgdir, where the manifest files live.")

        user_agent = property(None, None, None,
            "A string that identifies the user agent for the transport.")


class ImageTransportCfg(TransportCfg):
        """A subclass of TransportCfg that gets its configuration information
        from an Image object."""

        def __init__(self, image):
                self.__img = image
        
        def gen_publishers(self):
                return self.__img.gen_publishers()

        def get_policy(self, policy_name):
                if not self.__img.cfg_cache:
                        return False
                return self.__img.cfg_cache.get_policy(policy_name)

        def get_publisher(self, publisher_name):
                return self.__img.get_publisher(publisher_name)

        def __get_user_agent(self):
                return misc.user_agent_str(self.__img,
                    global_settings.client_name)

        cached_download_dir = property(
            lambda self: self.__img.cached_download_dir(),
            None, None, "Absolute pathname to directory of cached, "
            "completed downloads.")

        incoming_download_dir = property(
            lambda self: self.__img.incoming_download_dir(),
            None, None, "Absolute pathname to directory of in-progress "
            "downloads.")

        pkgdir = property(lambda self: self.__img.pkgdir, None, None,
            "Absolute pathname to pkgdir, where the manifest files live.")

        user_agent = property(__get_user_agent, None, None,
            "A string that identifies the user agent for the transport.")


class GenericTransportCfg(TransportCfg):
        """A subclass of TransportCfg for use by transport clients that
        do not have an image."""

        def __init__(self, publishers=misc.EmptyI, c_download=None,
            i_download=None, pkgdir=None, policy_map=misc.EmptyDict):

                self.__publishers = {}
                self.__cached_download_dir = c_download
                self.__incoming_download_dir = i_download
                self.__pkgdir = pkgdir
                self.__policy_map = policy_map

                for p in publishers:
                        self.__publishers[p.prefix] = p

        def add_publisher(self, pub):
                self.__publishers[pub.prefix] = pub

        def gen_publishers(self):
                return (p for p in self.__publishers.values())

        def get_policy(self, policy_name):
                return self.__policy_map.get(policy_name, False)

        def get_publisher(self, publisher_name):
                return self.__publishers.get(publisher_name)

        def remove_publisher(self, publisher_name):
                return self.__publishers.pop(publisher_name, None)

        def __get_user_agent(self):
                return misc.user_agent_str(None, global_settings.client_name)

        def __set_c_dl_dir(self, dl_dir):
                self.__cached_download_dir = dl_dir

        def __set_i_dl_dir(self, dl_dir):
                self.__incoming_download_dir = dl_dir

        def __set_pkgdir(self, pkgdir):
                self.__pkgdir = pkgdir

        cached_download_dir = property(
            lambda self: self.__cached_download_dir, __set_c_dl_dir, None,
            "Absolute pathname to directory of cached, completed downloads.")

        incoming_download_dir = property(
            lambda self: self.__incoming_download_dir, __set_i_dl_dir, None,
            "Absolute pathname to directory of in-progress downloads.")

        pkgdir = property(lambda self: self.__pkgdir, __set_pkgdir, None,
            "Absolute pathname to pkgdir, where the manifest files live.")

        user_agent = property(__get_user_agent, None, None,
            "A string that identifies the user agent for the transport.")


class Transport(object):
        """The generic transport wrapper object.  Its public methods should
        be used by all client code that wishes to perform file/network
        packaging operations."""

        def __init__(self, tcfg):
                """Initialize the Transport object. Caller must supply
                a TransportCfg object."""

                self.__tcfg = tcfg
                self.__engine = None
                self.__cadir = None
                self.__portal_test_executed = False
                self.__repo_cache = None
                self.__dynamic_mirrors = []
                self.__lock = nrlock.NRLock()
                self._caches = None
                self.stats = tstats.RepoChooser()

        def __setup(self):
                self.__engine = engine.CurlTransportEngine(self)

                # Configure engine's user agent
                self.__engine.set_user_agent(self.__tcfg.user_agent)

                self.__repo_cache = trepo.RepoCache(self.__engine)

                if not self._caches and self.__tcfg.cached_download_dir:
                        self.add_cache(self.__tcfg.cached_download_dir,
                            readonly=False)

                if self.__tcfg.get_policy(imageconfig.MIRROR_DISCOVERY):
                        self.__dynamic_mirrors = mdetect.MirrorDetector()
                        try:
                                self.__dynamic_mirrors.locate()
                        except tx.mDNSException:
                                # Not fatal.  Suppress.
                                pass


        def _reset_caches(self):
                # For now, transport write caches all publisher data in one
                # place regardless of publisher source.
                self._caches = {}
                if self.__tcfg.cached_download_dir:
                        self.add_cache(self.__tcfg.cached_download_dir,
                            readonly=False)

                # Automatically add any publisher repository origins
                # or mirrors that are filesystem-based as read-only caches.
                for pub in self.__tcfg.gen_publishers():
                        repo = pub.selected_repository
                        if not repo:
                                continue

                        for ruri in repo.origins + repo.mirrors:
                                scheme, netloc, path, params, query, fragment = \
                                    urlparse.urlparse(ruri.uri, "file",
                                    allow_fragments=0)

                                if scheme != "file":
                                        continue

                                path = urllib.url2pathname(path)
                                path = os.path.join(path, "file")
                                try:
                                        self.add_cache(path, pub=pub.prefix,
                                            readonly=True)
                                except apx.ApiException:
                                        # Cache isn't currently valid, so skip
                                        # it for now.  This essentially defers
                                        # any errors that might be encountered
                                        # accessing this repository until
                                        # later when transport attempts to
                                        # retrieve data through the engine.
                                        continue

        def reset(self):
                """Resets the transport.  This needs to be done
                if an install plan has been canceled and needs to
                be restarted.  This clears the state of the
                transport and its associated components."""

                if not self.__engine:
                        # Don't reset if not configured
                        return

                self.__lock.acquire()
                try:
                        self.__engine.reset()
                        self.__repo_cache.clear_cache()
                        self._reset_caches()
                        if self.__dynamic_mirrors:
                                try:
                                        self.__dynamic_mirrors.locate()
                                except tx.mDNSException:
                                        # Not fatal. Suppress.
                                        pass
                finally:
                        self.__lock.release()

        def shutdown(self):
                """Shuts down any portions of the transport that can
                actively be connected to remote endpoints."""

                if not self.__engine:
                        # Already shut down
                        return

                self.__lock.acquire()
                try:
                        self.__engine.shutdown()
                        self.__engine = None
                        if self.__repo_cache:
                                self.__repo_cache.clear_cache()
                        self.__repo_cache = None
                        self._caches = None
                        self.__dynamic_mirrors = []
                finally:
                        self.__lock.release()

        def add_cache(self, path, pub=None, readonly=True):
                """Adds the directory specified by 'path' as a location to read
                file data from, and optionally to store to for the specified
                publisher. 'path' must be a directory created for use with the
                pkg.file_manager module.  If the cache already exists for the
                specified 'pub', its 'readonly' status will be updated.

                'pub' is an optional publisher prefix to restrict usage of this
                cache to.  If not provided, it is assumed that file data for any
                publisher could be contained within this cache.

                'readonly' is an optional boolean value indicating whether file
                data should be stored here as well.  Only one writeable cache
                can exist for each 'pub' at a time."""

                if not pub:
                        pub = '__all'

                if self._caches is None:
                        self._caches = {}

                pub_caches = self._caches.setdefault(pub, [])

                write_caches = [
                    cache
                    for cache in pub_caches
                    if not cache.readonly
                ]

                # For now, there should be no write caches or a single one.
                assert len(write_caches) <= 1

                path = path.rstrip(os.path.sep)
                for cache in pub_caches:
                        if cache.root != path:
                                continue

                        if readonly:
                                # Nothing more to do.
                                cache.readonly = True
                                return

                        # Ensure no other writeable caches exist for this
                        # publisher.
                        for wr_cache in write_caches:
                                if id(wr_cache) == id(cache):
                                        continue
                                raise tx.TransportOperationError("Only one "
                                    "cache that is writable for all or a "
                                    "specific publisher may exist at a time.")

                        cache.readonly = False
                        break
                else:
                        # Either no caches exist for this publisher, or this is
                        # a new cache.
                        pub_caches.append(fm.FileManager(path, readonly))

        def _get_caches(self, pub=None, readonly=True):
                """Returns the file_manager cache objects for the specified
                publisher in order of preference.  That is, caches should
                be checked for file content in the order returned.

                'pub' is an optional publisher prefix.  If provided, caches
                designated for use with the given publisher will be returned
                first in addition to any caches designed for all publishers.

                'readonly' is an optional boolean value indicating whether
                a cache for storing file data should be returned.  By default,
                only caches for reading file data are returned."""

                if isinstance(pub, publisher.Publisher):
                        pub = pub.prefix
                elif not pub or not isinstance(pub, basestring):
                        pub = None

                if self._caches is None:
                        self._caches = {}

                caches = [
                    cache
                    for cache in self._caches.get(pub, [])
                    if readonly or not cache.readonly
                ]

                if not readonly and caches:
                        # If a publisher-specific writeable cache has been
                        # found, return it alone.
                        return caches

                # If this is a not a specific publisher case, a readonly case,
                # or no writeable cache exists for the specified publisher,
                # return any publisher-specific ones first and any additional
                # ones after.
                return caches + [
                    cache
                    for cache in self._caches.get("__all", [])
                    if readonly or not cache.readonly
                ]

        def do_search(self, pub, data, ccancel=None):
                """Perform a search request.  Returns a file-like object or an
                iterable that contains the search results.  Callers need to
                catch transport exceptions that this object may generate."""

                self.__lock.acquire()
                try:
                        fobj = self._do_search(pub, data, ccancel=ccancel)
                finally:
                        self.__lock.release()

                if hasattr(fobj, "set_lock"):
                        # Since we're returning a file object that's using the
                        # same engine as the rest of this transport, assign
                        # our lock to the fobj.  It must synchronize with us
                        # too.
                        fobj.set_lock(self.__lock)
                return fobj

        def _do_search(self, pub, data, ccancel=None):
                """Implementation of do_search, which is wrapper for this
                method."""

                failures = tx.TransportFailures()
                fobj = None
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = None

                if isinstance(pub, publisher.Publisher):
                        header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=ccancel)

                # For search, prefer remote sources if available.  This allows
                # consumers to configure both a file-based and network-based set
                # of origins for a publisher without incurring the significant
                # overhead of performing file-based search unless the network-
                # based resource is unavailable.
                for d in self.__gen_origins(pub, retry_count,
                    prefer_remote=True):

                        try:
                                fobj = d.do_search(data, header,
                                    ccancel=ccancel)
                                if hasattr(fobj, "_prime"):
                                        fobj._prime()
                                return fobj

                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)

                        except tx.TransportProtoError, e:
                                if e.code in (httplib.NOT_FOUND, errno.ENOENT):
                                        raise apx.UnsupportedSearchError(e.url,
                                            "search/1")
                                elif e.code == httplib.NO_CONTENT:
                                        raise apx.NegativeSearchResult(e.url)
                                elif e.code == (httplib.BAD_REQUEST,
                                    errno.EINVAL):
                                        raise apx.MalformedSearchRequest(e.url)
                                elif e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                        fobj = None
                                else:
                                        raise

                raise failures

        def get_ca_dir(self):
                """Return the path to the directory that contains CA
                certificates."""
                if self.__cadir is None:
                        cadir = os.path.join(os.path.sep, "usr", "share",
                            "pkg", "cacert")
                        if os.path.exists(cadir):
                                self.__cadir = cadir
                                return cadir
                        else:
                                self.__cadir = ""

                if self.__cadir == "":
                        return None

                return self.__cadir

        def get_catalog(self, pub, ts=None, ccancel=None):
                """Get the catalog for the specified publisher.  If
                ts is defined, request only changes newer than timestamp
                ts."""

                self.__lock.acquire()
                try:
                        self._get_catalog(pub, ts, ccancel=ccancel)
                finally:
                        self.__lock.release()

        def _get_catalog(self, pub, ts=None, ccancel=None):
                """Get catalog.  This is the implementation of get_catalog,
                a wrapper for this function."""

                failures = tx.TransportFailures()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(uuid=self.__get_uuid(pub))
                croot = pub.catalog_root

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=ccancel)

                for d in self.__gen_origins(pub, retry_count):

                        repostats = self.stats[d.get_url()]

                        # If a transport exception occurs,
                        # save it if it's retryable, otherwise
                        # raise the error to a higher-level handler.
                        try:

                                resp = d.get_catalog(ts, header,
                                    ccancel=ccancel)

                                updatelog.recv(resp, croot, ts, pub)

                                return

                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                        except tx.TransportProtoError, e:
                                if e.code == httplib.NOT_MODIFIED:
                                        return
                                elif e.retryable:
                                        failures.append(e)
                                else:
                                        raise
                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise
                        except pkg.fmri.IllegalFmri, e:
                                repostats.record_error()
                                raise tx.TransportOperationError(
                                    "Could not retrieve catalog from '%s'\n"
                                    " Unable to parse FMRI. Details follow:\n%s"
                                    % (pub.prefix, e))
                        except EnvironmentError, e:
                                repostats.record_error()
                                raise tx.TransportOperationError(
                                    "Could not retrieve catalog from '%s'\n"
                                    " Exception: str:%s repr:%r" % (pub.prefix,
                                    e, e))
                 
                raise failures

        @staticmethod
        def _verify_catalog(filename, dirname):
                """A wrapper for catalog.verify() that catches
                BadCatalogSignatures exceptions and translates them to
                the appropriate InvalidContentException that the transport
                uses for content verification."""

                filepath = os.path.join(dirname, filename)

                try:
                        catalog.verify(filepath)
                except (apx.BadCatalogSignatures, apx.InvalidCatalogFile), e:
                        os.remove(filepath)
                        te = tx.InvalidContentException(filepath,
                            "CatalogPart failed validation: %s" % e)
                        te.request = filename
                        raise te
                return

        def get_catalog1(self, pub, flist, ts=None, path=None,
            progtrack=None, ccancel=None):
                """Get the catalog1 files from publisher 'pub' that
                are given as a list in 'flist'.  If the caller supplies
                an optional timestamp argument, only get the files that
                have been modified since the timestamp.  At the moment,
                this interface only supports supplying a timestamp
                if the length of flist is 1.

                The timestamp, 'ts', should be provided as a floating
                point value of seconds since the epoch in UTC.  If callers
                have a datetime object, they should use something like:

                time.mktime(dtobj.timetuple()) -> float

                If the caller has a UTC datetime object, the following
                should be used instead:

                calendar.timegm(dtobj.utctimetuple()) -> float

                The examples above convert the object to the appropriate format
                for get_catalog1.

                If the caller wants the completed download to be placed
                in an alternate directory (pub.catalog_root is standard),
                set a directory path in 'path'."""

                self.__lock.acquire()
                try:
                        self._get_catalog1(pub, flist, ts=ts, path=path,
                            progtrack=progtrack, ccancel=ccancel)
                finally:
                        self.__lock.release()

        def _get_catalog1(self, pub, flist, ts=None, path=None,
            progtrack=None, ccancel=None):
                """This is the implementation of get_catalog1.  The
                other function is a wrapper for this one."""

                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                failures = []
                repo_found = False
                header = self.__build_header(uuid=self.__get_uuid(pub))

                if progtrack and ccancel:
                        progtrack.check_cancelation = ccancel

                # Ensure that caller only passed one item, if ts was
                # used.
                if ts and len(flist) > 1:
                        raise ValueError("Ts may only be used with a single"
                            " item flist.")

                # download_dir is temporary download path.  Completed_dir
                # is the cache where valid content lives.
                if path:
                        completed_dir = path
                else:
                        completed_dir = pub.catalog_root
                download_dir = self.__tcfg.incoming_download_dir

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=ccancel)

                # Check if the download_dir exists.  If it doesn't, create
                # the directories.
                self._makedirs(download_dir)
                self._makedirs(completed_dir)

                # Call statvfs to find the blocksize of download_dir's
                # filesystem.
                try:
                        destvfs = os.statvfs(download_dir)
                        # Set the file buffer size to the blocksize of our
                        # filesystem.
                        self.__engine.set_file_bufsz(destvfs[statvfs.F_BSIZE])
                except EnvironmentError, e:
                        if e.errno == errno.EACCES:
                                raise apx.PermissionsException(e.filename)
                        else:
                                raise tx.TransportOperationError(
                                    "Unable to stat VFS: %s" % e)
                except AttributeError, e:
                        # os.statvfs is not available on Windows
                        pass

                for d in self.__gen_origins_byversion(pub, retry_count,
                    "catalog", 1, ccancel=ccancel):

                        failedreqs = []
                        repostats = self.stats[d.get_url()]
                        repo_found = True
                        gave_up = False

                        # This returns a list of transient errors
                        # that occurred during the transport operation.
                        # An exception handler here isn't necessary
                        # unless we want to supress a permanent failure.
                        try:
                                errlist = d.get_catalog1(flist, download_dir,
                                    header, ts, progtrack=progtrack)
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that the client just gave up, make a note
                                # of this condition and try another host.
                                gave_up = True
                                errlist = ex.failures
                                success = ex.success

                        for e in errlist:
                                # General case: Fish the request information
                                # out of the exception, so the transport
                                # can retry the request at another host.
                                req = getattr(e, "request", None)
                                if req:
                                        failedreqs.append(req)
                                        failures.append(e)
                                else:
                                        raise e


                        if gave_up:
                                # If the transport gave up due to excessive
                                # consecutive errors, the caller is returned a
                                # list of successful requests, and a list of
                                # failures.  We need to consider the requests
                                # that were not attempted because we gave up
                                # early.  In this situation, they're failed
                                # requests, even though no exception was
                                # returned.  Filter the flist to remove the
                                # successful requests.  Everything else failed.
                                failedreqs = [
                                    x for x in flist
                                    if x not in success
                                ]
                                flist = failedreqs
                        elif failedreqs:
                                success = [
                                    x for x in flist
                                    if x not in failedreqs
                                ]
                                flist = failedreqs
                        else:
                                success = flist
                                flist = None

                        for s in success:
                                dl_path = os.path.join(download_dir, s)

                                try:
                                        self._verify_catalog(s, download_dir)
                                except tx.InvalidContentException, e:
                                        repostats.record_error(content=True)
                                        failedreqs.append(e.request)
                                        failures.append(e)
                                        if not flist:
                                                flist = failedreqs
                                        continue

                                final_path = os.path.normpath(
                                    os.path.join(completed_dir, s))
                                    
                                finaldir = os.path.dirname(final_path)

                                self._makedirs(finaldir)
                                portable.rename(dl_path, final_path)

                        # Return if everything was successful
                        if not flist and not errlist:
                                return

                if not repo_found:
                        raise apx.UnsupportedRepositoryOperation(pub,
                            "catalog/1")

                if failedreqs and failures:
                        failures = [
                            x for x in failures
                            if x.request in failedreqs
                        ]
                        tfailurex = tx.TransportFailures()
                        for f in failures:
                                tfailurex.append(f)
                        raise tfailurex

        def get_publisherdata(self, pub, ccancel=None):
                """Given a publisher pub, return the publisher/0
                information as a list of publisher objects.  If
                no publisher information was contained in the
                response, the list will be empty."""

                self.__lock.acquire()
                try:
                        return self._get_publisherdata(pub,
                            ccancel=ccancel)
                finally:
                        self.__lock.release()

        def _get_publisherdata(self, pub, ccancel=None):
                """Implementation of get_publisherdata.  This routine
                implements the method, the other is an external interface
                and lock wrapper."""

                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                failures = tx.TransportFailures()
                repo_found = False
                header = None

                if isinstance(pub, publisher.Publisher):
                        header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_origins_byversion(pub, retry_count,
                    "publisher", 0, ccancel=ccancel):
                        repo_found = True
                        try:
                                resp = d.get_publisherinfo(header,
                                    ccancel=ccancel)
                                infostr = resp.read()

                                # If parse succeeds, then the data is valid.
                                pub_data = p5i.parse(data=infostr)
                                return [pub for pub, ignored in pub_data if pub]
                        except tx.ExcessiveTransientFailure, e:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(e.failures)

                        except apx.InvalidP5IFile, e:
                                url = d.get_url()
                                exc = tx.TransferContentException(url,
                                    "api_errors.InvalidP5IFile:%s" %
                                    (" ".join([str(a) for a in e.args])))
                                repostats = self.stats[url]
                                repostats.record_error(content=True)
                                if exc.retryable:
                                        failures.append(exc)
                                else:
                                        raise exc

                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                if not repo_found:
                        raise apx.UnsupportedRepositoryOperation(pub,
                            "publisher/0")
                raise failures

        def get_content(self, pub, fhash, ccancel=None):
                """Given a fmri and fhash, return the uncompressed content
                from the remote object.  This is similar to get_datstream,
                except that the transport handles retrieving and decompressing
                the content."""
               
                self.__lock.acquire()
                try:
                        content = self._get_content(pub, fhash,
                            ccancel=ccancel)
                finally:
                        self.__lock.release()

                return content

        def _get_content(self, pub, fhash, ccancel=None):
                """This is the function that implements get_content.
                The other function is a wrapper for this one, which handles
                the transport locking correctly."""

                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                failures = tx.TransportFailures()
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_repos(pub, retry_count):

                        url = d.get_url()

                        try:
                                resp = d.get_datastream(fhash, header,
                                    ccancel=ccancel)
                                s = cStringIO.StringIO()
                                hash_val = misc.gunzip_from_stream(resp, s)
                                content = s.getvalue()
                                s.close()

                                return content

                        except tx.ExcessiveTransientFailure, e:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(e.failures)

                        except zlib.error, e:
                                exc = tx.TransferContentException(url,
                                    "zlib.error:%s" %
                                    (" ".join([str(a) for a in e.args])))
                                repostats = self.stats[url]
                                repostats.record_error(content=True)
                                if exc.retryable:
                                        failures.append(exc)
                                else:
                                        raise exc

                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise
                raise failures

        def touch_manifest(self, fmri, intent=None, ccancel=None):
                """Touch a manifest.  This operation does not
                return the manifest's content.  The FMRI is given
                as fmri.  An optional intent string may be supplied
                as intent."""

                self.__lock.acquire()
                try:
                        pass
                finally:
                        self.__lock.release()

        def _touch_manifest(self, fmri, intent=None, ccancel=None):
                """Implementation of touch_manifest, which is a wrapper
                around this function."""

                failures = tx.TransportFailures()
                pub_prefix = fmri.get_publisher()
                pub = self.__tcfg.get_publisher(pub_prefix)
                mfst = fmri.get_url_path()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(intent=intent,
                    uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_origins(pub, retry_count):

                        # If a transport exception occurs,
                        # save it if it's retryable, otherwise
                        # raise the error to a higher-level handler.
                        try:
                                d.touch_manifest(mfst, header, ccancel=ccancel)
                                return

                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)

                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                raise failures

        def get_manifest(self, fmri, excludes=misc.EmptyI, intent=None,
            ccancel=None, pub=None, content_only=False):
                """Given a fmri, and optional excludes, return a manifest
                object."""

                self.__lock.acquire()
                try:
                        m = self._get_manifest(fmri, excludes, intent,
                            ccancel=ccancel, pub=pub, content_only=content_only)
                finally:
                        self.__lock.release()

                return m

        def _get_manifest(self, fmri, excludes=misc.EmptyI, intent=None,
            ccancel=None, pub=None, content_only=False):
                """This is the implementation of get_manifest.  The
                get_manifest function wraps this."""

                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                failures = tx.TransportFailures()
                pub_prefix = fmri.get_publisher()
                download_dir = self.__tcfg.incoming_download_dir
                mcontent = None
                header = None

                if not pub:
                        pub = self.__tcfg.get_publisher(pub_prefix)

                if isinstance(pub, publisher.Publisher):
                        header = self.__build_header(intent=intent,
                            uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=ccancel)

                # Check if the download_dir exists.  If it doesn't create
                # the directories.
                self._makedirs(download_dir)

                for d in self.__gen_origins(pub, retry_count):

                        repostats = self.stats[d.get_url()]
                        verified = False
                        try:
                                resp = d.get_manifest(fmri, header,
                                    ccancel=ccancel)
                                mcontent = resp.read()

                                verified = self._verify_manifest(fmri,
                                    content=mcontent)

                                if content_only:
                                        return mcontent

                                m = manifest.CachedManifest(fmri,
                                    self.__tcfg.pkgdir, excludes, mcontent)

                                return m

                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                                mcontent = None

                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                        mcontent = None
                                else:
                                        raise
 
                        except (apx.InvalidPackageErrors, ActionError), e:
                                if verified:
                                        raise
                                repostats.record_error(content=True)
                                te = tx.TransferContentException(
                                    d.get_url(), reason=str(e))
                                failures.append(te)

                raise failures

        def prefetch_manifests(self, fetchlist, excludes=misc.EmptyI,
            progtrack=None, ccancel=None):
                """Given a list of tuples [(fmri, intent), ...], prefetch
                the manifests specified by the fmris in argument
                fetchlist.  Caller may supply a progress tracker in
                'progtrack' as well as the check-cancellation callback in
                'ccancel.'

                This method will not return transient transport errors,
                but it should raise any that would cause an immediate
                failure."""

                if not fetchlist:
                        return

                self.__lock.acquire()
                try:
                        try:
                                self._prefetch_manifests(fetchlist, excludes,
                                    progtrack, ccancel=ccancel)
                        except (apx.PermissionsException, 
                            apx.InvalidDepotResponseException):
                                pass             
                finally:
                        self.__lock.release()


        def _prefetch_manifests(self, fetchlist, excludes=misc.EmptyI,
            progtrack=None, ccancel=None):
                """This is the implementation of prefetch_manifests.
                The other function is a wrapper for this one."""

                download_dir = self.__tcfg.incoming_download_dir

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=ccancel)

                # Check if the download_dir exists.  If it doesn't create
                # the directories.
                self._makedirs(download_dir)

                # Call statvfs to find the blocksize of download_dir's
                # filesystem.
                try:
                        destvfs = os.statvfs(download_dir)
                        # set the file buffer size to the blocksize of
                        # our filesystem
                        self.__engine.set_file_bufsz(destvfs[statvfs.F_BSIZE])
                except EnvironmentError, e:
                        if e.errno == errno.EACCES:
                                raise apx.PermissionsException(e.filename)
                        else:
                                raise tx.TransportOperationError(
                                    "Unable to stat VFS: %s" % e)
                except AttributeError, e:
                        # os.statvfs is not available on Windows
                        pass

                # Walk the tuples in fetchlist and create a MultiXfr
                # instance for each publisher's worth of requests that
                # this routine must process.
                mx_pub = {}
                for fmri, intent in fetchlist:
                        pub_prefix = fmri.get_publisher()
                        pub = self.__tcfg.get_publisher(pub_prefix)
                        header = self.__build_header(intent=intent,
                            uuid=self.__get_uuid(pub))
                        if pub_prefix not in mx_pub:
                                mx_pub[pub_prefix] = MultiXfr(pub,
                                    progtrack=progtrack,
                                    ccancel=ccancel)
                        # Add requests keyed by requested package
                        # fmri.  Value contains (header, fmri) tuple.
                        mx_pub[pub_prefix].add_hash(
                            fmri, (header, fmri))

                for mxfr in mx_pub.values():
                        namelist = [k for k in mxfr]
                        while namelist:
                                chunksz = self.__chunk_size(pub,
                                    origin_only=True)
                                mfstlist = [
                                    (n, mxfr[n][0])
                                    for n in namelist[:chunksz]
                                ]
                                del namelist[:chunksz]

                                self._prefetch_manifests_list(mxfr, mfstlist,
                                    excludes)

        def _prefetch_manifests_list(self, mxfr, mlist, excludes=misc.EmptyI):
                """Perform bulk manifest prefetch.  This is the routine
                that downloads initiates the downloads in chunks
                determined by its caller _prefetch_manifests.  The mxfr
                argument should be a MultiXfr object, and mlist
                should be a list of tuples (fmri, header)."""

                # Don't perform multiple retries, since we're just prefetching.
                retry_count = 1
                mfstlist = mlist
                pub = mxfr.get_publisher()
                progtrack = mxfr.get_progtrack()

                # download_dir is temporary download path.
                download_dir = self.__tcfg.incoming_download_dir

                for d in self.__gen_origins(pub, retry_count):

                        failedreqs = []
                        repostats = self.stats[d.get_url()]
                        gave_up = False

                        # This returns a list of transient errors
                        # that occurred during the transport operation.
                        # An exception handler here isn't necessary
                        # unless we want to suppress a permanant failure.
                        try:
                                errlist = d.get_manifests(mfstlist,
                                    download_dir, progtrack=progtrack)
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, record this for later
                                # and try a different host.
                                gave_up = True
                                errlist = ex.failures
                                success = ex.success

                        for e in errlist:
                                req = getattr(e, "request", None)
                                if req:
                                        failedreqs.append(req)
                                else:
                                        raise e

                        if gave_up:
                                # If the transport gave up due to excessive
                                # consecutive errors, the caller is returned a
                                # list of successful requests, and a list of
                                # failures.  We need to consider the requests
                                # that were not attempted because we gave up
                                # early.  In this situation, they're failed
                                # requests, even though no exception was
                                # returned.  Filter the flist to remove the
                                # successful requests.  Everything else failed.
                                failedreqs = [
                                    x[0] for x in mfstlist
                                    if x[0] not in success
                                ]
                        elif failedreqs:
                                success = [
                                    x[0] for x in mfstlist
                                    if x[0] not in failedreqs
                                ]
                        else:
                                success = [ x[0] for x in mfstlist ]

                        for s in success:

                                dl_path = os.path.join(download_dir,
                                    s.get_url_path())

                                try:
                                        # Verify manifest content.
                                        fmri = mxfr[s][1]
                                        verified = self._verify_manifest(fmri,
                                            dl_path)
                                except tx.InvalidContentException, e:
                                        e.request = s
                                        repostats.record_error(content=True)
                                        failedreqs.append(s)
                                        continue

                                try:
                                        mf = file(dl_path)
                                        mcontent = mf.read()
                                        mf.close()
                                        manifest.CachedManifest(fmri,
                                            self.__tcfg.pkgdir,
                                            excludes, mcontent)
                                except (apx.InvalidPackageErrors,
                                    ActionError), e:
                                        if verified:
                                                # If the manifest was physically
                                                # valid, but can't be logically
                                                # parsed, drive on.
                                                os.remove(dl_path)
                                                progtrack.evaluate_progress(
                                                    fmri)
                                                mxfr.del_hash(s)
                                                continue
                                        repostats.record_error(content=True)
                                        failedreqs.append(s)
                                        os.remove(dl_path)
                                        continue
        
                                os.remove(dl_path)
                                progtrack.evaluate_progress(fmri)
                                mxfr.del_hash(s)

                        # If there were failures, re-generate list for just
                        # failed requests.
                        if failedreqs:
                                # Generate mfstlist here, which included any
                                # reqs that failed during verification.
                                mfstlist = [
                                    (x,y) for x,y in mfstlist
                                    if x in failedreqs
                                ]
                        # Return if everything was successful
                        else:
                                return
 
        def _verify_manifest(self, fmri, mfstpath=None, content=None):
                """Verify a manifest.  The caller must supply the FMRI
                for the package in 'fmri', as well as the path to the
                manifest file that will be verified.  If signature information
                is not present, this routine returns False.  If signature
                information is present, and the manifest verifies, this
                method returns true.  If the manifest fails to verify,
                this function throws an InvalidContentException.

                The caller may either specify a pathname to a file that
                contains the manifest in 'mfstpath' or a string that contains
                the manifest content in 'content'.  One of these arguments
                must be used."""

                # Get publisher information from FMRI.
                pub = self.__tcfg.get_publisher(fmri.get_publisher())

                if not pub:
                        return False

                # Use the publisher to get the catalog and its signature info.
                try:
                        sigs = dict(pub.catalog.get_entry_signatures(fmri))
                except apx.UnknownCatalogEntry:
                        return False

                if sigs and "sha-1" in sigs:
                        chash = sigs["sha-1"]
                else:
                        return False

                if mfstpath:
                        mf = file(mfstpath)
                        mcontent = mf.read()
                        mf.close()
                elif content:
                        mcontent = content
                else:
                        raise ValueError("Caller must supply either mfstpath "
                            "or content arguments.")

                newhash = manifest.Manifest.hash_create(mcontent)
                if chash != newhash:
                        if mfstpath:
                                sz = os.stat(mfstpath).st_size
                                os.remove(mfstpath)
                        else:
                                sz = None
                        raise tx.InvalidContentException(mfstpath,
                            "manifest hash failure: fmri: %s \n"
                            "expected: %s computed: %s" % 
                            (fmri, chash, newhash), size=sz)

                return True

        @staticmethod
        def __build_header(intent=None, uuid=None):
                """Return a dictionary that contains various
                header fields, depending upon what arguments
                were passed to the function.  Supply intent header in intent
                argument, uuid information in uuid argument."""

                header = {}

                if intent:
                        header["X-IPkg-Intent"] = intent

                if uuid:
                        header["X-IPkg-UUID"] = uuid

                if not header:
                        return None

                return header

        def __get_uuid(self, pub):
                if not self.__tcfg.get_policy(imageconfig.SEND_UUID):
                        return None

                try:
                        return pub.client_uuid
                except KeyError:
                        return None

        @staticmethod
        def _makedirs(newdir):
                """A helper function for _get_files that makes directories,
                if needed."""

                if not os.path.exists(newdir):
                        try:
                                os.makedirs(newdir)
                        except EnvironmentError, e:
                                if e.errno == errno.EACCES:
                                        raise apx.PermissionsException(
                                            e.filename)
                                if e.errno == errno.EROFS:
                                        raise apx.ReadOnlyFileSystemException(
                                            e.filename)
                                raise tx.TransportOperationError("Unable to "
                                    "make directory: %s" % e)

        def _get_files_list(self, mfile, flist):
                """Download the files given in argument 'flist'.  This
                allows us to break up download operations into multiple
                chunks.  Since we re-evaluate our host selection after
                each chunk, this gives us a better way of reacting to
                changing conditions in the network."""

                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                failures = []
                filelist = flist
                pub = mfile.get_publisher()
                progtrack = mfile.get_progtrack()
                header = None

                if isinstance(pub, publisher.Publisher):
                        header = self.__build_header(uuid=self.__get_uuid(pub))

                # download_dir is temporary download path.
                download_dir = self.__tcfg.incoming_download_dir

                cache = self._get_caches(pub, readonly=False)
                if cache:
                        # For now, pick first cache in list, if any are
                        # present.
                        cache = cache[0]

                for d in self.__gen_repos(pub, retry_count):

                        failedreqs = []
                        repostats = self.stats[d.get_url()]
                        gave_up = False

                        # This returns a list of transient errors
                        # that occurred during the transport operation.
                        # An exception handler here isn't necessary
                        # unless we want to supress a permanant failure.
                        try:
                                errlist = d.get_files(filelist, download_dir,
                                    progtrack, header)
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, record this for later
                                # and try a different host.
                                gave_up = True
                                errlist = ex.failures
                                success = ex.success

                        for e in errlist:
                                req = getattr(e, "request", None)
                                if req:
                                        failedreqs.append(req)
                                        failures.append(e)
                                else:
                                        raise e

                        if gave_up:
                                # If the transport gave up due to excessive
                                # consecutive errors, the caller is returned a
                                # list of successful requests, and a list of
                                # failures.  We need to consider the requests
                                # that were not attempted because we gave up
                                # early.  In this situation, they're failed
                                # requests, even though no exception was
                                # returned.  Filter the flist to remove the
                                # successful requests.  Everything else failed.
                                failedreqs = [
                                    x for x in filelist
                                    if x not in success
                                ]
                                filelist = failedreqs
                        elif failedreqs:
                                success = [
                                    x for x in filelist
                                    if x not in failedreqs
                                ]
                                filelist = failedreqs
                        else:
                                success = filelist
                                filelist = None

                        for s in success:

                                dl_path = os.path.join(download_dir, s)

                                try:
                                        self._verify_content(mfile[s][0],
                                            dl_path)
                                except tx.InvalidContentException, e:
                                        mfile.subtract_progress(e.size)
                                        e.request = s
                                        repostats.record_error(content=True)
                                        failedreqs.append(s)
                                        failures.append(e)
                                        if not filelist:
                                                filelist = failedreqs
                                        continue

                                if cache:
                                        cpath = cache.insert(s, dl_path)
                                        mfile.file_done(s, cpath)
                                else:
                                        mfile.file_done(s, dl_path)

                        # Return if everything was successful
                        if not filelist and not errlist:
                                return

                if failedreqs and failures:
                        failures = [
                            x for x in failures
                            if x.request in failedreqs
                        ]
                        tfailurex = tx.TransportFailures()
                        for f in failures:
                                tfailurex.append(f)
                        raise tfailurex

        def _get_files_impl(self, mfile):
                """The implementation of _get_files.  The _get_files
                function is a wrapper around this function, mainly for
                locking purposes."""

                download_dir = self.__tcfg.incoming_download_dir
                pub = mfile.get_publisher()

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=mfile.get_ccancel())

                # Check if the download_dir exists.  If it doesn't create
                # the directories.
                self._makedirs(download_dir)

                # Call statvfs to find the blocksize of download_dir's
                # filesystem.
                try:
                        destvfs = os.statvfs(download_dir)
                        # set the file buffer size to the blocksize of
                        # our filesystem
                        self.__engine.set_file_bufsz(destvfs[statvfs.F_BSIZE])
                except EnvironmentError, e:
                        if e.errno == errno.EACCES:
                                raise apx.PermissionsException(e.filename)
                        else:
                                raise tx.TransportOperationError(
                                    "Unable to stat VFS: %s" % e)
                except AttributeError, e:
                        # os.statvfs is not available on Windows
                        pass

                while mfile:

                        filelist = []
                        chunksz = self.__chunk_size(pub)

                        for i, v in enumerate(mfile):
                                if i >= chunksz:
                                        break
                                filelist.append(v)

                        self._get_files_list(mfile, filelist)

        def _get_files(self, mfile):
                """Perform an operation that gets multiple files at once.
                A mfile object contains information about the multiple-file
                request that will be performed."""

                self.__lock.acquire()
                try:
                        self._get_files_impl(mfile)
                finally:
                        self.__lock.release()

        def get_versions(self, pub, ccancel=None):
                """Query the publisher's origin servers for versions
                information.  Return a dictionary of "name":"versions" """

                self.__lock.acquire()
                try:
                        v = self._get_versions(pub, ccancel=ccancel)
                finally:
                        self.__lock.release()

                return v

        def _get_versions(self, pub, ccancel=None):
                """Implementation of get_versions"""

                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                failures = tx.TransportFailures()
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # If captive portal test hasn't been executed, run it
                # prior to this operation.
                self._captive_portal_test(ccancel=ccancel)

                for d in self.__gen_origins(pub, retry_count):
                        # If a transport exception occurs,
                        # save it if it's retryable, otherwise
                        # raise the error to a higher-level handler.
                        try:
                                vers = self.__get_version(d, header,
                                    ccancel=ccancel)
                                # Save this information for later use, too.
                                self.__populate_repo_versions(d, vers)
                                return vers 
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                for f in ex.failures:
                                        f.url = d.get_url()
                                        failures.append(f)
                        except tx.TransportException, e:
                                e.url = d.get_url()
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise
                        except ValueError:
                                raise apx.InvalidDepotResponseException(
                                    d.get_url(), "Unable to parse repository "
                                    "response")
                raise failures

        @staticmethod
        def __get_version(repo, header=None, ccancel=None):
                """An internal method that returns a versions dictionary
                given a transport repo object."""

                resp = repo.get_versions(header, ccancel=ccancel)
                verlines = resp.readlines()

                return dict(
                    s.split(None, 1)
                    for s in (l.strip() for l in verlines)
                )

        def __populate_repo_versions(self, repo, vers=None, ccancel=None):
                """Download versions information for the transport
                repository object and store that information inside
                of it."""

                # Call __get_version to get the version dictionary
                # from the repo.
                
                if not vers:
                        try:
                                vers = self.__get_version(repo, ccancel=ccancel)
                        except ValueError:
                                raise tx.PkgProtoError(repo.get_url(),
                                    "versions", 0,
                                    "VaueError while parsing response")

                for key, val in vers.items():
                        # Don't turn this line into a list of versions.
                        if key == "pkg-server":
                                continue

                        try:
                                versids = [
                                    int(v)
                                    for v in val.split()
                                ]
                        except ValueError:
                                raise tx.PkgProtoError(repo.get_url(),
                                    "versions", 0,
                                    "Unable to parse version ids.")

                        # Insert the list back into the dictionary.
                        vers[key] = versids

                repo.add_version_data(vers)

        def __gen_origins(self, pub, count, prefer_remote=False):
                """The pub argument may either be a Publisher or a RepositoryURI
                object.

                'prefer_remote' is an optional boolean value indicating whether
                network-based sources are preferred over local sources.  If
                True, network-based origins will be returned first after the
                default order criteria has been applied."""

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                if isinstance(pub, publisher.Publisher):
                        origins = pub.selected_repository.origins
                else:
                        # If search was invoked with -s option, we'll have
                        # a RepoURI instead of a publisher.  Convert
                        # this to a repo uri
                        origins = [pub]

                def remote_first(a, b):
                        # For now, any URI using the file scheme is considered
                        # local.  Realistically, it could be an NFS mount, etc.
                        # However, that's a further refinement that can be done
                        # later.
                        aremote = a[0].scheme != "file"
                        bremote = b[0].scheme != "file"
                        return cmp(aremote, bremote) * -1

                for i in xrange(count):
                        rslist = self.stats.get_repostats(origins, origins)
                        if prefer_remote:
                                rslist.sort(cmp=remote_first)
                        for rs, ruri in rslist:
                                yield self.__repo_cache.new_repo(rs, ruri)

        def __gen_publication_origin(self, pub, count):
                """The pub argument may either be a Publisher or a
                RepositoryURI object.  This function is specific to
                publication operations because it ensures that clients
                are using properly configured Publisher objects."""

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                # This is specifically to retry against a single origin
                # in the case that network failures have occurred.  If
                # the caller supplied a Publisher argument, make sure it
                # has only one origin.
                if isinstance(pub, publisher.Publisher):
                        origins = pub.selected_repository.origins
                        assert len(origins) == 1 
                else:
                        # If search was invoked with -s option, we'll have a
                        # RepoURI instead of a publisher.  Convert this to a
                        # repo uri
                        origins = [pub]

                for i in xrange(count):
                        rslist = self.stats.get_repostats(origins, origins)
                        for rs, ruri in rslist:
                                yield self.__repo_cache.new_repo(rs, ruri)

        def __gen_origins_byversion(self, pub, count, operation, version,
            ccancel=None):
                """Return origin repos for publisher pub, that support
                the operation specified as a string in the 'operation'
                argument.  The operation must support the version
                given in as an integer to the 'version' argument."""

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                if isinstance(pub, publisher.Publisher):
                        origins = pub.selected_repository.origins
                else:
                        # If search was invoked with -s option, we'll have
                        # a RepoURI instead of a publisher.  Convert
                        # this to a repo uri
                        origins = [pub]

                for i in xrange(count):
                        rslist = self.stats.get_repostats(origins)
                        for rs, ruri in rslist:
                                repo = self.__repo_cache.new_repo(rs, ruri)
                                if not repo.has_version_data():
                                        try:
                                                self.__populate_repo_versions(
                                                    repo, ccancel=ccancel)
                                        except tx.TransportException:
                                                continue

                                if repo.supports_version(operation, version):
                                        yield repo

        def __gen_repos(self, pub, count):
                """Generate a list of all repositories for a given publisher.
                This is used for content operations, whereas __gen_origins
                or __gen_origins_byversion should be used for metadata
                operations."""

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                if isinstance(pub, publisher.Publisher):
                        repo = pub.selected_repository
                        repolist = repo.mirrors[:]
                        repolist.extend(repo.origins)
                        repolist.extend(self.__dynamic_mirrors)
                        origins = repo.origins
                else:
                        # If caller passed RepositoryURI object in as
                        # pub argument, repolist is the RepoURI
                        repolist = [pub]
                        origins = repolist

                for i in xrange(count):
                        rslist = self.stats.get_repostats(repolist, origins)
                        for rs, ruri in rslist:
                                yield self.__repo_cache.new_repo(rs, ruri)

        def __chunk_size(self, pub, origin_only=False):
                """Determine the chunk size based upon how many of the known
                mirrors have been visited.  If not all mirrors have been
                visited, choose a small size so that if it ends up being
                a poor choice, the client doesn't transfer too much data."""

                CHUNK_SMALL = 10
                CHUNK_LARGE = 100

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                if isinstance(pub, publisher.Publisher):
                        repo = pub.selected_repository
                        repolist = repo.origins[:]
                        if not origin_only:
                                repolist.extend(repo.mirrors)
                else:
                        # If caller passed RepositoryURI object in as
                        # pub argument, repolist is the RepoURI
                        repolist = [pub]

                n = len(repolist)
                m = self.stats.get_num_visited(repolist)
                if m < n:
                        return CHUNK_SMALL
                return CHUNK_LARGE

        def valid_publisher_test(self, pub, ccancel=None):
                """Test that the publisher supplied in pub actually
                points to a valid packaging server."""

                self.__lock.acquire()
                try:
                        val = self._valid_publisher_test(pub)
                finally:
                        self.__lock.release()

                return val

        def _valid_publisher_test(self, pub, ccancel=None):
                """Implementation of valid_publisher_test."""

                try:
                        vd = self._get_versions(pub, ccancel=ccancel)
                except tx.TransportException, e:
                        # Failure when contacting server.  Report
                        # this as an error.  Attempt to report
                        # the specific origin that failed, and
                        # if not available, fallback to the
                        # first one for the publisher.
                        url = getattr(e, "url", pub["origin"])
                        raise apx.InvalidDepotResponseException(url,
                            "Transport errors encountered when trying to "
                            "contact repository.\nReported the following "
                            "errors:\n%s" % e)

                if not self._valid_versions_test(vd):
                        url = pub["origin"]
                        raise apx.InvalidDepotResponseException(url,
                            "Invalid or unparseable version information.")

                return True

        def captive_portal_test(self, ccancel=None):
                """A captive portal forces a HTTP client on a network
                to see a special web page, usually for authentication
                purposes.  (http://en.wikipedia.org/wiki/Captive_portal)."""

                self.__lock.acquire()
                try:
                        self._captive_portal_test(ccancel=ccancel)
                finally:
                        self.__lock.release()

        def _captive_portal_test(self, ccancel=None):
                """Implementation of captive_portal_test."""

                fail = tx.TransportFailures()

                if self.__portal_test_executed:
                        return

                self.__portal_test_executed = True
                vd = None

                for pub in self.__tcfg.gen_publishers():
                        try:
                                vd = self._get_versions(pub, ccancel=ccancel)
                        except tx.TransportException, ex:
                                # Encountered a transport error while
                                # trying to contact this publisher.
                                # Pick another publisher instead.
                                if isinstance(ex, tx.TransportFailures):
                                        fail.extend(ex.exceptions)
                                else:
                                        fail.append(ex)
                                continue
                        except apx.CanceledException:
                                self.__portal_test_executed = False
                                raise

                        if self._valid_versions_test(vd):
                                return
                        else:
                                fail.append(tx.PkgProtoError(pub.prefix,
                                    "version", 0,
                                    "Invalid content in response"))
                                continue

                if not vd:
                        # We got all the way through the list of publishers but
                        # encountered transport errors in every case.  This is
                        # likely a network configuration problem.  Report our
                        # inability to contact a server.
                        estr = "Unable to contact any configured publishers." \
                            "\nThis is likely a network configuration problem."
                        if fail:
                                estr += "\n%s" % fail
                        raise apx.InvalidDepotResponseException(None, estr)

        @staticmethod
        def _valid_versions_test(versdict):
                """Check that the versions information contained in
                versdict contains valid version specifications.

                In order to test for this condition, pick a publisher
                from the list of active publishers.  Check to see if
                we can connect to it.  If so, test to see if it supports
                the versions/0 operation.  If versions/0 is not found,
                we get an unparseable response, or the response does
                not contain pkg-server, or versions 0 then we're not
                talking to a depot.  Return an error in these cases."""

                if "pkg-server" in versdict:
                        # success!
                        return True
                elif "versions" in versdict:
                        try:
                                versids = [
                                    int(v)
                                    for v in versdict["versions"]
                                ]
                        except ValueError:
                                # Unable to determine version number.  Fail.
                                return False

                        if 0 not in versids:
                                # Paranoia.  Version 0 should be in the
                                # output for versions/0.  If we're here,
                                # something has gone very wrong.  EPIC FAIL!
                                return False

                        # Found versions/0, success!
                        return True

                # Some other error encountered. Fail.
                return False

        def multi_file(self, fmri, progtrack, ccancel):
                """Creates a MultiFile object for this transport.
                The caller may add actions to the multifile object
                and wait for the download to complete."""

                if not fmri:
                        return None

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()
                
                publisher = self.__tcfg.get_publisher(fmri.get_publisher())
                mfile = MultiFile(publisher, self, progtrack, ccancel)

                return mfile

        def multi_file_ni(self, publisher, final_dir, decompress=False,
            progtrack=None, ccancel=None):
                """Creates a MultiFileNI object for this transport.
                The caller may add actions to the multifile object
                and wait for the download to complete.

                This is used by callers who want to download files,
                but not install them through actions."""

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()
                
                mfile = MultiFileNI(publisher, self, final_dir,
                    decompress=decompress, progtrack=progtrack, ccancel=ccancel)

                return mfile

        def _action_cached(self, action, pub):
                """If a file with the name action.hash is cached,
                and if it has the same content hash as action.chash,
                then return the path to the file.  If the file can't
                be found, return None."""

                hashval = action.hash
                for cache in self._get_caches(pub=pub, readonly=True):
                        cache_path = cache.lookup(hashval)
                        try:
                                if cache_path:
                                        self._verify_content(action, cache_path)
                                        return cache_path
                        except tx.InvalidContentException:
                                # If the content in the cache doesn't match the
                                # hash of the action, verify will have already
                                # purged the item from the cache. 
                                pass

                return None

        @staticmethod
        def _verify_content(action, filepath):
                """If action contains an attribute that has the compressed
                hash, read the file specified in filepath and verify
                that the hash values match.  If the values do not match,
                remove the file and raise an InvalidContentException."""

                chash = action.attrs.get("chash", None)
                path = action.attrs.get("path", None)
                if not chash:
                        # Compressed hash doesn't exist.  Decompress and
                        # generate hash of uncompressed content.
                        ifile = open(filepath, "rb")
                        ofile = open(os.devnull, "wb")

                        try:
                                fhash = misc.gunzip_from_stream(ifile, ofile)
                        except zlib.error, e:
                                s = os.stat(filepath)
                                os.remove(filepath)
                                raise tx.InvalidContentException(path,
                                    "zlib.error:%s" %
                                    (" ".join([str(a) for a in e.args])),
                                    size=s.st_size)

                        ifile.close()
                        ofile.close()

                        if action.hash != fhash:
                                s = os.stat(filepath)
                                os.remove(filepath)
                                raise tx.InvalidContentException(action.path,
                                    "hash failure:  expected: %s"
                                    "computed: %s" % (action.hash, fhash),
                                    size=s.st_size)
                        return

                newhash = misc.get_data_digest(filepath)[0]
                if chash != newhash:
                        s = os.stat(filepath)
                        os.remove(filepath)
                        raise tx.InvalidContentException(path,
                            "chash failure: expected: %s computed: %s" % \
                            (chash, newhash), size=s.st_size)

        def publish_add(self, pub, action=None, trans_id=None):
                """Perform the 'add' publication operation to the publisher
                supplied in pub.  The caller should include the action in the
                action argument. The transaction-id is passed in trans_id."""

                self.__lock.acquire()
                try:
                        self._publish_add(pub, action=action, trans_id=trans_id)
                finally:
                        self.__lock.release()

        def _publish_add(self, pub, action=None, trans_id=None):
                """Implementation of publish_add.  The current publish_add
                function is a locking wrapper for the transport."""

                failures = tx.TransportFailures()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if the transport isn't configured or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_publication_origin(pub, retry_count):
                        try:
                                d.publish_add(action, header=header,
                                    trans_id=trans_id)
                                return
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                raise failures

        def publish_abandon(self, pub, trans_id=None):
                """Perform an 'abandon' publication operation to the
                publisher supplied in the pub argument.  The caller should
                also include the transaction id in trans_id."""

                self.__lock.acquire()
                try:
                        state, fmri = self._publish_abandon(pub,
                            trans_id=trans_id)
                finally:
                        self.__lock.release()

                return state, fmri

        def _publish_abandon(self, pub, trans_id=None):
                """Implementation of publish_abandon.  The current
                publish_abandon function is a locking wrapper for the
                transport."""

                failures = tx.TransportFailures()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if transport isn't configured, or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_publication_origin(pub, retry_count):
                        try:
                                state, fmri = d.publish_abandon(header=header,
                                    trans_id=trans_id)
                                return state, fmri
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                raise failures

        def publish_close(self, pub, trans_id=None, refresh_index=False,
            add_to_catalog=False):
                """Perform a 'close' publication operation to the
                publisher supplied in the pub argument.  The caller should
                also include the transaction id in trans_id.  If
                the refresh_index argument is true, the repository
                will be told to refresh its index.  If add_to_catalog
                is true, the pkg will be added to the catalog once
                the transactions close.  Not all transport methods
                recognize this parameter."""

                self.__lock.acquire()
                try:
                        state, fmri = self._publish_close(pub,
                            trans_id=trans_id, refresh_index=refresh_index,
                            add_to_catalog=add_to_catalog)
                finally:
                        self.__lock.release()

                return state, fmri

        def _publish_close(self, pub, trans_id=None, refresh_index=False,
            add_to_catalog=False):
                """Implementation of publish_close.  The current
                publish_close function is a locking wrapper for the
                transport."""

                failures = tx.TransportFailures()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if transport isn't configured, or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_publication_origin(pub, retry_count):
                        try:
                                state, fmri = d.publish_close(header=header,
                                    trans_id=trans_id,
                                    refresh_index=refresh_index,
                                    add_to_catalog=add_to_catalog)
                                return state, fmri
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                raise failures

        def publish_open(self, pub, client_release=None, pkg_name=None):
                """Perform an 'open' transaction to start a publication
                transaction to the publisher named in pub.  The caller should
                supply the client's OS release in client_release, and the
                package's name in pkg_name."""

                self.__lock.acquire()
                try:
                        trans_id = self._publish_open(pub,
                            client_release=client_release, pkg_name=pkg_name)
                finally:
                        self.__lock.release()

                return trans_id

        def _publish_open(self, pub, client_release=None, pkg_name=None):
                """Implementation of publish_open.  The current publish_open
                function is a locking wrapper for the transport."""

                failures = tx.TransportFailures()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if transport isn't configured, or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_publication_origin(pub, retry_count):
                        try:
                                trans_id = d.publish_open(header=header,
                                    client_release=client_release,
                                    pkg_name=pkg_name)
                                return trans_id
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                raise failures

        def publish_refresh_index(self, pub):
                """Instructs the repositories named by Publisher pub
                to refresh their index."""

                self.__lock.acquire()
                try:
                        self._publish_refresh_index(pub)
                finally:
                        self.__lock.release()

        def _publish_refresh_index(self, pub):
                """Implmentation of publish_refresh_index.  The current
                publish_refresh_index function is a locking wrapper for
                the transport."""

                failures = tx.TransportFailures()
                retry_count = global_settings.PKG_CLIENT_MAX_TIMEOUT
                header = self.__build_header(uuid=self.__get_uuid(pub))

                # Call setup if transport isn't configured, or was shutdown.
                if not self.__engine:
                        self.__setup()

                for d in self.__gen_publication_origin(pub, retry_count):
                        try:
                                d.publish_refresh_index(header=header)
                                return
                        except tx.ExcessiveTransientFailure, ex:
                                # If an endpoint experienced so many failures
                                # that we just gave up, grab the list of
                                # failures that it contains
                                failures.extend(ex.failures)
                        except tx.TransportException, e:
                                if e.retryable:
                                        failures.append(e)
                                else:
                                        raise

                raise failures

        def publish_cache_repository(self, pub, repo):
                """If the caller needs to override the underlying Repository
                object kept by the transport, it should use this method
                to replace the cached Repository object."""

                assert(isinstance(pub, publisher.Publisher))

                if not self.__engine:
                        self.__setup()

                origins = [pub.selected_repository.origins[0]]
                rslist = self.stats.get_repostats(origins, origins)
                rs, ruri = rslist[0]

                self.__repo_cache.update_repo(rs, ruri, repo)

        def publish_cache_contains(self, pub):
                """Returns true if the publisher's origin is cached
                in the repo cache."""

                if not self.__engine:
                        self.__setup()

                originuri = pub.selected_repository.origins[0].uri
                return originuri in self.__repo_cache



class MultiXfr(object):
        """A transport object for performing multiple simultaneous
        requests.  This object matches publisher to list of requests, and
        allows the caller to associate a piece of data with the request key."""

        def __init__(self, pub, progtrack=None, ccancel=None):
                """Supply the publisher as argument 'pub'."""

                self._publisher = pub
                self._hash = {}
                self._progtrack = progtrack
                # Add the check_cancelation to the progress tracker
                if progtrack and ccancel:
                        self._progtrack.check_cancelation = ccancel

        def __contains__(self, key):
                return key in self._hash

        def __getitem__(self, key):
                return self._hash[key]

        def __iter__(self):
                for k in self._hash:
                        yield k

        def __len__(self):
                return len(self._hash)

        def __nonzero__(self):
                return bool(self._hash)

        def add_hash(self, hashval, item):
                """Add 'item' to list of values that exist for
                hash value 'hashval'."""

                self._hash[hashval] = item

        def del_hash(self, hashval):
                """Remove the hashval from the dictionary, if it exists."""

                self._hash.pop(hashval, None)

        def get_ccancel(self):
                """If the progress tracker has an associated ccancel,
                return it.  Otherwise, return None."""

                return getattr(self._progtrack, "check_cancelation", None)
                
        def get_progtrack(self):
                """Return the progress tracker object for this MFile,
                if it has one."""

                return self._progtrack

        def get_publisher(self):
                """Return the publisher object that will be used
                for this MultiFile request."""

                return self._publisher

        def keys(self):
                """Return a list of the keys in the hash."""

                return self._hash.keys()


class MultiFile(MultiXfr):
        """A transport object for performing multi-file requests
        using pkg actions.  This takes care of matching the publisher
        with the actions, and performs the download and content
        verification necessary to assure correct content installation."""

        def __init__(self, pub, xport, progtrack, ccancel):
                """Supply the destination publisher in the pub argument.
                The transport object should be passed in xport."""

                MultiXfr.__init__(self, pub, progtrack=progtrack,
                    ccancel=ccancel)

                self._transport = xport

        def add_action(self, action):
                """The multiple file retrieval operation is asynchronous.
                Add files to retrieve with this function.  The caller
                should pass the action, which causes its file to
                be added to an internal retrieval list."""

                cpath = self._transport._action_cached(action,
                    self.get_publisher())
                if cpath:
                        action.data = self._make_opener(cpath)
                        if self._progtrack:
                                filesz = int(misc.get_pkg_otw_size(action))
                                self._progtrack.download_add_progress(1, filesz)
                        return

                hashval = action.hash

                self.add_hash(hashval, action)

        def add_hash(self, hashval, item):
                """Add 'item' to list of values that exist for
                hash value 'hashval'."""

                self._hash.setdefault(hashval, []).append(item)

        @staticmethod
        def _make_opener(cache_path):
                def opener():
                        f = open(cache_path, "rb")
                        return f
                return opener

        def file_done(self, hashval, current_path):
                """Tell MFile that the transfer completed successfully."""

                self._make_openers(hashval, current_path)
                self.del_hash(hashval)

        def _make_openers(self, hashval, cache_path):
                """Find each action associated with the hash value hashval.
                Create an opener that points to the cache file for the
                action's data method."""

                totalsz = 0
                nactions = 0

                filesz = os.stat(cache_path).st_size
                for action in self._hash[hashval]:
                        action.data = self._make_opener(cache_path)
                        nactions += 1
                        totalsz += misc.get_pkg_otw_size(action)

                # The progress tracker accounts for the sizes of all actions
                # even if we only have to perform one download to satisfy
                # multiple actions with the same hashval.  Since we know
                # the size of the file we downloaded, but not necessarily
                # the size of the action responsible for the download,
                # generate the total size and subtract the size that was
                # downloaded.  The downloaded size was already accounted for in
                # the engine's progress tracking.  Adjust the progress tracker
                # by the difference between what we have and the total we should
                # have received.
                nbytes = int(totalsz - filesz)
                if self._progtrack:
                        self._progtrack.download_add_progress((nactions - 1),
                            nbytes)

        def subtract_progress(self, size):
                """Subtract the progress accumulated by the download of
                file with hash of hashval.  make_openers accounts for
                hashes with multiple actions.  If this has been invoked,
                it has happened before make_openers, so it's only necessary
                to adjust the progress for a single file."""

                if not self._progtrack:
                        return

                self._progtrack.download_add_progress(-1, int(-size))

        def wait_files(self):
                """Wait for outstanding file retrieval operations to
                complete."""

                if self._hash:
                        self._transport._get_files(self)

class MultiFileNI(MultiFile):
        """A transport object for performing multi-file requests
        using pkg actions.  This takes care of matching the publisher
        with the actions, and performs the download and content
        verification necessary to assure correct content installation.

        This subclass is used when the actions won't be installed, but
        are used to identify and verify the content.  Additional parameters
        define what happens when download finishes successfully."""

        def __init__(self, pub, xport, final_dir, decompress=False,
            progtrack=None, ccancel=None):
                """Supply the destination publisher in the pub argument.
                The transport object should be passed in xport."""

                MultiFile.__init__(self, pub, xport, progtrack=progtrack,
                    ccancel=ccancel)

                self._final_dir = final_dir
                self._decompress = decompress

        def add_action(self, action):
                """The multiple file retrieval operation is asynchronous.
                Add files to retrieve with this function.   The caller
                should pass the action, which causes its file to
                be added to an internal retrieval list."""

                cpath = self._transport._action_cached(action,
                    self.get_publisher())
                hashval = action.hash

                if cpath:
                        self._final_copy(hashval, cpath)
                        if self._progtrack:
                                filesz = int(misc.get_pkg_otw_size(action))
                                self._progtrack.download_add_progress(1, filesz)
                        return

                self.add_hash(hashval, action)

        def file_done(self, hashval, current_path):
                """Tell MFile that the transfer completed successfully."""

                totalsz = 0
                nactions = 0

                filesz = os.stat(current_path).st_size
                for action in self._hash[hashval]:
                        nactions += 1
                        totalsz += misc.get_pkg_otw_size(action)

                # The progress tracker accounts for the sizes of all actions
                # even if we only have to perform one download to satisfy
                # multiple actions with the same hashval.  Since we know
                # the size of the file we downloaded, but not necessarily
                # the size of the action responsible for the download,
                # generate the total size and subtract the size that was
                # downloaded.  The downloaded size was already accounted for in
                # the engine's progress tracking.  Adjust the progress tracker
                # by the difference between what we have and the total we should
                # have received.
                nbytes = int(totalsz - filesz)
                if self._progtrack:
                        self._progtrack.download_add_progress((nactions - 1),
                            nbytes)

                self._final_copy(hashval, current_path)
                self.del_hash(hashval)

        def _final_copy(self, hashval, current_path):
                """Copy the file named by hashval from current_path
                to the final destination, decompressing, if necessary."""

                dest = os.path.join(self._final_dir, hashval)
                tmp_prefix = "%s." % hashval

                try:
                        os.makedirs(self._final_dir, mode=misc.PKG_DIR_MODE)
                except EnvironmentError, e:
                        if e.errno == errno.EACCES:
                                raise apx.PermissionsException(e.filename)
                        if e.errno == errno.EROFS:
                                raise apx.ReadOnlyFileSystemException(
                                    e.filename)
                        if e.errno != errno.EEXIST:
                                raise

                try:
                        fd, fn = tempfile.mkstemp(dir=self._final_dir,
                            prefix=tmp_prefix)
                except EnvironmentError, e:
                        if e.errno == errno.EACCES:
                                raise apx.PermissionsException(
                                    e.filename)
                        if e.errno == errno.EROFS:
                                raise apx.ReadOnlyFileSystemException(
                                    e.filename)
                        raise

                src = file(current_path, "rb")
                outfile = os.fdopen(fd, "wb")
                if self._decompress:
                        misc.gunzip_from_stream(src, outfile)
                else:
                        while True:
                                buf = src.read(64 * 1024)
                                if buf == "":
                                        break
                                outfile.write(buf)
                outfile.close()
                src.close()

                try:
                        os.chmod(fn, misc.PKG_FILE_MODE)
                        portable.rename(fn, dest)
                except EnvironmentError, e:
                        if e.errno == errno.EACCES:
                                raise apx.PermissionsException(e.filename)
                        if e.errno == errno.EROFS:
                                raise apx.ReadOnlyFileSystemException(
                                    e.filename)
                        raise

# The following two methods are to be used by clients without an Image that 
# need to configure a transport and or publishers.

def setup_publisher(repo_uri, prefix, xport, xport_cfg,
    remote_prefix=False, remote_publishers=False):
        """Given transport 'xport' and publisher configuration 'xport_cfg'
        take the string that identifies a repository by uri in 'repo_uri'
        and create a publisher object.  The caller must specify the prefix.

        If remote_prefix is True, the caller will contact the remote host
        and use its publisher info to determine the publisher's actual prefix.

        If remote_publishers is True, the caller will obtain the prefix and
        repository information from the repo's publisher info."""
        

        if isinstance(repo_uri, list):
                repo = publisher.Repository(origins=repo_uri)
                repouri_list = repo_uri
        else:
                repouri_list = [publisher.RepositoryURI(repo_uri)]
                repo = publisher.Repository(origins=repouri_list)

        pub = publisher.Publisher(prefix=prefix, repositories=[repo])

        if not remote_prefix and not remote_publishers:
                xport_cfg.add_publisher(pub)
                return pub

        try:
                newpubs = xport.get_publisherdata(pub) 
        except apx.UnsupportedRepositoryOperation:
                newpubs = None

        if not newpubs:
                xport_cfg.add_publisher(pub)
                return pub

        for p in newpubs:
                psr = p.selected_repository

                if not psr:
                        p.add_repository(repo)
                elif remote_publishers:
                        if not psr.origins:
                                for r in repouri_list:
                                        psr.add_origin(r)
                        elif repo not in psr.origins:
                                for i, r in enumerate(repouri_list):
                                        psr.origins.insert(i, r)
                else:
                        psr.origins = repouri_list

                xport_cfg.add_publisher(p)

        # Return first publisher in list
        return newpubs[0]

def setup_transport():
        """Initialize the transport and transport configuration. The caller
        must manipulate the transport configuration and add publishers
        once it receives control of the objects."""

        xport_cfg = GenericTransportCfg()
        xport = Transport(xport_cfg)

        return xport, xport_cfg
