"""
Repository analysis and NLP processing
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import Counter
import asyncio

from .config import Config
from .models import RepositoryMetadata, RepositoryAnalysis
from .github_client import GitHubClient


logger = logging.getLogger(__name__)


class RepositoryAnalyzer:
    """Analyzes repositories for agent-friendliness"""
    
    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
    
    async def analyze_repository(self, metadata: RepositoryMetadata) -> RepositoryAnalysis:
        """Perform complete analysis of a repository"""
        logger.info(f"Analyzing repository: {metadata.full_name}")
        
        # Get repository contents
        contents = await self.github_client.get_repository_contents(
            metadata.owner, metadata.name
        )
        
        # Analyze different aspects
        has_cli = await self._detect_cli_interface(metadata, contents)
        has_api = await self._detect_api_interface(metadata, contents)
        has_documentation, doc_quality = await self._analyze_documentation(metadata, contents)
        
        # Get code files for analysis
        code_files = await self._get_code_files(metadata, contents)
        complexity = await self._analyze_code_complexity(code_files)
        modularity = await self._analyze_modularity(code_files)
        
        # Analyze maintenance
        maintenance = self._analyze_maintenance(metadata)
        
        # Detect frameworks and patterns
        frameworks = await self._detect_frameworks(metadata, contents)
        patterns = await self._detect_patterns(metadata, contents)
        
        # Generate summary
        readme_summary = await self._generate_readme_summary(metadata)
        
        return RepositoryAnalysis(
            has_cli=has_cli,
            has_api=has_api,
            has_documentation=has_documentation,
            documentation_quality=doc_quality,
            code_complexity=complexity,
            modularity_score=modularity,
            maintenance_score=maintenance,
            detected_frameworks=frameworks,
            detected_patterns=patterns,
            readme_summary=readme_summary
        )
    
    async def _detect_cli_interface(self, metadata: RepositoryMetadata, contents: List[Dict]) -> bool:
        """Detect if repository has CLI interface"""
        # Check for CLI patterns in main files
        main_files = [f for f in contents if f.get("name", "").lower() in ["main.py", "__main__.py", "cli.py", "app.py"]]
        
        for file_info in main_files[:3]:  # Check first 3 main files
            if file_info.get("type") == "file":
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content and self._contains_cli_patterns(content):
                    return True
        
        # Check setup.py for entry points
        setup_files = [f for f in contents if f.get("name", "").lower() in ["setup.py", "pyproject.toml"]]
        for file_info in setup_files:
            if file_info.get("type") == "file":
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content and ("entry_points" in content or "console_scripts" in content):
                    return True
        
        return False
    
    async def _detect_api_interface(self, metadata: RepositoryMetadata, contents: List[Dict]) -> bool:
        """Detect if repository has API interface"""
        # Check for API patterns in main files
        api_files = [f for f in contents if any(keyword in f.get("name", "").lower() 
                                              for keyword in ["app", "server", "api", "main"])]
        
        for file_info in api_files[:5]:  # Check first 5 potential API files
            if file_info.get("type") == "file" and file_info.get("name", "").endswith(".py"):
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content and self._contains_api_patterns(content):
                    return True
        
        return False
    
    async def _analyze_documentation(self, metadata: RepositoryMetadata, contents: List[Dict]) -> Tuple[bool, float]:
        """Analyze documentation quality"""
        has_docs = False
        doc_quality = 0.0
        
        # Check for README
        readme_files = [f for f in contents if f.get("name", "").lower().startswith("readme")]
        if readme_files:
            has_docs = True
            readme_content = await self.github_client.get_file_content(
                metadata.owner, metadata.name, readme_files[0]["path"]
            )
            if readme_content:
                doc_quality += self._score_readme_quality(readme_content)
        
        # Check for docs directory
        docs_dirs = [f for f in contents if f.get("type") == "dir" and 
                    f.get("name", "").lower() in ["docs", "doc", "documentation"]]
        if docs_dirs:
            has_docs = True
            doc_quality += 0.3  # Bonus for having docs directory
        
        # Check for docstrings (sample a few Python files)
        python_files = [f for f in contents if f.get("name", "").endswith(".py")][:3]
        docstring_score = 0
        for file_info in python_files:
            if file_info.get("type") == "file":
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content and '"""' in content:
                    docstring_score += 0.1
        
        doc_quality += min(docstring_score, 0.3)
        
        return has_docs, min(doc_quality, 1.0)
    
    async def _get_code_files(self, metadata: RepositoryMetadata, contents: List[Dict]) -> List[str]:
        """Get sample of code files for analysis"""
        code_files = []
        
        # Get Python files (limit to avoid API overuse)
        python_files = [f for f in contents if f.get("name", "").endswith(".py")][:Config.CODE_SAMPLE_SIZE]
        
        for file_info in python_files:
            if file_info.get("type") == "file":
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content:
                    code_files.append(content)
        
        return code_files
    
    async def _analyze_code_complexity(self, code_files: List[str]) -> float:
        """Analyze code complexity (lower is better)"""
        if not code_files:
            return 0.5  # Neutral score
        
        total_complexity = 0
        file_count = 0
        
        for content in code_files:
            lines = content.split('\n')
            non_empty_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            
            if not non_empty_lines:
                continue
            
            # Simple complexity metrics
            function_count = len(re.findall(r'def\s+\w+', content))
            class_count = len(re.findall(r'class\s+\w+', content))
            nested_blocks = content.count('    ') + content.count('\t')  # Indentation levels
            
            # Normalize by file size
            file_complexity = (nested_blocks + function_count * 2 + class_count * 3) / len(non_empty_lines)
            total_complexity += file_complexity
            file_count += 1
        
        if file_count == 0:
            return 0.5
        
        avg_complexity = total_complexity / file_count
        
        # Convert to 0-1 scale (lower complexity = higher score)
        return max(0.0, min(1.0, 1.0 - (avg_complexity / 2.0)))
    
    async def _analyze_modularity(self, code_files: List[str]) -> float:
        """Analyze code modularity"""
        if not code_files:
            return 0.5
        
        total_score = 0
        file_count = 0
        
        for content in code_files:
            # Count imports (good modularity indicator)
            import_count = len(re.findall(r'^(import|from)\s+', content, re.MULTILINE))
            
            # Count functions and classes
            function_count = len(re.findall(r'def\s+\w+', content))
            class_count = len(re.findall(r'class\s+\w+', content))
            
            lines = len([line for line in content.split('\n') if line.strip()])
            
            if lines == 0:
                continue
            
            # Calculate modularity score
            structure_score = (import_count + function_count + class_count) / lines
            file_score = min(1.0, structure_score * 10)  # Scale appropriately
            
            total_score += file_score
            file_count += 1
        
        return total_score / file_count if file_count > 0 else 0.5
    
    def _analyze_maintenance(self, metadata: RepositoryMetadata) -> float:
        """Analyze repository maintenance activity (uses UTC for comparison)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        updated = metadata.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        days_since_update = (now - updated).days
        
        # Score based on recency of updates
        if days_since_update <= 30:
            return 1.0
        elif days_since_update <= 90:
            return 0.8
        elif days_since_update <= 180:
            return 0.6
        elif days_since_update <= 365:
            return 0.4
        else:
            return 0.2
    
    async def _detect_frameworks(self, metadata: RepositoryMetadata, contents: List[Dict]) -> List[str]:
        """Detect frameworks used in the repository"""
        frameworks = set()
        
        # Check requirements.txt and setup.py
        requirements_files = [f for f in contents if f.get("name", "").lower() in 
                            ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"]]
        
        for file_info in requirements_files:
            if file_info.get("type") == "file":
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content:
                    frameworks.update(self._extract_frameworks_from_dependencies(content))
        
        # Check Python files for import statements
        python_files = [f for f in contents if f.get("name", "").endswith(".py")][:3]
        for file_info in python_files:
            if file_info.get("type") == "file":
                content = await self.github_client.get_file_content(
                    metadata.owner, metadata.name, file_info["path"]
                )
                if content:
                    frameworks.update(self._extract_frameworks_from_imports(content))
        
        return list(frameworks)
    
    async def _detect_patterns(self, metadata: RepositoryMetadata, contents: List[Dict]) -> List[str]:
        """Detect architectural patterns"""
        patterns = set()
        
        # Check directory structure
        dir_names = [f.get("name", "").lower() for f in contents if f.get("type") == "dir"]
        
        if "tests" in dir_names or "test" in dir_names:
            patterns.add("testing")
        if "docs" in dir_names or "doc" in dir_names:
            patterns.add("documentation")
        if "api" in dir_names:
            patterns.add("api")
        if "cli" in dir_names:
            patterns.add("cli")
        if "config" in dir_names:
            patterns.add("configuration")
        
        # Check for common patterns in file names
        file_names = [f.get("name", "").lower() for f in contents if f.get("type") == "file"]
        
        if any("docker" in name for name in file_names):
            patterns.add("containerization")
        if any("makefile" in name for name in file_names):
            patterns.add("build-automation")
        if any("setup.py" in name for name in file_names):
            patterns.add("packaging")
        
        return list(patterns)
    
    async def _generate_readme_summary(self, metadata: RepositoryMetadata) -> Optional[str]:
        """Generate a summary from README"""
        readme_files = await self.github_client.get_repository_contents(
            metadata.owner, metadata.name
        )
        
        readme_file = None
        for file_info in readme_files:
            if file_info.get("name", "").lower().startswith("readme"):
                readme_file = file_info
                break
        
        if not readme_file:
            return None
        
        content = await self.github_client.get_file_content(
            metadata.owner, metadata.name, readme_file["path"]
        )
        
        if not content:
            return None
        
        # Extract first meaningful paragraph
        lines = content.split('\n')
        summary_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('!['):
                summary_lines.append(line)
                if len(' '.join(summary_lines)) > 200:
                    break
        
        summary = ' '.join(summary_lines)
        return summary[:200] + "..." if len(summary) > 200 else summary
    
    def _contains_cli_patterns(self, content: str) -> bool:
        """Check if content contains CLI patterns"""
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in Config.CLI_PATTERNS)
    
    def _contains_api_patterns(self, content: str) -> bool:
        """Check if content contains API patterns"""
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in Config.API_PATTERNS)
    
    def _score_readme_quality(self, readme_content: str) -> float:
        """Score README quality"""
        if not readme_content:
            return 0.0
        
        score = 0.0
        content_lower = readme_content.lower()
        
        # Check for important sections
        if "installation" in content_lower or "install" in content_lower:
            score += 0.2
        if "usage" in content_lower or "example" in content_lower:
            score += 0.2
        if "api" in content_lower or "documentation" in content_lower:
            score += 0.1
        if "license" in content_lower:
            score += 0.1
        if "contribute" in content_lower or "contributing" in content_lower:
            score += 0.1
        
        # Check for code examples
        if "```" in readme_content or "    " in readme_content:
            score += 0.2
        
        # Length bonus (but not too long)
        length_score = min(0.1, len(readme_content) / 5000)
        score += length_score
        
        return min(1.0, score)
    
    def _extract_frameworks_from_dependencies(self, content: str) -> Set[str]:
        """Extract framework names from dependency files"""
        frameworks = set()
        content_lower = content.lower()
        
        for category, framework_list in Config.FRAMEWORK_TAGS.items():
            for framework in framework_list:
                if framework in content_lower:
                    frameworks.add(framework)
        
        return frameworks
    
    def _extract_frameworks_from_imports(self, content: str) -> Set[str]:
        """Extract framework names from import statements"""
        frameworks = set()
        
        # Find import statements
        imports = re.findall(r'^(?:from\s+(\w+)|import\s+(\w+))', content, re.MULTILINE)
        
        for import_match in imports:
            module_name = import_match[0] or import_match[1]
            
            # Check against known frameworks
            for category, framework_list in Config.FRAMEWORK_TAGS.items():
                if module_name in framework_list:
                    frameworks.add(module_name)
        
        return frameworks