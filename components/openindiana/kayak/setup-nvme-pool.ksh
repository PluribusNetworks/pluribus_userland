#!/bin/ksh93

disk_errors=0
PROG="$0"
pool_disk="$1"
if [ "x$pool_disk" = "x" ]
then
	echo "Usage: $PROG <pool name>"
	exit 1
fi

# 1TiB Partition size
DEFAULT_PARTITION_SIZE=1099511627776

partition_disk()
{
	dev=$1
	partition_size=$2
	tmp1=/tmp/ptable.1.$$
	tmp2=/tmp/ptable.2.$$

	# Erase label, if any
	PDSK0="/dev/dsk/${dev}p0"
	dd if=/dev/zero of=$PDSK0 bs=512 count=32

	# Default partition table. One Solaris partition for whole disk
	P0="/dev/rdsk/${dev}p0"
	fdisk -B $P0

	# Now query the table and tweak the number of sectors to be
	# within DEFAULT_PARTITION_SIZE. Re-apply the new table.
	#
	fdisk -W $tmp1 $P0
	sector_size=`awk '/bytes\/sector/ { print $2 }' $tmp1`
	numsect=`echo "$partition_size / $sector_size" | bc`
	cat $tmp1 | awk '{
		if ($1 == "191") {
			if ($10 < numsect) {
				nsect = $10;
			} else {
				nsect = numsect;
			}
			printf "%s 128 0 0 0 0 0 0 %s %s\n", $1, $9, numsect;
		} else {
			printf "%s\n", $0;
		}
	}' numsect=$numsect > $tmp2
	fdisk -F $tmp2 $P0
	rm $tmp1 $tmp2
}

# Create pool on single disk
create_pool()
{
	POOL_NAME=$1
	DISK=$2

	partition_disk $DISK $DEFAULT_PARTITION_SIZE || exit 1

	zpool create $POOL_NAME ${DISK}p1
	if [ $? -ne 0 ]; then
		echo "$PROG: zpool create $POOL_NAME failed"
		exit 1
	fi
	zpool set failmode=continue $POOL_NAME
	if [ $? -ne 0 ]; then
		echo "$PROG: zpool set failmode prop failed."
		exit 1
	fi
}

# Create mirrored pool on two disks
create_mirror_pool()
{
	POOL_NAME=$1
	DEFAULT_ROOT_DISK=$2
	DEFAULT_MIRROR_DISK=$3

	partition_disk $DEFAULT_ROOT_DISK $DEFAULT_PARTITION_SIZE || exit 1
	partition_disk $DEFAULT_MIRROR_DISK $DEFAULT_PARTITION_SIZE || exit 1

	zpool create $POOL_NAME mirror ${DEFAULT_ROOT_DISK}p1 ${DEFAULT_MIRROR_DISK}p1
	if [ $? -ne 0 ]; then
		echo "$PROG: zpool create $POOL_NAME failed"
		exit 1
	fi
	zpool set failmode=continue $POOL_NAME
	if [ $? -ne 0 ]; then
		echo "$PROG: zpool set failmode prop failed."
		exit 1
	fi
}

get_cur_nvme_format()
{
	nvme_dev=$1
	set -- `nvmeadm identify $nvme_dev | grep "LBA Format: "`
	return $3
}

find_best_nvme_format()
{
	nvme_dev=$1
	typeset -A perf
	perf=([Degraded]=0
	[Good]=1
	[Better]=2
	[Best]=3)

	_OIFS="$IFS"
	NIFS="
"
	IFS="$NIFS"
	best_perf=0
	best_format=0
	set_format=0
	curr_format=0
	meta_size=0
	lba_size=512

	for line in `/usr/sbin/nvmeadm identify $nvme_dev`
	do
		IFS="$_OIFS"
		set -- $line
		IFS="$NIFS"
		if [[ "$line" =~ "LBA Format:" ]]
		then
			set_format=$3
		fi
		if [[ "$line" =~ "LBA Format " ]]
		then
			curr_format=$3
		elif [[ "$line" =~ "Metadata Size:" ]]
		then
			meta_size=$3
		elif [[ "$line" =~ "LBA Data Size:" ]]
		then
			lba_size=$4
		elif [[ "$line" =~ "Relative Performance:" ]]
		then
			rperf=${perf[$3]}
			if ((rperf > best_perf && meta_size == 0))
			then
				best_perf=$rperf
				best_format=$curr_format
			fi
		fi
	done
	return $best_format
}

build_nvme_pool()
{
	POOL_NAME=$1
	if [[ -z $POOL_NAME ]]
	then
		echo "$PROG: build_nvme_pool, Missing required fields."
		exit 1
	fi

	num_devs=$(/usr/sbin/nvmeadm list | grep "^  "| wc -l)
	[ $? -ne 0 -o $num_devs -eq 0 ] && return 254
	ROOT_DISK_NVME=$(/usr/sbin/nvmeadm list | nawk 'BEGIN { cnt = 0; }
		/^  / { cnt++; if (cnt == 1) {  print $1; } }
	')
	ROOT_DISK=$(/usr/sbin/nvmeadm list | grep "^  " | nawk 'BEGIN { cnt = 0; } {
		cnt += 1;
		gsub(/[\(\):]/, "", $2);
		if (cnt == 1) {
			print $2;
		}
	}')
	get_cur_nvme_format $ROOT_DISK_NVME
	cur_format=$?
	find_best_nvme_format $ROOT_DISK_NVME
	best_format=$?

	if [ $cur_format -ne $best_format ]
	then
		/usr/sbin/nvmeadm format $ROOT_DISK_NVME $best_format
		cur_format=$best_format
	fi

	if [ $num_devs -eq 1 ]
	then
		create_pool "$POOL_NAME" $ROOT_DISK
	else
		MIRROR_DISK_NVME=$(/usr/sbin/nvmeadm list | nawk 'BEGIN { cnt = 0; }
			/^  / { cnt++; if (cnt == 2) {  print $1; } }
		')
		MIRROR_DISK=$(/usr/sbin/nvmeadm list | grep "^  " | nawk 'BEGIN { cnt = 0; } {
			cnt += 1;
			gsub(/[\(\):]/, "", $2);
			if (cnt == 2) {
				print $2;
			}
		}')
		get_cur_nvme_format $MIRROR_DISK_NVME
		if [ $? -ne $cur_format ]
		then
			/usr/sbin/nvmeadm format $MIRROR_DISK_NVME $cur_format
		fi
		create_mirror_pool "$POOL_NAME" $ROOT_DISK $MIRROR_DISK
	fi
}

if [ -x /usr/sbin/nvmeadm ]
then
	build_nvme_pool "$pool_disk"
	ret_val=$?
	[ $ret_val -eq 254 ] && disk_errors=$((disk_errors + 1))
fi
if [ $disk_errors -gt 0 ]
then
	echo "$PROG: Missing Disks for external pools"
	exit 1
fi

