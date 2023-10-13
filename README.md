# Repository Coverage Report

This repository contains scripts to generate coverage report for github and bitbucket. Sample output - 
```
Workspace: alokit-innovations
  Repository: dev-profiler
        Processing Pr #10
     Processing PR #10 with author: vibi-test and reviewers: ['Tapish Rathore', 'vibi-test']
    Total deletions considered in PR: 12, unapproved deletions: 0, repo_coverage: 1, prs_considered: 1
    ============<Coverage percentage for Merged PR #10: 100.00%>=============
        Processing Pr #4
        No non-author deletions in PR #4, not included in coverage calculation
        Processing Pr #2
        No non-author deletions in PR #2, not included in coverage calculation
        Processing Pr #1
        No non-author deletions in PR #1, not included in coverage calculation
    # of prs considered = 1 in repo dev-profiler. workspace_coverage: 1.0
    ~~~~~~~~~~~~><><><><><><Coverage percentage for Repository dev-profiler = 100.00%><>><><><><~~~~~~~~~~~~~~
  Repository: repo-profiler-pipe
        Processing Pr #7
        No non-author deletions in PR #7, not included in coverage calculation
        Processing Pr #6
    ============<Relevant authors who did not review the PR: {'Tapish Rathore'}>=============
     Processing PR #6 with author: Avikalp Gupta and reviewers: ['Avikalp Gupta']
    Total deletions considered in PR: 3, unapproved deletions: 3, repo_coverage: 0.0, prs_considered: 1
    ============<Coverage percentage for Merged PR #6: 0.00%>=============
        Processing Pr #5
        No non-author deletions in PR #5, not included in coverage calculation
        Processing Pr #4
        No non-author deletions in PR #4, not included in coverage calculation
        Processing Pr #3
            Skipped Users = {'{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
        No non-author deletions in PR #3, not included in coverage calculation
        Processing Pr #2
            Skipped Users = {'{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
        No non-author deletions in PR #2, not included in coverage calculation
        Processing Pr #1
            Skipped Users = {'{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
            Skipped Users = {'{"raw": "Bitbucket Pipelines Push Bot <commits-noreply@bitbucket.org>", "type": "author"}', '{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
            Skipped Users = {'{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
            Skipped Users = {'{"raw": "Bitbucket Pipelines Push Bot <commits-noreply@bitbucket.org>", "type": "author"}', '{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
            Skipped Users = {'{"raw": "bitbucket-pipelines <commits-noreply@bitbucket.org>", "type": "author"}'}
        No non-author deletions in PR #1, not included in coverage calculation
    # of prs considered = 1 in repo repo-profiler-pipe. workspace_coverage: 1.0
    ~~~~~~~~~~~~><><><><><><Coverage percentage for Repository repo-profiler-pipe = 0.00%><>><><><><~~~~~~~~~~~~~~
  Repository: pipeline-testing
No valid prs in repo pipeline-testing, not including in coverage calculation
  Repository: pipeline
No valid prs in repo pipeline, not including in coverage calculation
  Repository: demo-repo
        Processing Pr #3
        No non-author deletions in PR #3, not included in coverage calculation
        Processing Pr #2
        No non-author deletions in PR #2, not included in coverage calculation
No valid prs in repo demo-repo, not including in coverage calculation
Total repos considered = 2, total_coverage = 0.5
######################### Coverage percentage for Workspace alokit-innovations = 50.00% #####################################
Workspaces analyzed: 1
Total coverage across all workspaces: 50.00
```

## Table of Contents

- [About Coverage Percentage](#about-coverage-percentage)
- [GitHub PR Coverage Analyzer](#github-pr-coverage-analyzer)
- [Bitbucket PR Coverage Analyzer](#bitbucket-pr-coverage-analyzer)

## About Coverage Percentage

In a pull/merge request, if the author overwrites a developer's code but fails to get the overwritten code reviewed by that developer, we call it unreviewed or un-'covered' code. 

Example - In a pull/merge request, out of 100 lines of code in the diff, 20 lines are uncovered/unreviewed. The coverage is 80%.

A higher coverage percent is good and indicates how much of the code that was overwritten was actually looked at by reviewers. A higher percentage indicates that more of the overwritten code was reviewed, ensuring that the change was appropriate and didn't introduce any issues.

## GitHub PR Coverage Analyzer

### Description

This script calculates the coverage percentage of merged pull requests on GitHub based on the number of deletions that were reviewed.

### How to run:

1. Get a [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) from your github account. The script needs read permissions on account, repository, pull request, organization.

2. Create a new virtual environment:
    ```bash
    virtualenv venv
    ```

3. Activate the virtual environment:
- On Windows: 
  ```bash
  venv\Scripts\activate
  ```
- On macOS and Linux: 
  ```bash
  source venv/bin/activate
  ```

4. Install the required packages:
  ```bash
  pip install -r requirements.txt
  ```

5. Run the script:
  ```bash
  python historical_coverage_report.py
  ```

6. When prompted, enter the personal access token generated in step 1. If you use github cloud, you don't need to provide BASE_URL, just press Enter. Otherwise, enter your github organization's url.

## Bitbucket PR Coverage Analyzer

### Description

This script is similar to the GitHub PR Coverage Analyzer but is tailored for Bitbucket Cloud repositories. It calculates the coverage percentage of merged pull requests on Bitbucket based on the number of deletions that were reviewed.

### How to run:

1. Get an [app password](https://support.atlassian.com/bitbucket-cloud/docs/create-an-app-password/) from your bitbucket account. The script needs read permissions on account, repository, merge request, workspace, email.

2. Create a new virtual environment:
    ```bash
    virtualenv venv
    ```

3. Activate the virtual environment:
- On Windows: 
  ```bash
  venv\Scripts\activate
  ```
- On macOS and Linux: 
  ```bash
  source venv/bin/activate
  ```

4. Install the required packages:
  ```bash
  pip install -r requirements.txt
  ```

5. Replace `username` and `app_password` at the top of the script with your username and the app password generated in step 1

6. Run the script:
  ```bash
  python historical_coverage_report.py
  ```

---
