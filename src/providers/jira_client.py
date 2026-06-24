"""
Jira Client
Work with tickets via atlassian-python-api
"""

import logging
from typing import Dict, Any, Optional, List
from atlassian import Jira

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for working with Jira"""
    
    def __init__(self, url: str, email: str, api_token: str):
        """
        Args:
            url: Jira URL (https://your-domain.atlassian.net)
            email: User email
            api_token: API token
        """
        self.url = url
        self.email = email
        self.api_token = api_token
        
        # Initialize Jira client
        self.client = Jira(
            url=url,
            username=email,
            password=api_token,
            cloud=True
        )
        
        logger.info(f"JiraClient initialized for {url}")
    
    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Get issue information"""
        try:
            logger.info(f"Fetching Jira issue: {issue_key}")
            issue = self.client.issue(issue_key)
            
            if not issue:
                return None
            
            fields = issue.get('fields', {})
            
            result = {
                'key': issue.get('key'),
                'id': issue.get('id'),
                'summary': fields.get('summary'),
                'description': fields.get('description'),
                'status': fields.get('status', {}).get('name'),
                'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
                'reporter': fields.get('reporter', {}).get('displayName'),
                'priority': fields.get('priority', {}).get('name') if fields.get('priority') else None,
                'created': fields.get('created'),
                'updated': fields.get('updated'),
                'labels': fields.get('labels', []),
                'issue_type': fields.get('issuetype', {}).get('name'),
                'project': fields.get('project', {}).get('key')
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get issue {issue_key}: {e}")
            raise
    
    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create new issue"""
        try:
            logger.info(f"Creating Jira issue in {project_key}: {summary}")
            
            fields = {
                'project': {'key': project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type}
            }
            
            if priority:
                fields['priority'] = {'name': priority}
            
            if labels:
                fields['labels'] = labels
            
            if assignee:
                fields['assignee'] = {'name': assignee}
            
            issue = self.client.create_issue(fields=fields)
            
            result = {
                'key': issue.get('key'),
                'id': issue.get('id'),
                'self': issue.get('self')
            }
            
            logger.info(f"Issue created: {result['key']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            raise
    
    def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any]
    ) -> bool:
        """Update issue"""
        try:
            logger.info(f"Updating Jira issue: {issue_key}")
            
            self.client.update_issue_field(
                key=issue_key,
                fields=fields
            )
            
            logger.info(f"Issue {issue_key} updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update issue {issue_key}: {e}")
            raise
    
    def transition_issue(
        self,
        issue_key: str,
        transition_name: str
    ) -> bool:
        """Change issue status"""
        try:
            logger.info(f"Transitioning issue {issue_key} to: {transition_name}")
            
            # Get available transitions
            transitions = self.client.get_issue_transitions(issue_key)
            
            transition_id = None
            for t in transitions:
                if t['name'].lower() == transition_name.lower():
                    transition_id = t['id']
                    break
            
            if not transition_id:
                available = [t['name'] for t in transitions]
                raise ValueError(
                    f"Transition '{transition_name}' not found. "
                    f"Available transitions: {', '.join(available)}"
                )
            
            self.client.set_issue_status(issue_key, transition_id)
            
            logger.info(f"Issue {issue_key} transitioned successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to transition issue {issue_key}: {e}")
            raise
    
    def add_comment(
        self,
        issue_key: str,
        comment: str
    ) -> Dict[str, Any]:
        """Add comment to issue"""
        try:
            logger.info(f"Adding comment to issue {issue_key}")
            
            result = self.client.issue_add_comment(issue_key, comment)
            
            comment_data = {
                'id': result.get('id'),
                'body': result.get('body'),
                'author': result.get('author', {}).get('displayName'),
                'created': result.get('created'),
                'updated': result.get('updated')
            }
            
            logger.info(f"Comment added to {issue_key}")
            return comment_data
            
        except Exception as e:
            logger.error(f"Failed to add comment to {issue_key}: {e}")
            raise
    
    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search issues using JQL"""
        try:
            logger.info(f"Searching Jira issues: {jql}")
            
            if fields is None:
                fields = ['summary', 'status', 'assignee', 'priority', 'created']
            
            issues = self.client.jql(jql, limit=max_results, fields=fields)
            
            results = []
            for issue in issues.get('issues', []):
                issue_fields = issue.get('fields', {})
                
                results.append({
                    'key': issue.get('key'),
                    'id': issue.get('id'),
                    'summary': issue_fields.get('summary'),
                    'status': issue_fields.get('status', {}).get('name'),
                    'assignee': issue_fields.get('assignee', {}).get('displayName') if issue_fields.get('assignee') else None,
                    'priority': issue_fields.get('priority', {}).get('name') if issue_fields.get('priority') else None,
                    'created': issue_fields.get('created'),
                    'issue_type': issue_fields.get('issuetype', {}).get('name'),
                    'project': issue_fields.get('project', {}).get('key')
                })
            
            logger.info(f"Found {len(results)} issues")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search issues: {e}")
            raise
    
    def get_project(self, project_key: str) -> Dict[str, Any]:
        """Get project information"""
        try:
            logger.info(f"Fetching project: {project_key}")
            
            project = self.client.project(project_key)
            
            result = {
                'key': project.get('key'),
                'id': project.get('id'),
                'name': project.get('name'),
                'description': project.get('description'),
                'lead': project.get('lead', {}).get('displayName'),
                'project_type': project.get('projectTypeKey'),
                'url': project.get('self')
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get project {project_key}: {e}")
            raise
    
    def get_issue_types(self, project_key: str) -> List[Dict[str, Any]]:
        """Get available issue types for project"""
        try:
            logger.info(f"Fetching issue types for project: {project_key}")
            
            project = self.client.project(project_key)
            issue_types = project.get('issueTypes', [])
            
            results = []
            for it in issue_types:
                results.append({
                    'id': it.get('id'),
                    'name': it.get('name'),
                    'description': it.get('description'),
                    'subtask': it.get('subtask', False)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get issue types: {e}")
            raise
    
    def assign_issue(self, issue_key: str, assignee: str) -> bool:
        """Assign issue to user"""
        try:
            logger.info(f"Assigning issue {issue_key} to {assignee}")
            
            self.client.assign_issue(issue_key, assignee)
            
            logger.info(f"Issue {issue_key} assigned successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign issue {issue_key}: {e}")
            raise
    
    def get_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get all comments for issue"""
        try:
            logger.info(f"Fetching comments for issue: {issue_key}")
            
            issue = self.client.issue(issue_key, fields='comment')
            comments = issue.get('fields', {}).get('comment', {}).get('comments', [])
            
            results = []
            for comment in comments:
                results.append({
                    'id': comment.get('id'),
                    'body': comment.get('body'),
                    'author': comment.get('author', {}).get('displayName'),
                    'created': comment.get('created'),
                    'updated': comment.get('updated')
                })
            
            logger.info(f"Found {len(results)} comments")
            return results
            
        except Exception as e:
            logger.error(f"Failed to get comments for {issue_key}: {e}")
            raise
