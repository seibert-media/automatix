from bundlewrap.exceptions import NoSuchNode
from bundlewrap.repo import Repository

from .command import Command


class AutomatixBwRepo(Repository):
    def reload(self):
        self.__init__(repo_path=self.path)


class BWCommand(Command):
    def _generate_python_vars(self):
        locale_vars = {'AUTOMATIX_BW_REPO': self.env.config["bw_repo"]}
        for key, value in self.env.systems.items():
            if not value.startswith('hostname!'):
                try:
                    locale_vars[f'{key}_node'] = self.env.config["bw_repo"].get_node(value)
                except NoSuchNode:
                    self.env.LOG.warning(f'bw node "{value}" does not exist, "{key}_node" not set')
        locale_vars['vars'] = self.env.vars
        return locale_vars

    def _get_remote_hostname(self):
        system = self.get_system()
        if system.startswith('hostname!'):
            return system.replace('hostname!', '')
        node = self.env.config['bw_repo'].get_node(system)
        return node.hostname
