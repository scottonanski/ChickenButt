project('chickenbutt', meson_version: '>=0.64.0')
# No version: kwarg here — release_info.VERSION is the single source of
# truth for ChickenButt's version; Meson's project() can't read it (it must
# be the file's first statement, before any run_command()), and a literal
# here would be a second, driftable copy of the same number.

# Bounded installed-runtime task: a private application directory under
# <prefix>/<libdir>/chickenbutt/, mirroring the source tree's existing
# relative-resource layout (web/, vendor/, icons/ sit beside the Python
# modules exactly as they do in the checkout) so transcript_view.py's
# WEB_DIR, message_widgets.py's vendor/mistune sys.path insert, and the
# WebKit page's ../icons/ references all keep working unmodified.
#
# Desktop entry / AppStream / icon-theme / Flatpak integration are
# deliberately NOT part of this step — see HANDOFF.md.

python3 = find_program('python3')

pkglibdir = get_option('prefix') / get_option('libdir') / 'chickenbutt'
bindir = get_option('prefix') / get_option('bindir')

# Explicit allowlist — do not glob *.py. In particular this keeps the
# untracked, dev-only profiling.py (and anything else not listed here) out
# of the installed tree.
runtime_python_sources = files(
  'main.py',
  'conversation_store.py',
  'message_widgets.py',
  'ollama_client.py',
  'ollama_health.py',
  'release_info.py',
  'tray.py',
  'transcript_view.py',
  'window.py',
  'x11_sidebar.py',
)

install_data(runtime_python_sources, install_dir: pkglibdir)

# web/ — transcript page + vendored browser JS/CSS (marked, DOMPurify, hljs)
install_subdir('web', install_dir: pkglibdir)

# icons/ — private fallback icons the app resolves relative to itself
# (APP_DIR-relative in main.py; ../icons/ from web/index.html).
install_subdir('icons', install_dir: pkglibdir)

# vendor/ — vendored Python (mistune). install_subdir()'s exclude_directories
# doesn't match nested __pycache__ dirs reliably across versions, so list
# files explicitly (any depth, any future subpackage) via run_command and
# install them with their relative paths preserved.
vendor_files = run_command(
  python3, '-c',
  'import pathlib, sys\n' +
  'for p in sorted(pathlib.Path("vendor").rglob("*")):\n' +
  '    if p.is_file() and "__pycache__" not in p.parts:\n' +
  '        print(p)',
  check: true,
).stdout().strip().split('\n')

install_data(
  vendor_files,
  install_dir: pkglibdir,
  preserve_path: true,
)

# Launcher: <prefix>/<bindir>/chickenbutt — PKGLIBDIR is resolved at
# configure time against the actual selected prefix/libdir, never
# hardcoded. The launcher deliberately does NOT embed python3.full_path():
# Meson (and its `python3 = find_program('python3')` above, used only for
# the vendor-file enumeration) may itself be run from a disposable
# build-tool venv, and baking that interpreter's path into the installed
# launcher would break ChickenButt the moment that venv is deleted. `exec
# python3` at run time resolves through the installed environment's own
# PATH instead.
launcher_conf = configuration_data()
launcher_conf.set('PKGLIBDIR', pkglibdir)

configure_file(
  input: 'packaging/chickenbutt.in',
  output: 'chickenbutt',
  configuration: launcher_conf,
  install: true,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
)
