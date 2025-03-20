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
import json
import logging
import re
import sys
import time
import typing

import click
import requests

from spdx_tools.spdx.model import SpdxNone, SpdxNoAssertion
from spdx_tools.spdx.parser.error import SPDXParsingError
from spdx_tools.spdx.parser.parse_anything import parse_file

from grimoirelab_metrics.grimoirelab_client import GrimoireLabClient
from grimoirelab_metrics.metrics import get_repository_metrics

if typing.TYPE_CHECKING:
    from typing import Any

GIT_REPO_REGEX = r"((git|http(s)?)|(git@[\w\.]+))://?([\w\.@\:/\-~]+)(\.git)(/)?"


@click.command()
@click.argument("filename")
@click.option(
    "--grimoirelab-url",
    help="GrimoireLab URL server",
    show_default=True,
)
@click.option("--grimoirelab-user", help="GrimoireLab API user")
@click.option("--grimoirelab-password", help="GrimoireLab API password")
@click.option(
    "--opensearch-url",
    help="OpenSearch URL server",
    default="http://localhost:9200/",
)
@click.option("--opensearch-index", help="OpenSearch index", default="events")
@click.option("--opensearch-user", type=str, help="OpenSearch user", default=None)
@click.option("--opensearch-password", type=str, help="OpenSearch password", default=None)
@click.option("--opensearch-ca-certs", type=str, help="OpenSearch CA certificate path (.pem file)", default=None)
@click.option("--output", help="File where the scores will be written", type=click.File("w"), default=sys.stdout)
@click.option(
    "--repository-timeout",
    type=int,
    help="Timeout in seconds to wait for a repository to be analyzed",
    default=3600,
)
@click.option(
    "--from-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date, by default last year",
    default=(datetime.datetime.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d"),
)
@click.option(
    "--to-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date, by default today",
    default=datetime.datetime.today().strftime("%Y-%m-%d"),
)
@click.option("--verify-certs", is_flag=True, default=False, help="Verify SSL/TLS certificates")
@click.option("--verbose", is_flag=True, default=False, help="Increase output verbosity")
@click.option("--code-file-pattern", help="Regular expression to match code file types")
@click.option("--binary-file-pattern", help="Regular expression to match binary file types")
@click.option("--pony-threshold", type=click.FloatRange(0, 1), show_default=True, help="Pony factor threshold", default=0.5)
@click.option(
    "--elephant-threshold", type=click.FloatRange(0, 1), show_default=True, help="Elephant factor threshold", default=0.5
)
@click.option(
    "--dev-categories-thresholds",
    type=(click.FloatRange(0, 1), click.FloatRange(0, 1)),
    show_default=True,
    help="Developer categories thresholds",
    default=(0.8, 0.95),
)
def grimoirelab_metrics(
    filename: str,
    grimoirelab_url: str,
    grimoirelab_user: str,
    grimoirelab_password: str,
    opensearch_url: str,
    opensearch_index: str,
    opensearch_user: str | None = None,
    opensearch_password: str | None = None,
    opensearch_ca_certs: str | None = None,
    output: typing.TextIO = sys.stdout,
    repository_timeout: int = 3600,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    verify_certs: bool = False,
    verbose: bool = False,
    code_file_pattern: str | None = None,
    binary_file_pattern: str | None = None,
    pony_threshold: float = 0.5,
    elephant_threshold: float = 0.5,
    dev_categories_thresholds: tuple[float, float] = (0.8, 0.95),
) -> None:
    """Calculate metrics using GrimoireLab.

    Given a SPDX SBOM file with git repositories as input, this tool will generate
    a set of Project Health metrics. These metrics are calculated using the data
    stored on GrimoireLab about those repositories.

    If any of the listed repositories is not available on GrimoireLab, the tool
    will add it to GrimoireLab to have it analyzed.

    FILENAME: SPDX SBoM file with git repositories
    """
    log_level = "DEBUG" if verbose else "INFO"
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        grimoirelab_client = GrimoireLabClient(grimoirelab_url, grimoirelab_user, grimoirelab_password)
        grimoirelab_client.connect()

        packages = get_sbom_packages(filename)
        git_urls = list(set(repo for repo in packages.values() if is_valid(repo)))

        if len(git_urls) > 0:
            logging.info(f"Found {len(git_urls)} git repositories")
        else:
            logging.info("Could not find any git repositories to analyze")
            sys.exit(0)

        schedule_repositories(git_urls, grimoirelab_client)

        metrics = generate_metrics_when_ready(
            grimoirelab_client=grimoirelab_client,
            repositories=git_urls,
            opensearch_url=opensearch_url,
            opensearch_index=opensearch_index,
            opensearch_user=opensearch_user,
            opensearch_password=opensearch_password,
            opensearch_ca_certs=opensearch_ca_certs,
            from_date=from_date,
            to_date=to_date,
            verify_certs=verify_certs,
            timeout=repository_timeout,
            code_file_pattern=code_file_pattern,
            binary_file_pattern=binary_file_pattern,
            pony_threshold=pony_threshold,
            elephant_threshold=elephant_threshold,
            dev_categories_thresholds=dev_categories_thresholds,
        )

        package_metrics = {"packages": {}}
        for package, repo in packages.items():
            if repo and repo in metrics["repositories"]:
                package_metrics["packages"][package] = metrics["repositories"][repo]
                package_metrics["packages"][package]["repository"] = repo
            else:
                package_metrics["packages"][package] = {"metrics": None}

        output.write(json.dumps(package_metrics, indent=4))
    except SPDXParsingError as e:
        logging.error(e.messages[0])
        sys.exit(1)
    except OSError as e:
        logging.error(e)
        sys.exit(1)


def get_repository(download_location: str) -> str | None:
    if is_valid(download_location):
        git_regex = re.search(GIT_REPO_REGEX, download_location)
        if git_regex:
            uri = f"https://{git_regex.group(5)}"
            return uri


def get_sbom_packages(file: str) -> dict[str, str]:
    """Extract packages and git repositories from SPDX SBoM file.

    :param file: SPDX SBoM file.

    :return: Dict with package and repositories.
    """
    logging.info(f"Parsing file {file}")

    packages = {}
    document = parse_file(file)
    for package in document.packages:
        repository = get_repository(package.download_location)
        if repository:
            packages[package.spdx_id] = repository
        else:
            packages[package.spdx_id] = None
            logging.warning(f"Could not find a git repository for {package.spdx_id} ({package.name})")

    return packages


def schedule_repositories(repositories: list[str], grimoirelab_client: GrimoireLabClient) -> None:
    """Schedule tasks to collect data from a list of repositories.

    :param repositories: List of git repositories.
    :param grimoirelab_client: GrimoireLab API client.
    """
    logging.info("Scheduling tasks")
    for package_url in repositories:
        logging.debug(f"Scheduling task to fetch commits from {package_url}")
        try:
            schedule_repository(grimoirelab_client=grimoirelab_client, uri=package_url, datasource="git", category="commit")
        except (requests.HTTPError, requests.ConnectionError) as e:
            logging.error(f"Error scheduling task: {e}")
            raise e


def generate_metrics_when_ready(
    grimoirelab_client: GrimoireLabClient,
    repositories: list[str],
    opensearch_url: str,
    opensearch_index: str,
    opensearch_user: str | None = None,
    opensearch_password: str | None = None,
    opensearch_ca_certs: str | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    verify_certs: bool = False,
    timeout: int = 3600,
    code_file_pattern: str | None = None,
    binary_file_pattern: str | None = None,
    pony_threshold: float = 0.5,
    elephant_threshold: float = 0.5,
    dev_categories_thresholds: tuple[float, float] = (0.8, 0.95),
) -> dict[str:Any]:
    """Generate metrics once the repositories have finished the collection.

    :param grimoirelab_client: GrimoireLab API client.
    :param repositories: List of repositories.
    :param opensearch_url: OpenSearch URL.
    :param opensearch_index: OpenSearch index.
    :param opensearch_user: OpenSearch user.
    :param opensearch_password: OpenSearch password.
    :param opensearch_ca_certs: OpenSearch CA certificate.
    :param from_date: Start date for metrics.
    :param to_date: End date for metrics.
    :param verify_certs: Verify SSL/TLS certificates.
    :param timeout: Seconds to wait before failing getting metrics
    :param code_file_pattern: Regular expression to match code file types.
    :param binary_file_pattern: Regular expression to match binary file types.
    :param pony_threshold: Pony Factor threshold.
    :param elephant_threshold: Elephant Factor threshold.
    :param dev_categories_thresholds: Developer Categories thresholds.
    """
    logging.info("Generating metrics")

    limit_time = time.time() + timeout

    after_date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)
    pending_repositories = set(repositories)
    metrics = {"repositories": {}}

    while pending_repositories:
        processed = set()
        for repository in pending_repositories:
            if repository_ready(grimoirelab_client, repository, after_date):
                metrics["repositories"][repository] = get_repository_metrics(
                    repository=repository,
                    opensearch_url=opensearch_url,
                    opensearch_index=opensearch_index,
                    opensearch_user=opensearch_user,
                    opensearch_password=opensearch_password,
                    opensearch_ca_certs=opensearch_ca_certs,
                    from_date=from_date,
                    to_date=to_date,
                    verify_certs=verify_certs,
                    code_file_pattern=code_file_pattern,
                    binary_file_pattern=binary_file_pattern,
                    pony_threshold=pony_threshold,
                    elephant_threshold=elephant_threshold,
                    dev_categories_thresholds=dev_categories_thresholds,
                )
                processed.add(repository)

        pending_repositories -= processed

        if pending_repositories and time.time() < limit_time:
            logging.info(f"Waiting for {len(pending_repositories)} repositories to be ready")
            logging.debug(f"Repositories not ready: {pending_repositories}")
            time.sleep(25)
        else:
            break

    for repository in pending_repositories:
        logging.warning(f"Timeout waiting for repository {repository} to be ready")

    return metrics


def repository_ready(grimoirelab_client: GrimoireLabClient, repository: str, after_date: datetime.datetime) -> bool:
    """
    Check if the task related to the repository has finished.

    :param grimoirelab_client: GrimoireLab API client.
    :param repository: Repository URI
    :param after_date: Date to check if the task has finished
    """
    try:
        r = grimoirelab_client.get("/datasources/repositories/", params={"uri": repository})
    except requests.HTTPError as e:
        logging.warning(f"Error checking repository status: {e}")
        return False

    repo_data = r.json()

    task = repo_data["results"][0]["task"]
    if task["status"] == "failed":
        logging.warning(f"Metrics for '{repository}' might be incomplete")
        return True
    elif task["last_run"]:
        last_run_dt = datetime.datetime.fromisoformat(task["last_run"])
        return last_run_dt > after_date

    return False


def is_valid(repository: str) -> bool:
    """Check that the value is not empty nor invalid."""

    return repository and not isinstance(repository, SpdxNone) and not isinstance(repository, SpdxNoAssertion)


def schedule_repository(grimoirelab_client: GrimoireLabClient, uri: str, datasource: str, category: str) -> Any:
    """Schedule a task to fetch a Git repository.

    :param grimoirelab_client: GrimoireLab API client.
    :param uri: Repository URI.
    :param datasource: Data source type.
    :param category: Data source category.

    :return: Scheduled task.
    """
    data = {
        "uri": uri,
        "datasource_type": datasource,
        "datasource_category": category,
    }
    try:
        res = grimoirelab_client.post("datasources/add_repository", json=data)
        res.raise_for_status()
    except requests.HTTPError as e:
        if res.status_code == 405 and "already exists" in res.json()["error"]:
            pass
        else:
            raise e


if __name__ == "__main__":
    grimoirelab_metrics()
