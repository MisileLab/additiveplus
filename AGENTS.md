# additiveplus

Minecraft Fabric modpack based on [Additive](https://modrinth.com/modpack/additive), published as **BasicCraft** on Modrinth (project id `q5leAqeh`).

## STRUCTURE

```
versions/fabric/<mc>/    # one dir per MC version: mods/, config/, resourcepacks/, pack.toml, index.toml
versions/active/         # symlinks -> ../fabric/<ver>; controls which versions justfile targets
archived/fabric/         # old versions (1.16.5, 1.18.2, 1.19.x, 1.20.x)
justfile                 # wraps simple-packwiz-wrapper.sh
simple-packwiz-wrapper.sh # loops packwiz over versions/active/*
upload_to_modrinth.py    # .mrpack -> Modrinth API
shell.nix                # dev env: packwiz, just, nodejs, pnpm
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add/remove mod | `versions/fabric/<ver>/mods/*.pw.toml` |
| Export modpack | `just export` |
| Update all mods | `just update` |
| Refresh index | `just refresh` |
| Upload to Modrinth | `just upload q5leAqeh` |

## CONVENTIONS

- Active versions = symlinks in `versions/active/`. Wrapper globs `versions/active/*` and runs packwiz in each. Remove symlink to stop targeting a version.
- **obe** (Orthogonal Block Entities) for block-entity rendering on all versions except **1.21.1**, which keeps **ebe** (Enhanced Block Entities) due to a chest-render issue.
- Modrinth `game_versions` tags omit `mc` prefix (e.g. `1.21.11`, `26.1.2`), though `pack.toml` embeds `+mc<ver>`.
- Mod manifests are `.pw.toml` (packwiz format). packwiz resolves jars at export.
- Upload script auto-parses `BasicCraft-<ver>+mc<mcver>.fabric.mrpack` filenames for version/MC/loader metadata.

## COMMANDS

```bash
just export                    # build .mrpack for all active versions
just update                    # update all mods to latest compatible
just refresh                   # rehash index.toml after file changes
just upload q5leAqeh           # upload to Modrinth
just upload-dry-run q5leAqeh   # preview upload
just cleanup                   # rm *.mrpack
```

## NOTES

- Modrinth token: `~/.config/modrinth/token` or `MODRINTH_TOKEN` env var. Never commit or print.
- Dev shell: `nix-shell` or install packwiz + just manually.
