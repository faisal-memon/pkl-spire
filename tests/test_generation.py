"""Exercise consumer overrides and reject configurations unsafe to deploy."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKL = os.environ.get('PKL', 'pkl')

class GenerationTests(unittest.TestCase):
    def evaluate(self, overrides='', expression=None):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            module = directory / 'consumer.pkl'
            module.write_text(f'amends "{ROOT}/examples/compose.pkl"\n' + overrides)
            command = [PKL, 'eval']
            if expression:
                command += ['-x', f'new JsonRenderer {{}}.renderDocument({expression})']
            else:
                command += ['-m', str(directory / 'out')]
            result = subprocess.run(command + [str(module)], capture_output=True, text=True)
            files = {p.name: p.read_text() for p in (directory / 'out').glob('*')}
            return result, files

    def test_bootstrap_is_explicit_and_keys_persist(self):
        result, files = self.evaluate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(files), {'server.conf', 'agent.conf', 'server.compose.yaml', 'agent.compose.yaml'})
        agent = json.loads(files['agent.conf'])
        server = json.loads(files['server.conf'])
        self.assertNotIn('insecure_bootstrap', agent['agent'])
        self.assertNotIn('join_token', agent['agent'])
        self.assertEqual(agent['agent']['join_token_file'], '/opt/spire/bootstrap/join-token')
        self.assertEqual(agent['agent']['trust_bundle_path'], '/opt/spire/bootstrap/bundle.pem')
        self.assertIn('disk', server['plugins']['KeyManager'])
        self.assertIn('disk', agent['plugins']['KeyManager'])

    def test_override_propagates_to_both_roles(self):
        result, files = self.evaluate('trustDomain = "test.example"\nserverPort = 9443\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        server = json.loads(files['server.conf'])['server']
        agent = json.loads(files['agent.conf'])['agent']
        self.assertEqual(server['trust_domain'], 'test.example')
        self.assertEqual(agent['trust_domain'], 'test.example')
        self.assertEqual(server['bind_port'], 9443)
        self.assertEqual(agent['server_port'], 9443)

    def test_server_uses_local_storage_and_published_port(self):
        result, _ = self.evaluate('hostRoot = "/srv/identity"\n', 'serverCompose')
        self.assertEqual(result.returncode, 0, result.stderr)
        service = json.loads(result.stdout)['services']['server']
        self.assertNotIn('deploy', service)
        self.assertEqual(service['volumes'][0]['source'], '/srv/identity/server')
        self.assertFalse(service['volumes'][0]['bind']['create_host_path'])
        self.assertEqual(service['ports'][0]['published'], 8081)
        self.assertEqual(service['restart'], 'unless-stopped')

    def test_agent_retains_host_access_and_local_storage(self):
        result, _ = self.evaluate(expression='agentCompose')
        self.assertEqual(result.returncode, 0, result.stderr)
        service = json.loads(result.stdout)['services']['agent']
        self.assertEqual(service['pid'], 'host')
        mounts = {v['target']: v for v in service['volumes']}
        self.assertIn('/var/run/docker.sock', mounts)
        self.assertTrue(mounts['/opt/spire/bootstrap']['read_only'])
        self.assertFalse(mounts['/opt/spire/data/agent']['bind']['create_host_path'])

    def test_bad_inputs_fail_generation(self):
        for override in ('serverPort = 0', 'serverPort = 65536', 'trustDomain = "spiffe://example.org"',
                         'hostRoot = "relative"', 'hostRoot = "/srv/$HOME"',
                         'version = "latest"'):
            with self.subTest(override=override):
                result, _ = self.evaluate(override)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('constraint', result.stderr.lower())

    def test_renderers_can_be_used_without_deployment(self):
        for role in ('Server', 'Agent'):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                module = Path(temporary) / 'config.pkl'
                address = '; serverAddress = "192.0.2.20"' if role == 'Agent' else ''
                module.write_text(f'amends "{ROOT}/src/render/{role}Config.pkl"\n'
                                  f'settings {{ trustDomain = "independent.example"{address} }}\n')
                result = subprocess.run([PKL, 'eval', str(module)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(result.stdout)
                self.assertEqual(config[role.lower()]['trust_domain'], 'independent.example')

    def test_release_version_matches_metadata_and_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = dict(os.environ, PKL_PACKAGE_VERSION='0.2.7')
            result = subprocess.run([PKL, 'project', 'package', str(ROOT),
                                     '--skip-publish-check', '--output-path', temporary],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata = json.loads((Path(temporary) / 'pkl-spire@0.2.7').read_text())
            self.assertEqual(metadata['version'], '0.2.7')
            self.assertTrue(metadata['packageUri'].endswith('/v0.2.7/pkl-spire@0.2.7'))
            self.assertTrue(metadata['packageZipUrl'].endswith('/v0.2.7/pkl-spire@0.2.7.zip'))
            self.assertEqual(len(list(Path(temporary).iterdir())), 4)
