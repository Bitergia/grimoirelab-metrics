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

from __future__ import annotations

import datetime
import logging
import re
import typing

from collections import Counter

from opensearchpy import OpenSearch, Search, Q

from grimoirelab_toolkit.datetime import (
    str_to_datetime,
    datetime_utcnow,
    datetime_to_utc,
    InvalidDateError,
)

logging.getLogger("opensearch").setLevel(logging.WARNING)


if typing.TYPE_CHECKING:
    from typing import Any


GIT_EVENT_COMMIT = "org.grimoirelab.events.git.commit"
GIT_EVENT_ACTION_ADDED = "org.grimoirelab.events.git.file.added"
GIT_EVENT_ACTION_DELETED = "org.grimoirelab.events.git.file.deleted"
GIT_EVENT_ACTION_REPLACED = "org.grimoirelab.events.git.file.replaced"
GIT_EVENT_ACTION_COPIED = "org.grimoirelab.events.git.file.copied"
GIT_EVENT_FILE_ACTIONS = [
    GIT_EVENT_ACTION_ADDED,
    GIT_EVENT_ACTION_DELETED,
    GIT_EVENT_ACTION_REPLACED,
    GIT_EVENT_ACTION_COPIED,
]

AUTHOR_FIELD = "Author"
FILE_TYPE_CODE = (
    r"\.bazel$|\.bazelrc$|\.bzl$|\.c$|\.cc$|\.cp$|\.cpp$|\.cs$\|\.cxx$|\.c\+\+$|"
    r"\.go$|\.h$|\.hpp$|\.js$|\.mjs$|\.java$|\.pl$|\.py$|\.rs$|\.sh$|\.tf$|\.ts$"
)
FILE_TYPE_BINARY = (
    r"\.7z$|\.a$|\.abb$|\.apk$|\.app$|\.appx$|\.arc$|\.bin$|\.bz2$|\.class$|\.deb$|"
    r"\.dll$|\.dmg$|\.exe$|\.gz$|\.ipa$|\.iso$|\.jar$|\.lib$|\.msi$|\.o$|\.obj$|\.rar$|"
    r"\.rpm$|\.so$|\.tar$|\.xar$|\.xz$|\.zip$|\.zst$|\.Z$"
)
LICENSE_FILE_REGEX = r"LICENSE|LICENSE\.md|LICENSE\.txt|COPYING"
ADOPTERS_FILE_REGEX = r"ADOPTERS|ADOPTERS\.md|ADOPTERS\.txt"
COMPILED_LICENSE_FILE_REGEX = re.compile(LICENSE_FILE_REGEX)
COMPILED_ADOPTERS_FILE_REGEX = re.compile(ADOPTERS_FILE_REGEX)


class GitEventsAnalyzer:
    def __init__(
        self,
        from_date: datetime.datetime | None = None,
        to_date: datetime.datetime | None = None,
        code_file_pattern: str | None = None,
        binary_file_pattern: str | None = None,
        pony_threshold: float = 0.5,
        elephant_threshold: float = 0.5,
        dev_categories_thresholds: tuple[float, float] = (0.8, 0.95),
    ):
        # Define the default dates if not provided
        if from_date:
            self.from_date = datetime_to_utc(from_date)
        else:
            self.from_date = datetime_utcnow() - datetime.timedelta(days=365)
        if to_date:
            self.to_date = datetime_to_utc(to_date)
        else:
            self.to_date = datetime_utcnow()

        self.total_commits: int = 0
        self.recent_commits: int = 0
        self.contributors: Counter = Counter()
        self.contributors_growth: dict[str, set] = {"first_half": set(), "second_half": set()}
        self.returning_contributors: dict[str, set] = {"first_period": set(), "second_period": set()}
        self.organizations: Counter = Counter()
        self.recent_organizations: set = set()
        self.recent_contributors: set = set()
        self.file_types: dict = {"code": 0, "binary": 0, "other": 0}
        self.added_lines: int = 0
        self.removed_lines: int = 0
        self.messages_sizes: list = []
        self.re_code_pattern = re.compile(code_file_pattern or FILE_TYPE_CODE)
        self.re_binary_pattern = re.compile(binary_file_pattern or FILE_TYPE_BINARY)
        self.pony_threshold = pony_threshold
        self.elephant_threshold = elephant_threshold
        self.dev_categories_thresholds = dev_categories_thresholds
        self.first_commit: str | None = None
        self.last_commit: str | None = None
        self.first_commit_date: datetime.datetime | None = None
        self.last_commit_date: datetime.datetime | None = None
        self.active_branches: set = set()
        self._half_period = self.from_date + (self.to_date - self.from_date) / 2
        self.files_found: dict[str, int] = {"license": 0, "adopters": 0}

    def process_events(self, events: iter(dict[str, Any])):
        for event in events:
            if event["type"] == GIT_EVENT_COMMIT:
                event_data = event.get("data")

                self._update_commit_count(event_data)
                self._update_branches(event_data)
                self._update_contributors(event_data)
                self._update_organizations(event_data)
                self._update_file_metrics(event_data)
                self._update_message_size_metrics(event_data)
                self._update_first_and_last_commit(event_data)
            elif event["type"] in GIT_EVENT_FILE_ACTIONS:
                self._check_files_found(event)

    def get_commit_count(self):
        return self.total_commits

    def get_contributor_count(self):
        return len(self.contributors)

    def get_organization_count(self):
        return len(self.organizations)

    def get_pony_factor(self):
        """Number of individuals producing up to 50% of the total number of code contributions"""

        partial_contributions = 0
        pony_factor = 0

        if len(self.contributors) == 0:
            return 0

        for _, contributions in self.contributors.most_common():
            partial_contributions += contributions
            pony_factor += 1
            if partial_contributions / self.total_commits > self.pony_threshold:
                break

        return pony_factor

    def get_elephant_factor(self):
        """Number of organizations producing up to 50% of the total number of code contributions"""

        partial_contributions = 0
        elephant_factor = 0

        if len(self.organizations) == 0:
            return 0

        for _, contributions in self.organizations.most_common():
            partial_contributions += contributions
            elephant_factor += 1
            if partial_contributions / self.total_commits > self.elephant_threshold:
                break

        return elephant_factor

    def get_file_type_metrics(self):
        """Get the file type metrics"""

        return self.file_types

    def get_commit_size_metrics(self):
        """Get the commit size metrics"""

        metrics = {
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
        }
        return metrics

    def get_message_size_metrics(self):
        """Get the message size metrics"""

        total = sum(self.messages_sizes)
        number = len(self.messages_sizes)
        mean = 0
        median = 0
        if number > 0:
            mean = total / number
            median = sorted(self.messages_sizes)[number // 2]

        metrics = {
            "total": total,
            "mean": mean,
            "median": median,
        }
        return metrics

    def get_commit_frequency_metrics(self, days_interval: int):
        """
        Get the average (mean) number of commits per week, month and
        year if the days of interval is greater than the metrics interval.

        :param days_interval: Interval of days to calculate the mean
        """
        metrics = {"week": None, "month": None, "year": None}

        if days_interval >= 7:
            metrics["week"] = self.total_commits / (days_interval / 7)

        if days_interval >= 30:
            metrics["month"] = self.total_commits / (days_interval / 30)

        if days_interval >= 365:
            metrics["year"] = self.total_commits / (days_interval / 365)

        return metrics

    def get_developer_categories(self):
        """Return the number of core, regular and casual developers"""

        core = 0
        regular = 0
        casual = 0
        regular_threshold = int(self.dev_categories_thresholds[0] * self.total_commits)
        casual_threshold = int(self.dev_categories_thresholds[1] * self.total_commits)
        acc_commits = 0
        last_core_contribution = 0

        for _, contributions in self.contributors.most_common():
            acc_commits += contributions

            if acc_commits <= regular_threshold or contributions > last_core_contribution:
                last_core_contribution = contributions
                core += 1
            elif acc_commits <= casual_threshold or contributions == last_core_contribution:
                regular += 1
            else:
                casual += 1

        return {
            "core": core,
            "regular": regular,
            "casual": casual,
        }

    def get_recent_organizations(self):
        """Return the number of recent organizations."""

        return len(self.recent_organizations)

    def get_recent_contributors(self):
        """Return the number of contributors from the last 90d."""

        return len(self.recent_contributors)

    def get_recent_commits(self) -> int:
        """Return the number of commits in the last 90d."""

        return self.recent_commits

    def get_commits_over_periods_rate(self):
        """Return the rate of commits between a recent period and the last year."""

        try:
            return self.recent_commits / self.total_commits
        except ZeroDivisionError:
            return 0.0

    def get_growth_of_contributors(self):
        """Return the growth of contributors by period."""

        first_half = len(self.contributors_growth["first_half"])
        second_half = len(self.contributors_growth["second_half"])

        return second_half - first_half

    def get_growth_rate_of_contributors(self):
        """Return the growth of contributors by period."""

        first_half = len(self.contributors_growth["first_half"])
        second_half = len(self.contributors_growth["second_half"])

        if first_half == 0 and second_half == 0:
            return 0
        elif first_half == 0 and second_half != 0:
            # It increased infinitely
            return second_half
        else:
            return (second_half - first_half) / first_half

    def get_active_branch_count(self):
        """Return the number of active branches."""

        return len(self.active_branches)

    def get_analysis_metadata(self):
        """Return metadata about the analysis."""

        metadata = {
            "first_commit": self.first_commit,
            "last_commit": self.last_commit,
            "first_commit_date": None,
            "last_commit_date": None,
        }

        if self.first_commit_date:
            metadata["first_commit_date"] = self.first_commit_date.isoformat()
        if self.last_commit_date:
            metadata["last_commit_date"] = self.last_commit_date.isoformat()

        return metadata

    def get_days_since_last_commit(self):
        """Return the number of days since the last commit."""

        if not self.last_commit_date:
            return None

        days_since_last_commit = (self.to_date - self.last_commit_date).days

        return days_since_last_commit

    def get_casual_regular_contributors_rate(self):
        """Calculate the rate between casual contributors and regular contributors."""

        dev_categories = self.get_developer_categories()
        core_and_regular = dev_categories["core"] + dev_categories["regular"]
        casual = dev_categories["casual"]

        if not core_and_regular:
            # If there are no core or regular contributors, return 0
            # because there shouldn't be any casual contributors.
            return 0.0
        else:
            return casual / core_and_regular

    def get_found_files(self):
        """Return the files found in the repository."""

        return {
            "license": 1 if self.files_found["license"] > 0 else 0,
            "adopters": 1 if self.files_found["adopters"] > 0 else 0,
        }

    def get_returning_contributors(self):
        """Return the number of returning contributors by period."""

        returning_contributors = 0
        for author in self.returning_contributors["first_period"]:
            if author in self.returning_contributors["second_period"]:
                returning_contributors += 1

        return returning_contributors

    def _update_commit_count(self, event_data):
        """Update the commit count and commits by period."""

        # Update total commits
        self.total_commits += 1

        # Update commits by period
        try:
            commit_date = str_to_datetime(event_data.get("CommitDate"))
            days_interval = (self.to_date - commit_date).days
        except (ValueError, TypeError, InvalidDateError):
            return

        if days_interval <= 90:
            self.recent_commits += 1

    def _update_contributors(self, event_data):
        author = event_data[AUTHOR_FIELD]

        self.contributors[author] += 1

        # Update contributor growth
        try:
            commit_date = event_data.get("CommitDate")
            commit_date = str_to_datetime(commit_date)
        except (ValueError, TypeError, InvalidDateError):
            commit_date = None

        if commit_date and self._half_period:
            if commit_date < self._half_period:
                self.contributors_growth["first_half"].add(author)
            else:
                self.contributors_growth["second_half"].add(author)

        # Update contributors by period
        if commit_date:
            days_interval = (self.to_date - commit_date).days
            if days_interval <= 90:
                self.recent_contributors.add(author)
                self.returning_contributors["second_period"].add(author)
            else:
                self.returning_contributors["first_period"].add(author)

    def _update_organizations(self, event_data):
        try:
            author = event_data[AUTHOR_FIELD]
            organization = author.split("@")[1][:-1]
        except (IndexError, KeyError):
            return

        self.organizations[organization] += 1

        # Update organizations by period
        try:
            commit_date = str_to_datetime(event_data.get("CommitDate"))
            days_interval = (self.to_date - commit_date).days
        except (ValueError, TypeError, InvalidDateError):
            pass
        else:
            if days_interval <= 90:
                self.recent_organizations.add(organization)

    def _update_file_metrics(self, event):
        if "files" not in event:
            return

        for file in event["files"]:
            if not file["file"]:
                continue

            # File type metrics
            if self.re_code_pattern.search(file["file"]):
                self.file_types["code"] += 1
            elif self.re_binary_pattern.search(file["file"]):
                self.file_types["binary"] += 1
            else:
                self.file_types["other"] += 1

            # Line added/removed metrics
            if "added" in file:
                try:
                    self.added_lines += int(file["added"])
                except ValueError:
                    pass
            if "removed" in file:
                try:
                    self.removed_lines += int(file["removed"])
                except ValueError:
                    pass

    def _check_files_found(self, event):
        """
        Check if the file exists in the event data and update metrics accordingly.

        To identify if a file exists, it checks the filename against
        the regular expressions for license and adopters files.
        When the filename matches, added and copied actions increase the count,
        deleted and replaced actions decrease the count if it is the filename,
        and increase if it is the new filename.
        If the file count is greater than zero, it indicates that at least one
        of the files exists in the repository.
        """
        event_type = event["type"]
        data = event["data"]

        if event_type == GIT_EVENT_ACTION_ADDED:
            if COMPILED_LICENSE_FILE_REGEX.fullmatch(data["filename"]):
                self.files_found["license"] += 1
            elif COMPILED_ADOPTERS_FILE_REGEX.fullmatch(data["filename"]):
                self.files_found["adopters"] += 1

        elif event_type == GIT_EVENT_ACTION_DELETED:
            if COMPILED_LICENSE_FILE_REGEX.fullmatch(data["filename"]):
                self.files_found["license"] -= 1
            elif COMPILED_ADOPTERS_FILE_REGEX.fullmatch(data["filename"]):
                self.files_found["adopters"] -= 1

        elif event_type == GIT_EVENT_ACTION_REPLACED:
            if COMPILED_LICENSE_FILE_REGEX.fullmatch(data["filename"]):
                self.files_found["license"] -= 1
            elif COMPILED_ADOPTERS_FILE_REGEX.fullmatch(data["filename"]):
                self.files_found["adopters"] -= 1
            if COMPILED_LICENSE_FILE_REGEX.fullmatch(data["new_filename"]):
                self.files_found["license"] += 1
            elif COMPILED_ADOPTERS_FILE_REGEX.fullmatch(data["new_filename"]):
                self.files_found["adopters"] += 1

        elif event_type == GIT_EVENT_ACTION_COPIED:
            if COMPILED_LICENSE_FILE_REGEX.fullmatch(data["new_filename"]):
                self.files_found["license"] += 1
            elif COMPILED_ADOPTERS_FILE_REGEX.fullmatch(data["new_filename"]):
                self.files_found["adopters"] += 1

    def _update_message_size_metrics(self, event):
        message = event.get("message", "")
        self.messages_sizes.append(len(message))

    def _update_first_and_last_commit(self, event):
        """Update last commit and first commit metadata."""

        commit = event.get("commit")
        commit_date = event.get("CommitDate")
        if not commit_date or not commit:
            return

        commit_date = str_to_datetime(commit_date)

        if not self.first_commit or self.first_commit_date > commit_date:
            self.first_commit = commit
            self.first_commit_date = commit_date

        if not self.last_commit or self.last_commit_date < commit_date:
            self.last_commit = commit
            self.last_commit_date = commit_date

    def _update_branches(self, event_data):
        """Identify the refs that are branches and update the active branches."""

        if "refs" not in event_data:
            return

        for ref in event_data["refs"]:
            if "refs/heads/" not in ref:
                continue

            branch_name = ref.split("refs/heads/")[1]
            self.active_branches.add(branch_name)


def get_repository_metrics(
    repository: str,
    opensearch_url: str,
    opensearch_index: str,
    opensearch_user: str = None,
    opensearch_password: str = None,
    opensearch_ca_certs: str = None,
    from_date: datetime.datetime = None,
    to_date: datetime.datetime = None,
    verify_certs: bool = True,
    code_file_pattern: str | None = None,
    binary_file_pattern: str | None = None,
    pony_threshold: float | None = None,
    elephant_threshold: float | None = None,
    dev_categories_thresholds: tuple[float, float] = (0.8, 0.95),
):
    """
    Get the metrics from a repository.

    :param repository: Repository URI
    :param opensearch_url: URL of the OpenSearch instance
    :param opensearch_index: Name of the index where the data is stored
    :param opensearch_user: Username to connect to OpenSearch, by default None
    :param opensearch_password: Password to connect to OpenSearch, by default None
    :param opensearch_ca_certs: Path to the CA certificate, by default None
    :param verify_certs: Boolean, verify SSL/TLS certificates, default True
    :param from_date: Start date, by default None
    :param to_date: End date, by default None
    :param code_file_pattern: Regular expression to match code file types.
    :param binary_file_pattern: Regular expression to match binary file types.
    :param pony_threshold: Threshold for the pony factor
    :param elephant_threshold: Threshold for the elephant factor
    :param dev_categories_thresholds: Threshold for the developer categories
    """
    os_conn = connect_to_opensearch(
        url=opensearch_url,
        username=opensearch_user,
        password=opensearch_password,
        ca_certs_path=opensearch_ca_certs,
        verify_certs=verify_certs,
    )

    analyzer = GitEventsAnalyzer(
        from_date=from_date,
        to_date=to_date,
        code_file_pattern=code_file_pattern,
        binary_file_pattern=binary_file_pattern,
        pony_threshold=pony_threshold,
        elephant_threshold=elephant_threshold,
        dev_categories_thresholds=dev_categories_thresholds,
    )

    # Process commit events for the repository within the specified date range
    events = get_repository_events(
        connection=os_conn,
        index_name=opensearch_index,
        repository=repository,
        event_type=[GIT_EVENT_COMMIT],
        from_date=from_date,
        to_date=to_date,
    )
    analyzer.process_events(events)

    # Process file events for the repository, only for license and adopters files
    file_regex = ADOPTERS_FILE_REGEX + r"|" + LICENSE_FILE_REGEX
    file_filter = Q(
        "bool",
        should=[Q("regexp", data__filename=file_regex), Q("regexp", data__new_filename=file_regex)],
        minimum_should_match=1,
    )
    events = get_repository_events(
        connection=os_conn,
        index_name=opensearch_index,
        repository=repository,
        event_type=GIT_EVENT_FILE_ACTIONS,
        to_date=to_date,
        additional_filter=file_filter,
    )

    analyzer.process_events(events)

    metrics = {"metrics": {}}
    metrics["metrics"]["total_commits"] = analyzer.get_commit_count()
    metrics["metrics"]["total_contributors"] = analyzer.get_contributor_count()
    metrics["metrics"]["total_organizations"] = analyzer.get_organization_count()
    metrics["metrics"]["pony_factor"] = analyzer.get_pony_factor()
    metrics["metrics"]["elephant_factor"] = analyzer.get_elephant_factor()
    metrics["metrics"]["recent_organizations"] = analyzer.get_recent_organizations()
    metrics["metrics"]["recent_contributors"] = analyzer.get_recent_contributors()
    metrics["metrics"]["recent_commits"] = analyzer.get_recent_commits()
    metrics["metrics"]["contributor_growth"] = analyzer.get_growth_of_contributors()
    metrics["metrics"]["contributor_growth_rate"] = analyzer.get_growth_rate_of_contributors()
    metrics["metrics"]["active_branches"] = analyzer.get_active_branch_count()
    metrics["metrics"]["days_since_last_commit"] = analyzer.get_days_since_last_commit()
    metrics["metrics"]["casual_regular_contributors_rate"] = analyzer.get_casual_regular_contributors_rate()
    metrics["metrics"]["returning_contributors"] = analyzer.get_returning_contributors()
    metrics["metrics"]["commits_over_periods_rate"] = analyzer.get_commits_over_periods_rate()

    if from_date and to_date:
        days = (to_date - from_date).days
    else:
        days = 365

    # Flatten two-level metrics
    metrics_to_flatten = {
        "file_types": analyzer.get_file_type_metrics(),
        "commit_size": analyzer.get_commit_size_metrics(),
        "message_size": analyzer.get_message_size_metrics(),
        "developer_categories": analyzer.get_developer_categories(),
        "commits_per": analyzer.get_commit_frequency_metrics(days),
        "found_file": analyzer.get_found_files(),
    }

    for prefix, metrics_set in metrics_to_flatten.items():
        for name, value in metrics_set.items():
            metrics["metrics"][prefix + "_" + name] = value

    metrics["metadata"] = analyzer.get_analysis_metadata()

    return metrics


def get_repository_events(
    connection: OpenSearch,
    index_name: str,
    repository: str,
    event_type: list[str] | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    additional_filter: Any | None = None,
) -> iter(dict[str, Any]):
    """
    Returns the events for a repository within a specified date range and event type.

    :param connection: OpenSearch connection object
    :param index_name: Name of the alias where Git data is stored in BAP
    :param repository: Name of the repository to filter commits
    :param event_type: List of event types to filter, e.g., [GIT_EVENT_COMMIT]
    :param from_date: Start date, by default None
    :param to_date: End date, by default None
    :param additional_filter: Additional filter to apply to the search query, by default None
    """
    s = Search(using=connection, index=index_name).filter("match", source=repository)

    if event_type:
        s = s.filter("terms", type=event_type)

    date_range = _format_date(from_date, to_date)
    if date_range:
        s = s.filter("range", time=date_range)

    if additional_filter:
        s = s.filter(additional_filter)

    return s.scan()


def connect_to_opensearch(
    url: str,
    username: str | None = None,
    password: str | None = None,
    ca_certs_path: str | None = None,
    verify_certs: bool = True,
    max_retries: int = 3,
) -> OpenSearch:
    """
    Connect to an OpenSearch instance using the given parameters.

    :param url: URL of the OpenSearch instance
    :param username: Username to connect to OpenSearch
    :param password: Password to connect to OpenSearch
    :param ca_certs_path: Path to the CA certificate
    :param verify_certs: Boolean, verify SSL/TLS certificates
    :param max_retries: Maximum number of retries in case of timeout

    :return: OpenSearch connection
    """
    auth = None
    if username and password:
        auth = (username, password)

    os_conn = OpenSearch(
        hosts=[url],
        http_auth=auth,
        http_compress=True,
        verify_certs=verify_certs,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        ca_certs=ca_certs_path,
        max_retries=max_retries,
        retry_on_timeout=True,
    )

    return os_conn


def _format_date(from_date: datetime.datetime | None, to_date: datetime.datetime | None) -> dict:
    """
    Format the date range for the OpenSearch query.

    :param from_date: Start date
    :param to_date: End date
    """
    date_range = {}
    if from_date:
        date_range["gte"] = from_date
    if to_date:
        date_range["lt"] = to_date

    return date_range
