# Snyk Duplicate Projects Finder

This script identifies duplicate Snyk projects within an organization. Duplicates are detected when multiple projects target the same repository.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
export SNYK_TOKEN="your-snyk-api-token"
python find_duplicates.py <org_id>
```

### With API Token Argument

```bash
python find_duplicates.py <org_id> --api-token "your-snyk-api-token"
```

### Save Output to File

```bash
python find_duplicates.py <org_id> -o duplicates.json
```

## Example

```bash
# Set your Snyk API token
export SNYK_TOKEN="snyk-api-token-here"

# Find duplicates and save to file
python find_duplicates.py xxx-xxx-xxx -o duplicates.json
```

## Output Format

The script outputs a JSON report containing:

- `org_id`: The Snyk organization ID
- `total_targets_with_duplicates`: Number of repositories/targets with duplicate projects
- `total_duplicate_projects`: Total count of duplicate projects across all targets
- `duplicates_by_target`: Array of targets with duplicates, each containing:
  - `target_name`: Repository/target name
  - `duplicate_project_names`: Array of duplicate project name groups, each containing:
    - `project_name`: The duplicated project name
    - `duplicate_count`: Number of times this project appears
    - `projects`: Array of project details including:
      - `project_id`: Project ID (used for deletion API)
      - `project_name`: Project name
      - `target_id`: Target ID
      - `target_name`: Target/repository name
      - `project_type`: Type of project
      - `origin`: Origin of the project

## Example Output

```json
{
  "org_id": "xxx-xxx-xxx",
  "total_targets_with_duplicates": 1,
  "total_duplicate_projects": 2,
  "duplicates_by_target": [
    {
      "target_name": "my-org/my-repo",
      "duplicate_project_names": [
        {
          "project_name": "my-org/my-repo:package.json",
          "duplicate_count": 2,
          "projects": [
            {
              "project_id": "abc123-first-duplicate",
              "project_name": "my-org/my-repo:package.json",
              "target_id": "xyz789",
              "target_name": "my-org/my-repo",
              "project_type": "npm",
              "origin": "github"
            },
            {
              "project_id": "def456-second-duplicate",
              "project_name": "my-org/my-repo:package.json",
              "target_id": "xyz789",
              "target_name": "my-org/my-repo",
              "project_type": "npm",
              "origin": "github"
            }
          ]
        }
      ]
    }
  ]
}
```

## Next Steps

After identifying duplicates, you can use the Snyk Delete Projects API to remove unwanted duplicates:

```
DELETE https://api.snyk.io/rest/orgs/{org_id}/projects/{project_id}?version=2025-11-05
```

The `project_id` from the output JSON can be used with this API endpoint.
