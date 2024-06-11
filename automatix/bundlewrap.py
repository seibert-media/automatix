from bundlewrap.exceptions import NoSuchNode, NoSuchGroup
from bundlewrap.group import Group
from bundlewrap.node import Node
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
                    self.env.config['bw_repo'].get_node(value)
                except NoSuchNode:
                    try:
                        self.env.config['bw_repo'].get_group(value)
                    except NoSuchGroup:
                        self.env.LOG.warning(f'"{value}" is neither a BW node nor a BW group')
        locale_vars['vars'] = self.env.vars
        locale_vars['NODES'] = BWNodesWrapper(repo=self.env.config['bw_repo'], systems=self.env.systems)
        return locale_vars

    def _remote_action(self) -> int:
        bw_repo: Repository = self.env.config['bw_repo']
        system = self.get_system()
        if system.startswith('hostname!'):
            return self._remote_action_on_hostname(hostname=system.replace('hostname!', ''))
        try:
            node: Node = bw_repo.get_node(system)
            return self._remote_action_on_hostname(hostname=node.hostname)
        except NoSuchNode as exc:
            try:
                group: Group = bw_repo.get_group(system)
            except NoSuchGroup:
                raise exc
            print()
            self.env.LOG.info(f' --- Executing command for all nodes in BW group >{group.name}< ---')
            for node in group.nodes:
                print()
                self.env.LOG.info(f'- {node.name} -')
                self._remote_bw_group_action(node=node)
            return 0

    def _remote_bw_group_action(self, node: Node):
        return_code = self._remote_action_on_hostname(hostname=node.hostname)
        if return_code != 0:
            self.env.LOG.error(f'Command ({self.index}) on {node.name} failed with return code {return_code}.')
            if self.env.cmd_args.force:
                return

            err_answer = self._ask_user(question='[PF] What should I do?', allowed_options=['p', 'T', 'v', 'r', 'a'])
            # answers 'a' and 'c' are handled by _ask_user, 'p' means just pass
            if err_answer == 'r':
                return self._remote_bw_group_action(node=node)


class BWNodesWrapper:
    def __init__(self, repo: Repository, systems: dict):
        self.repo = repo
        self.systems = systems

    def __getattr__(self, name):
        return self.repo.get_node(self.systems[name])
