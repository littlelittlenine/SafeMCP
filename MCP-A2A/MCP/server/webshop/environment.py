"""
WebshopEnvServer with MCP Protocol Support
"""
from typing import Optional, Dict, Any, List, Tuple
import logging
import time
import random
import threading  # 关键修复
import gym
from agentenv_webshop.webshop.web_agent_site.envs import WebAgentTextEnv

class WebshopEnvServer:
    """
    MCP-compatible WebShop Environment Server
    
    Features:
    - Thread-safe environment management
    - Rate limiting
    - Detailed logging
    - MCP protocol compliance
    """
    
    def __init__(self, max_environments: int = 8000) -> None:
        """
        Initialize the environment server
        
        Args:
            max_environments: Maximum number of concurrent environments
        """
        self._max_id = 0
        self.env = {}
        self.session_map = {}  # session_id -> env_idx mapping
        self.max_environments = max_environments
        self.lock = threading.Lock()
        self.logger = logging.getLogger("webshop_env")
        
        # Rate limiting configuration
        self.rate_limit = {
            'create': {'per_minute': 100},
            'step': {'per_second': 5, 'per_minute': 100}
        }
        self.request_counters = {
            'create': {'minute': 0, 'last_reset': time.time()},
            'step': {'second': 0, 'minute': 0, 'last_reset': time.time()}
        }

    def _check_rate_limit(self, operation: str) -> None:
        """Internal rate limiting check"""
        now = time.time()
        config = self.rate_limit.get(operation, {})
        counters = self.request_counters.get(operation, {})
        
        if 'per_second' in config:
            if now - counters.get('last_reset', 0) > 1:
                counters['second'] = 0
                counters['last_reset'] = now
            if counters.get('second', 0) >= config['per_second']:
                raise RuntimeError(f"Rate limit exceeded for {operation} (per second)")
            counters['second'] += 1
            
        if 'per_minute' in config:
            if now - counters.get('last_minute_reset', 0) > 60:
                counters['minute'] = 0
                counters['last_minute_reset'] = now
            if counters.get('minute', 0) >= config['per_minute']:
                raise RuntimeError(f"Rate limit exceeded for {operation} (per minute)")
            counters['minute'] += 1

    def create(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new WebShop environment
        
        Args:
            session_id: Optional session identifier for persistence
            
        Returns:
            Dictionary containing:
            - env_idx: Environment ID
            - session_id: Associated session ID
            - timestamp: Creation time
        """
        try:
            self._check_rate_limit('create')
            
            with self.lock:
                # Reuse existing environment if session exists
                if session_id and session_id in self.session_map:
                    env_idx = self.session_map[session_id]
                    self.logger.info(f"Reusing environment {env_idx} for session {session_id}")
                    return {
                        'env_idx': env_idx,
                        'session_id': session_id,
                        'timestamp': time.time()
                    }
                
                # Create new environment
                env_idx = self._max_id
                self._max_id += 1
                
                # Implement environment pool if max reached
                if len(self.env) >= self.max_environments:
                    oldest_env = min(self.env.keys())
                    self.env[oldest_env].close()
                    del self.env[oldest_env]
                    self.logger.warning(f"Recycled environment {oldest_env} due to pool limit")
                
                # Initialize new environment
                self.env[env_idx] = gym.make(
                    "WebAgentTextEnv-v0",
                    observation_mode="text",
                    num_products=1000,
                )
                self.env[env_idx].reset()
                
                # Track session if provided
                if session_id:
                    self.session_map[session_id] = env_idx
                
                self.logger.info(f"Created new environment {env_idx} for session {session_id or 'N/A'}")
                
                return {
                    'env_idx': env_idx,
                    'session_id': session_id or str(env_idx),
                    'timestamp': time.time()
                }
                
        except Exception as e:
            self.logger.error(f"Environment creation failed: {str(e)}")
            return {'error': str(e)}

    def step(self, env_idx: int, action: str) -> Dict[str, Any]:
        """
        Execute an action in the specified environment
        
        Args:
            env_idx: Environment ID
            action: Action string (e.g., "search[product]")
            
        Returns:
            Dictionary containing:
            - state: New environment state
            - reward: Action reward
            - done: Whether episode is complete
            - info: Additional metadata
            - available_actions: Current available actions
        """
        try:
            self._check_rate_limit('step')
            
            if env_idx not in self.env:
                raise ValueError(f"Environment {env_idx} does not exist")
                
            state, reward, done, info = self.env[env_idx].step(action)
            
            # Get updated available actions
            available_actions = self.get_available_actions(env_idx)
            
            self.logger.debug(f"Step in env {env_idx}: action={action}, reward={reward}, done={done}")
            
            return {
                'state': state,
                'reward': reward,
                'done': done,
                'info': info,
                'available_actions': available_actions
            }
            
        except Exception as e:
            self.logger.error(f"Step failed in env {env_idx}: {str(e)}")
            return {'error': str(e)}

    def get_available_actions(self, env_idx: int) -> Dict[str, Any]:
        """Get available actions for the environment"""
        try:
            if env_idx not in self.env:
                raise ValueError(f"Environment {env_idx} does not exist")
                
            actions = self.env[env_idx].get_available_actions()
            return {
                'has_search_bar': actions.get('has_search_bar', False),
                'clickables': actions.get('clickables', []),
                'valid_actions': actions  # Raw action data
            }
        except Exception as e:
            self.logger.error(f"Failed to get actions for env {env_idx}: {str(e)}")
            return {'error': str(e)}

    def get_instruction_text(self, env_idx: int) -> Dict[str, Any]:
        """Get the current instruction text"""
        try:
            if env_idx not in self.env:
                raise ValueError(f"Environment {env_idx} does not exist")
                
            text = self.env[env_idx].get_instruction_text()
            return {
                'instruction': text,
                'env_idx': env_idx,
                'timestamp': time.time()
            }
        except Exception as e:
            self.logger.error(f"Failed to get instruction for env {env_idx}: {str(e)}")
            return {'error': str(e)}

    def reset(self, env_idx: int, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Reset the specified environment"""
        try:
            with self.lock:
                if env_idx not in self.env:
                    raise ValueError(f"Environment {env_idx} does not exist")
                    
                # Reset the environment
                result = self.env[env_idx].reset(session=session_id)
                
                # Update session mapping if provided
                if session_id:
                    self.session_map[session_id] = env_idx
                
                self.logger.info(f"Reset environment {env_idx} for session {session_id or 'N/A'}")
                
                return {
                    'result': result,
                    'env_idx': env_idx,
                    'session_id': session_id or str(env_idx),
                    'timestamp': time.time()
                }
        except Exception as e:
            self.logger.error(f"Reset failed for env {env_idx}: {str(e)}")
            return {'error': str(e)}

    def close(self, env_idx: int) -> Dict[str, Any]:
        """Close and clean up an environment"""
        try:
            with self.lock:
                if env_idx in self.env:
                    self.env[env_idx].close()
                    del self.env[env_idx]
                    
                    # Remove from session map
                    for sid, eid in list(self.session_map.items()):
                        if eid == env_idx:
                            del self.session_map[sid]
                    
                    self.logger.info(f"Closed environment {env_idx}")
                    return {'status': 'success', 'env_idx': env_idx}
                return {'status': 'not_found', 'env_idx': env_idx}
        except Exception as e:
            self.logger.error(f"Failed to close env {env_idx}: {str(e)}")
            return {'error': str(e)}

    def list_envs(self) -> Dict[str, Any]:
        """List all active environments"""
        try:
            with self.lock:
                return {
                    'active_envs': list(self.env.keys()),
                    'session_mapping': self.session_map.copy(),
                    'count': len(self.env),
                    'timestamp': time.time()
                }
        except Exception as e:
            self.logger.error(f"Failed to list environments: {str(e)}")
            return {'error': str(e)}

# Global instance for MCP compatibility
webshop_env_server = WebshopEnvServer()