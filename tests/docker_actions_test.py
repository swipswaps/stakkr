import os
import subprocess
import sys
from docker.errors import NotFound
import unittest
from stakkr import docker_actions


base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, base_dir + '/../')


# https://docs.python.org/3/library/unittest.html#assert-methods
class DockerActionsTest(unittest.TestCase):
    def test_container_running(self):
        """Make sure, even in another directory, the venv base dir is correct."""
        stop_remove_container('pytest')
        docker_actions.get_client().containers.run(
            'edyan/adminer:latest', detach=True, name='pytest')

        self.assertTrue(docker_actions.container_running('pytest'))

    def test_container_not_running(self):
        """Make sure, even in another directory, the venv base dir is correct."""
        stop_remove_container('pytest')

        self.assertFalse(docker_actions.container_running('pytest'))

    def test_get_container_info(self):
        """
        Start docker compose with another configuration fileself.
        Then extract VM Info.
        """

        config = base_dir + '/static/stakkr.yml'

        # Clean
        exec_cmd(['stakkr-compose', '-c', config, 'stop'])
        remove_network('static_stakkr')

        # Start again
        cmd = ['stakkr-compose', '-c', config, 'up', '-d', '--force-recreate']
        exec_cmd(cmd)

        numcts, cts = docker_actions.get_running_containers('static')
        self.assertIs(len(cts), 3)
        for ct_id, ct_info in cts.items():
            if ct_info['name'] in ('static_maildev', 'static_portainer'):
                continue

            self.assertTrue('name' in ct_info)
            self.assertTrue('compose_name' in ct_info)
            self.assertTrue('ports' in ct_info)
            self.assertTrue('running' in ct_info)
            self.assertTrue('ip' in ct_info)
            self.assertTrue('image' in ct_info)

            self.assertEqual(ct_info['name'], 'static_php')
            self.assertEqual(ct_info['compose_name'], 'php')
            self.assertTrue(ct_info['running'])
            self.assertNotEqual(ct_info['ip'][:10], '192.168.23')
            self.assertEqual(ct_info['image'], 'edyan/php:7.2')

        self.assertTrue(docker_actions._container_in_network('static_php', 'static_stakkr'))
        self.assertTrue(docker_actions.network_exists('static_stakkr'))
        self.assertFalse(docker_actions._container_in_network('static_php', 'bridge'))

        exec_cmd(['stakkr-compose', '-c', config, 'stop'])
        stop_remove_container('static_php')

        with self.assertRaisesRegex(LookupError, 'Container static_php does not seem to exist'):
            docker_actions._container_in_network('static_php', 'bridge')

        exec_cmd(['stakkr', 'stop'])
        remove_network('static_stakkr')
        self.assertFalse(docker_actions.network_exists('static_stakkr'))

    def test_get_container_info_network_set(self):
        """
        Start docker compose with another configuration file,
        definint a network, then extract VM Info

        """
        exec_cmd(['stakkr-compose', '-c', base_dir + '/static/config_valid_network.yml', 'stop'])
        exec_cmd(['stakkr-compose', '-c', base_dir + '/static/config_valid_network.yml', 'down'])
        exec_cmd([
            'stakkr-compose', '-c', base_dir + '/static/config_valid_network.yml',
            'up', '-d', '--force-recreate', '--remove-orphans'])
        numcts, cts = docker_actions.get_running_containers('testnet')

        self.assertIs(numcts, 1)
        self.assertIs(len(cts), 1)
        for ct_id, ct_info in cts.items():
            self.assertEqual(ct_info['ip'][:10], '192.168.23')
            self.assertEqual(ct_info['image'], 'edyan/php:7.2')

    def test_create_network(self):
        """
        Create a network then a container, attache one to the other
        And verify everything is OK

        """
        stop_remove_container('pytest')

        docker_actions.get_client().containers.run(
            'edyan/adminer:latest', detach=True, name='pytest')

        self.assertTrue(docker_actions.container_running('pytest'))
        self.assertFalse(docker_actions._container_in_network('pytest', 'pytest'))
        self.assertFalse(docker_actions.network_exists('nw_pytest'))

        network_created = docker_actions.create_network('nw_pytest')
        self.assertNotEqual(False, network_created)
        self.assertIs(str, type(network_created))

        self.assertFalse(docker_actions.create_network('nw_pytest'))
        self.assertTrue(docker_actions.add_container_to_network('pytest', 'nw_pytest'))
        self.assertFalse(docker_actions.add_container_to_network('pytest', 'nw_pytest'))
        self.assertTrue(docker_actions._container_in_network('pytest', 'nw_pytest'))

        stop_remove_container('pytest')
        remove_network('nw_pytest')

    def test_get_container_info_not_exists(self):
        self.assertIs(None, docker_actions._extract_container_info('not_exists', 'not_exists'))

    def test_guess_shell_sh(self):
        stop_remove_container('pytest')

        docker_actions.get_client().containers.run(
            'edyan/adminer:latest', detach=True, name='pytest')

        shell = docker_actions.guess_shell('pytest')
        self.assertEqual('/bin/sh', shell)

        stop_remove_container('pytest')

    def test_guess_shell_bash(self):
        stop_remove_container('pytest')

        docker_actions.get_client().containers.run(
            'edyan/php:7.2', detach=True, name='pytest')

        shell = docker_actions.guess_shell('pytest')
        self.assertEqual('/bin/bash', shell)

        stop_remove_container('pytest')

    def tearDownClass():
        stop_remove_container('pytest')
        stop_remove_container('static_maildev')
        stop_remove_container('static_php')
        stop_remove_container('static_portainer')
        remove_network('nw_pytest')
        remove_network('static_stakkr')


def exec_cmd(cmd: list):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.communicate()


def stop_remove_container(ct_name: str):
    try:
        ct = docker_actions.get_client().containers.get(ct_name)
        ct.stop()
        ct.remove()
    except NotFound:
        pass


def remove_network(network_name: str):
    try:
        network = docker_actions.get_client().networks.get(network_name)
        network.remove()
    except NotFound:
        pass


if __name__ == "__main__":
    unittest.main()
