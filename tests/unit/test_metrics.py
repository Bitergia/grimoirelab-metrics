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
import unittest

from grimoirelab_metrics.metrics import GitEventsAnalyzer


def read_file(filename):
    with open(filename) as f:
        return f.read()


class TestGitEventsAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = GitEventsAnalyzer()
        self.events = json.loads(read_file("data/events.json"))

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


if __name__ == "__main__":
    unittest.main()
