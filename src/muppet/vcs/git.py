from muppet.vcs.base import Reference, Branch, Revision, VCSBase, NoSuchRevision, NoSuchReference
from muppet.utils import do_cmd, line_by_line, traverse_dict
from muppet.exceptions import MuppetException, MuppetExternalCommandError, MuppetConfigurationError
import os

class GitReference(Reference):
    def __init__(self, git, ref):
        self.git = git
        self._ref = ref

    @property
    def name(self):
        return self._ref

    @property
    def referenced(self):
        return self.git[self._ref]

    @property
    def id(self):
        return self.referenced.id

class GitRevision(Revision):
    def __init__(self, git, sha1):
        self.git = git
        self._sha1 = sha1
        self._parents = None
        self._message = None

    def __eq__(self, that):
        return self._sha1 == that._sha1

    def populate_with_raw(self, props, message):
        self._parents = [self.git.get_rev(parent_rev) for parent_rev in props.get('parent', [])]
        self._message = message

    def populate(self):
        if self._parents is None or self._message is None:
            self.populate_with_raw(*self.git.wrapper.do_log_1(self._sha1))

    @property
    def id(self):
        return self._sha1

    @property
    def parents(self):
        self.populate()
        return self._parents

    @property
    def message(self):
        self.populate()
        return self._message

class GitBranch(GitReference):
    pass

class GitLowLevelWrapper(object):
    def __init__(self, command, cwd):
        self.command = command
        self.cwd = cwd

    def do_cmd(self, *args):
       return do_cmd(self.command, cwd=self.cwd, *args)

    def do_log_1(self, commit):
        i = line_by_line(sef.do_cmd('log', '-1', '--format=raw', commit))
        props = {}
        for line in i:
            line = line.strip()
            if line == '':
                break
            key, value = line.split(' ', 1)
            props.setdefault(key, []).append(value)
        message = unicode(
            ''.join([line[4:].strip() for line in i]),
            self.do_config('i18n.logOutputEncoding', 'utf-8')
            )
        return props, message

    def do_branches(self):
        i = line_by_line(self.do_cmd('branch'))
        current = None
        branches = []
        for line in i:
            line = line.strip()
            branch = line[2:]
            if line[0] == '*':
                current = branch
            branches.append(branch)
        return branches, current

    def do_tag(self, name, commit):
        return self.do_cmd('tag', '-f', name, commit)

    def do_revparse(self, name):
        try:
            return self.do_cmd('rev-parse', name)
        except MuppetExternalCommandError:
            return None

    def do_diff(self, rev1, rev2, path):
        return self.do_cmd('diff', rev1, rev2, '--', path)

    def do_get_gitdir(self):
        return os.path.normpath(os.path.join(self.cwd, self.do_cmd('rev-parse', '--git-dir')))

    def do_config(self, key, default=None):
        try:
            return self.do_cmd('config', key)
        except MuppetExternalCommandError:
            return default

class GitConfig(object):
    def __init__(self, git):
        self.git = git

    def __getitem__(self, key):
        value = self.git.wrapper.do_config(key)
        if value is None:
            raise KeyError(key)
        return value

class Git(VCSBase):
    def __init__(self, command, cwd):
        if not os.path.exists(command):
            raise MuppetConfigurationError(u'%s does not exist' % command)
        self.wrapper = GitLowLevelWrapper(command, cwd)
        self.config = GitConfig(self)
        self._branch = None
        self._branches = None
        self._refs = {}
        self._revs = {}

    @classmethod
    def from_settings_and_variables(self, settings, variables):
        return self(settings['git.command'], variables['cwd'])

    @property
    def repo_root(self):
        return os.path.dirname(self.wrapper.do_get_gitdir())

    def diff(self, rev1, rev2, path):
        self.wrapper.do_diff(rev1.id, rev2.id, path)

    def __getitem__(self, commit):
        props, message = self.wrapper.do_log_1(commit)
        rev_obj = self._get_rev(props['commit'][0])
        rev_obj.populate_with_raw(props, message)
        return rev_obj

    def get_tag(self, name):
        rev = self.wrapper.do_revparse(name)
        if rev is None:
            raise NoSuchReference(name)
        self._get_rev(rev)
        return self._get_ref(name)

    def put_tag(self, name):
        self.wrapper.do_tag(name, ref)
        return self._get_ref(name)

    def _get_ref(self, ref):
        ref_obj = self._refs.get(ref)
        if ref_obj is not None:
            if ref_obj.__class__ != GitReference:
                raise MuppetException("%s was not a reference" % ref)
        else:
            ref_obj = self._refs[ref] = GitReference(self, ref)
        return ref_obj

    def _get_branch(self, ref):
        ref_obj = self._refs.get(ref)
        if ref_obj is not None:
            if ref_obj.__class__ != GitBranch:
                raise MuppetException("%s was not a branch" % ref)
        else:
            ref_obj = self._refs[ref] = GitBranch(self, ref)
        return ref_obj

    def _get_rev(self, rev):
        rev_obj = self._revs.get(rev)
        if rev_obj is None:
            rev_obj = self._revs[rev] = GitRevision(self, rev)
        return rev_obj

    def _populate_branches(self):
        if self._branches is None:
            branch_refs, current_branch_ref = self.wrapper.do_branches()
            self._branches = [self._get_branch(ref) for ref in branch_refs]
            self._branch = self._get_branch(current_branch_ref)

    @property
    def branches(self):
        self._populate_branches()
        return self._branches

    @property
    def branch(self):
        self._populate_branches()
        return self._branch

