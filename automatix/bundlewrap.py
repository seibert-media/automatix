from .command import Command


class BWCommand(Command):
    def _prepare_python_action(self, scope: dict):
        for key, scope['value'] in self.systems.items():
            exec(f'{key}_node = self.config["bw_repo"].get_node(value)', globals(), scope)

    def _get_remote_hostname(self):
        node = self.config['bw_repo'].get_node(self.get_system())
        return node.hostname
