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
import unittest

from grimoirelab_metrics.metrics import GitEventsAnalyzer


def read_file(filename):
    with open(filename) as f:
        return f.read()


class TestGitEventsAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = GitEventsAnalyzer()
        self.events = json.loads(read_file("data/events.json"))
        self.file_events = json.loads(read_file("data/file_events.json"))

    def test_commit_count(self):
        """Test that the commit count is calculated correctly"""

        self.analyzer.process_events(self.events)
        self.assertEqual(self.analyzer.get_commit_count(), 9)

    def test_contributor_count(self):
        """Test that the contributor count is calculated correctly"""

        self.analyzer.process_events(self.events)
        self.assertEqual(self.analyzer.get_contributor_count(), 3)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            }
        ]
        self.analyzer.process_events(extra_events)
        self.assertEqual(self.analyzer.get_contributor_count(), 4)

    def test_organization_count(self):
        """Test that the organization count is calculated correctly"""

        self.analyzer.process_events(self.events)
        self.assertEqual(self.analyzer.get_organization_count(), 2)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example3.com>", "message": "Another commit"},
            }
        ]
        self.analyzer.process_events(extra_events)
        self.assertEqual(self.analyzer.get_organization_count(), 3)

    def test_get_pony_factor(self):
        """Test the computation of the pony factor is correct"""

        self.assertEqual(self.analyzer.get_pony_factor(), 0)

        self.analyzer.process_events(self.events)
        self.assertEqual(self.analyzer.get_pony_factor(), 1)

        # Include commits from another author to increase the pony factor
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
        ]
        self.analyzer.process_events(extra_events)
        self.assertEqual(self.analyzer.get_pony_factor(), 2)

    def test_get_pony_factor_custom_threshold(self):
        """Test the computation of the pony factor is correct with a custom threshold"""

        analyzer = GitEventsAnalyzer(pony_threshold=0.8)
        analyzer.process_events(self.events)

        self.assertEqual(analyzer.get_pony_factor(), 2)

    def test_get_elephant_factor(self):
        """Test the computation of the elephant factor is correct"""

        self.assertEqual(self.analyzer.get_elephant_factor(), 0)

        self.analyzer.process_events(self.events)
        self.assertEqual(self.analyzer.get_elephant_factor(), 1)

        # Include commits from another company to increase the elephant factor.
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example2.com>", "message": "Another commit"},
            },
        ]
        self.analyzer.process_events(extra_events)
        self.assertEqual(self.analyzer.get_elephant_factor(), 2)

    def test_get_elephant_factor_custom_threshold(self):
        """Test the computation of the elephant factor is correct with a custom threshold"""

        analyzer = GitEventsAnalyzer(elephant_threshold=0.8)
        analyzer.process_events(self.events)

        self.assertEqual(analyzer.get_elephant_factor(), 2)

    def test_file_type_metrics(self):
        """Test that file type metrics are calculated correctly"""

        self.analyzer.process_events(self.events)

        file_metrics = self.analyzer.get_file_type_metrics()
        self.assertEqual(file_metrics["code"], 54)
        self.assertEqual(file_metrics["binary"], 1)
        self.assertEqual(file_metrics["other"], 24)

    def test_file_type_metrics_empty(self):
        """Test that file type metrics are calculated correctly without events"""

        file_metrics = self.analyzer.get_file_type_metrics()
        self.assertEqual(file_metrics["code"], 0)
        self.assertEqual(file_metrics["binary"], 0)
        self.assertEqual(file_metrics["other"], 0)

    def test_file_type_metrics_new_regex(self):
        """Test that file type metrics are calculated correctly with new regex"""

        analyzer = GitEventsAnalyzer(code_file_pattern=r"\.py$", binary_file_pattern=r"\.md$")

        analyzer.process_events(self.events)

        file_metrics = analyzer.get_file_type_metrics()
        self.assertEqual(file_metrics["code"], 53)
        self.assertEqual(file_metrics["binary"], 4)
        self.assertEqual(file_metrics["other"], 22)

    def test_commit_size_metrics(self):
        """Test that commit size metrics are calculated correctly"""

        self.assertEqual(self.analyzer.get_commit_size_metrics(), {"added_lines": 0, "removed_lines": 0})

        self.analyzer.process_events(self.events)

        commit_size = self.analyzer.get_commit_size_metrics()
        self.assertEqual(commit_size["added_lines"], 5352)
        self.assertEqual(commit_size["removed_lines"], 562)

    def test_message_size_metrics(self):
        """Test that message size metrics are calculated correctly"""

        self.analyzer.process_events(self.events)

        metrics = self.analyzer.get_message_size_metrics()
        self.assertEqual(metrics["total"], 1891)
        self.assertAlmostEqual(metrics["mean"], 210.11, delta=0.1)
        self.assertEqual(metrics["median"], 229)

    def test_get_commits_frequency(self):
        """Test whether the average (mean) commits per week is calculated correctly"""

        self.analyzer.process_events(self.events)
        metrics = self.analyzer.get_commit_frequency_metrics(days_interval=30)
        self.assertAlmostEqual(metrics["week"], 9 / (30 / 7), delta=0.1)
        self.assertAlmostEqual(metrics["month"], 9, delta=0.1)
        self.assertIsNone(metrics["year"])

    def test_get_all_commits_frequency(self):
        """Test whether the average (mean) commits per week and year is calculated correctly"""

        self.analyzer.process_events(self.events)
        metrics = self.analyzer.get_commit_frequency_metrics(days_interval=365)
        self.assertAlmostEqual(metrics["week"], 9 / (365 / 7), delta=0.1)
        self.assertAlmostEqual(metrics["month"], 9 / (365 / 30), delta=0.1)
        self.assertAlmostEqual(metrics["year"], 9, delta=0.1)

    def test_get_developer_categories(self):
        """Test if the developer categories are calculated correctly"""

        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 0, "regular": 0, "casual": 0})

        self.analyzer.process_events(self.events)
        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 1, "regular": 1, "casual": 1})

        # Add a core developer to change the categories
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
        ]

        self.analyzer.process_events(extra_events)
        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 2, "regular": 1, "casual": 1})

    def test_get_categories_one_developer(self):
        """Test if the categories are calculated correctly when there is only one developer"""

        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 0, "regular": 0, "casual": 0})

        # Add a core developer with 100% of the contributions
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
        ]

        self.analyzer.process_events(extra_events)
        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 1, "regular": 0, "casual": 0})

    def test_get_developer_categories_tied(self):
        """Test if the categories are calculated correctly when the core developers have the same contributions"""

        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 0, "regular": 0, "casual": 0})

        # Add core developers with the same number of contributions
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 1 <author1@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 2 <author2@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 3 <author3@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 4 <author4@example_new.com>", "message": "Another commit"},
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {"Author": "Author 5 <author5@example_new.com>", "message": "Another commit"},
            },
        ]

        self.analyzer.process_events(extra_events)
        categories = self.analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 4, "regular": 1, "casual": 0})

    def test_get_developer_categories_custom_threshold(self):
        """Test if the categories are calculated correctly with a custom threshold"""

        analyzer = GitEventsAnalyzer(dev_categories_thresholds=(0.5, 0.9))
        analyzer.process_events(self.events)

        categories = analyzer.get_developer_categories()
        self.assertDictEqual(categories, {"core": 1, "regular": 1, "casual": 1})

        analyzer_2 = GitEventsAnalyzer(dev_categories_thresholds=(0.95, 0.99))
        analyzer_2.process_events(self.events)

        categories = analyzer_2.get_developer_categories()
        self.assertDictEqual(categories, {"core": 2, "regular": 0, "casual": 1})

    def test_repository_metadata(self):
        """Test if the repository metadata is calculated correctly"""

        self.analyzer.process_events(self.events)

        metadata = self.analyzer.get_analysis_metadata()
        self.assertEqual(metadata["first_commit"], "c82f679dea593bfb069b2ad83726bb90d99bee13")
        self.assertEqual(metadata["last_commit"], "fd7d80fc8d33a97013119fe52170467c20ee8b37")
        self.assertEqual(metadata["first_commit_date"], "2024-01-09T11:15:39+01:00")
        self.assertEqual(metadata["last_commit_date"], "2024-04-05T16:45:24+02:00")

    def test_get_recent_organizations(self):
        """Test if the recent organizations are calculated correctly"""

        self.analyzer.process_events(self.events)

        recent_organizations = self.analyzer.get_recent_organizations()
        self.assertEqual(recent_organizations, 0)

        # Add events from a new organization in the last 30 days and 90 days
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=15)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 2 <author2@example_new_2.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=60)).isoformat(),
                },
            },
        ]

        self.analyzer.process_events(extra_events)
        recent_organizations = self.analyzer.get_recent_organizations()
        self.assertEqual(recent_organizations, 2)

    def test_recent_contributors(self):
        """Test if the recent contributors are calculated correctly"""

        self.analyzer.process_events(self.events)

        recent_contributors = self.analyzer.get_recent_contributors()
        self.assertEqual(recent_contributors, 0)

        # Add events from new contributors in the last days
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=35)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 2 <author2@example_new_2.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=60)).isoformat(),
                },
            },
        ]

        self.analyzer.process_events(extra_events)
        recent_contributors = self.analyzer.get_recent_contributors()
        self.assertEqual(recent_contributors, 2)

    def test_growth_rate_of_contributors(self):
        """Test if the growth rate of contributors is calculated correctly"""

        self.analyzer.process_events(self.events)

        growth = self.analyzer.get_growth_rate_of_contributors()
        self.assertEqual(growth, -1.0)

        # Add events from new contributors in the last days
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=15)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 2 <author2@example_new_2.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=60)).isoformat(),
                },
            },
        ]

        self.analyzer.process_events(extra_events)
        growth = self.analyzer.get_growth_rate_of_contributors()
        self.assertAlmostEqual(growth, -0.33, delta=0.01)

    def test_growth_of_contributors(self):
        """Test if the growth of contributors is calculated correctly"""

        self.analyzer.process_events(self.events)

        growth = self.analyzer.get_growth_of_contributors()
        self.assertEqual(growth, -3)

        # Add events from new contributors in the last days
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=15)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 2 <author2@example_new_2.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=60)).isoformat(),
                },
            },
        ]

        self.analyzer.process_events(extra_events)
        growth = self.analyzer.get_growth_of_contributors()
        self.assertEqual(growth, -1)

    def test_active_branch_count(self):
        """Test if the active branch count is calculated correctly"""

        self.analyzer.process_events(self.events)

        active_branches = self.analyzer.get_active_branch_count()
        self.assertEqual(active_branches, 2)

        # Add events from a new branch
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "commit": "1234567890abcdef1234567890abcdef12345678",
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "refs": ["refs/heads/another-branch"],
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "commit": "abcdef1234567890abcdef1234567890abcdef12",
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "parents": ["1234567890abcdef1234567890abcdef12345678"],
                    "refs": ["HEAD -> refs/heads/main"],
                },
            },
        ]

        self.analyzer.process_events(extra_events)
        active_branches = self.analyzer.get_active_branch_count()
        self.assertEqual(active_branches, 3)

    def test_get_days_since_last_commit(self):
        """Test if the days since last commit are calculated correctly"""

        # Add an event with a commit from 10 days ago
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "commit": "abcdef1234567890abcdef1234567890abcdef12",
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Old commit",
                    "CommitDate": (now - datetime.timedelta(days=10, hours=1)).isoformat(),
                },
            }
        ]
        self.analyzer.process_events(events)
        days_since_last_commit = self.analyzer.get_days_since_last_commit()
        self.assertEqual(days_since_last_commit, 10)

    def test_get_recent_commits(self):
        """Test if the recent commits are calculated correctly"""

        self.analyzer.process_events(self.events)

        recent_commits = self.analyzer.get_recent_commits()
        self.assertEqual(recent_commits, 0)

        # Add an event with a commit from 10 days ago
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "commit": "abcdef1234567890abcdef1234567890abcdef12",
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Old commit",
                    "CommitDate": (now - datetime.timedelta(days=10, hours=1)).isoformat(),
                },
            }
        ]
        self.analyzer.process_events(extra_events)

        recent_commits = self.analyzer.get_recent_commits()
        self.assertEqual(recent_commits, 1)

    def test_found_files(self):
        """Test if license and adopters files are found correctly"""

        self.analyzer.process_events(self.file_events)

        found_files = self.analyzer.get_found_files()
        self.assertTrue(found_files["license"])
        self.assertFalse(found_files["adopters"])

        # Add an event with an ADOPTERS file and rename LICENSE file to LICENSES
        extra_events = [
            {
                "specversion": "1.0",
                "id": "1235c7782e670b0a476e45b16e3fee462c1d3f1",
                "source": "https://github.com/bitergia/grimoirelab-metrics",
                "type": "org.grimoirelab.events.git.file.added",
                "time": 1750233485,
                "data": {
                    "filename": "ADOPTERS.txt",
                    "modes": ["000000", "100644"],
                    "indexes": ["0000000", "9cecc1d"],
                    "similarity": None,
                    "new_filename": None,
                    "added_lines": "674",
                    "deleted_lines": "0",
                },
                "linked_event": "12349eb604662a3bf52a99e3cd5bcb1e5b21f155",
            },
            {
                "specversion": "1.0",
                "id": "98f5938cebd712b8b3f84661fbc8ce8895a1bbdd",
                "source": "https://github.com/bitergia/grimoirelab-metrics",
                "type": "org.grimoirelab.events.git.file.replaced",
                "time": 1750233485,
                "data": {
                    "filename": "LICENSE",
                    "modes": ["100644", "100644"],
                    "indexes": ["e69de29", "e69de29"],
                    "similarity": None,
                    "new_filename": "LICENSES",
                    "added_lines": "0",
                    "deleted_lines": "0",
                },
                "linked_event": "c0ed58001d78e096ad5bcb1267f5dd596ac5f6d3",
            },
        ]
        self.analyzer.process_events(extra_events)
        found_files = self.analyzer.get_found_files()
        self.assertFalse(found_files["license"])
        self.assertTrue(found_files["adopters"])

    def test_get_casual_regular_contributors_rate(self):
        """Test if the rate of casual and regular contributors is calculated correctly"""

        # 0 contributors
        rate = self.analyzer.get_casual_regular_contributors_rate()
        self.assertEqual(rate, 0)

        self.analyzer.process_events(self.events)

        # 1 casual contributors and 2 regular contributor
        rate = self.analyzer.get_casual_regular_contributors_rate()
        self.assertEqual(rate, 0.5)

        # Add events from new contributors
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": now.isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new_2.com>",
                    "message": "Another commit 2",
                    "CommitDate": now.isoformat(),
                },
            },
        ]

        # 1 casual contributor and 4 regular contributors
        self.analyzer.process_events(extra_events)
        rate = self.analyzer.get_casual_regular_contributors_rate()
        self.assertEqual(rate, 0.25)

    def test_get_returning_contributors(self):
        """Test if the returning contributors are calculated correctly"""

        self.analyzer.process_events(self.events)

        returning_contributors = self.analyzer.get_returning_contributors()
        self.assertEqual(returning_contributors, 0)

        # Add events from returning contributors
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "UserTwo <usertwo@example2.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=15)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "User One <userone@example.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=60)).isoformat(),
                },
            },
        ]

        self.analyzer.process_events(extra_events)
        returning_contributors = self.analyzer.get_returning_contributors()
        self.assertEqual(returning_contributors, 2)

    def test_get_commits_rate_empty(self):
        """Test if the commits rate is calculated correctly when there are no commits"""

        # There are no commits
        rate = self.analyzer.get_commits_over_periods_rate()
        self.assertEqual(rate, 0)

    def test_get_commits_rate(self):
        """Test if the commits rate is calculated correctly"""

        self.analyzer.process_events(self.events)

        # 0 commits in the last 90 days vs 9 commits in total
        rate = self.analyzer.get_commits_over_periods_rate()
        self.assertEqual(rate, 0)

        # Add events from new commits
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        extra_events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=15)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 2 <author2@example_new_2.com>",
                    "message": "Another commit 2",
                    "CommitDate": (now - datetime.timedelta(days=60)).isoformat(),
                },
            },
        ]
        self.analyzer.process_events(extra_events)

        # 2 commits in the last 90 days vs 11 commits in total
        rate = self.analyzer.get_commits_over_periods_rate()
        self.assertAlmostEqual(rate, 0.18, delta=0.01)

    def test_get_commits_rate_only_last_30_days(self):
        """Test if the commits rate is calculated correctly when there are only commits in the last 30 days"""

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        events = [
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 1 <author1@example_new.com>",
                    "message": "Another commit",
                    "CommitDate": (now - datetime.timedelta(days=15)).isoformat(),
                },
            },
            {
                "type": "org.grimoirelab.events.git.commit",
                "data": {
                    "Author": "Author 2 <author2@example_new_2.com>",
                    "message": "Another commit 2",
                    "CommitDate": (now - datetime.timedelta(days=20)).isoformat(),
                },
            },
        ]
        self.analyzer.process_events(events)

        # 2 commits in the last 30 days vs 2 commits in total
        rate = self.analyzer.get_commits_over_periods_rate()
        self.assertEqual(rate, 1.0)


if __name__ == "__main__":
    unittest.main()
