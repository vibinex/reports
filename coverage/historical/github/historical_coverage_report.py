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
   $ python historical_coverage_report.py 2> error.log

When prompted, enter your GitHub token. Optionally, you can also provide a custom API URL or use the default (https://api.github.com).

"""
import re
import requests
import inquirer
from tqdm import tqdm
import json
import sys
import traceback

BASE_URL = "https://api.github.com"

def main():
    """
    Main function to initiate the script.
    """
    # Printing prompts separately because input() prompts are printed in stderr for some operating systems
    sys.stdout.write("Enter your GitHub token: ")
    token = input()
    sys.stdout.write("Enter the base API URL (press Enter to use the default): ")
    BASE_URL = input()
    if not BASE_URL:
        BASE_URL = "https://api.github.com"

    all_workspaces = get_workspaces(token)
    selected_workspaces = prompt_for_workspaces(all_workspaces)

    report = {
        'total_coverage': 0,
        'workspace_considered': 0,
        'workspaces': [],
        'skipped_workspaces': []
    }

    try:
        for workspace in tqdm(selected_workspaces, desc='Processing workspaces:', file=sys.stdout):
            try:
                process_workspace(report, workspace, token)
            except KeyboardInterrupt as ki:
                raise KeyboardInterrupt(*ki.args)
            except Exception as e:
                report['skipped_workspaces'].append({
                    'name': workspace,
                    'reason': f"[ERROR] Something went wrong while processing the workspace {workspace}: " + f"{type(e).__name__}: {str(e)}" + "\n\t" + traceback.format_exc()
                })
    except KeyboardInterrupt as ki:
        if "manual" not in ki.args:
            print("\n\nKeyboardInterrupt received, exiting...")
        if len(report['workspaces']) > 0:
            report['total_coverage'] /= len(report['workspaces'])
        print("\n\nGenerating report...")
        with open('report.json', 'w') as f:
            json.dump(report, f, indent=4)
        sys.stderr.flush()
        sys.exit(1)

    if report['workspace_considered'] == 0:
        print("No workspace with valid repos, unable to perform coverage calculation")
        with open('report.json', 'w') as f:
            json.dump(report, f, indent=4)
        sys.stderr.flush()
        return

    for workspace in report['workspaces']:
        print(f"[Workspace: {workspace['name']}] coverage: {workspace['coverage'] * 100:.2f} across {workspace['repos_considered']} repositories")
        for repo in workspace['repositories']:
            print(f"  [Repo: {repo['name']}] coverage: {repo['coverage'] * 100:.2f} across {repo['prs_considered']} pull requests")
    report['total_coverage'] /= report['workspace_considered']
    print(f"Workspaces analyzed: {report['workspace_considered']}")
    print(f"Total coverage across all workspaces: {report['total_coverage'] * 100:.2f}")
    with open('report.json', 'w') as f:
        json.dump(report, f, indent=4)
    sys.stderr.flush()
        
def process_workspace(report, workspace, token):
    """
    Process each workspace and calculate the coverage.
    """
    keyboard_interrupted = False
    all_repositories = get_repositories(token, workspace)
    selected_repositories = prompt_for_repositories(all_repositories)

    workspace_report = {
        'name': workspace,
        'coverage': 0,
        'repos_considered': 0,
        'repositories': [],
        'skipped_repos': []
    }
    try:
        for repo in tqdm(selected_repositories, desc=f"  Processing repos in {workspace}:", leave=False, file=sys.stdout):
            try:
                process_repo(workspace_report, repo, workspace, token)
            except Exception as e:
                workspace_report['skipped_repos'].append({
                    'name': f"{workspace}/{repo}",
                    'reason': f"[ERROR] Something went wrong while processing the repo {workspace}/{repo}: " + f"{type(e).__name__}: {str(e)}" + "\n\t" + traceback.format_exc()
                })
                continue
    except KeyboardInterrupt as ki:
        if "manual" not in ki.args:
            print("\n\nKeyboardInterrupt received, exiting...")
        keyboard_interrupted = True
    finally:
        if workspace_report['repos_considered'] == 0:
            report['skipped_workspaces'].append({
                'name': workspace,
                'reason': f"No valid repos in workspace {workspace}"+ (" (possibly because of KeyboardInterrupt)" if keyboard_interrupted else "") + ", not including in coverage calculation",
                'repositories': workspace_report['skipped_repos']
            })
        else:
            report['workspace_considered'] += 1
            workspace_report['coverage'] /= workspace_report['repos_considered']
            report['total_coverage'] += workspace_report['coverage']
            report['workspaces'].append(workspace_report)
    if keyboard_interrupted:
        raise KeyboardInterrupt("manual")

def process_repo(workspace_report, repo, workspace, token):
    """
    Process each repository within a workspace and calculate the coverage.
    """
    keyboard_interrupted = False
    repo_report = {
        'name': repo,
        'coverage': 0,
        'prs_considered': 0,
        'pull_requests': [],
        'skipped_prs': []
    }
    try:
        for pr in tqdm(get_pull_requests(token, workspace, repo), desc=f"    Processing PRs in {repo}:", leave=False, file=sys.stdout):
            try:
                process_pr(repo_report, pr, repo, workspace, token)
            except KeyboardInterrupt as ki:
                raise KeyboardInterrupt(*ki.args)
            except Exception as e:
                repo_report['skipped_prs'].append({
                    'pr_id': f"{workspace}/{repo}/{pr.get('number', str(pr))}",
                    'reason': f"[ERROR] Something went wrong while processing the pull request {workspace}/{repo}/{pr.get('number', str(pr))}: " + f"{type(e).__name__}: {str(e)}" + "\n\t" + traceback.format_exc()
                })
                continue
    except KeyboardInterrupt as ki:
        if "manual" not in ki.args:
            print("\n\nKeyboardInterrupt received, exiting...")
        keyboard_interrupted = True
    finally:
        if repo_report['prs_considered'] == 0:
            workspace_report['skipped_repos'].append({
                'name': f"{workspace}/{repo}",
                'reason': f"No valid prs in repo {repo}"+ (" (possibly because of KeyboardInterrupt)" if keyboard_interrupted else "") + ", not including in coverage calculation",
                'skipped_prs': repo_report['skipped_prs']
            })
        else:
            workspace_report['repos_considered'] += 1
            repo_report['coverage'] /= repo_report['prs_considered']
            workspace_report['coverage'] += repo_report['coverage']
            workspace_report['repositories'].append(repo_report)
    return

def process_pr(repo_report, pr, repo, workspace, token):
    """
    Process each pull request within a repository and calculate the coverage.
    """
    keyboard_interrupted = False
    if pr["state"] != "MERGED":
        repo_report['skipped_prs'].append({
            'pr_id': f"{workspace}/{repo}/{pr.get('number', str(pr))}",
            'reason': f"PR #{pr['number']} is not merged, not included in coverage calculation"
        })
        return

    pr_report = {
        'id': pr.get('number', str(pr)),
        'author': pr['author']['login'],
        'reviewers': set(),
        'merged_by': pr['mergedBy']['login'],
        'coverage': 0,
        'total_unapproved_deletions': 0,
        'total_deletions': 0,
        'non_reviewer_relevant_authors': set(),
        'file_level_error_logs': []
    }
    try:
        pr_report['reviewers'] = set([review['author']['login'] for review in pr['reviews']['nodes']])
        if 'mergedBy' in pr and pr['mergedBy']['login'] not in pr_report['reviewers']:
            pr_report['reviewers'].add(pr['mergedBy']['login'])
        get_files_url = f"{BASE_URL}/repos/{workspace}/{repo}/pulls/{pr['number']}/files"
        for file in tqdm(get_files_of_pull_request(get_files_url, token), desc=f"      Processing files in PR #{pr['number']}:", leave=False, file=sys.stdout):
            process_file(pr_report, file, pr, repo, workspace, token)
    except KeyboardInterrupt as ki:
        if "manual" not in ki.args:
            print("\n\nKeyboardInterrupt received, exiting...")
        keyboard_interrupted = True
    finally:
        if pr_report['total_deletions'] == 0:
            repo_report['skipped_prs'].append({
                'pr_id': f"{workspace}/{repo}/{pr.get('number', str(pr))}",
                'reason': f"No non-author deletions in PR #{pr['number']}"+ (" (possibly because of KeyboardInterrupt)" if keyboard_interrupted else "") + ", not included in coverage calculation"
            })
        else:
            if pr_report['total_unapproved_deletions'] < 1 :
                pr_report['coverage'] = 1
            else:
                pr_report['coverage'] = 1 - (pr_report['total_unapproved_deletions'] / pr_report['total_deletions'])
            repo_report['coverage'] += pr_report['coverage']
            repo_report['prs_considered'] += 1
            pr_report['non_reviewer_relevant_authors'] = list(pr_report['non_reviewer_relevant_authors'])
            pr_report['reviewers'] = list(pr_report['reviewers'])
            repo_report['pull_requests'].append(pr_report)
    
    if keyboard_interrupted:
        raise KeyboardInterrupt("manual")

def process_file(pr_report, file, pr, repo, workspace, token):
    """
    Process each file within a pull request and calculate the coverage.
    """
    if file and 'deletions' in file and file['deletions'] > 2000:
        pr_report['file_level_error_logs'].append(f"[{file['filename']}] Unable to process file, cant handle file diffs larger than 2000 deletions")
        return
    if not file_exists_in_commit(token, workspace, repo, pr['baseRefOid'], file['filename']):
        pr_report['file_level_error_logs'].append(f"[{file['filename']}] File does not exist in base commit")
        return
    if 'patch' not in file:
        pr_report['file_level_error_logs'].append(f"[{file['filename']}] No patch in file, not included in calculation cover of PR #{pr['number']}.")
        return
    diff = file['patch']
    blame = get_blame_for_commit(token, workspace, repo, pr['baseRefOid'], file['filename'])
    if not blame:
        pr_report['file_level_error_logs'].append(f"[{file['filename']}] WARN: Could not get blame for commit: {pr['baseRefOid']}, file: {file['filename']}")
        return
    unapproved_deletions_file, total_deletions_file, unassigned_authors = calculate_coverage_percentage(diff, blame, pr_report['reviewers'], pr['author']['login'])
    if total_deletions_file == 0:
        pr_report['file_level_error_logs'].append(f"[{file['filename']}] No deletions in file, not included in coverage calculation")
        return
    if unapproved_deletions_file > 0 and (unassigned_authors == None or len(unassigned_authors) == 0):
        # No blame authors found for unapproved deleted lines
        return
    # sys.stderr.write(f"file = {file["filename"]} {unapproved_deletions_file} {total_deletions_file} {unassigned_authors} {total_unassigned}\n")
    pr_report['total_unapproved_deletions'] += unapproved_deletions_file
    pr_report['total_deletions'] += total_deletions_file
    pr_report['non_reviewer_relevant_authors'] = pr_report['non_reviewer_relevant_authors'].union(unassigned_authors)
    return

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

def prompt_for_workspaces(all_workspaces):
    """
    Prompt the user to select the workspaces they want to analyze using checkboxes.
    """
    questions = [
        inquirer.Checkbox('workspaces',
                          message="Select the workspaces to analyze",
                          choices=all_workspaces,
                          default=all_workspaces,
                          ),
    ]

    answers = inquirer.prompt(questions)

    selected_workspaces = answers['workspaces']
    return selected_workspaces

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
        sys.stderr.write(f"Warning: Organization '{workspace}' not found or no access.")
        return []

def prompt_for_repositories(all_repositories):
    """
    Prompt the user to select the repositories they want to analyze using checkboxes.
    """
    questions = [
        inquirer.Checkbox('repositories',
                          message="Select the repositories you want to analyze",
                          choices=all_repositories,
                          default=all_repositories,
                          ),
    ]

    answers = inquirer.prompt(questions)

    selected_repos = answers['repositories']
    return selected_repos

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
            sys.stderr.write(f"No blame author found for line : {line_number} in blame: {blame}, will be considered approved")
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
