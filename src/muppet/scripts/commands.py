from muppet.vcs import query_backends
from muppet.vcs.base import NoSuchReference
from muppet.exceptions import MuppetException
from muppet.scripts.common import MuppetApplicationError
from muppet.settings import config_wrapper_from_file
from muppet.tree import Tree, copy
from datetime import datetime
import fabric.api, fabric.contrib.project
import logging
import re, os

class Command(object):
    def __init__(self, settings, variables):
        self.settings = settings
        self.variables = variables

class ProjectCommand(Command):
    def __init__(self, settings, variables):
        Command.__init__(self, settings, variables)
        project_dir = variables['project_dir']
        if not project_dir:
            raise MuppetApplicationError("Please specify a project directory")
        project_local_settings_file = os.path.join(project_dir, '.muppetrc')
        if not os.path.exists(project_local_settings_file):
            raise MuppetApplicationError(".muppetrc does not exist in %s" % project_dir)

        logging.info("reading %s" % project_local_settings_file)
        settings.add(config_wrapper_from_file(project_local_settings_file))

class VCSCommand(Command):
    def __init__(self, settings, variables):
        backends = query_backends(settings, variables)
        if not backends:
            raise MuppetApplicationError("Directory (%s) is not version-controlled" % variables['cwd'])
        repo_root = backends[0].repo_root
        if repo_root != variables['project_dir']:
            raise MuppetApplicationError("Project directory (%s) is not the root directory of the repository (%s)" % (variables['project_dir'], repo_root))
        ProjectCommand.__init__(self, settings, variables)
        self.vcs = backends[0]

class apply(VCSCommand):
    def __call__(self, *servers):
        servers_ = []
        for server in servers:
            servers_str = self.settings.get('servers.%s' % servers, '').strip()
            servers_.extend(servers_str and re.split(r'\s+,\s+', servers_str) or [server])
        self.do(servers_)

    def do(self, servers):
        for server, tag, head in self.gather_info(servers):
            print("%s:" % server)
            print("  Tag: %s\n  Head: %s" % (tag.referenced.id, head.referenced.id))
 
    def gather_info(self, servers):
        retval = []
        for server in servers:
            try:
                retval.append((
                    server,
                    self.vcs.get_tag(server),
                    self.vcs.branch))
            except NoSuchReference:
                raise MuppetApplicationError("%s is not managed" % server)
        return retval

class put(ProjectCommand):
    def __call__(self, *servers):
        servers_ = []
        for server in servers:
            servers_str = self.settings.get('servers.%s' % servers, '').strip()
            servers_.extend(servers_str and re.split(r'\s+,\s+', servers_str) or [server])
        self.do(servers_)

    def do(self, servers):
        settings_dir = os.path.join(self.variables['project_dir'], self.settings['settings.dir'])
        for server in servers:
            server_settings_dir = os.path.join(settings_dir, server)
            if not os.path.exists(server_settings_dir):
                raise MuppetApplicationError("%s does not exist" % server_settings_dir)
            host_string = self.settings.get('hosts.%s' % server, server)
            fabric.api.env['host_string'] = host_string
            remote_dir = os.path.join(
                self.settings['muppet.cache_dir'],
                datetime.now().strftime(self.settings['muppet.timestamp'])
                )
            fabric.contrib.project.rsync_project(local_dir=server_settings_dir + '/', remote_dir=remote_dir)
            options = []
            if self.variables.get('verbose'):
                options.append('-v')
            if self.variables.get('dry_run'):
                options.append('-n')
            @fabric.api.task
            def put_local(remote_dir, options):
                fabric.api.sudo(' '.join(['muppet'] + options + ['put-local', remote_dir]))
            put_local(remote_dir, options)

class put_local(Command):
    def __call__(self, src, dest='/'):
        try:
            logging.warning("Copying %s to %s ..." % (src, dest))
            copy(dest, src, Tree.from_annotated_fs(src), dry_run=self.variables.get('dry_run', False))
            logging.warning("Done.")
        except EnvironmentError, e:
            raise MuppetApplicationError(e)
        except MuppetException, e:
            raise MuppetApplicationError(e)
    
