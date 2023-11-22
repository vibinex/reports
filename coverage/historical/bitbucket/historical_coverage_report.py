"""
Bitbucket PR Coverage Analyzer

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

5. Add your config like username, app_password in the script at the top

6. Run the script:
   $ python historical_coverage_report.py
"""
import re
import requests
import json
import base64
from urllib.parse import quote
import inquirer
from tqdm import tqdm
import json
import sys

username = "rtapish"
app_password = "ATBBRrc4kErjKAyBXKXtUTfM5HJB7F388C19"
BASE_URL = "https://api.bitbucket.org/2.0"
NUM_CHARS_DIFF = 4

credentials = f"{username}:{app_password}"
base64_encoded_credentials = base64.b64encode(credentials.encode()).decode()


def main():
    """
    Main function to initiate the script.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }

    all_workspaces = get_workspaces(headers)
    # Prompt user for workspace selection
    selected_workspaces = prompt_for_workspaces(all_workspaces)

    report = {
        'total_coverage': 0,
        'workspace_considered': 0,
        'workspaces': [],
        'skipped_workspaces': []
    }

    for workspace in tqdm(selected_workspaces, desc='Processing workspaces:'):
        try:
            process_workspace(workspace, headers, report)
        except Exception as e:
            report['skipped_workspaces'].append({
                'name': workspace['name'],
                'reason': f"[ERROR] Something went wrong while processing the workspace {workspace}:" + str(e),
            })

    if report['workspace_considered'] == 0:
        print("No workspace with valid repos, unable to perform coverage calculation")
        return
    
    for workspace in report['workspaces']:
        print(f"[Workspace: {workspace['name']}] coverage: {workspace['coverage'] * 100:.2f} across {workspace['repos_considered']} repositories")
        for repo in workspace['repositories']:
            print(f"  [Repo: {repo['name']}] coverage: {repo['coverage'] * 100:.2f} across {repo['prs_considered']} pull requests")
            for pr in repo['pull_requests']:
                print(f"    [PR: {pr['id']}] coverage: {pr['coverage'] * 100:.2f}")
    report['total_coverage'] /= report['workspace_considered']
    print(f"Workspaces analyzed: {report['workspace_considered']}")
    print(f"Total coverage across all workspaces: {report['total_coverage'] * 100:.2f}")
    with open('report.json', 'w') as f:
        json.dump(report, f, indent=4)
    sys.stderr.flush()

def process_workspace(workspace, token, report={'total_coverage': 0, 'workspace_considered': 0}):
    """
    Process each workspace and calculate the coverage.
    """
    all_repos = get_repositories(token, workspace)
    selected_repos = prompt_for_repositories(all_repos)

    workspace_report = {
        'name': workspace,
        'coverage': 0,
        'repos_considered': 0,
        'repositories': [],
        'skipped_repos': []
    }

    for repo in tqdm(selected_repos, desc=f"  Processing repos in {workspace}:", leave=False):
        try:
            process_repo(workspace_report, repo, workspace, token)
        except Exception as e:
            workspace_report['skipped_repos'].append({
                'name': f"{workspace}/{repo['slug']}",
                'reason': f"[ERROR] Something went wrong while processing the repo {workspace}/{repo['slug']}:" + str(e)
            })
    if workspace_report['repos_considered'] == 0:
        report['skipped_workspaces'].append({
            'name': workspace,
            'reason': f"No valid repos in workspace {workspace}, not including in coverage calculation"
        })
        return
    report['workspace_considered'] += 1
    workspace_report['coverage'] /= workspace_report['repos_considered']
    report['total_coverage'] += workspace_report['coverage']
    report['workspaces'].append(workspace_report)

def process_repo(workspace_report, repo, workspace, token):
    """
    Process each repository within a workspace and calculate the coverage.
    """
    repo_report = {
        'name': repo['slug'],
        'coverage': 0,
        'prs_considered': 0,
        'pull_requests': [],
        'skipped_prs': []
    }
    commit_cache = {}
    diff_cache = {}
    for pr in tqdm(get_pull_requests(token, workspace, repo['slug']), desc=f"    Processing PRs in {workspace}/{repo['slug']}:", leave=False):
        try:
            process_pr(repo_report, pr, repo, workspace, commit_cache, diff_cache)
        except Exception as e:
            repo_report['skipped_prs'].append({
                'pr_id': f"{workspace}/{repo['slug']}/{pr.get('id', str(pr))}",
                'reason': f"[ERROR] Something went wrong while processing the pull request {workspace}/{repo}/{pr.get('id', str(pr))}:" + str(e)
            })
    if repo_report['prs_considered'] == 0:
        workspace_report['skipped_repos'].append({
            'name': f"{workspace}/{repo['slug']}",
            'reason': f"No valid prs in repo {repo['slug']}, not including in coverage calculation"
        })
        return
    workspace_report['repos_considered'] += 1
    repo_report['coverage'] /= repo_report['prs_considered']
    workspace_report['coverage'] += repo_report['coverage']
    workspace_report['repositories'].append(repo_report)

def process_pr(repo_report, pr, repo, workspace, commit_cache, diff_cache):
    """
    Process each pull request within a repository and calculate the coverage.
    """
    if pr["state"] != "MERGED":
        repo_report['skipped_prs'].append({
            'pr_id': f"{workspace}/{repo['slug']}/{pr.get('id', str(pr))}",
            'reason': f"PR #{pr['id']} is not merged, not included in coverage calculation"
        })
        return
    reviewers = get_reviewers_from_activity(workspace, repo['slug'], pr['id'])
    if 'merge_commit' in pr:
        reviewers = add_merge_user(reviewers, pr["merge_commit"]["links"]["self"]["href"])
    reviewer_names = [reviewer['display_name'] for reviewer in reviewers.values()]
    total_unapproved_deletions = 0
    total_deletions = 0
    total_unassigned = set()
    old_commit_hash = pr['source']['commit']['hash']
    new_commit_hash = pr['destination']['commit']['hash']
    for file in tqdm(get_files_of_pull_request(workspace, repo['slug'], old_commit_hash, new_commit_hash), desc=f"      Processing files in PR #{pr['id']}:", leave=False):
        total_unapproved_deletions, total_deletions, total_unassigned = process_file(total_unapproved_deletions, total_deletions, total_unassigned, file, pr, repo, workspace, reviewer_names, commit_cache, diff_cache)
    if total_deletions == 0:
        repo_report['skipped_prs'].append({
            'pr_id': f"{workspace}/{repo['slug']}/{pr.get('id', str(pr))}",
            'reason': f"No non-author deletions in PR #{pr['id']}, not included in coverage calculation"
        })
        return
    if total_unapproved_deletions < 1 :
        coverage_percentage = 1
    else:
        coverage_percentage = 1 - (total_unapproved_deletions / total_deletions)
    repo_report['coverage'] += coverage_percentage
    repo_report['prs_considered'] += 1
    repo_report['pull_requests'].append({
        'id': pr['id'],
        'author': pr['author']['display_name'],
        'reviewers': reviewer_names,
        'total_deletions': total_deletions,
        'total_unapproved_deletions': total_unapproved_deletions,
        'relevant_authors_who_did_not_review': list(total_unassigned),
        'coverage': coverage_percentage
    })
    # print(f"     Processing PR #{pr['id']} with author: {pr['author']['display_name']} and reviewers: {reviewer_names}")
    # print(f"    Total deletions considered in PR: {total_deletions}, unapproved deletions: {total_unapproved_deletions}, repo_coverage: {repo_report['coverage']}, prs_considered: {repo_report['prs_considered']}")
    # print(f"    ============<Coverage percentage for Merged PR #{pr['id']}: {coverage_percentage * 100:.2f}%>=============")

def process_file(total_unapproved_deletions, total_deletions, total_unassigned, file, pr, repo, workspace, reviewers, commit_cache, diff_cache):
    """
    Process each file within a pull request and calculate the coverage.
    """
    # print(f"            Processing file: {file}")
    if not file or 'old' not in file or not file['old']:
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    if file and 'lines_removed' in file and file['lines_removed'] > 2000:
        # printf(f"       Unable to process file: {file['filename']}, cant handle file diffs larger than 2000 deletions")
        return (total_unapproved_deletions, total_deletions, total_unassigned)
    old_commit_hash = pr['source']['commit']['hash']
    new_commit_hash = pr['destination']['commit']['hash']
    filepath = file['old']['path']
    diff = get_diff(workspace, repo['slug'], old_commit_hash, new_commit_hash, filepath)
    unapproved_deletions_file, total_deletions_file, unassigned_authors = calculate_coverage_percentage(workspace, repo, pr, file, diff, reviewers, commit_cache, diff_cache)
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

def get_workspaces(headers):
    """
    Retrieve the list of workspaces for the authenticated user.
    """
    url = f"{BASE_URL}/workspaces?sort=-updated_on"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return [workspace['slug'] for workspace in data['values']]

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

def get_repositories(headers, workspace):
    """
    Retrieve the list of repositories for a given workspace.
    """
    url = f"{BASE_URL}/repositories/{workspace}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    repos = data['values']
    total_repos = data['size']
    with tqdm(total=total_repos, initial=len(repos), desc=f"  Fetching repos", leave=False) as progress_bar:
        while 'next' in data:
            url = data['next']
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            repos.extend(data['values'])
            progress_bar.update(len(data['values']))
    return repos

def prompt_for_repositories(all_repositories):
    """
    Prompt the user to select the repositories they want to analyze using checkboxes.
    """
    options = [repo['slug'] for repo in all_repositories]
    questions = [
        inquirer.Checkbox('repositories',
                          message="Select the repositories you want to analyze",
                          choices=options,
                          default=options,
                          ),
    ]

    answers = inquirer.prompt(questions)

    selected_repos = [repo for repo in all_repositories if repo.get('slug') in answers['repositories']]
    return selected_repos

def get_pull_requests(headers, workspace, repo_name):
    """
    Retrieve the list of pull requests for a given repository.
    """
    url = f"{BASE_URL}/repositories/{workspace}/{repo_name}/pullrequests?state=MERGED&sort=-updated_on"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    prs = data['values']
    with tqdm(total=data['size'], initial=len(data['values']), desc=f"    Fetching pull requests", leave=False) as progress_bar:
        while 'next' in data:
            url = data['next']
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            prs.extend(data['values'])
            progress_bar.update(len(data['values']))
    return prs

def get_diff(workspace, repo_slug, old_commit_id, new_commit_id, filepath):
    """
    Retrieve the diff for a specific file between two commits in Bitbucket.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    url = f"{BASE_URL}/repositories/{workspace}/{repo_slug}/diff/{old_commit_id}..{new_commit_id}"
    params = {"path": filepath}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.text

def get_blame(workspace, repo_slug, commit, path):
    """
    Retrieve the blame information for a file in a specific commit in Bitbucket.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    encoded_path = quote(path)
    print(f"cred = {base64_encoded_credentials}")
    url = f"{BASE_URL}/repositories/{workspace}/{repo_slug}/src/{commit}/{encoded_path}"
    params = {
        "annotate": "true"
    }
    print(f"url = {url}")
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    print(f"response = {json.dumps(response)}")
    return response.text

def get_reviewers_from_activity(workspace, repo_name, pr_id):
    """
    Retrieve the set of reviewers for a specified pull request from the activity feed.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    url = f"{BASE_URL}/repositories/{workspace}/{repo_name}/pullrequests/{pr_id}/activity"
    
    reviewer_dict = {}
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        activity_data = response.json()
        
        # Extracting users from the 'reviewers' list in the activity data
        for activity in activity_data['values']:
            if 'update' in activity and 'reviewers' in activity['update']:
                for reviewer in activity['update']['reviewers']:
                    serialized_reviewer = json.dumps(reviewer, sort_keys=True)
                    reviewer_dict[serialized_reviewer] = reviewer
        
        # Check for the next page
        url = activity_data.get('next', None)
    
    return reviewer_dict

def add_merge_user(reviewers, merge_commit_url):
    """
    Retrieve the user who merged the PR using the merge_commit_url.
    If the merge user is not in the reviewers list, add them.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    response = requests.get(merge_commit_url, headers=headers)
    response.raise_for_status()
    commit_data = response.json()
    
    # Extracting the author of the merge commit
    merge_user = commit_data['author']['user']
    serialized_merge_user = json.dumps(merge_user, sort_keys=True)
    if serialized_merge_user not in reviewers:
        reviewers[serialized_merge_user] = merge_user
    return reviewers

def get_files_of_pull_request(workspace, repo_slug, old_commit_id, new_commit_id):
    """
    Retrieve the list of files associated with a pull request in Bitbucket.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    spec = f"{old_commit_id}..{new_commit_id}"
    url = f"{BASE_URL}/repositories/{workspace}/{repo_slug}/diffstat/{spec}"
    
    all_files = []
    
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        all_files.extend(data['values'])
        
        # Check for the next page
        url = data.get('next', None)
    
    return all_files

def calculate_coverage_percentage(workspace, repo, pr, file, diff, reviewers, commit_cache, diff_cache):
    """
    Calculate the coverage percentage based on the diff and blame information.
    """
    unapproved_deletions = 0
    deleted_lines = get_deleted_lines(diff)
    if len(deleted_lines) == 0:
        return (None, 0, None)
    total_deletions = 0
    unassigned_relevant = set()
    commit_id = pr['source']['commit']['hash']
    file_path = file['old']['path']
    # First, get the list of commits for the file up to the base commit.
    commits = get_commits_for_file(workspace, repo['slug'], file_path, commit_id)
    if not commits:
        sys.stderr.write(f"[{workspace}/{repo['slug']}/{pr['id']}/{file['filename']}] No commits for file diff: {diff}")
        return None
    # Then, fetch the diffs for each of these commits.
    diffs = [get_diff_for_commit(workspace, repo['slug'], commit["hash"], file_path, diff_cache) for commit in commits]
    if not diffs:
        sys.stderr.write(f"[{workspace}/{repo['slug']}/{pr['id']}/{file['filename']}] no diffs for commits: {commits}")
        return None
    skipped_users = set()
    for line in tqdm(deleted_lines, desc='        Calculating coverage:', leave=False):
        blame_author = reconstruct_blame(commits, diffs, line, commit_cache)
        if not blame_author:
            sys.stderr.write(f"[{workspace}/{repo['slug']}/{pr['id']}/{file['filename']}] No blame author found for line : {line} in file diff: {file['old']['path']}, will be considered approved")
            continue
        if 'user' not in blame_author:
            skipped_users.add(json.dumps(blame_author, sort_keys=True))
            continue
        if blame_author['user']['display_name'] == pr['author']['display_name']:
            continue
        total_deletions += 1
        if blame_author['user']['display_name'] not in reviewers:
            unapproved_deletions += 1
            unassigned_relevant.add(blame_author['user']['display_name'])
    if skipped_users:
        sys.stderr.write(f"[{workspace}/{repo['slug']}/{pr['id']}/{file['filename']}] Skipped Users = {skipped_users}")
    return (unapproved_deletions, total_deletions, unassigned_relevant)

def get_deleted_lines(diffstr):
    diff_changes_pattern = re.compile(r"@@ \-\d+,(\d+) \+\d+,\d+ @@")
    difflines = diffstr.splitlines()
    deleted_lines = []
    i = 0
    while i < len(difflines):
        diff = difflines[i]
        changed_blocks = diff_changes_pattern.findall(diff)
        if not changed_blocks:
            i += 1
            continue
        num_lines = int(changed_blocks[0])
        for j in range(i+1, i+num_lines):
            if difflines[j].startswith("-"):
                diff_line = difflines[j][1:].strip()
                if len(diff_line) < NUM_CHARS_DIFF:
                    continue
                deleted_lines.append(diff_line)
        i += num_lines
    return deleted_lines

def line_exists_in_range(blame_line, line_number):
    return blame_line['line_number'] == line_number

def reconstruct_blame(commits, diffs, current_line, commit_cache):
    """Reconstruct the blame using the diffs."""
    for i, diff in enumerate(diffs):
        if diff:
            for line in diff.splitlines():
                if line.startswith("+"):
                    actual_line = line[1:].strip()
                    if len(actual_line) < NUM_CHARS_DIFF:
                        continue
                    if actual_line == current_line:
                        commit_author = get_commit_author(commits[i]['links']['self']['href'], commit_cache)
                        return commit_author
    return None
def get_commits_for_file(workspace, repo_slug, file_path, commit_id):
    """Fetch the list of commits for the file using the filehistory endpoint."""
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    commits = []
    url = f"{BASE_URL}/repositories/{workspace}/{repo_slug}/filehistory/{commit_id}/{file_path}"
    while url:
        response = requests.get(url, headers=headers)
        if not response.ok:
            sys.stderr.write(f"[{workspace}/{repo_slug}/{commit_id}/{file_path}] [get_commits_for_file] error in file-history response = {response.text}")
            return None
        data = response.json()
        commits.extend([value["commit"] for value in data["values"]])
        url = data.get("next", None)
    return commits


def get_diff_for_commit(workspace, repo_slug, commit_id, filepath, diff_cache):
    """Fetch the diff for a specific commit."""
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    cache_key = f'{commit_id}-{filepath}'
    if cache_key in diff_cache:
        return diff_cache[cache_key]
    url = f"{BASE_URL}/repositories/{workspace}/{repo_slug}/diff/{commit_id}"
    params = {"path": filepath}
    response = requests.get(url, headers=headers, params=params)
    if not response.ok:
        sys.stderr.write(f"[{workspace}/{repo_slug}] No diff for commit: {commit_id}, file: {filepath}")
        return None
    diff = response.text
    diff_cache[cache_key] = diff
    return diff

def get_commit_author(commit_url, commit_cache):
    """
    Get commit author
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }
    cache_key = f'{commit_url}'
    if cache_key in commit_cache:
        return commit_cache[cache_key]
    response = requests.get(commit_url, headers=headers)
    if not response.ok:
        sys.stderr.write(f"\t[get_commit_author] error in getting commit from URL {commit_url} = {response.text}")
        return None
    response_json = response.json()
    author = response_json["author"]
    commit_cache[cache_key] = author
    return author


if __name__ == "__main__":
    main()
