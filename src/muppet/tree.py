import simplejson as json
import os
import logging
from stat import *
from muppet.exceptions import MuppetException, MuppetPrerequisiteError
import shutil

MUPPET_META = '.muppetmeta'

class Tree(object):
    def __init__(self):
        self.root = None

    def __repr__(self):
        return '%s(root=%r)' % (self.__class__.__name__, self.root)

    @classmethod
    def from_annotated_fs(self, root, prototype=None):
        retval = Tree()
        retval.root = Directory.from_annotated_fs(retval, root, prototype)
        return retval

class EntryMetadata(object):
    def __init__(self, entry_defaults=None, expects=None):
        self.entry_defaults = entry_defaults or Entry()
        self.expects = expects or {}

    def merge(self, that):
        if self.expects:
            expects = dict(self.expects)
            if that.expects:
                expects.update(that.expects)
        else:
            if that.expects:
                expects = dict(that.expects)
            else:
                expects = {}
        return self.__class__(
            entry_defaults=self.entry_defaults.merge(that.entry_defaults),
            expects=expects
            )

    @classmethod
    def from_json_dict(self, dict_):
        entry_defaults = dict_.get('entry-defaults')
        expects = dict_.get('expects')
        return self(
            entry_defaults=entry_defaults and Entry.from_json_dict(entry_defaults),
            expects=(expects and dict(
                expect.partition(':')[0::2] for expect in expects
                ))
            )

class Entry(object):
    def __init__(self, tree=None, parent=None, name=None, meta=None, mode=None, owner=None, group=None, **kwargs):
        self.tree = tree
        self.parent = parent
        self.name = name
        self.meta = meta
        self.mode = mode
        self.owner = owner
        self.group = group

    def merge(self, that):
        if isinstance(that, self.__class__):
            klass = that.__class__
        elif isinstance(self, that.__class__):
            klass = self.__class__
        else:
            raise MuppetException("%r != %r" % (self.__class__, that.__class__))
        if self.meta:
            if that.meta:
                meta = self.meta.merge(that.meta)
            else:
                meta = self.meta
        else:
            if that.meta:
                meta = that.meta
            else:
                meta = None
        return klass(
            name=that.name or self.name,
            tree=that.tree or self.tree,
            parent=that.parent or self.parent,
            meta=meta,
            mode=that.mode or self.mode,
            owner=that.owner or self.owner,
            group=that.group or self.group
            )

    @classmethod
    def from_json_dict(self, dict):
        mode = dict.get('file-mode')
        if isinstance(mode, basestring):
            mode = int(mode, 8)
        return self( 
            meta=EntryMetadata.from_json_dict(dict),
            mode=mode,
            owner=dict.get('file-owner'),
            group=dict.get('file-group')
            )

class File(Entry):
    pass

class Symlink(Entry):
    def __init__(self, *args, **kwargs):
        Entry.__init__(self, *args, **kwargs)
        self.to = kwargs.get('to', None)

    def merge(self, that):
        retval = Entry.merge(self, that)
        if isinstance(that, Symlink):
            retval.to = retval.to or that.to
        return retval

class Directory(Entry):
    def __init__(self, *args, **kwargs):
        Entry.__init__(self, *args, **kwargs)
        self.entries = set()

    def add(self, entry):
        self.entries.add(entry)

    def merge(self, that):
        retval = Entry.merge(self, that)
        if isinstance(that, Directory):
            retval.entries.update(that.entries)
        return retval

    def __repr__(self):
        return '%s[%s]' % (object.__repr__(self), ', '.join(repr(i) for i in self.entries))

    @classmethod
    def from_annotated_fs(self, tree, root, prototype):
        metadata_file = os.path.join(root, MUPPET_META)
        metadata_json = None
        retval = Directory(tree, None, None, EntryMetadata())
        if prototype:
            retval = prototype.merge(retval)
        if os.path.exists(metadata_file):
            try:
                metadata_json = json.load(open(metadata_file))
            except ValueError, e:
                raise MuppetException("%s" % metadata_file, e)
            retval = retval.merge(
                Entry.from_json_dict(metadata_json))

        entry_prototypes = dict()
        if metadata_json is not None:
            for entry_name, metadata_json_for_entry in \
                    metadata_json['entries'].iteritems():
                symlink_to = metadata_json_for_entry.get('symlink')
                if entry_name[-1] == '/':
                    entry = Directory(None, None, entry_name[:-1])
                elif symlink_to:
                    entry = Symlink(None, None, entry_name, to=symlink_to)
                else:
                    entry = File(None, None, entry_name)
                entry_prototypes[entry.name] = entry.merge(
                    retval.meta.entry_defaults.merge(
                        Entry.from_json_dict(metadata_json_for_entry)))
 
        for entry_name in os.listdir(root):
            abs_path = os.path.join(root, entry_name)
            if entry_name == MUPPET_META:
                continue
            
            entry_prototype = entry_prototypes.get(entry_name)

            stat = os.lstat(abs_path)
            if stat.st_mode & S_IFDIR:
                entry = Directory(tree, retval, entry_name, EntryMetadata())
            elif stat.st_mode & S_IFLNK == S_IFLNK:
                entry = Symlink(tree, retval, entry_name, EntryMetadata(), to=os.readlink(abs_path))
            else:
                if entry_prototype is None and stat.st_mode & S_IFREG == S_IFREG:
                    entry = File(tree, retval, entry_name, EntryMetadata())
                else:
                    entry = Entry(tree, retval, entry_name, EntryMetadata())

            if entry_prototype is not None:
                entry = entry_prototype.merge(entry)
            else:
                logging.info("Metadata for %s is not provided" % abs_path)
            if isinstance(entry, Directory):
                entry = Directory.from_annotated_fs(tree, abs_path, entry)
            if entry.__class__ == Entry:
                logging.warning("%s is not a regular file; ignored" % entry.name)
            else:
                retval.add(entry)
 
        return retval

def set_mode_and_owner(entry_path, entry):
    if entry.mode is not None:
        os.chmod(entry_path, entry.mode)
    if entry.owner is not None:
        os.chown(entry_path, entry.owner)
    if entry.group is not None:
        os.chgrp(entry_path, entry.group)

class TreeCopyier(object):
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.unmanaged_files = []

    def check_unmanaged(self, path, entries):
        self.unmanaged_files.extend(os.path.join(path, file) for file in set(os.listdir(path)) - set(entry.name for entry in entries))

    def _copy(self, dest, src, dir):
        for entry in dir.entries:
            dest_path = os.path.join(dest, entry.name)
            src_path = os.path.join(src, entry.name)
            try:
                stat = os.lstat(dest_path)
            except EnvironmentError, e:
                if e.errno == 2:
                    stat = None
                else:
                    raise
            if 'precreated' in entry.meta.expects:
                if stat is None:
                    raise MuppetPrerequisiteError("%s must have been created" % dest_path)
                if isinstance(entry, Directory):
                    logging.info("Verifying %s is a directory" % dest_path)
                    if stat.st_mode & S_IFDIR != S_IFDIR:
                        raise MuppetPrerequisiteError("%s must be a directory" % dest_path)
                    self._copy(dest_path, src_path, entry)
                    self.check_unmanaged(dest_path, entry.entries)
                elif isinstance(entry, Symlink):
                    logging.info("Verifying %s is a symbolic link" % dest_path)
                    if stat.st_mode & S_IFLNK != S_IFLNK:
                        raise MuppetPrerequisiteError("%s must be a symbolic link" % dest_path)
                elif isinstance(entry, File):
                    logging.info("Verifying %s is a regular file" % dest_path)
                    if stat.st_mode & S_IFREG != S_IFREG:
                        raise MuppetPrerequisiteError("%s must be a regular file" % dest_path)
            else:
                if isinstance(entry, Directory):
                    if stat and stat.st_mode & S_IFDIR != S_IFDIR:
                        logging.info("%s is not a directory; removing it" % dest_path)
                        if not self.dry_run:
                            os.unlink(dest_path)
                    logging.info("Creating %s" % dest_path)
                    if not self.dry_run:
                        if stat is None:
                            os.mkdir(dest_path)
                        set_mode_and_owner(dest_path, dir)
                    self._copy(dest_path, src_path, entry)
                    self.check_unmanaged(dest_path, entry.entries)
                elif isinstance(entry, Symlink):
                    if stat:
                        logging.info("%s already exists; removing it" % dest_path)
                        if not self.dry_run:
                            if stat.st_mode & S_IFDIR == S_IFDIR:
                                shutil.rmtree(dest_path)
                            else:
                                os.unlink(dest_path)
                    logging.info("Creating %s" % dest_path)
                    if not self.dry_run:
                        os.symlink(entry.to, dest_path)
                        set_mode_and_owner(dest_path, entry) 
                elif isinstance(entry, File):
                    if stat:
                        logging.info("%s already exists; removing it" % dest_path)
                        if not self.dry_run:
                            if stat.st_mode & S_IFDIR == S_IFDIR:
                                shutil.rmtree(dest_path)
                            else:
                                os.unlink(dest_path)
                    logging.info("Copying %s to %s" % (src_path, dest_path))
                    if not self.dry_run:
                        shutil.copyfile(src_path, dest_path)
                        set_mode_and_owner(dest_path, entry) 

    def __call__(self, dest, src, tree):
        self._copy(dest, src, tree.root)

def copy(dest, src, tree, dry_run=False):
    copier = TreeCopyier(dry_run)
    copier(dest, src, tree)
    if copier.unmanaged_files:
        logging.warning("The following files are unmanaged:")
        for file in copier.unmanaged_files:
            logging.warning("  %s" % file)

