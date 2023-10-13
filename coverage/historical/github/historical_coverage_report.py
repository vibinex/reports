"""
GitHub PR Coverage Analyzer

This script calculates the coverage percentage of merged pull requests based on the number of deletions that were reviewed.

How to run:
1. Install virtualenv:
   $ pip install virtualenv

2. Create a new virtual environment:
   $ virtualenv venv

3. Activate the virtual environment:
   On Windows: venv\Scripts\activate
   On macOS and Linux: source venv/bin/activate

4. Install the required packages:
   $ pip install -r requirements.txt

5. Run the script:
   $ python historical_coverage_report.py

When prompted, enter your GitHub token. Optionally, you can also provide a custom API URL or use the default (https://api.github.com).

"""
import re
import requests

BASE_URL = "https://api.github.com"

def main():
    """
    Main function to initiate the script.
    """
    token = input("Enter your GitHub token: ")
    BASE_URL = input("Enter the base API URL (press Enter to use the default): ")
    if not BASE_URL:
        BASE_URL = "https://api.github.com"

    total_coverage = 0
    workspace_considered = 0
    for workspace in get_workspaces(token):
        total_coverage, workspace_considered = process_workspace(total_coverage, workspace_considered, workspace, token)
    if workspace_considered == 0:
        print("No workspace with valid repos, unable to perform coverage calculation")
        return
    total_coverage /= workspace_considered
    print(f"Workspaces analyzed: {workspace_considered}")
    print(f"Total coverage across all workspaces: {total_coverage * 100:.2f}")
        
def process_workspace(total_coverage, workspace_considered, workspace, token):
    """
    Process each workspace and calculate the coverage.
    """
    print(f"Workspace: {workspace}")
    workspace_coverage = 0
    repos_considered = 0
    for repo in get_repositories(token, workspace):
        workspace_coverage, repos_considered = process_repo(workspace_coverage, repos_considered, repo, workspace, token)
    if repos_considered == 0:
        print(f"No valid repos in workspace {workspace}, not including in coverage calculation")
        return (total_coverage, workspace_considered)
    workspace_considered += 1
    workspace_coverage /= repos_considered
    total_coverage += workspace_coverage
    print(f"Total repos considered = {repos_considered}, total_coverage = {total_coverage}")
    print(f"######################### Coverage percentage for Workspace {workspace} = {workspace_coverage * 100:.2f}% #####################################")
    print("\n\n\n\n")
    return (total_coverage, workspace_considered)

def process_repo(workspace_coverage, repos_considered, repo, workspace, token):
    """
    Process each repository within a workspace and calculate the coverage.
    """
    print(f"  Repository: {repo}")
    repo_coverage = 0
    prs_considered = 0
    for pr in get_pull_requests(token, workspace, repo):
        repo_coverage, prs_considered = process_pr(repo_coverage, prs_considered, pr, repo, workspace, token)
    if prs_considered == 0:
        print(f"No valid prs in repo {repo}, not including in coverage calculation")
        return (workspace_coverage, repos_considered)
    repos_considered += 1
    repo_coverage /= prs_considered
    print(f"    # of prs considered = {prs_considered} in repo {repo}. workspace_coverage: {workspace_coverage}")
    workspace_coverage += repo_coverage
    print(f"    ~~~~~~~~~~~~><><><><><><Coverage percentage for Repository {repo} = {repo_coverage * 100:.2f}%><>><><><><~~~~~~~~~~~~~~")
    return (workspace_coverage, repos_considered)

def process_pr(repo_coverage, prs_considered, pr, repo, workspace, token):
    """
    Process each pull request within a repository and calculate the coverage.
    """
    if pr["state"] == "MERGED":
        reviewers = [review['author']['login'] for review in pr['reviews']['nodes']]
        if 'mergedBy' in pr and pr['mergedBy']['login'] not in reviewers:
            reviewers.append(pr['mergedBy']['login'])
        total_unapproved_deletions = 0
        total_deletions = 0
        total_unassigned = set()
        get_files_url = f"{BASE_URL}/repos/{workspace}/{repo}/pulls/{pr['number']}/files"
        for file in get_files_of_pull_request(get_files_url, token):
           total_unapproved_deletions, total_deletions, total_unassigned = process_file(total_unapproved_deletions, total_deletions, total_unassigned, file, pr, repo, workspace, reviewers, token)
        if total_deletions == 0:
            print(f"        No non-author deletions in PR #{pr['number']}, not included in coverage calculation")
            return (repo_coverage, prs_considered)
        if total_unapproved_deletions < 1 :
            coverage_percentage = 1
        else:
            coverage_percentage = 1 - (total_unapproved_deletions / total_deletions)
            print(f"    ============<Relevant authors who did not review the PR: {total_unassigned}>=============")
        print(f"     Processing PR #{pr['number']} with author: {pr['author']['login']} and reviewers: {reviewers}, merged by: {pr['mergedBy']['login']}")
        print(f"    Total deletions considered in PR: {total_deletions}, unapproved deletions: {total_unapproved_deletions}, repo_coverage: {repo_coverage}, prs_considered: {prs_considered}")
        print(f"    ============<Coverage percentage for Merged PR #{pr['number']}: {coverage_percentage * 100:.2f}%>=============")
        
        repo_coverage += coverage_percentage
        prs_considered += 1
    return (repo_coverage, prs_considered)

def process_file(total_unapproved_deletions, total_deletions, total_unassigned, file, pr, repo, workspace, reviewers, token):
    """
    Process each file within a pull request and calculate the coverage.
    """
    # print(f"            Processing file: {file['filename']}")
    if file and 'deletions' in file and file['deletions'] > 2000:
        # printf(f"       Unable to process file: {file['filename']}, cant handle file diffs larger than 2000 deletions")
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    if not file_exists_in_commit(token, workspace, repo, pr['baseRefOid'], file['filename']):
        # print(f"No file {file['filename']} in base commit")
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    if 'patch' not in file:
        # print(f"No patch in file: ${file['patch']}, not included in calculation cover of PR #{pr['number']}")
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    diff = file['patch']
    blame = get_blame_for_commit(token, workspace, repo, pr['baseRefOid'], file['filename'])
    if not blame:
        print(f"Could not get blame for commit: {pr['baseRefOid']}, file: {file['filename']}")
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    unapproved_deletions_file, total_deletions_file, unassigned_authors = calculate_coverage_percentage(diff, blame, reviewers, pr['author']['login'])
    if total_deletions_file == 0:
        # print(f"                No deletions in PR #{pr['number']} in file {file['filename']}, not included in coverage calculation")
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    if unapproved_deletions_file > 0 and (unassigned_authors == None or len(unassigned_authors) == 0):
        # No blame authors found for unapproved deleted lines
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    # print("file = ",file["filename"], unapproved_deletions_file, total_deletions_file, unassigned_authors, total_unassigned)
    total_unapproved_deletions += unapproved_deletions_file
    total_deletions += total_deletions_file
    total_unassigned = total_unassigned.union(unassigned_authors)
    return (total_unapproved_deletions, total_deletions, total_unassigned)

def run_query(query, token):
    """
    Run a GraphQL query against the GitHub API.
    """
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(BASE_URL + '/graphql', json={'query': query}, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed with status code {response.status_code}. {response.text}")


def get_workspaces(token):
    """
    Retrieve the list of workspaces for the authenticated user.
    """
    query = """
    {
      viewer {
        organizations(first: 100) {
          nodes {
            login
          }
        }
      }
    }
    """
    result = run_query(query, token)
    return [org['login'] for org in result['data']['viewer']['organizations']['nodes']]


def get_repositories(token, workspace):
    """
    Retrieve the list of repositories for a given workspace.
    """
    query = f"""
    {{
      organization(login: "{workspace}") {{
        repositories(first: 100) {{
          nodes {{
            name
          }}
        }}
      }}
    }}
    """
    result = run_query(query, token)
    if 'organization' in result['data'] and result['data']['organization']:
        return [repo['name'] for repo in result['data']['organization']['repositories']['nodes']]
    else:
        print(f"Warning: Organization '{workspace}' not found or no access.")
        return []


def get_pull_requests(token, workspace, repo_name):
    """
    Retrieve the list of pull requests for a given repository.
    """
    query = f"""
    {{
      repository(owner: "{workspace}", name: "{repo_name}") {{
        pullRequests(first: 100) {{
          nodes {{
            number
            state
            author {{
              login
            }}
            mergedBy {{
              login
            }}
            reviews(first: 100) {{
              nodes {{
                author {{
                  login
                }}
                state
              }}
            }}
            baseRefOid
          }}
        }}
      }}
    }}
    """
    result = run_query(query, token)
    return result['data']['repository']['pullRequests']['nodes']

def get_blame_for_commit(token, workspace, repo_name, commit_oid, path):
    """
    Retrieve the blame information for a given commit and file path.
    """
    query = f"""
    {{
      repository(owner: "{workspace}", name: "{repo_name}") {{
        object(oid: "{commit_oid}") {{
          ... on Commit {{
            blame(path: "{path}") {{
              ranges {{
                age
                commit {{
                  author {{
                    user {{
                      login
                    }}
                  }}
                }}
                startingLine
                endingLine
              }}
            }}
          }}
        }}
      }}
    }}
    """
    result = run_query(query, token)
    return result['data']['repository']['object']['blame']['ranges']


def get_diff_of_pull_request(pr_url, token):
    """
    Retrieve the diff of a pull request.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    response = requests.get(pr_url, headers=headers)
    response.raise_for_status()
    return response.text


def calculate_coverage_percentage(diff, blame, reviewers, pr_author):
    """
    Calculate the coverage percentage based on the diff and blame information.
    """
    deletions = 0
    unapproved_deletions = 0
    # Modified regex pattern to make the number of lines optional
    diff_changes_pattern = re.compile(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
    changed_blocks = diff_changes_pattern.findall(diff)
    deleted_lines = []
    for block in changed_blocks:
        start_line = int(block[0])
        # Provide a default value of 1 when the number of lines is not specified
        num_lines = int(block[1]) if block[1] else 1
        deletions += num_lines
        for i in range(num_lines):
            deleted_lines.append(start_line + i)
    if len(deleted_lines) == 0:
        return (None,0,None)
    total_deletions = 0
    unassigned_relevant = set()
    for line_number in deleted_lines:
        blame_author = next((
            range['commit']['author']['user']['login'] 
            for range in blame 
            if line_exists_in_range(range, line_number)
        ), None)

        if not blame_author:
            print(f"No blame author found for line : {line_number} in blame: {blame}, will be considered approved")
            continue
        if blame_author == pr_author:
            continue
        total_deletions += 1
        if blame_author not in reviewers:
            unapproved_deletions += 1
            unassigned_relevant.add(blame_author)
    return (unapproved_deletions, total_deletions, unassigned_relevant)

def line_exists_in_range(range, line_number):
    """
    Returns true if line number is within range
    """
    return range \
        and 'commit' in range \
        and range['commit'] \
        and 'author' in range['commit'] \
        and range['commit']['author'] \
        and 'user' in range['commit']['author'] \
        and range['commit']['author']['user'] \
        and 'login' in range['commit']['author']['user'] \
        and range['commit']['author']['user']['login'] \
        and 'startingLine' in range \
        and range['startingLine'] \
        and 'endingLine' in range \
        and range['endingLine'] \
        and range['startingLine'] <= line_number <= range['endingLine']

def get_files_of_pull_request(pr_url, token):
    """
    Retrieve the list of files associated with a pull request.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(pr_url, headers=headers)
    response.raise_for_status()
    return response.json()

def file_exists_in_commit(token, owner, repo, commit_sha, filepath):
    """
    Check if a file exists in a specific commit using the GitHub API.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}?ref={commit_sha}"
    response = requests.get(url, headers=headers)
    
    return response.status_code == 200

if __name__ == "__main__":
    main()
