"""
Common Logic & Project Context Manager.
Centralizes project discovery, config loading, scanning, and dependency resolution.
Facade pattern to simplify command implementations.
"""
from multiprocessing import Value
import tomllib
from pathlib import Path

from rich.console import Console

from . import scanner, resolver

console: Console = Console()

DEFAULT_CONFIG_RAW = """# Codigest Configuration File
[tool.codigest.filter]
max_file_size_kb = 100 
extensions = [
    ".py", ".pyi",
    ".ts", ".tsx", ".js", ".jsx",
    ".json", ".html", ".css",
    ".md", ".toml", ".yaml", ".yml", ".txt"
]
exclude_patterns = [
    "*.lock",
    "dist/",
    "build/",
    "node_modules/",
    "__pycache__/"
]

[tool.codigest.output]
format = "xml"
structure = "toon"
"""



def _deep_merge(default: dict, user_config: dict) -> dict:
    result: dict = default.copy()
    for key, val in user_config.items():
        if (
            isinstance(val, dict) and
            key in default and
            isinstance(default[key], dict)
        ):
            default: dict = _deep_merge(default[key], val)
        else: 
            user_config[key] = val
    return user_config


class ProjectContext:
    def __init__(self, targets: list[Path] | Path | None = None):
        
        # TODO: Rest of the targets are not used at all.
        if targets is None:
            targets: list[Path] = [Path.cwd().resolve()]
        elif isinstance(targets, Path):
            targets: list[Path] = [targets]
        # 1. 탐색 시작점 결정
        if len(targets) > 0:
            self.start_path: Path = targets[0].resolve()

        # 2. 루트 찾기
        self.root_path: Path = self._find_project_root(self.start_path)
        self.config_extensions, self.config_ignores = self._load_config_filters()

    def _find_project_root(self, start_path: Path) -> Path:
        """
        Locates the project root by looking for marker directories/files.
        """
        current: Path = start_path if start_path.is_dir() else start_path.parent
        
        # Traverse up
        for parent in [current] + list(current.parents):
            if (parent / ".codigest").exists():
                return parent
            if (parent / ".git").exists() or (parent / ".shadow_git").exists():
                return parent
        
        return start_path if start_path.is_dir() else start_path.parent

    def _load_config_filters(self) -> tuple[set[str] | None, list[str]]:
        # config_path = self.root_path / ".codigest" / "config.toml"
        config_path: Path = self.root_path / "pyproject.toml"

        # TODO: Warn user to make pyproject.toml
        if not config_path.exists():
            return set(), []
        
        config: dict = self.get_config(config_path)
        filters: dict | None = config['filters']
        if filters is None:
            return set(), []
        if ext_list := filters.get("extensions", []):
            extensions: set = set(ext_list)
        else:
            extensions: set = set()
        exclude_patterns: list[str] = filters.get("exclude_patterns", [])
        return extensions, exclude_patterns
    
    def get_config(
        self,
        config_file: Path | str
    ) -> dict:

        default_config: dict = tomllib.loads(DEFAULT_CONFIG_RAW)
        default_cdg_config: dict = default_config['tool']['codigest']

        config_file: Path = Path(config_file)
        if not config_file.exists():
            return default_cdg_config

        with open(config_file, "rb") as f:
            config: dict = tomllib.load(f)
        cdg_config: dict | None = config.get("tool", {}).get("codigest", None)
        if cdg_config is None:
            return default_cdg_config

        cdg_config: dict = _deep_merge(default_cdg_config, cdg_config)
        
        return cdg_config

    def get_target_files(
        self, 
        targets: list[Path] | Path | None = None, 
        ignore_config: bool = False,
        resolve_deps: bool = False
    ) -> list[Path]:
        """
        The Master Method:
        """
        # [핵심 수정] 입력된 경로를 무조건 '절대 경로'로 변환 (Resolve)
        # 이걸 안 하면 'src' 같은 상대 경로 입력 시 root_path(절대 경로)와 비교 실패함
        resolved_targets = []
        if targets:
            # 단일 Path면 리스트로 변환
            if isinstance(targets, Path):
                targets = [targets]
            
            # 리스트 내부의 모든 경로를 resolve()
            for t in targets:
                resolved_targets.append(t.resolve())
        
        # 이후 로직에서는 변환된 resolved_targets를 사용
        scan_scope = resolved_targets if resolved_targets else None
        
        # 1. Determine Filters
        exts, ignores = (None, [])
        if not ignore_config:
            exts, ignores = self.config_extensions, self.config_ignores

        # 2. Scope Warning UI (이제 정상 작동함)
        if scan_scope:
            for p in scan_scope:
                if not p.is_relative_to(self.root_path):
                    console.print(f"[yellow][Warning] {p.name} is outside detected root {self.root_path}[/yellow]")

        # 3. dump
        files = scanner.scan_project(
            self.root_path, 
            extensions=exts, 
            extra_ignores=ignores, 
            include_paths=scan_scope
        )

        # 4. Resolve Dependencies
        if resolve_deps:
            files = resolver.resolve_dependencies(self.root_path, files)

        return files

# Helper for quick access
def get_context(targets: list[Path] | Path | None = None) -> ProjectContext:
    return ProjectContext(targets)