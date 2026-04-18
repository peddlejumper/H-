#!/usr/bin/env python3
"""
Simple packaging helper for H# project.

Usage:
  python3 packager.py --target {exe,dmg,pkg} --entry hsharp.py --out dist --dry-run

This script performs a best-effort packaging by invoking platform tools:
  - Windows .exe: uses PyInstaller (`pyinstaller --onefile`) (best run on Windows)
  - macOS .dmg: uses `hdiutil` to create a DMG containing the app bundle (macOS only)
  - macOS .pkg: uses `pkgbuild`/`productbuild` (macOS only)

It will check for required tools and print the commands it would run when `--dry-run` is used.
"""
import argparse
import os
import shutil
import subprocess
import sys


def check_cmd(cmd):
    return shutil.which(cmd) is not None


def run(cmd, dry_run=False):
    print('CMD:', ' '.join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def build_exe(entry, outdir, name=None, dry_run=False):
    # Use pyinstaller
    if not check_cmd('pyinstaller'):
        print('pyinstaller not found. Install with: pip install pyinstaller')
        return 2
    name = name or os.path.splitext(os.path.basename(entry))[0]
    cmd = ['pyinstaller', '--onefile', '--name', name, entry]
    if outdir:
        cmd += ['--distpath', outdir]
    return run(cmd, dry_run=dry_run)


def build_app(entry, outdir, name=None, dry_run=False):
    # Create a minimal .app bundle that runs the entry script via the system Python.
    name = name or 'hsharp'
    app_name = name + '.app'
    app_dir = os.path.join(outdir or '.', app_name)
    contents = os.path.join(app_dir, 'Contents')
    macos = os.path.join(contents, 'MacOS')
    resources = os.path.join(contents, 'Resources')
    os.makedirs(macos, exist_ok=True)
    os.makedirs(resources, exist_ok=True)
    # create a small launcher script
    launcher_path = os.path.join(macos, name)
    with open(launcher_path, 'w', encoding='utf-8') as f:
        f.write('#!/bin/sh\n')
        f.write('DIR="$(cd "$(dirname "$0")/.." && pwd)"\n')
        # Prefer to run the CLI `hsharp.py` if present (so flags like --version are handled).
        f.write('if [ -f "${DIR}/Resources/hsharp.py" ]; then\n')
        f.write('  exec /usr/bin/env python3 "${DIR}/Resources/hsharp.py" "$@"\n')
        f.write('else\n')
        f.write('  exec /usr/bin/env python3 "${DIR}/Resources/%s" "$@"\n' % os.path.basename(entry))
        f.write('fi\n')
    os.chmod(launcher_path, 0o755)
    # copy entry into Resources
    shutil.copy(entry, os.path.join(resources, os.path.basename(entry)))
    # also copy other python modules from the same directory as the entry so imports work
    try:
        entry_dir = os.path.dirname(os.path.abspath(entry))
        for fn in os.listdir(entry_dir):
            if fn.endswith('.py') and fn != os.path.basename(entry):
                shutil.copy(os.path.join(entry_dir, fn), os.path.join(resources, fn))
    except Exception:
        pass
    return app_dir


def build_app_with_pyinstaller(entry, outdir, name=None, dry_run=False):
    """Build a standalone binary using PyInstaller and place it into a .app bundle.

    Steps (best run on macOS or appropriate CI):
    - Run PyInstaller to produce a single-file executable.
    - Create the .app bundle structure and copy the executable into Contents/MacOS/<name>.
    - Copy additional resources if needed.
    """
    name = name or 'hsharp'
    # ensure PyInstaller is available
    if not check_cmd('pyinstaller'):
        print('pyinstaller not found. Install with: pip install pyinstaller')
        return 2

    work_dir = os.path.abspath(outdir or '.')
    pyinstaller_dist = os.path.join(work_dir, 'pyinstaller_dist')
    os.makedirs(pyinstaller_dist, exist_ok=True)

    # Run PyInstaller
    cmd = ['pyinstaller', '--onefile', '--name', name, entry, '--distpath', pyinstaller_dist]
    ret = run(cmd, dry_run=dry_run)
    if ret != 0:
        return ret

    exe_path = os.path.join(pyinstaller_dist, name)
    if not dry_run and not os.path.exists(exe_path):
        # PyInstaller may append .exe on Windows; on macOS it should be a binary named `name`
        print('PyInstaller did not produce expected binary at', exe_path)
        return 2

    # create app bundle and put the binary into Contents/MacOS
    app_dir = os.path.join(work_dir, f'{name}-pyi.app')
    contents = os.path.join(app_dir, 'Contents')
    macos = os.path.join(contents, 'MacOS')
    resources = os.path.join(contents, 'Resources')
    os.makedirs(macos, exist_ok=True)
    os.makedirs(resources, exist_ok=True)

    # copy binary
    target_bin = os.path.join(macos, name)
    if not dry_run:
        shutil.copy(exe_path, target_bin)
        os.chmod(target_bin, 0o755)

    # copy entry and other python files for reference (optional)
    try:
        entry_dir = os.path.dirname(os.path.abspath(entry))
        for fn in os.listdir(entry_dir):
            if fn.endswith('.py'):
                shutil.copy(os.path.join(entry_dir, fn), os.path.join(resources, fn))
    except Exception:
        pass

    # create a simple Info.plist for the app (minimal)
    plist = os.path.join(contents, 'Info.plist')
    if not dry_run:
        with open(plist, 'w', encoding='utf-8') as f:
            f.write("""<?xml version='1.0' encoding='UTF-8'?>\n<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n<plist version=\"1.0\">\n<dict>\n  <key>CFBundleName</key>\n  <string>%s</string>\n  <key>CFBundleExecutable</key>\n  <string>%s</string>\n  <key>CFBundleIdentifier</key>\n  <string>com.example.%s</string>\n  <key>CFBundleVersion</key>\n  <string>0.1</string>\n</dict>\n</plist>\n""" % (name, name, name))

    # move/rename the created app into the final outdir with standard name
    final_app = os.path.join(work_dir, f'{name}.app')
    if not dry_run:
        if os.path.exists(final_app):
            shutil.rmtree(final_app)
        shutil.move(app_dir, final_app)

    # cleanup pyinstaller dist
    if not dry_run:
        try:
            shutil.rmtree(pyinstaller_dist)
        except Exception:
            pass

    print('Created PyInstaller-based app at', final_app)
    return 0


def build_dmg(entry, outdir, name=None, dry_run=False, create_app=False, sign_identity=None):
    # Create dmg from either a staging folder or an .app bundle; optionally codesign the app first
    if sys.platform != 'darwin':
        print('DMG creation requires macOS (hdiutil).')
        return 2
    if not check_cmd('hdiutil'):
        print('hdiutil not found (macOS expected).')
        return 2
    name = name or 'hsharp-app'
    if create_app:
        app_dir = build_app(entry, outdir, name=name, dry_run=dry_run)
        if sign_identity:
            cmd_sign = ['codesign', '--deep', '--force', '--options', 'runtime', '--sign', sign_identity, app_dir]
            ret = run(cmd_sign, dry_run=dry_run)
            if ret != 0:
                return ret
        staging = app_dir
    else:
        staging = os.path.join(outdir or '.', f'{name}-staging')
        os.makedirs(staging, exist_ok=True)
        shutil.copy(entry, os.path.join(staging, os.path.basename(entry)))

    dmg_path = os.path.join(outdir or '.', f'{name}.dmg')
    cmd = ['hdiutil', 'create', '-volname', name, '-srcfolder', staging, '-ov', '-format', 'UDZO', dmg_path]
    ret = run(cmd, dry_run=dry_run)
    # cleanup staging when not using app bundle
    if not dry_run and not create_app:
        shutil.rmtree(staging, ignore_errors=True)
    return ret


def build_pkg(entry, outdir, name=None, dry_run=False, sign_identity=None):
    if sys.platform != 'darwin':
        print('PKG creation requires macOS (pkgbuild/productbuild).')
        return 2
    if not check_cmd('pkgbuild'):
        print('pkgbuild not found. It is available on macOS.')
        return 2
    name = name or 'hsharp-pkg'
    stagedir = os.path.join(outdir or '.', f'{name}-payload')
    os.makedirs(stagedir, exist_ok=True)
    # place entry under /usr/local/bin in package payload
    bin_dir = os.path.join(stagedir, 'usr', 'local', 'bin')
    os.makedirs(bin_dir, exist_ok=True)
    shutil.copy(entry, os.path.join(bin_dir, os.path.basename(entry)))
    pkg_path = os.path.join(outdir or '.', f'{name}.pkg')
    cmd = ['pkgbuild', '--root', stagedir, '--install-location', '/', pkg_path]
    ret = run(cmd, dry_run=dry_run)
    if ret != 0:
        return ret
    # optionally sign the pkg with productsign (requires a Developer ID Installer cert)
    if sign_identity:
        if not check_cmd('productsign'):
            print('productsign not found; cannot sign pkg')
            return 2
        signed_pkg = os.path.join(outdir or '.', f'{name}-signed.pkg')
        cmd2 = ['productsign', '--sign', sign_identity, pkg_path, signed_pkg]
        ret = run(cmd2, dry_run=dry_run)
        if ret == 0 and not dry_run:
            # replace unsigned with signed
            os.remove(pkg_path)
            os.rename(signed_pkg, pkg_path)
    if not dry_run and ret == 0:
        shutil.rmtree(stagedir, ignore_errors=True)
    return ret


def main():
    p = argparse.ArgumentParser(description='Packager for H# project')
    p.add_argument('--target', choices=['exe', 'dmg', 'pkg'], required=True)
    p.add_argument('--entry', default='hsharp.py', help='Entry script to package')
    p.add_argument('--out', default='dist', help='Output directory')
    p.add_argument('--name', help='Name for generated package')
    p.add_argument('--dry-run', action='store_true', help='Print commands without executing')
    p.add_argument('--create-app', action='store_true', help='Create a .app bundle before making a dmg')
    p.add_argument('--sign-identity', help='Code signing identity (macOS) to sign .app/.pkg')
    p.add_argument('--notarize', action='store_true', help='Submit generated dmg/pkg for Apple notarization')
    p.add_argument('--notary-key', help='Path to Apple notary API key (.p8 or key JSON)')
    p.add_argument('--notary-key-id', help='Notary API key id')
    p.add_argument('--notary-issuer', help='Notary API issuer (team id)')
    p.add_argument('--apple-id', help='Apple ID (email) for altool fallback')
    p.add_argument('--app-password', help='App-specific password for Apple ID (altool fallback)')
    p.add_argument('--bundle-id', help='Primary bundle id for notarization (e.g. com.example.hsharp)')
    p.add_argument('--use-pyinstaller', action='store_true', help='Build a standalone macOS binary with PyInstaller and place it in the .app')
    args = p.parse_args()

    out = args.out
    os.makedirs(out, exist_ok=True)

    if args.target == 'exe':
        code = build_exe(args.entry, out, name=args.name, dry_run=args.dry_run)
    elif args.target == 'dmg':
        # allow building an app using PyInstaller-built binary for a fully self-contained app
        if args.create_app and args.use_pyinstaller:
            # build a pyinstaller binary and place it inside the .app before creating dmg
            def build_with_pyinstaller():
                return build_app_with_pyinstaller(args.entry, out, name=args.name, dry_run=args.dry_run)
            # build pyinstaller binary (or dry-run)
            ret = build_with_pyinstaller()
            if ret != 0:
                code = ret
            else:
                # now create a .app from existing Resources (build_app will add launcher and resources)
                code = build_dmg(args.entry, out, name=args.name, dry_run=args.dry_run, create_app=True, sign_identity=args.sign_identity)
        else:
            code = build_dmg(args.entry, out, name=args.name, dry_run=args.dry_run, create_app=args.create_app, sign_identity=args.sign_identity)
        # produced file path
        produced = os.path.join(out, (args.name or 'hsharp-app') + '.dmg')
    elif args.target == 'pkg':
        code = build_pkg(args.entry, out, name=args.name, dry_run=args.dry_run, sign_identity=args.sign_identity)
        produced = os.path.join(out, (args.name or 'hsharp-pkg') + '.pkg')
    else:
        print('Unknown target')
        code = 1

    # notarize if requested and build succeeded
    if code == 0 and args.notarize and args.target in ('dmg', 'pkg'):
        artifact = produced
        def notarize(artifact_path):
            # Prefer xcrun notarytool
            if check_cmd('xcrun'):
                # build notarytool command
                if args.notary_key and args.notary_key_id and args.notary_issuer:
                    cmd = ['xcrun', 'notarytool', 'submit', artifact_path, '--key', args.notary_key, '--key-id', args.notary_key_id, '--issuer', args.notary_issuer, '--wait']
                    ret = run(cmd, dry_run=args.dry_run)
                    if ret != 0:
                        return ret
                elif args.apple_id and args.app_password:
                    # fallback to altool (deprecated)
                    cmd = ['xcrun', 'altool', '--notarize-app', '-f', artifact_path, '--primary-bundle-id', args.bundle_id or 'com.example.hsharp', '-u', args.apple_id, '-p', args.app_password]
                    ret = run(cmd, dry_run=args.dry_run)
                    if ret != 0:
                        return ret
                    print('Note: altool submission may require polling for status; this script does not poll automatically in non-interactive mode.')
                else:
                    print('Notarization requested but no valid credentials provided (--notary-key+--notary-key-id+--notary-issuer or --apple-id+--app-password)')
                    return 2
                # staple the artifact
                staple_cmd = ['xcrun', 'stapler', 'staple', artifact_path]
                return run(staple_cmd, dry_run=args.dry_run)
            else:
                print('xcrun not found; cannot notarize on this machine')
                return 2

        ncode = notarize(artifact)
        if ncode != 0:
            print('Notarization failed or skipped')
            sys.exit(ncode)

    sys.exit(code)


if __name__ == '__main__':
    main()
