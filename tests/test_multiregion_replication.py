#!/usr/bin/python

import json
import os
import paramiko
import unittest

from uuid import uuid4


class UploadError(Exception):
    pass


class DownloadError(Exception):
    pass


class TestMultiRegionReplication(unittest.TestCase):

    def setUp(self):
        """
            This test case reads in SSH credentials to swift nodes from
            swift_nodes_credentials.json. Please ensure this file exists
            in the test directory following the format

            {"hosts":
                [
                    {
                        "address":"127.0.0.1",
                        "username":"root",
                        "password":"secret"
                    },
                    {
                        "address":"127.0.0.2",
                        "username":"root",
                        "password":"secret2"
                    }
                ]
            }
        """
        self.connections = []
        with open('swift_nodes_credentials.json', 'r') as f:
            self.nodes = json.loads(f.read())

    def _get_connection(self, host, username, password):
        # Open an SSH connection using the user's SSH config file
        client = paramiko.SSHClient()
        client._policy = paramiko.WarningPolicy()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh_config = paramiko.SSHConfig()
        user_config_file = os.path.expanduser("~/.ssh/config")
        if os.path.exists(user_config_file):
            with open(user_config_file) as f:
                ssh_config.parse(f)

        cfg = {'hostname': host, 'username': username, 'password': password}

        user_config = ssh_config.lookup(cfg['hostname'])
        for k in ('hostname', 'username', 'port'):
            if k in user_config:
                cfg[k] = user_config[k]

        if 'proxycommand' in user_config:
            cfg['sock'] = paramiko.ProxyCommand(user_config['proxycommand'])
        while True:
            try:
                client.connect(**cfg)
                return client
            except paramiko.ssh_exception.AuthenticationException:
                print "Authentication failed when connecting to %s" % host
                raise

    def test_multiregion_replication(self):
        for n in self.nodes['hosts']:
            conn = self._get_connection(host=n['address'],
                                        username=n['username'],
                                        password=n['password'])
            self.connections.append(conn)

        for connection, i in\
                zip(self.connections, range(len(self.connections))):

            testfname = str(uuid4())
            testcname = str(uuid4())

            stdin, stdout, stderr = connection.exec_command(
                "dd if=/dev/urandom of=./%s.dat bs=512 count=2048" % testfname)
            stdin, stdout, stderr = connection.exec_command(
                "md5sum %s.dat" % testfname)
            md5_in = stdout.read()

            stdin, stdout, stderr = connection.exec_command(
                "swift -A http://%s:8080/auth/v1.0 -U admin:admin\
                -K admin upload %s %s.dat" %
                (self.nodes['hosts'][i]['address'], testcname, testfname))
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == -1:
                raise UploadError("Upload failed")

            for c, j in\
                    zip(self.connections, range(len(self.connections))):
                if j == i:
                    continue

                stdin, stdout, stderr = c.exec_command(
                    "swift -A http://%s:8080/auth/v1.0 -U admin:admin\
                    -K admin download %s %s.dat" %
                    (self.nodes['hosts'][i]['address'], testcname, testfname)
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == -1:
                    raise DownloadError("Download failed")

                stdin, stdout, stderr = c.exec_command(
                    "md5sum %s.dat" % testfname)
                md5_out = stdout.read()

                self.assertTrue(md5_in == md5_out)

    def tearDown(self):
        for conn in self.connections:
            stdin, stdout, stderr = conn.exec_command(
                "rm -f *.dat")
            conn.close()


if __name__ == "__main__":
    unittest.main()
