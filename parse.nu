#!/usr/bin/env nu

let files = open data.json | get files
let version = input "version: "
cd $"./versions/active/($version)"
for i in $files {
  let downloads = $i | get downloads
  if (($downloads | length) != 1) {
    continue
  }
  let download = $downloads | get 0 | str replace "https://cdn.modrinth.com/data/" "" | split row "/" | get 0
  print $download
  let exit_code = (packwiz mr add -y $download | complete | $in.exit_code)
  if ($exit_code != 0) {
    $"($download)\n" | save -a missing-mods
  }
}

