"""
Confluence Client
Work with wiki via atlassian-python-api
"""

import logging
from typing import Dict, Any, Optional, List
from atlassian import Confluence

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """Client for working with Confluence"""
    
    def __init__(self, url: str, email: str, api_token: str, space_key: str):
        """
        Args:
            url: Confluence URL (https://your-domain.atlassian.net/wiki)
            email: User email
            api_token: API token
            space_key: Default space key
        """
        self.url = url
        self.email = email
        self.api_token = api_token
        self.space_key = space_key
        
        # Initialize Confluence client
        self.client = Confluence(
            url=url,
            username=email,
            password=api_token,
            cloud=True
        )
        
        logger.info(f"ConfluenceClient initialized for {url}")
    
    def get_page(
        self,
        page_id: Optional[str] = None,
        title: Optional[str] = None,
        space_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get page by ID or title"""
        try:
            if page_id:
                logger.info(f"Fetching Confluence page by ID: {page_id}")
                page = self.client.get_page_by_id(
                    page_id=page_id,
                    expand='body.storage,version,space'
                )
            elif title:
                space = space_key or self.space_key
                logger.info(f"Fetching Confluence page by title: {title} in {space}")
                page = self.client.get_page_by_title(
                    space=space,
                    title=title,
                    expand='body.storage,version,space'
                )
            else:
                raise ValueError("Either page_id or title must be provided")
            
            if not page:
                return None
            
            result = {
                'id': page.get('id'),
                'title': page.get('title'),
                'type': page.get('type'),
                'status': page.get('status'),
                'space': page.get('space', {}).get('key'),
                'version': page.get('version', {}).get('number'),
                'body': page.get('body', {}).get('storage', {}).get('value'),
                'url': f"{self.url}/pages/viewpage.action?pageId={page.get('id')}"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get page: {e}")
            raise
    
    def create_page(
        self,
        title: str,
        body: str,
        space_key: Optional[str] = None,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create new page"""
        try:
            space = space_key or self.space_key
            logger.info(f"Creating Confluence page: {title} in {space}")
            
            page = self.client.create_page(
                space=space,
                title=title,
                body=body,
                parent_id=parent_id
            )
            
            result = {
                'id': page.get('id'),
                'title': page.get('title'),
                'space': page.get('space', {}).get('key'),
                'version': page.get('version', {}).get('number'),
                'url': f"{self.url}/pages/viewpage.action?pageId={page.get('id')}"
            }
            
            logger.info(f"Page created: {result['id']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            raise
    
    def update_page(
        self,
        page_id: str,
        title: str,
        body: str
    ) -> Dict[str, Any]:
        """Update existing page"""
        try:
            logger.info(f"Updating Confluence page: {page_id}")
            
            # Get current version
            current_page = self.client.get_page_by_id(page_id, expand='version')
            current_version = current_page.get('version', {}).get('number', 1)
            
            page = self.client.update_page(
                page_id=page_id,
                title=title,
                body=body,
                parent_id=None,
                type='page',
                representation='storage',
                minor_edit=False,
                version_comment='Updated via API'
            )
            
            result = {
                'id': page.get('id'),
                'title': page.get('title'),
                'version': page.get('version', {}).get('number'),
                'url': f"{self.url}/pages/viewpage.action?pageId={page.get('id')}"
            }
            
            logger.info(f"Page updated: {result['id']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to update page {page_id}: {e}")
            raise
    
    def delete_page(self, page_id: str) -> bool:
        """Delete page"""
        try:
            logger.info(f"Deleting Confluence page: {page_id}")
            
            self.client.remove_page(page_id)
            
            logger.info(f"Page {page_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete page {page_id}: {e}")
            raise
    
    def search_pages(
        self,
        cql: str,
        limit: int = 25,
        expand: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search pages using CQL"""
        try:
            logger.info(f"Searching Confluence pages: {cql}")
            
            results = self.client.cql(cql, limit=limit, expand=expand)
            
            pages = []
            for result in results.get('results', []):
                content = result.get('content', {})
                pages.append({
                    'id': content.get('id'),
                    'title': content.get('title'),
                    'type': content.get('type'),
                    'space': content.get('space', {}).get('key'),
                    'url': f"{self.url}{content.get('_links', {}).get('webui', '')}"
                })
            
            logger.info(f"Found {len(pages)} pages")
            return pages
            
        except Exception as e:
            logger.error(f"Failed to search pages: {e}")
            raise
    
    def add_attachment(
        self,
        page_id: str,
        file_path: str,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add attachment to page"""
        try:
            logger.info(f"Adding attachment to page {page_id}: {file_path}")
            
            result = self.client.attach_file(
                filename=file_path,
                page_id=page_id,
                comment=comment
            )
            
            attachment = {
                'id': result.get('id'),
                'title': result.get('title'),
                'type': result.get('type'),
                'version': result.get('version', {}).get('number'),
                'url': f"{self.url}{result.get('_links', {}).get('download', '')}"
            }
            
            logger.info(f"Attachment added: {attachment['id']}")
            return attachment
            
        except Exception as e:
            logger.error(f"Failed to add attachment to page {page_id}: {e}")
            raise
    
    def get_space(self, space_key: Optional[str] = None) -> Dict[str, Any]:
        """Get space information"""
        try:
            space = space_key or self.space_key
            logger.info(f"Fetching space: {space}")
            
            space_data = self.client.get_space(space, expand='description,homepage')
            
            result = {
                'key': space_data.get('key'),
                'id': space_data.get('id'),
                'name': space_data.get('name'),
                'type': space_data.get('type'),
                'description': space_data.get('description', {}).get('plain', {}).get('value'),
                'homepage': space_data.get('homepage', {}).get('id'),
                'url': f"{self.url}/spaces/{space_data.get('key')}"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get space: {e}")
            raise
    
    def get_page_children(
        self,
        page_id: str,
        expand: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get child pages"""
        try:
            logger.info(f"Fetching children of page: {page_id}")
            
            children = self.client.get_page_child_by_type(
                page_id=page_id,
                type='page',
                expand=expand
            )
            
            results = []
            for child in children:
                results.append({
                    'id': child.get('id'),
                    'title': child.get('title'),
                    'type': child.get('type'),
                    'status': child.get('status'),
                    'url': f"{self.url}/pages/viewpage.action?pageId={child.get('id')}"
                })
            
            logger.info(f"Found {len(results)} child pages")
            return results
            
        except Exception as e:
            logger.error(f"Failed to get page children: {e}")
            raise
    
    def get_page_labels(self, page_id: str) -> List[str]:
        """Get page labels"""
        try:
            logger.info(f"Fetching labels for page: {page_id}")
            
            labels = self.client.get_page_labels(page_id)
            
            label_names = [label.get('name') for label in labels.get('results', [])]
            
            logger.info(f"Found {len(label_names)} labels")
            return label_names
            
        except Exception as e:
            logger.error(f"Failed to get page labels: {e}")
            raise
    
    def add_page_label(self, page_id: str, label: str) -> bool:
        """Add label to page"""
        try:
            logger.info(f"Adding label '{label}' to page {page_id}")
            
            self.client.set_page_label(page_id, label)
            
            logger.info(f"Label added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add label: {e}")
            raise
