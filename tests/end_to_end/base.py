#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import logging
import os
import signal
import subprocess
import tempfile
import time
import unittest

from click.testing import CliRunner
from testcontainers.redis import RedisContainer
from testcontainers.mysql import MySqlContainer
from testcontainers.opensearch import OpenSearchContainer
from testcontainers.core.waiting_utils import wait_for_logs

from grimoirelab_metrics.cli import grimoirelab_metrics

GRIMOIRELAB_URL = "http://localhost:8000"


class EndToEndTestCase(unittest.TestCase):
    """Base class to build end to end tests.

    This class contains all necessary to build end to end test cases
    for GrimoireLab metrics. It provides an OpenSearch server and a
    GrimoireLab 2.x server and workers, along with its required
    MariaDB and Redis databases.
    """

    @classmethod
    def setUpClass(cls):
        logging.getLogger().handlers = []
        cls.temp_file = tempfile.NamedTemporaryFile(delete=False)
        cls.runner = CliRunner()
        cls._start_redis_container(cls)
        cls._start_database_container(cls)
        cls._start_opensearch_container(cls)
        cls._start_grimoirelab(cls)
        cls._preload_repositories(cls)

    @classmethod
    def tearDownClass(cls):
        cls.grimoirelab_eventizers.terminate()
        cls.grimoirelab_archivists.terminate()
        time.sleep(20)
        cls.grimoirelab_server.send_signal(signal.SIGINT)
        cls.mysql_container.stop()
        cls.opensearch_container.stop()
        cls.redis_container.stop()

    def _start_database_container(self):
        self.mysql_container = MySqlContainer(image="mariadb:latest", root_password="root").with_exposed_ports(3306)
        self.mysql_container.start()

    def _start_redis_container(self):
        self.redis_container = RedisContainer().with_exposed_ports(6379)
        self.redis_container.start()

    def _start_opensearch_container(self):
        self.opensearch_container = OpenSearchContainer().with_exposed_ports(9200)
        self.opensearch_container.start()
        wait_for_logs(self.opensearch_container, ".*recovered .* indices into cluster_state.*")
        port = self.opensearch_container.get_exposed_port(9200)
        self.opensearch_url = f"http://admin:admin@localhost:{port}"

    def _start_grimoirelab(self):
        env = os.environ
        env["DJANGO_SETTINGS_MODULE"] = "grimoirelab.core.config.settings"
        env["GRIMOIRELAB_REDIS_PORT"] = self.redis_container.get_exposed_port(6379)
        env["GRIMOIRELAB_DB_PORT"] = self.mysql_container.get_exposed_port(3306)
        env["GRIMOIRELAB_DB_PASSWORD"] = self.mysql_container.root_password
        env["GRIMOIRELAB_ARCHIVIST_STORAGE_URL"] = self.opensearch_url
        env["GRIMOIRELAB_USER_PASSWORD"] = "admin"
        env["GRIMOIRELAB_ARCHIVIST_BLOCK_TIMEOUT"] = "1000"

        from grimoirelab.core.runner.cmd import grimoirelab

        self.runner.invoke(grimoirelab, "admin setup")
        subprocess.run(["grimoirelab", "admin", "create-user", "--username", "admin", "--no-interactive"])
        self.grimoirelab_server = subprocess.Popen(
            ["grimoirelab", "run", "server", "--dev"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.grimoirelab_eventizers = subprocess.Popen(
            ["grimoirelab", "run", "eventizers", "--workers", "10"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.grimoirelab_archivists = subprocess.Popen(
            ["grimoirelab", "run", "archivists", "--workers", "10"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(10)

    def _preload_repositories(self):
        self.runner.invoke(
            grimoirelab_metrics,
            [
                "./data/archived_repos.spdx.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--grimoirelab-user",
                "admin",
                "--grimoirelab-password",
                "admin",
                "--opensearch-url",
                self.opensearch_url,
                "--opensearch-index",
                "events",
                "--output",
                self.temp_file.name,
                "--from-date=2000-01-01",
            ],
        )
        time.sleep(20)
