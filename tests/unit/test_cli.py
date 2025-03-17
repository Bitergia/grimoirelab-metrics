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

import datetime
import json
import logging
import os
import tempfile
import unittest

import httpretty
import requests

from unittest.mock import patch

from click.testing import CliRunner
from grimoirelab_metrics.cli import grimoirelab_metrics, get_repository


GRIMOIRELAB_URL = "http://localhost:8000"
OPENSEARCH_URL = "https://admin:admin@localhost:9200"
OPENSEARCH_INDEX = "events"

TASK_URL = f"{GRIMOIRELAB_URL}/datasources/add_repository"
REPOSITORIES_URL = f"{GRIMOIRELAB_URL}/datasources/repositories/"


def setup_add_repository_mock_server():
    """Set up a mock HTTP server for API calls"""

    http_requests = []

    def request_callback(request, uri, headers):
        last_request = httpretty.last_request()
        http_requests.append(last_request)
        data = {"message": "Task scheduled correctly"}
        body = json.dumps(data)

        return (200, headers, body)

    def exception_callback(request, uri, headers):
        last_request = httpretty.last_request()
        http_requests.append(last_request)

        raise requests.ConnectionError()

    httpretty.register_uri(httpretty.POST, TASK_URL, responses=[httpretty.Response(body=request_callback)])
    httpretty.register_uri(
        httpretty.POST,
        "http://localhost:8001/datasources/add_repository",
        responses=[httpretty.Response(body=exception_callback)],
    )

    return http_requests


def setup_get_repositories_mock_server():
    """Setup a mock HTTP server for repository API calls"""

    http_requests = []

    def request_callback(request, uri, headers):
        last_request = httpretty.last_request()
        http_requests.append(last_request)
        data = {
            "results": [
                {
                    "task": {
                        "last_run": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                        "status": "completed",
                    }
                }
            ]
        }
        body = json.dumps(data)

        return 200, headers, body

    httpretty.register_uri(httpretty.GET, REPOSITORIES_URL, responses=[httpretty.Response(body=request_callback)])

    return http_requests


def setup_get_never_ending_repositories_mock_server():
    """Setup a mock HTTP server for repository API calls"""

    http_requests = []

    def request_callback(request, uri, headers):
        last_request = httpretty.last_request()
        http_requests.append(last_request)
        last_run = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=365)
        data = {
            "results": [
                {
                    "task": {
                        "last_run": last_run.isoformat(),
                        "status": "running",
                    }
                }
            ]
        }
        body = json.dumps(data)

        return 200, headers, body

    httpretty.register_uri(httpretty.GET, REPOSITORIES_URL, responses=[httpretty.Response(body=request_callback)])

    return http_requests


class TestCli(unittest.TestCase):
    def setUp(self):
        logging.getLogger().handlers = []
        # temporary file for output metrics
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)

    def tearDown(self):
        os.remove(self.temp_file.name)

    @httpretty.activate
    @patch("grimoirelab_metrics.cli.get_repository_metrics")
    def test_valid_file(self, mock_get_repository_metrics):
        """Check if it schedules tasks to analyze all git repositories from a valid file"""

        http_requests = setup_add_repository_mock_server()
        http_requests_repos = setup_get_repositories_mock_server()
        mock_get_repository_metrics.return_value = {"metrics": {"num_commits": 10}}

        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/valid.spdx.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Found 5 git repositories", result.output)
        self.assertIn("Scheduling tasks", result.output)
        self.assertNotIn("Scheduling task to fetch commits", result.output)
        self.assertEqual(len(http_requests), 5)
        self.assertEqual(len(http_requests_repos), 5)

        expected_packages = [
            "SPDXRef-bootstrap-gnu-config.bst-0",
            "SPDXRef-public-linux-headers.bst-6.10.2",
            "SPDXRef-bootstrap-glibc.bst-2.40",
            "SPDXRef-bootstrap-attr.bst-2.5.2",
            "SPDXRef-bootstrap-acl.bst-2.3.2",
        ]
        with open(self.temp_file.name) as f:
            metrics = json.load(f)
            self.assertEqual(len(metrics["packages"]), 5)
            i = 0
            for package, data in metrics["packages"].items():
                self.assertEqual(package, expected_packages[i])
                self.assertEqual(data["metrics"]["num_commits"], 10)
                i += 1

    @httpretty.activate
    @patch("grimoirelab_metrics.cli.get_repository_metrics")
    def test_verbose(self, mock_get_repository_metrics):
        """Check if it logs all information when using '--verbose'"""

        http_requests = setup_add_repository_mock_server()
        http_requests_repos = setup_get_repositories_mock_server()
        mock_get_repository_metrics.return_value = {"metrics": {"num_commits": 10}}

        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/valid.spdx.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
                "--verbose",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Found 5 git repositories", result.output)
        self.assertIn("Scheduling tasks", result.output)
        self.assertIn("Scheduling task to fetch commits", result.output)
        self.assertEqual(len(http_requests), 5)
        self.assertEqual(len(http_requests_repos), 5)

    @httpretty.activate
    def test_invalid_file_type(self):
        """Check if it returns an error when the file type is not valid"""

        http_requests = setup_add_repository_mock_server()
        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "invalid.doc",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unsupported SPDX file type", result.output)
        self.assertEqual(len(http_requests), 0)

    @httpretty.activate
    def test_invalid_sbom_format(self):
        """Check if it returns an error when the SBoM is not formatted correctly"""

        http_requests = setup_add_repository_mock_server()
        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/invalid_format.spdx.json",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error while parsing document", result.output)
        self.assertEqual(len(http_requests), 0)

    @httpretty.activate
    @patch("grimoirelab_metrics.cli.get_repository_metrics")
    def test_no_repository(self, mock_get_repository_metrics):
        """Check if it returns a warning when a package does not provide a git repository"""

        http_requests = setup_add_repository_mock_server()
        http_requests_repos = setup_get_repositories_mock_server()
        mock_get_repository_metrics.return_value = {"metrics": {"num_commits": 10}}

        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/missing_repo.spdx.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Could not find a git repository for SPDXRef-bootstrap-gnu-config.bst-0 (bootstrap/gnu-config.bst)",
            result.output,
        )
        self.assertEqual(len(http_requests), 4)

    @httpretty.activate
    @patch("grimoirelab_metrics.cli.get_repository_metrics")
    def test_invalid_git_repository(self, mock_get_repository_metrics):
        """Check if it returns a warning when a package URI is not a valid git repository"""

        http_requests = setup_add_repository_mock_server()
        http_requests_repos = setup_get_repositories_mock_server()
        mock_get_repository_metrics.return_value = {"metrics": {"num_commits": 10}}

        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/invalid_repo.spdx.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Could not find a git repository for SPDXRef-ncurses-6.40 (bootstrap/ncurses.bst)", result.output)
        self.assertEqual(len(http_requests), 4)
        self.assertEqual(len(http_requests_repos), 4)

    @httpretty.activate
    def test_no_file(self):
        """Check if it returns an error when the file does not exist"""

        http_requests = setup_add_repository_mock_server()
        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/no_file.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("No such file or directory", result.output)
        self.assertEqual(len(http_requests), 0)

    @httpretty.activate
    def test_server_error(self):
        """Check if it returns a warning when there is a server error"""

        http_requests = setup_add_repository_mock_server()
        runner = CliRunner()
        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/valid.spdx.xml",
                "--grimoirelab-url",
                "http://localhost:8001",
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
            ],
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error scheduling task", result.output)
        self.assertEqual(len(http_requests), 5)

    @httpretty.activate
    @patch("grimoirelab_metrics.cli.get_repository_metrics")
    def test_never_ending_repository(self, mock_get_repository_metrics):
        """Check if it returns a warning when a repository task never ends"""

        http_requests = setup_add_repository_mock_server()
        http_requests_repos = setup_get_never_ending_repositories_mock_server()
        mock_get_repository_metrics.return_value = {"metrics": {"num_commits": 10}}

        runner = CliRunner()

        result = runner.invoke(
            grimoirelab_metrics,
            [
                "./data/valid.spdx.xml",
                "--grimoirelab-url",
                GRIMOIRELAB_URL,
                "--opensearch-url",
                OPENSEARCH_URL,
                "--opensearch-index",
                OPENSEARCH_INDEX,
                "--output",
                self.temp_file.name,
                "--repository-timeout",
                15,
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Timeout waiting for repository https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux to be ready",
            result.output,
        )
        self.assertEqual(len(http_requests), 5)
        self.assertEqual(len(http_requests_repos), 10)


class TestGetRepository(unittest.TestCase):
    def test_valid_git_repository(self):
        valid_git_uris = [
            "https://git.myproject.org/MyProject.git",
            "http://git.myproject.org/MyProject.git",
            "git+https://git.myproject.org/MyProject.git",
            "git+http://git.myproject.org/MyProject.git",
            "git+https://git.myproject.org/MyProject.git@v1.0",
            "git://git.myproject.org/MyProject.git",
            "git://git.myproject.org/MyProject.git@master",
            "git+git://git.myproject.org/MyProject.git",
        ]

        for uri in valid_git_uris:
            with self.subTest(uri=uri):
                result = get_repository(uri)
                self.assertEqual(result, "https://git.myproject.org/MyProject")

    def test_invalid_git_repository(self):
        invalid_git_uris = [
            "http://git.myproject.org/MyProject",
            "git+https://git.myproject.org/MyProject",
            "svn+svn://svn.myproject.org/svn/MyProject",
            "https://git.myproject.org/MyProject/file.py",
        ]

        for uri in invalid_git_uris:
            with self.subTest(uri=uri):
                result = get_repository(uri)
                self.assertEqual(result, None)


if __name__ == "__main__":
    unittest.main()
