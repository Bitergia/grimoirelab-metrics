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

import json
import logging
import unittest

from grimoirelab_metrics.cli import grimoirelab_metrics
from end_to_end.base import EndToEndTestCase

GRIMOIRELAB_URL = "http://localhost:8000"


class TestMetrics(EndToEndTestCase):
    """End to end tests for grimoirelab metrics CLI"""

    def test_metrics(self):
        """Check whether the metrics are correctly calculated"""

        with self.assertLogs(logging.getLogger()) as logger:
            result = self.runner.invoke(
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
                    "--to-date=2025-01-01",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            # Check logs
            self.assertIn("INFO:root:Parsing file ./data/archived_repos.spdx.xml", logger.output)
            self.assertIn("INFO:root:Found 2 git repositories", logger.output)
            self.assertIn("INFO:root:Scheduling tasks", logger.output)
            self.assertIn("INFO:root:Generating metrics", logger.output)

            # Check metrics
            with open(self.temp_file.name) as f:
                metrics = json.load(f)
                self.assertEqual(len(metrics["packages"]), 2)

                self.assertIn("SPDXRef-angular", metrics["packages"])
                self.assertEqual(metrics["packages"]["SPDXRef-angular"]["repository"], "https://github.com/angular/quickstart")
                quickstart_metrics = metrics["packages"]["SPDXRef-angular"]["metrics"]
                self.assertEqual(quickstart_metrics["total_commits"], 164)
                self.assertEqual(quickstart_metrics["total_contributors"], 25)
                self.assertEqual(quickstart_metrics["pony_factor"], 2)
                self.assertEqual(quickstart_metrics["elephant_factor"], 2)
                self.assertEqual(quickstart_metrics["file_types_other"], 683)
                self.assertEqual(quickstart_metrics["file_types_binary"], 0)
                self.assertEqual(quickstart_metrics["file_types_code"], 479)
                self.assertEqual(quickstart_metrics["commit_size_added_lines"], 53121)
                self.assertEqual(quickstart_metrics["commit_size_removed_lines"], 51852)
                self.assertEqual(quickstart_metrics["message_size_total"], 9778)
                self.assertAlmostEqual(quickstart_metrics["message_size_mean"], 59.6219, delta=0.1)
                self.assertEqual(quickstart_metrics["message_size_median"], 46)
                self.assertEqual(quickstart_metrics["developer_categories_core"], 3)
                self.assertEqual(quickstart_metrics["developer_categories_regular"], 13)
                self.assertEqual(quickstart_metrics["developer_categories_casual"], 9)
                # From 2000 to 2025 there are 9132 days
                self.assertAlmostEqual(quickstart_metrics["commits_per_week"], 164 / (9132 / 7), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_month"], 164 / (9132 / 30), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_year"], 164 / (9132 / 365), delta=0.1)

                self.assertIn("SPDXRef-angular-seed", metrics["packages"])
                self.assertEqual(
                    metrics["packages"]["SPDXRef-angular-seed"]["repository"], "https://github.com/angular/angular-seed"
                )
                angular_metrics = metrics["packages"]["SPDXRef-angular-seed"]["metrics"]
                self.assertEqual(angular_metrics["total_commits"], 207)
                self.assertEqual(angular_metrics["total_contributors"], 58)
                self.assertEqual(angular_metrics["pony_factor"], 5)
                self.assertEqual(angular_metrics["elephant_factor"], 2)
                self.assertEqual(angular_metrics["file_types_other"], 534)
                self.assertEqual(angular_metrics["file_types_binary"], 4)
                self.assertEqual(angular_metrics["file_types_code"], 2129)
                self.assertEqual(angular_metrics["commit_size_added_lines"], 218483)
                self.assertEqual(angular_metrics["commit_size_removed_lines"], 245784)
                self.assertEqual(angular_metrics["message_size_total"], 15488)
                self.assertAlmostEqual(angular_metrics["message_size_mean"], 74.8212, delta=0.1)
                self.assertEqual(angular_metrics["message_size_median"], 45)
                self.assertEqual(angular_metrics["developer_categories_core"], 16)
                self.assertEqual(angular_metrics["developer_categories_regular"], 31)
                self.assertEqual(angular_metrics["developer_categories_casual"], 11)
                # From 2000 to 2025 there are 9132 days
                self.assertAlmostEqual(angular_metrics["commits_per_week"], 207 / (9132 / 7), delta=0.1)
                self.assertAlmostEqual(angular_metrics["commits_per_month"], 207 / (9132 / 30), delta=0.1)
                self.assertAlmostEqual(angular_metrics["commits_per_year"], 207 / (9132 / 365), delta=0.1)

    def test_from_date(self):
        """Check if it returns the number of commits of one repository from a particular date"""

        with self.assertLogs(logging.getLogger()) as logger:
            result = self.runner.invoke(
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
                    "--from-date=2017-01-01",
                    "--to-date=2025-01-01",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            # Check logs
            self.assertIn("INFO:root:Parsing file ./data/archived_repos.spdx.xml", logger.output)
            self.assertIn("INFO:root:Found 2 git repositories", logger.output)
            self.assertIn("INFO:root:Scheduling tasks", logger.output)
            self.assertIn("INFO:root:Generating metrics", logger.output)

            # Check metrics
            with open(self.temp_file.name) as f:
                metrics = json.load(f)
                self.assertEqual(len(metrics["packages"]), 2)

                self.assertIn("SPDXRef-angular", metrics["packages"])
                self.assertEqual(metrics["packages"]["SPDXRef-angular"]["repository"], "https://github.com/angular/quickstart")
                quickstart_metrics = metrics["packages"]["SPDXRef-angular"]["metrics"]
                self.assertEqual(quickstart_metrics["total_commits"], 22)
                self.assertEqual(quickstart_metrics["total_contributors"], 8)
                self.assertEqual(quickstart_metrics["pony_factor"], 2)
                self.assertEqual(quickstart_metrics["elephant_factor"], 1)
                self.assertEqual(quickstart_metrics["file_types_other"], 37)
                self.assertEqual(quickstart_metrics["file_types_binary"], 0)
                self.assertEqual(quickstart_metrics["file_types_code"], 17)
                self.assertEqual(quickstart_metrics["commit_size_added_lines"], 269)
                self.assertEqual(quickstart_metrics["commit_size_removed_lines"], 103)
                self.assertEqual(quickstart_metrics["message_size_total"], 1866)
                self.assertAlmostEqual(quickstart_metrics["message_size_mean"], 84.8181, delta=0.1)
                self.assertEqual(quickstart_metrics["message_size_median"], 57)
                self.assertEqual(quickstart_metrics["developer_categories_core"], 3)
                self.assertEqual(quickstart_metrics["developer_categories_regular"], 3)
                self.assertEqual(quickstart_metrics["developer_categories_casual"], 2)
                # From 2017 to 2025 there are 2922 days
                self.assertAlmostEqual(quickstart_metrics["commits_per_week"], 22 / (2922 / 7), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_month"], 22 / (2922 / 30), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_year"], 22 / (2922 / 365), delta=0.1)

                self.assertIn("SPDXRef-angular-seed", metrics["packages"])
                self.assertEqual(
                    metrics["packages"]["SPDXRef-angular-seed"]["repository"], "https://github.com/angular/angular-seed"
                )
                angular_metrics = metrics["packages"]["SPDXRef-angular-seed"]["metrics"]
                self.assertEqual(angular_metrics["total_commits"], 11)
                self.assertEqual(angular_metrics["total_contributors"], 4)
                self.assertEqual(angular_metrics["pony_factor"], 1)
                self.assertEqual(angular_metrics["elephant_factor"], 1)
                self.assertEqual(angular_metrics["file_types_other"], 24)
                self.assertEqual(angular_metrics["file_types_binary"], 0)
                self.assertEqual(angular_metrics["file_types_code"], 13)
                self.assertEqual(angular_metrics["commit_size_added_lines"], 4849)
                self.assertEqual(angular_metrics["commit_size_removed_lines"], 149)
                self.assertEqual(angular_metrics["message_size_total"], 911)
                self.assertAlmostEqual(angular_metrics["message_size_mean"], 82.8181, delta=0.1)
                self.assertEqual(angular_metrics["message_size_median"], 56)
                self.assertEqual(angular_metrics["developer_categories_core"], 1)
                self.assertEqual(angular_metrics["developer_categories_regular"], 2)
                self.assertEqual(angular_metrics["developer_categories_casual"], 1)
                # From 2017 to 2025 there are 2922 days
                self.assertAlmostEqual(angular_metrics["commits_per_week"], 11 / (2922 / 7), delta=0.1)
                self.assertAlmostEqual(angular_metrics["commits_per_month"], 11 / (2922 / 30), delta=0.1)
                self.assertAlmostEqual(angular_metrics["commits_per_year"], 11 / (2922 / 365), delta=0.1)

    def test_to_date(self):
        """Check if it returns the number of commits of one repository up to a particular date"""

        with self.assertLogs(logging.getLogger()) as logger:
            result = self.runner.invoke(
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
                    "--to-date=2017-01-01",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            # Check logs
            self.assertIn("INFO:root:Parsing file ./data/archived_repos.spdx.xml", logger.output)
            self.assertIn("INFO:root:Found 2 git repositories", logger.output)
            self.assertIn("INFO:root:Scheduling tasks", logger.output)
            self.assertIn("INFO:root:Generating metrics", logger.output)

            # Check metrics
            with open(self.temp_file.name) as f:
                metrics = json.load(f)
                self.assertEqual(len(metrics["packages"]), 2)

                self.assertIn("SPDXRef-angular", metrics["packages"])
                self.assertEqual(metrics["packages"]["SPDXRef-angular"]["repository"], "https://github.com/angular/quickstart")
                quickstart_metrics = metrics["packages"]["SPDXRef-angular"]["metrics"]
                self.assertEqual(quickstart_metrics["total_commits"], 142)
                self.assertEqual(quickstart_metrics["total_contributors"], 20)
                self.assertEqual(quickstart_metrics["pony_factor"], 2)
                self.assertEqual(quickstart_metrics["elephant_factor"], 2)
                self.assertEqual(quickstart_metrics["file_types_other"], 646)
                self.assertEqual(quickstart_metrics["file_types_binary"], 0)
                self.assertEqual(quickstart_metrics["file_types_code"], 462)
                self.assertEqual(quickstart_metrics["commit_size_added_lines"], 52852)
                self.assertEqual(quickstart_metrics["commit_size_removed_lines"], 51749)
                self.assertEqual(quickstart_metrics["message_size_total"], 7912)
                self.assertAlmostEqual(quickstart_metrics["message_size_mean"], 55.71830985915493, delta=0.1)
                self.assertEqual(quickstart_metrics["message_size_median"], 44)
                self.assertEqual(quickstart_metrics["developer_categories_core"], 3)
                self.assertEqual(quickstart_metrics["developer_categories_regular"], 9)
                self.assertEqual(quickstart_metrics["developer_categories_casual"], 8)
                # From 2000 to 2017 there are 6210 days
                self.assertAlmostEqual(quickstart_metrics["commits_per_week"], 142 / (6210 / 7), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_month"], 142 / (6210 / 30), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_year"], 142 / (6210 / 365), delta=0.1)

                self.assertIn("SPDXRef-angular-seed", metrics["packages"])
                self.assertEqual(
                    metrics["packages"]["SPDXRef-angular-seed"]["repository"], "https://github.com/angular/angular-seed"
                )
                angular_metrics = metrics["packages"]["SPDXRef-angular-seed"]["metrics"]
                self.assertEqual(angular_metrics["total_commits"], 196)
                self.assertEqual(angular_metrics["total_contributors"], 56)
                self.assertEqual(angular_metrics["pony_factor"], 5)
                self.assertEqual(angular_metrics["elephant_factor"], 2)
                self.assertEqual(angular_metrics["file_types_other"], 510)
                self.assertEqual(angular_metrics["file_types_binary"], 4)
                self.assertEqual(angular_metrics["file_types_code"], 2116)
                self.assertEqual(angular_metrics["commit_size_added_lines"], 213634)
                self.assertEqual(angular_metrics["commit_size_removed_lines"], 245635)
                self.assertEqual(angular_metrics["message_size_total"], 14577)
                self.assertAlmostEqual(angular_metrics["message_size_mean"], 74.37244897959184, delta=0.1)
                self.assertEqual(angular_metrics["message_size_median"], 45)
                self.assertEqual(angular_metrics["developer_categories_core"], 16)
                self.assertEqual(angular_metrics["developer_categories_regular"], 30)
                self.assertEqual(angular_metrics["developer_categories_casual"], 10)
                # From 2000 to 2017 there are 6210 days
                self.assertAlmostEqual(angular_metrics["commits_per_week"], 196 / (6210 / 7), delta=0.1)
                self.assertAlmostEqual(angular_metrics["commits_per_month"], 196 / (6210 / 30), delta=0.1)
                self.assertAlmostEqual(angular_metrics["commits_per_year"], 196 / (6210 / 365), delta=0.1)

    def test_duplicate_repo(self):
        """Check if it ignores duplicated URLs"""

        with self.assertLogs(logging.getLogger()) as logger:
            result = self.runner.invoke(
                grimoirelab_metrics,
                [
                    "./data/duplicate_repo.spdx.xml",
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
                    "--to-date=2025-01-01",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            # Check logs
            self.assertIn("INFO:root:Parsing file ./data/duplicate_repo.spdx.xml", logger.output)
            self.assertIn("INFO:root:Found 1 git repositories", logger.output)
            self.assertIn("INFO:root:Scheduling tasks", logger.output)
            self.assertIn("INFO:root:Generating metrics", logger.output)

            # Check metrics
            with open(self.temp_file.name) as f:
                metrics = json.load(f)
                self.assertEqual(len(metrics["packages"]), 2)
                self.assertIn("SPDXRef-angular", metrics["packages"])
                self.assertIn("SPDXRef-angular-2", metrics["packages"])
                self.assertEqual(metrics["packages"]["SPDXRef-angular"]["repository"], "https://github.com/angular/quickstart")
                self.assertEqual(metrics["packages"]["SPDXRef-angular-2"]["repository"], "https://github.com/angular/quickstart")
                quickstart_metrics = metrics["packages"]["SPDXRef-angular"]["metrics"]
                self.assertEqual(quickstart_metrics["total_commits"], 164)
                self.assertEqual(quickstart_metrics["total_contributors"], 25)
                self.assertEqual(quickstart_metrics["pony_factor"], 2)
                self.assertEqual(quickstart_metrics["elephant_factor"], 2)
                self.assertEqual(quickstart_metrics["file_types_other"], 683)
                self.assertEqual(quickstart_metrics["file_types_binary"], 0)
                self.assertEqual(quickstart_metrics["file_types_code"], 479)
                self.assertEqual(quickstart_metrics["commit_size_added_lines"], 53121)
                self.assertEqual(quickstart_metrics["commit_size_removed_lines"], 51852)
                self.assertEqual(quickstart_metrics["message_size_total"], 9778)
                self.assertAlmostEqual(quickstart_metrics["message_size_mean"], 59.6219, delta=0.1)
                self.assertEqual(quickstart_metrics["message_size_median"], 46)
                self.assertEqual(quickstart_metrics["developer_categories_core"], 3)
                self.assertEqual(quickstart_metrics["developer_categories_regular"], 13)
                self.assertEqual(quickstart_metrics["developer_categories_casual"], 9)
                # From 2000 to 2025 there are 9132 days
                self.assertAlmostEqual(quickstart_metrics["commits_per_week"], 164 / (9132 / 7), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_month"], 164 / (9132 / 30), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_year"], 164 / (9132 / 365), delta=0.1)

    def test_non_git_repo(self):
        """Check if it flags non-git dependencies"""

        with self.assertLogs(logging.getLogger()) as logger:
            result = self.runner.invoke(
                grimoirelab_metrics,
                [
                    "./data/mercurial_repo.spdx.xml",
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
                    "--to-date=2025-01-01",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            # Check logs
            self.assertIn("INFO:root:Parsing file ./data/mercurial_repo.spdx.xml", logger.output)
            self.assertIn("WARNING:root:Could not find a git repository for SPDXRef-sql-dk (sql-dk)", logger.output)
            self.assertIn("INFO:root:Found 1 git repositories", logger.output)
            self.assertIn("INFO:root:Scheduling tasks", logger.output)
            self.assertIn("INFO:root:Generating metrics", logger.output)

            # Check metrics
            with open(self.temp_file.name) as f:
                metrics = json.load(f)
                self.assertEqual(len(metrics["packages"]), 2)

                self.assertIn("SPDXRef-angular", metrics["packages"])
                self.assertEqual(metrics["packages"]["SPDXRef-angular"]["repository"], "https://github.com/angular/quickstart")
                quickstart_metrics = metrics["packages"]["SPDXRef-angular"]["metrics"]
                self.assertEqual(quickstart_metrics["total_commits"], 164)
                self.assertEqual(quickstart_metrics["total_contributors"], 25)
                self.assertEqual(quickstart_metrics["pony_factor"], 2)
                self.assertEqual(quickstart_metrics["elephant_factor"], 2)
                self.assertEqual(quickstart_metrics["file_types_other"], 683)
                self.assertEqual(quickstart_metrics["file_types_binary"], 0)
                self.assertEqual(quickstart_metrics["file_types_code"], 479)
                self.assertEqual(quickstart_metrics["commit_size_added_lines"], 53121)
                self.assertEqual(quickstart_metrics["commit_size_removed_lines"], 51852)
                self.assertEqual(quickstart_metrics["message_size_total"], 9778)
                self.assertAlmostEqual(quickstart_metrics["message_size_mean"], 59.6219, delta=0.1)
                self.assertEqual(quickstart_metrics["message_size_median"], 46)
                self.assertEqual(quickstart_metrics["developer_categories_core"], 3)
                self.assertEqual(quickstart_metrics["developer_categories_regular"], 13)
                self.assertEqual(quickstart_metrics["developer_categories_casual"], 9)
                # From 2000 to 2025 there are 9132 days
                self.assertAlmostEqual(quickstart_metrics["commits_per_week"], 164 / (9132 / 7), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_month"], 164 / (9132 / 30), delta=0.1)
                self.assertAlmostEqual(quickstart_metrics["commits_per_year"], 164 / (9132 / 365), delta=0.1)

                self.assertIn("SPDXRef-sql-dk", metrics["packages"])
                self.assertEqual(metrics["packages"]["SPDXRef-sql-dk"]["metrics"], None)


if __name__ == "__main__":
    unittest.main()
