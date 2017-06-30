import os
import sys

#
# A simple python script to prune duplicate dependencies in 
# the given manifest. The longest matching dependency entry
# for the fmri is retained.
# This also strips java dependencies. We have a transform rule
# but somehow that does not work properly.
#

mfname = sys.argv[1]
print "Checking manifest: %s" % mfname

dep_fmris = []
fmri_dict = {}
m = open(mfname, "r")
mfnew = "%s.new" % mfname
m1 = open(mfnew, "w")
found_dups = False
for ln in m:
	ent = ln.strip()
	if ent.startswith("depend"):
                if ent.find("fmri=runtime/java") > -1 or \
                   ent.find("fmri=developer/java/jdk") > -1:
                        found_dups = True
                        continue
		toks = ent.split()
		fmri = None
		for tok in toks:
			if tok.startswith("fmri="):
				fmri = tok
				break
		if fmri is not None:
			if fmri not in fmri_dict:
				dep_fmris.append(fmri)
				fmri_dict[fmri] = ent
			else:
				print "Pruning duplicates:\n\t%s\n\t%s" % (fmri_dict[fmri], ent)
				if len(ent) > len(fmri_dict[fmri]):
					fmri_dict[fmri] = ent
					found_dups = True
	else:
		m1.write("%s\n" % ent)
for fmri in dep_fmris:
	m1.write("%s\n" % fmri_dict[fmri])
m1.close()
m.close()
if found_dups:
	os.rename(mfnew, mfname)

