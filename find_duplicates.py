#!/usr/bin/env python3
"""
Script to find duplicate Snyk projects in an organization.
Duplicates are identified as multiple projects targeting the same repository.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Any

import requests


class SnykDuplicateFinder:
    def __init__(self, org_id: str, api_token: str):
        self.org_id = org_id
        self.api_token = api_token
        self.base_url = "https://api.eu.snyk.io/rest"
        self.api_version = "2025-11-05"
        self.headers = {
            "Authorization": f"token {api_token}",
            "Content-Type": "application/vnd.api+json"
        }

    def fetch_all_projects(self) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Fetch all projects from the Snyk organization with pagination.
        Returns projects data and included targets data.
        """
        url = f"{self.base_url}/orgs/{self.org_id}/projects"
        params = {
            "version": self.api_version,
            "expand": "target",
            "limit": 100  # Max limit per page (must be multiple of 10, >= 10)
        }

        all_projects = []
        all_targets = {}

        while url:
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()

                # Check for errors in response
                if "errors" in data:
                    print(f"API Error: {json.dumps(data['errors'], indent=2)}", file=sys.stderr)
                    break

                # Extract projects from response
                if "data" in data:
                    all_projects.extend(data["data"])
                    print(f"Fetched {len(data['data'])} projects... (Total: {len(all_projects)})", file=sys.stderr)

                # Extract included targets (these contain the display_name)
                if "included" in data:
                    for item in data["included"]:
                        if item.get("type") == "target":
                            target_id = item.get("id")
                            all_targets[target_id] = item

                # Check for next page
                next_url = data.get("links", {}).get("next")
                if next_url:
                    # Handle relative URLs by prepending the base domain
                    if next_url.startswith("/"):
                        url = f"https://api.eu.snyk.io{next_url}"
                    else:
                        url = next_url
                    # Clear params for next request as URL already includes them
                    params = None
                else:
                    url = None

            except requests.exceptions.RequestException as e:
                print(f"Error fetching projects: {e}", file=sys.stderr)
                sys.exit(1)

        return all_projects, all_targets

    def extract_project_info(self, project: Dict[str, Any], targets: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract relevant information from a project object.
        """
        project_id = project.get("id", "")
        attributes = project.get("attributes", {})
        relationships = project.get("relationships", {})

        # Extract project name
        project_name = attributes.get("name", "Unknown")

        # Extract target information
        target_data = relationships.get("target", {}).get("data", {})
        target_id = target_data.get("id", "")

        # Get target display name from the included targets data
        target_name = ""
        if target_id and target_id in targets:
            target_attributes = targets[target_id].get("attributes", {})
            target_name = target_attributes.get("display_name", "")

        return {
            "project_id": project_id,
            "project_name": project_name,
            "target_id": target_id,
            "target_name": target_name,
            "project_type": attributes.get("type", ""),
            "origin": attributes.get("origin", "")
        }

    def find_duplicates(self, projects: List[Dict[str, Any]], targets: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Group projects by target, then find duplicate project names within each target.
        Returns a nested dict: {target_name: {project_name: [projects]}}
        """
        # First group by target
        by_target = defaultdict(list)

        for project in projects:
            info = self.extract_project_info(project, targets)
            target_key = info["target_name"] or info["target_id"] or "unknown"
            by_target[target_key].append(info)

        # Now find duplicates within each target (same project name)
        duplicates = {}

        for target_name, target_projects in by_target.items():
            # Group projects by name within this target
            by_project_name = defaultdict(list)
            for proj in target_projects:
                by_project_name[proj["project_name"]].append(proj)

            # Filter to only include project names with duplicates
            duplicate_projects = {
                proj_name: proj_list
                for proj_name, proj_list in by_project_name.items()
                if len(proj_list) > 1
            }

            # Only include targets that have duplicate projects
            if duplicate_projects:
                duplicates[target_name] = duplicate_projects

        return duplicates

    def generate_report(self, duplicates: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Any]:
        """
        Generate a report of duplicate projects grouped by target.
        """
        report = {
            "org_id": self.org_id,
            "total_targets_with_duplicates": len(duplicates),
            "duplicates_by_target": []
        }

        total_duplicate_projects = 0

        for target_name, duplicate_projects in duplicates.items():
            target_group = {
                "target_name": target_name,
                "duplicate_project_names": []
            }

            for project_name, projects in duplicate_projects.items():
                total_duplicate_projects += len(projects)
                duplicate_entry = {
                    "project_name": project_name,
                    "duplicate_count": len(projects),
                    "projects": projects
                }
                target_group["duplicate_project_names"].append(duplicate_entry)

            report["duplicates_by_target"].append(target_group)

        report["total_duplicate_projects"] = total_duplicate_projects

        return report

    def run(self) -> Dict[str, Any]:
        """
        Main execution method.
        """
        print(f"Fetching projects for organization: {self.org_id}", file=sys.stderr)
        projects, targets = self.fetch_all_projects()
        print(f"Total projects fetched: {len(projects)}", file=sys.stderr)
        print(f"Total unique targets: {len(targets)}", file=sys.stderr)

        print("Analyzing for duplicates...", file=sys.stderr)
        duplicates = self.find_duplicates(projects, targets)

        if not duplicates:
            print("No duplicate projects found!", file=sys.stderr)
            return {"org_id": self.org_id, "duplicates_by_target": []}

        print(f"Found {len(duplicates)} targets with duplicate projects", file=sys.stderr)

        report = self.generate_report(duplicates)
        return report


def main():
    parser = argparse.ArgumentParser(
        description="Find duplicate Snyk projects in an organization"
    )
    parser.add_argument(
        "org_id",
        help="Snyk Organization ID"
    )
    parser.add_argument(
        "--api-token",
        help="Snyk API token (or set SNYK_TOKEN environment variable)",
        default=os.environ.get("SNYK_TOKEN")
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
        default=None
    )

    args = parser.parse_args()

    if not args.api_token:
        print("Error: Snyk API token is required. Provide via --api-token or SNYK_TOKEN environment variable.",
              file=sys.stderr)
        sys.exit(1)

    finder = SnykDuplicateFinder(args.org_id, args.api_token)
    report = finder.run()

    # Output results
    output_json = json.dumps(report, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
