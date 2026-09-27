export:
  ./simple-packwiz-wrapper.sh export

update:
  ./simple-packwiz-wrapper.sh update

refresh:
  ./simple-packwiz-wrapper.sh refresh

move:
  ./simple-packwiz-wrapper.sh mv

remove:
  ./simple-packwiz-wrapper.sh rm

cleanup:
  rm -rv *.mrpack

upload-dry-run project_id:
  python3 upload_to_modrinth.py --project-id {{project_id}} --dry-run

upload project_id:
  python3 upload_to_modrinth.py --project-id {{project_id}}
