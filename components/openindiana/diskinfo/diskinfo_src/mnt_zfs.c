#include <sys/types.h>
#include <sys/mount.h>
#include <sys/mntent.h>


int
main(int argc, char *argv[]) {
	char optstr[MAX_MNTOPT_STR];
	char *ds = argv[1];
	char *mntpt = argv[2];

	optstr[0] = '\0';

	if (mount(ds, mntpt, MS_OPTIONSTR, "zfs", NULL, 0, optstr, sizeof (optstr)) != 0) {
		perror("Mount: ");
	}
	return (0);
}

