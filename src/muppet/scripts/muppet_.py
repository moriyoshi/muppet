from argparse import ArgumentParser
from muppet.utils import find_executable
from muppet.settings import config_wrapper_from_file, Settings
from muppet.scripts.constants import *
from muppet.scripts import commands 
from muppet.scripts.common import MuppetApplicationError
import logging
from inspect import getargspec
import os, sys, re

global_settings_files = [
    os.path.join(SYSCONFDIR, 'muppetrc'),
    '~/.muppetrc',
    ]

def initialize_logger(verbose, progname):
    logging.basicConfig(
        stream=sys.stderr,
        level=verbose and logging.INFO or logging.WARNING,
        format="%s: %%(message)s" % progname
        )
    logging.captureWarnings(True)

def dynamic_defaults():
    return {
        'git.command': find_executable('git'),
        'muppet.cache_dir': os.path.join(CACHEDIR, 'muppet'),
        'muppet.timestamp': '%Y%m%d%H%M%S.%f',
        }

def build_settings():
    settings = Settings()
    settings.add(dynamic_defaults())
    for settings_file in global_settings_files:
        if os.path.exists(settings_file):
            logging.info("reading %s" % settings_file)
            settings.add(config_wrapper_from_file(settings_file))
        else:
            logging.info("%s does not exist" % settings_file)
    return settings


def main():
    global _progname
    parser = ArgumentParser()
    parser.add_argument(
        'command', type=str, nargs=1,
        help='subcommand')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='turn on verbose output')
    parser.add_argument(
        '-C', '--project-dir', type=str, metavar='dir',
        help='project directory (must be version-controlled)')
    parser.add_argument(
        '-n', '--dry-run', action='store_true',
        help='preflight; use this to verify what will be done')
    parser.add_argument(
        'arg', type=str, nargs='*',
        help='argument to subcommand')
    args = parser.parse_args()
    initialize_logger(args.verbose, parser.prog)
    try:
        settings = build_settings()
        variables = {
            'cwd': args.project_dir or os.getcwd(),
            'project_dir': args.project_dir,
            'dry_run': args.dry_run,
            'verbose': args.verbose
            }

        cmd_klass = getattr(commands, args.command[0].replace('-', '_'), None)
        if cmd_klass is not None:
            instance = cmd_klass(settings, variables)
            try:
                instance(*args.arg)
            except TypeError, e:
                raise MuppetApplicationError("usage: %s %s" % (args.command[0], ' '.join(getargspec(instance.__call__).args[1:])))
        else:
            raise MuppetApplicationError("command %s is not supported" % args.command[0])
    except MuppetApplicationError, e:
        logging.error(e.message)
        sys.exit(1)

if __name__ == '__main__':
    main()

