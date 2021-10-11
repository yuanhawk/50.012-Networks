#!/bin/sh

if [ ! -d "$1" ]; then
    printf 'Usage: %s directory\n' "$0" >&2
    exit 1
fi

# set positional parameters to the list of files in the given directory
set -- "$1"/*

# while there's still files to process...
while [ "$#" -gt 0 ]; do
    # skip over non-regular files
    if [ ! -f "$1" ]; then
        shift
        continue
    fi

    # now process the first item in the list against the other ones
    item=$1

    # shift off the first item from the list
    shift

    # loop over the remaining items...
    for name do
        # we're still not interested in non-regular files
        [ ! -f "$name" ] && continue

        # if they are the same, report this
        if cmp -s "$item" "$name"; then
            printf '%s and %s has same content\n' "$item" "$name"
        fi
    done
done
