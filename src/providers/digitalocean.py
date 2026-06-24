"""
Digital Ocean Provider
Manages droplets via pydo
"""

import logging
from typing import List, Dict, Any, Optional
from pydo import Client

logger = logging.getLogger(__name__)


class DigitalOceanProvider:
    """Provider for working with Digital Ocean"""
    
    def __init__(self, api_token: str):
        """
        Args:
            api_token: DO API token
        """
        self.api_token = api_token
        self.client = Client(token=api_token)
        logger.info("DigitalOceanProvider initialized")
    
    def list_droplets(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all droplets
        
        Args:
            tag: Filter by tag (optional)
            
        Returns:
            List of droplets
        """
        try:
            logger.info(f"Fetching droplets list (tag={tag})")
            
            params = {}
            if tag:
                params['tag_name'] = tag
            
            response = self.client.droplets.list(**params)
            droplets_data = response.get('droplets', [])
            
            result = []
            for droplet in droplets_data:
                # Обработка droplet - может быть dict или объектом
                if isinstance(droplet, dict):
                    d = droplet
                else:
                    # Если это объект, пытаемся получить его атрибуты
                    try:
                        d = droplet.__dict__ if hasattr(droplet, '__dict__') else dict(droplet)
                    except:
                        d = {}
                
                # Безопасное извлечение данных с проверкой типов
                networks = d.get('networks', {})
                if isinstance(networks, dict):
                    v4_networks = networks.get('v4', [])
                else:
                    try:
                        v4_networks = getattr(networks, 'v4', [])
                    except:
                        v4_networks = []
                
                # Получаем публичный IP
                public_ip = 'N/A'
                if v4_networks and len(v4_networks) > 0:
                    first_v4 = v4_networks[0]
                    if isinstance(first_v4, dict):
                        public_ip = first_v4.get('ip_address', 'N/A')
                    else:
                        try:
                            public_ip = getattr(first_v4, 'ip_address', 'N/A')
                        except:
                            public_ip = 'N/A'
                
                # Безопасное получение региона
                region_data = d.get('region', {})
                if isinstance(region_data, dict):
                    region_slug = region_data.get('slug', 'unknown')
                    region_name = region_data.get('name', 'Unknown')
                else:
                    try:
                        region_slug = getattr(region_data, 'slug', 'unknown')
                        region_name = getattr(region_data, 'name', 'Unknown')
                    except:
                        region_slug = 'unknown'
                        region_name = 'Unknown'
                
                # Безопасное получение size
                size_data = d.get('size', {})
                if isinstance(size_data, dict):
                    size_slug = size_data.get('slug', 'unknown')
                    size_description = size_data.get('description', size_slug)
                    price_monthly = size_data.get('price_monthly', 0)
                else:
                    try:
                        size_slug = getattr(size_data, 'slug', 'unknown')
                        size_description = getattr(size_data, 'description', size_slug)
                        price_monthly = getattr(size_data, 'price_monthly', 0)
                    except:
                        size_slug = 'unknown'
                        size_description = 'unknown'
                        price_monthly = 0
                
                # Безопасное получение image
                image_data = d.get('image', {})
                if isinstance(image_data, dict):
                    image_slug = image_data.get('slug', 'unknown')
                    image_name = image_data.get('name', 'unknown')
                    image_distribution = image_data.get('distribution', 'Unknown')
                else:
                    try:
                        image_slug = getattr(image_data, 'slug', 'unknown')
                        image_name = getattr(image_data, 'name', 'unknown')
                        image_distribution = getattr(image_data, 'distribution', 'Unknown')
                    except:
                        image_slug = 'unknown'
                        image_name = 'unknown'
                        image_distribution = 'Unknown'
                
                # Формируем результат с полными данными для UI
                droplet_result = {
                    'id': d.get('id', 0),
                    'name': d.get('name', 'unknown'),
                    'status': d.get('status', 'unknown'),
                    'networks': {
                        'v4': [{'ip_address': public_ip, 'type': 'public'}] if public_ip != 'N/A' else []
                    },
                    'region': {
                        'slug': region_slug,
                        'name': region_name
                    },
                    'size': {
                        'slug': size_slug,
                        'description': size_description,
                        'price_monthly': price_monthly
                    },
                    'size_slug': size_slug,
                    'image': {
                        'slug': image_slug,
                        'name': image_name,
                        'distribution': image_distribution
                    },
                    'tags': d.get('tags', []),
                    'created_at': d.get('created_at', 'unknown')
                }
                
                result.append(droplet_result)
            
            logger.info(f"Found {len(result)} droplets")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list droplets: {e}", exc_info=True)
            raise
    
    def create_droplet(
        self,
        name: str,
        region: str = 'nyc3',
        size: str = 's-1vcpu-1gb',
        image: str = 'ubuntu-22-04-x64',
        tags: Optional[List[str]] = None,
        ssh_keys: Optional[List[str]] = None,
        user_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create new droplet
        
        Args:
            name: Droplet name
            region: Region slug
            size: Size slug
            image: Image slug
            tags: Tags list
            ssh_keys: SSH keys list
            user_data: User data script
            
        Returns:
            Created droplet info
        """
        try:
            logger.info(f"Creating droplet: {name} in {region}")
            
            body = {
                'name': name,
                'region': region,
                'size': size,
                'image': image
            }
            
            if tags:
                body['tags'] = tags
            if ssh_keys:
                body['ssh_keys'] = ssh_keys
            if user_data:
                body['user_data'] = user_data
            
            response = self.client.droplets.create(body=body)
            droplet = response.get('droplet', {})
            
            result = {
                'id': droplet.get('id'),
                'name': droplet.get('name'),
                'status': droplet.get('status'),
                'region': droplet.get('region', {}).get('slug'),
                'size': droplet.get('size', {}).get('slug'),
                'created_at': droplet.get('created_at')
            }
            
            logger.info(f"Droplet created: {result['id']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create droplet: {e}")
            raise
    
    def get_droplet(self, droplet_id: int) -> Dict[str, Any]:
        """
        Get droplet info by ID
        
        Args:
            droplet_id: Droplet ID
            
        Returns:
            Droplet info
        """
        try:
            logger.info(f"Fetching droplet: {droplet_id}")
            
            response = self.client.droplets.get(droplet_id=droplet_id)
            droplet_data = response.get('droplet', {})
            
            # Обработка droplet - может быть dict или объектом
            if isinstance(droplet_data, dict):
                d = droplet_data
            else:
                try:
                    d = droplet_data.__dict__ if hasattr(droplet_data, '__dict__') else dict(droplet_data)
                except:
                    d = {}
            
            # Безопасное извлечение networks и IP
            networks = d.get('networks', {})
            if isinstance(networks, dict):
                v4_networks = networks.get('v4', [])
            else:
                try:
                    v4_networks = getattr(networks, 'v4', [])
                except:
                    v4_networks = []
            
            # Получаем публичный IP
            public_ip = 'N/A'
            if v4_networks and len(v4_networks) > 0:
                first_v4 = v4_networks[0]
                if isinstance(first_v4, dict):
                    public_ip = first_v4.get('ip_address', 'N/A')
                else:
                    try:
                        public_ip = getattr(first_v4, 'ip_address', 'N/A')
                    except:
                        public_ip = 'N/A'
            
            # Безопасное получение region
            region_data = d.get('region', {})
            if isinstance(region_data, dict):
                region_slug = region_data.get('slug', 'unknown')
            else:
                try:
                    region_slug = getattr(region_data, 'slug', 'unknown')
                except:
                    region_slug = 'unknown'
            
            # Безопасное получение size
            size_data = d.get('size', {})
            if isinstance(size_data, dict):
                size_slug = size_data.get('slug', 'unknown')
            else:
                try:
                    size_slug = getattr(size_data, 'slug', 'unknown')
                except:
                    size_slug = 'unknown'
            
            # Безопасное получение image
            image_data = d.get('image', {})
            if isinstance(image_data, dict):
                image_slug = image_data.get('slug', 'unknown')
            else:
                try:
                    image_slug = getattr(image_data, 'slug', 'unknown')
                except:
                    image_slug = 'unknown'
            
            result = {
                'id': d.get('id', 0),
                'name': d.get('name', 'unknown'),
                'status': d.get('status', 'unknown'),
                'ip_address': public_ip,
                'region': region_slug,
                'size': size_slug,
                'image': image_slug,
                'tags': d.get('tags', []),
                'created_at': d.get('created_at', 'unknown'),
                'vcpus': d.get('vcpus', 0),
                'memory': d.get('memory', 0),
                'disk': d.get('disk', 0)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get droplet {droplet_id}: {e}", exc_info=True)
            raise
    
    def droplet_action(self, droplet_id: int, action: str) -> Dict[str, Any]:
        """
        Execute action on droplet
        
        Args:
            droplet_id: Droplet ID
            action: Action name (reboot, power_off, power_on, shutdown, etc)
            
        Returns:
            Action result
        """
        try:
            logger.info(f"Executing action '{action}' on droplet {droplet_id}")
            
            body = {'type': action}
            response = self.client.droplet_actions.post(droplet_id=droplet_id, body=body)
            action_result = response.get('action', {})
            
            result = {
                'id': action_result.get('id'),
                'type': action_result.get('type'),
                'status': action_result.get('status'),
                'started_at': action_result.get('started_at'),
                'completed_at': action_result.get('completed_at')
            }
            
            logger.info(f"Action executed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute action '{action}' on droplet {droplet_id}: {e}")
            raise
    
    def delete_droplet(self, droplet_id: int) -> bool:
        """
        Delete droplet
        
        Args:
            droplet_id: Droplet ID
            
        Returns:
            True if deleted successfully
        """
        try:
            logger.info(f"Deleting droplet: {droplet_id}")
            
            self.client.droplets.destroy(droplet_id=droplet_id)
            
            logger.info(f"Droplet {droplet_id} deleted")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete droplet {droplet_id}: {e}")
            raise
    
    def list_regions(self) -> List[Dict[str, Any]]:
        """
        Get list of available regions
        
        Returns:
            List of regions
        """
        try:
            logger.info("Fetching regions list")
            
            response = self.client.regions.list()
            regions = response.get('regions', [])
            
            result = []
            for region in regions:
                if region.get('available'):
                    result.append({
                        'slug': region.get('slug'),
                        'name': region.get('name'),
                        'available': region.get('available'),
                        'features': region.get('features', []),
                        'sizes': region.get('sizes', [])
                    })
            
            logger.info(f"Found {len(result)} available regions")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list regions: {e}")
            raise
    
    def list_sizes(self) -> List[Dict[str, Any]]:
        """
        Get list of available sizes
        
        Returns:
            List of sizes
        """
        try:
            logger.info("Fetching sizes list")
            
            response = self.client.sizes.list()
            sizes = response.get('sizes', [])
            
            result = []
            for size in sizes:
                if size.get('available'):
                    result.append({
                        'slug': size.get('slug'),
                        'memory': size.get('memory'),
                        'vcpus': size.get('vcpus'),
                        'disk': size.get('disk'),
                        'transfer': size.get('transfer'),
                        'price_monthly': size.get('price_monthly'),
                        'price_hourly': size.get('price_hourly'),
                        'regions': size.get('regions', []),
                        'available': size.get('available')
                    })
            
            logger.info(f"Found {len(result)} available sizes")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list sizes: {e}")
            raise
    
    def list_images(self, image_type: str = 'distribution') -> List[Dict[str, Any]]:
        """
        Get list of available images
        
        Args:
            image_type: Image type (distribution, application, etc)
            
        Returns:
            List of images
        """
        try:
            logger.info(f"Fetching images list (type={image_type})")
            
            params = {'type': image_type}
            response = self.client.images.list(**params)
            images = response.get('images', [])
            
            result = []
            for image in images:
                result.append({
                    'id': image.get('id'),
                    'name': image.get('name'),
                    'slug': image.get('slug'),
                    'distribution': image.get('distribution'),
                    'public': image.get('public'),
                    'regions': image.get('regions', []),
                    'created_at': image.get('created_at'),
                    'min_disk_size': image.get('min_disk_size')
                })
            
            logger.info(f"Found {len(result)} images")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list images: {e}")
            raise
    
    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        """
        Get list of SSH keys from DO account
        
        Returns:
            List of SSH keys
        """
        try:
            logger.info("Fetching SSH keys list")
            
            response = self.client.ssh_keys.list()
            keys = response.get('ssh_keys', [])
            
            result = []
            for key in keys:
                result.append({
                    'id': key.get('id'),
                    'name': key.get('name'),
                    'fingerprint': key.get('fingerprint'),
                    'public_key': key.get('public_key')[:50] + '...' if key.get('public_key') else None  # Shortened for display
                })
            
            logger.info(f"Found {len(result)} SSH keys")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list SSH keys: {e}")
            raise
