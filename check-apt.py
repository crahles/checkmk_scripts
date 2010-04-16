#! /usr/bin/python

import apt_pkg
import os
import sys

SYNAPTIC_PINFILE = "/var/lib/synaptic/preferences"

class OpNullProgress(object):
    def update(self, percent):
        pass
    def done(self):
        pass

def clean(cache,depcache):
    # mvo: looping is too inefficient with the new auto-mark code
    #for pkg in cache.Packages:
    #    depcache.MarkKeep(pkg)
    depcache.Init()

def save_dist_upgrade(cache,depcache):
    """ this functions mimics a upgrade but will never remove anything """
    depcache.Upgrade(True)
    if depcache.DelCount > 0:
        clean(cache,depcache)
    depcache.Upgrade()

def _handle_exception(type, value, tb):
    sys.stderr.write("E: "+ _("Unkown Error: '%s' (%s)") % (type,value))
    sys.exit(-1)


def is_security_upgrade(ver):
    " check if the given version is a security update (or masks one) "
    for (file, index) in ver.FileList:
        if (file.Archive.endswith("-security") and
            file.Origin == "Ubuntu"):
            return True
    return False

def run():
    # be nice
    os.nice(19)
    # FIXME: do a ionice here too?

    # init
    apt_pkg.init()

    # force apt to build its caches in memory for now to make sure
    # that there is no race when the pkgcache file gets re-generated
    apt_pkg.Config.Set("Dir::Cache::pkgcache","")

    # get caches
    try:
        cache = apt_pkg.GetCache(OpNullProgress())
    except SystemError, e:
        sys.stderr.write("E: "+ _("Error: Opening the cache (%s)") % e)
        sys.exit(-1)
    depcache = apt_pkg.GetDepCache(cache)

    # read the pin files
    depcache.ReadPinFile()
    # read the synaptic pins too
    if os.path.exists(SYNAPTIC_PINFILE):
        depcache.ReadPinFile(SYNAPTIC_PINFILE)

    # init the depcache
    depcache.Init()

    if depcache.BrokenCount > 0:
        sys.stderr.write("E: "+ _("Error: BrokenCount > 0"))
        sys.exit(-1)

# do the upgrade (not dist-upgrade!)
    try:
        save_dist_upgrade(cache,depcache)
    except SystemError, e:
        sys.stderr.write("E: "+ _("Error: Marking the upgrade (%s)") % e)
        sys.exit(-1)

    # check for upgrade packages, we need to do it this way
    # because of ubuntu #7907
    upgrades = 0
    security_updates = 0
    for pkg in cache.Packages:
        if depcache.MarkedInstall(pkg) or depcache.MarkedUpgrade(pkg):
            inst_ver = pkg.CurrentVer
            cand_ver = depcache.GetCandidateVer(pkg)
            # check if this is really a upgrade or a false positive
            # (workaround for ubuntu #7907)
	    if cand_ver != inst_ver:
                # check for security upgrades
                upgrades = upgrades + 1
                if is_security_upgrade(cand_ver):
                    security_updates += 1
                # now check for security updates that are masked by a
                # canidate version from another repo (-proposed or -updates)
                for ver in pkg.VersionList:
                    if (inst_ver and apt_pkg.VersionCompare(ver.VerStr, inst_ver.VerStr) <= 0):
                        #print "skipping '%s' " % ver.VerStr
                        continue
                    if is_security_upgrade(ver):
                        security_updates += 1
                        break
                        
    if (upgrades > 0 and security_updates == 0):
        print("1 APT packages=%s;10;25;0; WARNING - %s packages need an update" % (upgrades,upgrades))
    if (upgrades > 0 and security_updates > 0):
        print("2 APT packages=%s;10;25;0; CRITICAL - %s security updates available" % (security_updates,security_updates))
    if (upgrades == 0 and security_updates == 0):
        print("0 APT packages=0;10;25;0; OK - all packages up2date")
    return()


if __name__ == "__main__":
    # setup a exception handler to make sure that uncaught stuff goes
    # to the notifier
    sys.excepthook = _handle_exception

    # run it
    run()