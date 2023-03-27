#!/bin/bash

active=(versions/active/*)

if [ $1 = "export" ]
then
    cmd="packwiz mr export"
elif [ $1 = "refresh" ]
then
    cmd="packwiz refresh"
else
    cmd="packwiz update --all"
fi

for i in "${active[@]}"
do
    echo "$i"
    cd "$i"
    $cmd
    cd -
done
