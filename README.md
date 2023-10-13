# Repository Coverage Report

This repository contains scripts to generate the coverage report of merged pull requests based on the number of deletions that were reviewed for both GitHub and Bitbucket.

## Table of Contents

- [About Coverage Percentage](#about-coverage-percentage)
- [GitHub PR Coverage Analyzer](#github-pr-coverage-analyzer)
- [Bitbucket PR Coverage Analyzer](#bitbucket-pr-coverage-analyzer)

## About Coverage Percentage

Coverage Percentage in this context refers to the percentage of deletions in merged pull requests that were reviewed. It provides an insight into how much of the code that was removed was actually looked at by reviewers. A higher percentage indicates that more of the deleted code was reviewed, ensuring that the removal was appropriate and didn't introduce any issues.

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

**Note**: Always ensure you have the necessary permissions and tokens to access and analyze repositories.