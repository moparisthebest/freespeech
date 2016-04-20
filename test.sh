#!/bin/bash
count=$1
bs=$2
dd if=/dev/urandom count=$count bs=$bs 2>/dev/null | tee >(md5sum 1>&2) >(./freespeech.py english.txt | ./freespeech.py -d english.txt | md5sum 1>&2) 1>/dev/null 2>&1 | cat
#dd if=/dev/urandom count=$count bs=$bs 2>/dev/null | tee >(md5sum 1>&2) >(base64 | base64 -di | md5sum 1>&2) 1>/dev/null 2>&1 | cat
