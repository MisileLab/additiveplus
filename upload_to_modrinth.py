#!/usr/bin/env python3
"""
Upload .mrpack files to Modrinth via the official API.

This script uploads modpack releases to Modrinth using the POST /v2/version API.
It supports uploading single or multiple .mrpack files, derives metadata from
filenames when possible, and requires explicit project configuration.

Usage:
  # Upload all .mrpack files in current directory (interactive)
  python upload_to_modrinth.py --project-id PROJECT_ID

  # Upload specific files with explicit metadata
  python upload_to_modrinth.py \\
    --project-id PROJECT_ID \\
    --files BasicCraft-1.44.0+1.21.11.fabric.mrpack \\
    --version-number 1.44.0 \\
    --version-title "BasicCraft 1.44.0" \\
    --changelog "Release notes here" \\
    --game-versions 1.21.11 \\
    --loaders fabric

  # Dry-run to preview what would be uploaded
  python upload_to_modrinth.py --project-id PROJECT_ID --dry-run

  # Upload with glob pattern
  python upload_to_modrinth.py \\
    --project-id PROJECT_ID \\
    --files "*.mrpack"

Environment Variables:
  MODRINTH_TOKEN - Modrinth API Personal Access Token (required if not passed via --token)

Exit Codes:
  0 - Success
  1 - Configuration/validation error
  2 - API request failed
  3 - Missing required metadata
"""

import argparse
import glob as glob_module
import json
import os
import re
import sys
from http.client import HTTPSConnection
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote


VERSION = "1.0.0"
USER_AGENT = f"additiveplus-modrinth-uploader/{VERSION} (https://github.com/misilelab/additiveplus)"
FILE_PART_NAME = "file"


class ModrinthUploadError(Exception):
    """Base exception for Modrinth upload errors."""
    pass


def parse_filename(filename: str) -> Dict[str, Optional[str]]:
    """
    Parse metadata from filename pattern: Name-Version+MinecraftVersion.loader.mrpack
    
    Example: BasicCraft-1.44.0+1.21.11.fabric.mrpack
    Returns: {
        'name': 'BasicCraft',
        'version': '1.44.0',
        'mc_version': '1.21.11',
        'loader': 'fabric'
    }
    """
    pattern = r'^([^-]+)-([^+]+)\+(.+)\.([^.]+)\.mrpack$'
    match = re.match(pattern, filename)
    
    if match:
        return {
            'name': match.group(1),
            'version': match.group(2),
            'mc_version': match.group(3),
            'loader': match.group(4)
        }
    
    return {
        'name': None,
        'version': None,
        'mc_version': None,
        'loader': None
    }


def get_token(args: argparse.Namespace) -> str:
    """Get Modrinth API token from args or environment."""
    token = args.token or os.environ.get('MODRINTH_TOKEN')
    
    if not token:
        raise ModrinthUploadError(
            "Modrinth API token required. Set MODRINTH_TOKEN environment variable "
            "or pass --token argument."
        )
    
    return token


def get_optional_token(args: argparse.Namespace) -> Optional[str]:
    if args.dry_run:
        return args.token or os.environ.get('MODRINTH_TOKEN')

    return get_token(args)


def resolve_files(file_patterns: List[str]) -> List[str]:
    """Resolve file patterns to actual .mrpack files."""
    files = []
    
    for pattern in file_patterns:
        if '*' in pattern or '?' in pattern:
            # Glob pattern
            matches = glob_module.glob(pattern)
            files.extend([f for f in matches if f.endswith('.mrpack')])
        else:
            # Explicit file
            if not os.path.exists(pattern):
                raise ModrinthUploadError(f"File not found: {pattern}")
            if not pattern.endswith('.mrpack'):
                raise ModrinthUploadError(f"Not a .mrpack file: {pattern}")
            files.append(pattern)
    
    if not files:
        raise ModrinthUploadError("No .mrpack files found matching the specified patterns")
    
    return sorted(set(files))


def build_version_data(
    args: argparse.Namespace,
    filename: str,
    parsed: Dict[str, Optional[str]]
) -> Dict:
    """Build the version data JSON for the Modrinth API."""
    
    # Version number: CLI arg > parsed from filename > error
    version_number = args.version_number or parsed['version']
    if not version_number:
        raise ModrinthUploadError(
            f"Could not determine version number for {filename}. "
            "Either use the naming pattern Name-Version+MCVersion.loader.mrpack "
            "or specify --version-number explicitly."
        )
    
    # Version title: CLI arg > "Name Version" > version number
    if args.version_title:
        version_title = args.version_title
    elif parsed['name'] and parsed['version']:
        version_title = f"{parsed['name']} {parsed['version']}"
    else:
        version_title = version_number
    
    # Changelog: CLI arg > default
    changelog = args.changelog or f"Release {version_number}"
    
    # Game versions: CLI arg > parsed from filename > error
    game_versions = args.game_versions
    if not game_versions and parsed['mc_version']:
        game_versions = [parsed['mc_version']]
    if not game_versions:
        raise ModrinthUploadError(
            f"Could not determine Minecraft version for {filename}. "
            "Either use the naming pattern or specify --game-versions explicitly."
        )
    
    # Loaders: CLI arg > parsed from filename > error
    loaders = args.loaders
    if not loaders and parsed['loader']:
        loaders = [parsed['loader']]
    if not loaders:
        raise ModrinthUploadError(
            f"Could not determine mod loader for {filename}. "
            "Either use the naming pattern or specify --loaders explicitly."
        )
    
    # Build the data structure
    data = {
        'project_id': args.project_id,
        'version_number': version_number,
        'name': version_title,
        'changelog': changelog,
        'game_versions': game_versions,
        'version_type': args.version_type,
        'loaders': loaders,
        'featured': args.featured,
        'status': args.status,
        'file_parts': [FILE_PART_NAME],
        'primary_file': FILE_PART_NAME,
        'dependencies': args.dependencies or [],
    }
    
    return data


def create_multipart_body(data: Dict, file_path: str) -> Tuple[bytes, str]:
    """Create multipart/form-data body for the upload request."""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body_parts = []
    
    # Add the data JSON part
    body_parts.append(f'--{boundary}'.encode())
    body_parts.append(b'Content-Disposition: form-data; name="data"')
    body_parts.append(b'Content-Type: application/json')
    body_parts.append(b'')
    body_parts.append(json.dumps(data).encode('utf-8'))
    
    # Add the file part
    filename = os.path.basename(file_path)
    body_parts.append(f'--{boundary}'.encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="{FILE_PART_NAME}"; filename="{filename}"'.encode()
    )
    body_parts.append(b'Content-Type: application/x-modrinth-modpack+zip')
    body_parts.append(b'')
    
    with open(file_path, 'rb') as f:
        body_parts.append(f.read())
    
    # Final boundary
    body_parts.append(f'--{boundary}--'.encode())
    body_parts.append(b'')
    
    body = b'\r\n'.join(body_parts)
    content_type = f'multipart/form-data; boundary={boundary}'
    
    return body, content_type


def resolve_project_id(token: Optional[str], project_ref: str, dry_run: bool = False) -> str:
    conn = HTTPSConnection('api.modrinth.com')
    headers = {
        'User-Agent': USER_AGENT,
    }
    if token:
        headers['Authorization'] = token

    try:
        conn.request('GET', f'/v2/project/{quote(project_ref, safe="")}', headers=headers)
        response = conn.getresponse()
        response_data = response.read()

        if response.status != 200:
            error_detail = response_data.decode('utf-8')
            raise ModrinthUploadError(
                f"Failed to resolve project '{project_ref}' with status {response.status}: {error_detail}"
            )

        project = json.loads(response_data.decode('utf-8'))
        project_id = project.get('id')
        if not project_id:
            raise ModrinthUploadError(
                f"Project '{project_ref}' resolved successfully but did not return an ID"
            )

        if dry_run and project_ref != project_id:
            print(f"[DRY RUN] Resolved project '{project_ref}' -> '{project_id}'")

        return project_id
    finally:
        conn.close()


def upload_version(
    token: Optional[str],
    data: Dict,
    file_path: str,
    dry_run: bool = False
) -> Optional[Dict]:
    """Upload a version to Modrinth via the API."""
    
    if dry_run:
        print(f"[DRY RUN] Would upload: {file_path}")
        print(f"[DRY RUN] Version data: {json.dumps(data, indent=2)}")
        return None

    if not token:
        raise ModrinthUploadError(
            "Modrinth API token required. Set MODRINTH_TOKEN environment variable "
            "or pass --token argument."
        )
    
    # Create multipart body
    body, content_type = create_multipart_body(data, file_path)
    
    # Create connection
    conn = HTTPSConnection('api.modrinth.com')
    
    headers = {
        'Authorization': token,
        'User-Agent': USER_AGENT,
        'Content-Type': content_type,
        'Content-Length': str(len(body))
    }
    
    try:
        # Send request
        conn.request('POST', '/v2/version', body, headers)
        response = conn.getresponse()
        response_data = response.read()
        
        # Check response
        if response.status == 200:
            result = json.loads(response_data.decode('utf-8'))
            print(f"✓ Successfully uploaded: {file_path}")
            print(f"  Version ID: {result.get('id')}")
            print(f"  Version Number: {result.get('version_number')}")
            return result
        else:
            error_detail = response_data.decode('utf-8')
            raise ModrinthUploadError(
                f"Upload failed with status {response.status}: {error_detail}"
            )
    
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Upload .mrpack files to Modrinth',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Required arguments
    parser.add_argument(
        '--project-id',
        required=True,
        help='Modrinth project ID or slug (required)'
    )
    
    # File selection
    parser.add_argument(
        '--files',
        nargs='+',
        default=['*.mrpack'],
        help='Files to upload (supports glob patterns, default: *.mrpack)'
    )
    
    # Authentication
    parser.add_argument(
        '--token',
        help='Modrinth API token (or set MODRINTH_TOKEN env var)'
    )
    
    # Version metadata (optional, can be derived from filename)
    parser.add_argument(
        '--version-number',
        help='Version number (e.g., 1.44.0). Auto-detected from filename if omitted.'
    )
    
    parser.add_argument(
        '--version-title',
        help='Version title (e.g., "BasicCraft 1.44.0"). Auto-generated if omitted.'
    )
    
    parser.add_argument(
        '--changelog',
        help='Changelog/release notes. Default: "Release VERSION"'
    )
    
    parser.add_argument(
        '--game-versions',
        nargs='+',
        help='Minecraft versions (e.g., 1.21.11). Auto-detected from filename if omitted.'
    )
    
    parser.add_argument(
        '--loaders',
        nargs='+',
        help='Mod loaders (e.g., fabric, forge). Auto-detected from filename if omitted.'
    )
    
    parser.add_argument(
        '--version-type',
        choices=['release', 'beta', 'alpha'],
        default='release',
        help='Version type (default: release)'
    )
    
    parser.add_argument(
        '--status',
        choices=['listed', 'archived', 'draft', 'unlisted'],
        default='listed',
        help='Version status (default: listed)'
    )
    
    parser.add_argument(
        '--featured',
        action='store_true',
        help='Mark version as featured'
    )
    
    parser.add_argument(
        '--dependencies',
        type=json.loads,
        help='Dependencies as JSON array (advanced)'
    )
    
    # Control flags
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be uploaded without actually uploading'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {VERSION}'
    )
    
    args = parser.parse_args()
    
    try:
        token = get_optional_token(args)
        args.project_id = resolve_project_id(token, args.project_id, dry_run=args.dry_run)

        # Resolve files
        files = resolve_files(args.files)
        
        print(f"Found {len(files)} file(s) to upload:")
        for f in files:
            print(f"  - {f}")
        print()
        
        # Upload each file
        results = []
        for file_path in files:
            filename = os.path.basename(file_path)
            parsed = parse_filename(filename)
            
            print(f"Processing: {filename}")
            if parsed['version']:
                print(f"  Detected version: {parsed['version']}")
                print(f"  Detected MC version: {parsed['mc_version']}")
                print(f"  Detected loader: {parsed['loader']}")
            
            # Build version data
            data = build_version_data(args, filename, parsed)
            
            # Upload
            result = upload_version(token, data, file_path, dry_run=args.dry_run)
            if result:
                results.append(result)
            
            print()
        
        # Summary
        if not args.dry_run:
            print("=" * 60)
            print("UPLOAD SUMMARY")
            print("=" * 60)
            print(f"Total files processed: {len(files)}")
            print(f"Successfully uploaded: {len(results)}")
            
            if results:
                print("\nUploaded versions:")
                for r in results:
                    print(f"  - {r.get('version_number')} (ID: {r.get('id')})")
        else:
            print("[DRY RUN] No files were actually uploaded.")
            print("Remove --dry-run to perform the actual upload.")
        
        return 0
    
    except ModrinthUploadError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n✗ Upload cancelled by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
