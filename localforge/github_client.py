from ghapi.all import GhApi
import logging
from typing import Optional, List

# Configure logger
logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self, token: str):
        self._github = GhApi(token=token)
    
    def get_issues(self, owner: str, repo: str, label: str) -> List:
        """Get issues with a specific label."""
        try:
            issues = self._github.issues.list(owner=owner, repo=repo, state='open', labels=[label])
            return issues
        except Exception as e:
            logger.error(f'Error fetching issues: {e}')
            raise
    
    def update_issue_state(self, owner: str, repo: str, issue_number: int, state: str) -> bool:
        """Update an issue's state."""
        try:
            self._github.issues.update(owner=owner, repo=repo, issue_number=issue_number, state=state)
            return True
        except Exception as e:
            logger.error(f'Error updating issue {issue_number}: {e}')
            raise
    
    def create_branch(self, owner: str, repo: str, branch_name: str, base_commit: str) -> bool:
        """Create a new branch in the repository."""
        try:
            # Get the repository
            repo_info = self._github.repos.get(owner=owner, repo=repo)
            
            # Create branch from base commit
            self._github.branches.create(
                owner=owner,
                repo=repo,
                data={
                    'ref': f'refs/heads/{branch_name}',
                    'sha': base_commit
                }
            )
            return True
        except Exception as e:
            logger.error(f'Error creating branch {branch_name}: {e}')
            raise
    
    def create_pull_request(self, owner: str, repo: str, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        """Create a pull request."""
        try:
            pr = self._github.pulls.create(
                owner=owner,
                repo=repo,
                data={
                    'title': title,
                    'body': body,
                    'head': head_branch,
                    'base': base_branch
                }
            )
            return {
                'number': pr.number,
                'url': pr.html_url
            }
        except Exception as e:
            logger.error(f'Error creating pull request: {e}')
            raise
