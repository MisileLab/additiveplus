active=(versions/active/*)

if [ $1 = "export" ]
then
    cmd="packwiz mr export"
elif [ $1 = "refresh" ]
then
    cmd="packwiz refresh"
elif [ $1 = "update" ]
then
    cmd="packwiz update --all"
elif [ $1 = "mv" ]
then
    cmd="mv -v *.mrpack ../../../"
else
    cmd="packwiz mr add $2"
fi

for i in "${active[@]}"
do
    echo "$i"
    cd "$i"
    $cmd
    cd -
done
