from bundlewrap.exceptions import NoSuchNode
from bundlewrap.repo import Repository

from .command import Command


class AutomatixBwRepo(Repository):
    def reload(self):
        self.__init__(repo_path=self.path)


class BWCommand(Command):
    def _generate_python_vars(self):
        locale_vars = {'AUTOMATIX_BW_REPO': self.env.config['bw_repo']}
        for key, value in self.env.systems.items():
            if not value.startswith('hostname!'):
                try:
                    # DEPRECATED, use NODES instead
                    locale_vars[f'{key}_node'] = self.env.config['bw_repo'].get_node(value)
                except NoSuchNode:
                    self.env.LOG.warning(f'bw node "{value}" does not exist, "{key}_node" not set')
        locale_vars['vars'] = self.env.vars
        locale_vars['NODES'] = BWNodesWrapper(repo=self.env.config['bw_repo'], systems=self.env.systems)
        return locale_vars

    def _get_remote_hostname(self):
        system = self.get_system()
        if system.startswith('hostname!'):
            return system.replace('hostname!', '')
        node = self.env.config['bw_repo'].get_node(system)
        return node.hostname


class BWNodesWrapper:
    def __init__(self, repo: Repository, systems: dict):
        self.repo = repo
        self.systems = systems

    def __getattr__(self, name):
        return self.repo.get_node(self.systems[name])
