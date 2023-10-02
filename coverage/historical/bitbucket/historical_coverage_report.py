from datetime import datetime
import re
import requests
import json
import base64
from urllib.parse import quote



BASE_URL = "https://api.bitbucket.org/2.0"
username = "rtapish"
app_password = "ATBBRrc4kErjKAyBXKXtUTfM5HJB7F388C19"
credentials = f"{username}:{app_password}"
base64_encoded_credentials = base64.b64encode(credentials.encode()).decode()
NUM_CHARS_DIFF = 4


def main():
    """
    Main function to initiate the script.
    """
    headers = {
        "Authorization": f"Basic {base64_encoded_credentials}"
    }

    total_coverage = 0
    workspace_considered = 0
    for workspace in get_workspaces(headers):
        total_coverage, workspace_considered = process_workspace(total_coverage, workspace_considered, workspace, headers)
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
    print(f"  Repository: {repo['slug']}")
    repo_coverage = 0
    prs_considered = 0
    commit_cache = {}
    diff_cache = {}
    for pr in get_pull_requests(token, workspace, repo['slug']):
        print(f"        Processing Pr #{pr['id']}")
        repo_coverage, prs_considered = process_pr(repo_coverage, prs_considered, pr, repo, workspace, commit_cache, diff_cache)
    if prs_considered == 0:
        print(f"No valid prs in repo {repo['slug']}, not including in coverage calculation")
        return (workspace_coverage, repos_considered)
    repos_considered += 1
    repo_coverage /= prs_considered
    workspace_coverage += repo_coverage
    print(f"    # of prs considered = {prs_considered} in repo {repo['slug']}. workspace_coverage: {workspace_coverage}")
    print(f"    ~~~~~~~~~~~~><><><><><><Coverage percentage for Repository {repo['slug']} = {repo_coverage * 100:.2f}%><>><><><><~~~~~~~~~~~~~~")
    return (workspace_coverage, repos_considered)

def process_pr(repo_coverage, prs_considered, pr, repo, workspace, commit_cache, diff_cache):
    """
    Process each pull request within a repository and calculate the coverage.
    """
    if pr["state"] == "MERGED":
        reviewers = get_reviewers_from_activity(workspace, repo['slug'], pr['id'])
        if 'merge_commit' in pr:
            reviewers = add_merge_user(reviewers, pr["merge_commit"]["links"]["self"]["href"])
        reviewer_names = [reviewer['display_name'] for reviewer in reviewers.values()]
        total_unapproved_deletions = 0
        total_deletions = 0
        total_unassigned = set()
        old_commit_hash = pr['source']['commit']['hash']
        new_commit_hash = pr['destination']['commit']['hash']
        for file in get_files_of_pull_request(workspace, repo['slug'], old_commit_hash, new_commit_hash):
           total_unapproved_deletions, total_deletions, total_unassigned = process_file(total_unapproved_deletions, total_deletions, total_unassigned, file, pr, repo, workspace, reviewer_names, commit_cache, diff_cache)
        if total_deletions == 0:
            print(f"        No non-author deletions in PR #{pr['id']}, not included in coverage calculation")
            return (repo_coverage, prs_considered)
        if total_unapproved_deletions < 1 :
            coverage_percentage = 1
        else:
            coverage_percentage = 1 - (total_unapproved_deletions / total_deletions)
            print(f"    ============<Relevant authors who did not review the PR: {total_unassigned}>=============")        
        repo_coverage += coverage_percentage
        prs_considered += 1
        print(f"     Processing PR #{pr['id']} with author: {pr['author']['display_name']} and reviewers: {reviewer_names}")
        print(f"    Total deletions considered in PR: {total_deletions}, unapproved deletions: {total_unapproved_deletions}, repo_coverage: {repo_coverage}, prs_considered: {prs_considered}")
        print(f"    ============<Coverage percentage for Merged PR #{pr['id']}: {coverage_percentage * 100:.2f}%>=============")
    return (repo_coverage, prs_considered)

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
    # blame = get_blame(workspace, repo, old_commit_hash, filepath)
    # print(f"\n\n\n\n pr = {pr}")
    # if not blame:
    #     print(f"Could not get blame for commit: {pr['baseRefOid']}, file: {file['filename']}")
    #     return (total_unapproved_deletions, total_deletions, total_unassigned)
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
    url = f"{BASE_URL}/workspaces"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return [workspace['slug'] for workspace in data['values']]

def get_repositories(headers, workspace):
    """
    Retrieve the list of repositories for a given workspace.
    """
    url = f"{BASE_URL}/repositories/{workspace}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return [repo for repo in data['values']]

def get_pull_requests(headers, workspace, repo_name):
    """
    Retrieve the list of pull requests for a given repository.
    """
    url = f"{BASE_URL}/repositories/{workspace}/{repo_name}/pullrequests?state=MERGED"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data['values']

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
        print(f"No commits for file diff: {diff}")
        return None
    # Then, fetch the diffs for each of these commits.
    diffs = [get_diff_for_commit(workspace, repo['slug'], commit["hash"], file_path, diff_cache) for commit in commits]
    if not diffs:
        print(f"[calculate_coverage_percentage] no diffs for commits: {commits}")
        return None
    skipped_users = set()
    for line in deleted_lines:
        blame_author = reconstruct_blame(commits, diffs, line, commit_cache)
        if not blame_author:
            print(f"No blame author found for line : {line} in file diff: {file['old']['path']}, will be considered approved")
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
        print(f"            Skipped Users = {skipped_users}")
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
            print(f"[get_commits_for_file] error in response = {response.text}")
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
        print(f"No diff for commit: {commit_id}, file: {filepath}")
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
        print(f"[get_commit_author] error in response = {response.text}")
        return None
    response_json = response.json()
    author = response_json["author"]
    commit_cache[cache_key] = author
    return author


if __name__ == "__main__":
    main()
