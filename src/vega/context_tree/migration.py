"""Migration utilities for importing Obsidian vault contents into the Vega Context Tree.

Walks through an Obsidian vault directory structure, creates
nodes for each .md file, and preserves folder hierarchy
as branch/leaf structure.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from vega.context_tree.db import ContextTreeDB
from vega.context_tree.node import Edge, Node, NodeType, RelationshipType


# ── Obsidian-specific helpers ──────────────────────────────────────────


def parse_obsidian_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter from Obsidian markdown content.

    A simple parser for key: value pairs without full YAML deps.

    Args:
        content: Raw markdown content.

    Returns:
        Tuple of (metadata dict, body content).
    """
    metadata: dict[str, str] = {}
    body = content

    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            frontmatter = content[3:end_idx].strip()
            body = content[end_idx + 3 :].strip()
            for line in frontmatter.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    metadata[key.strip()] = val.lstrip().strip()
    return metadata, body


def extract_obsidian_links(content: str) -> list[str]:
    """Extract wiki-links from Obsidian content.

    Args:
        content: Raw markdown content.

    Returns:
        List of link target names.
    """
    return re.findall(r"\[\[([^\]]+?)\]\]", content)


def extract_tags_from_content(content: str) -> list[str]:
    """Extract tags from content (e.g., #tag).

    Args:
        content: Raw text content.

    Returns:
        List of unique tag strings (without #).
    """
    tags = re.findall(r"(?<!\w)#([a-zA-Z][a-zA-Z0-9_/-]*)", content)
    return list(set(tags))


def compute_importance_from_metadata(metadata: dict[str, str]) -> Optional[float]:
    """Compute importance score from Obsidian frontmatter metadata.

    Looks for keys like 'importance', 'weight', 'priority', 'rating'.

    Args:
        metadata: Parsed frontmatter dict.

    Returns:
        Float between 0.0 and 1.0, or None if not found.
    """
    for key in ("importance", "weight", "priority", "rating"):
        val = metadata.get(key)
        if val is None:
            continue
        try:
            imp = float(val)
            return max(0.0, min(1.0, imp / 10.0 if imp > 1.0 else imp))
        except (ValueError, TypeError):
            continue
    return None


# ── Vault scanning ─────────────────────────────────────────────────────


def scan_vault(vault_path: str) -> dict[str, Path]:
    """Scan an Obsidian vault directory for markdown files.

    Args:
        vault_path: Path to the vault root.

    Returns:
        Dict mapping relative paths to Path objects.

    Raises:
        NotADirectoryError: If vault_path is not a valid directory.
    """
    vault = Path(vault_path)
    if not vault.is_dir():
        raise NotADirectoryError(
            f"Vault path does not exist or is not a directory: {vault_path}"
        )

    files: dict[str, Path] = {}
    for md_file in vault.rglob("*.md"):
        rel = md_file.relative_to(vault)
        files[str(rel)] = md_file
    return files


# ── Migration ──────────────────────────────────────────────────────────


def scrape_progress_files(vault_path: str) -> list[dict[str, str]]:
    """Scrape .md files from vault returning metadata dicts (mock test helper).

    This function exists to allow testing. It's internal."""
    result: list[dict[str, str]] = []
    md_files = scan_vault(vault_path)
    for rel_str, full_path in md_files.items():
        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            continue
        metadata, body = parse_obsidian_frontmatter(content)
        result.append({
            "rel": rel_str,
            "content": content,
            "metadata": metadata,
            "body": body,
        })
    return result


class MigrationReport:
    """Report of a vault migration operation.

    Attributes:
        vault_path: Path to the source vault.
        nodes_created: int: Number of nodes created.
        edges_created: Number of edges created.
        files_failed: Number of files that could not be read.
    """

    def __init__(
        self,
        vault_path: str = "",
        nodes_created: int = 0,
        edges_created = 0,
        files_failed = 0,
    ) -> None:
        self.vault_path = vault_path
        self.nodes_created = nodes_created
        self.edges_created = edges_created
        self.files_failed = files_failed

    def __str__(self) -> str:
        msg = (
            f"Migration from '{self.vault_path}': "
            f"{self.nodes_created} nodes, {self.edges_created} edges"
        )
        if self.files_failed:
            msg += f", {self.files_failed} files failed"
        return msg


def migrate_from_obsidian(
    db: ContextTreeDB,
    vault_path: str,
    root_node_id: Optional[str] = None,
    default_importance: float = 0.5,
) -> MigrationReport:
    """Import an Obsidian vault into the context tree.

    Creates a branch node for the vault, then walks all .md files
    creating a branch/leaf hierarchy mirroring the vault's directory
    structure. Wiki-links are extracted and stored as edges.

    Args:
        db: Database instance.
        vault_path: Path to the Obsidian vault directory.
        root_node_id: Optional root node under which to place the vault.
        default_importance: Default importance for imported nodes.

    Returns:
        MigrationReport with counts.
    """
    vault_name = Path(vault_path).name

    # Create the vault branch
    if root_node_id is not None:
        vault_branch_id = root_node_id
    else:
        vault_branch = Node(
            title=f"Obsidian Vault: {vault_name}",
            type=NodeType.BRANCH,
            importance=default_importance,
            source="obsidian",
        )
        vault_branch_id = db.create_node(vault_branch)

    # Scan vault for markdown files
    md_files = scan_vault(vault_path)
    created_nodes = 1  # vault branch itself
    created_edges = 0
    files_failed = 0

    # Track path -> node_id for wiki-link resolution
    path_node_map: dict[str, str] = {}
    # Track directory path -> branch node_id
    dir_nodes: dict[str, str] = {"": vault_branch_id}

    # Sort files by path depth for deterministic parent creation
    sorted_paths = sorted(md_files.keys(), key=lambda p: (len(p.split("/")), p))

    # -- First pass: create nodes --
    for rel_path in sorted_paths:
        full_path = md_files[rel_path]

        # Build or find directory branch hierarchy
        parent_id = vault_branch_id
        parts = rel_path.split("/")
        file_name = parts[-1]
        dir_parts = parts[:-1]

        accumulated = ""
        for dp in dir_parts:
            accumulated = f"{accumulated}/{dp}" if accumulated else dp
            if accumulated not in dir_nodes:
                dir_branch = Node(
                    title=dp,
                    type=NodeType.BRANCH,
                    parent_id=parent_id,
                    importance=default_importance,
                    source="obsidian",
                )
                dir_branch_id = db.create_node(dir_branch)
                dir_nodes[accumulated] = dir_branch_id
                created_nodes += 1
            parent_id = dir_nodes[accumulated]

        # Read file content
        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            files_failed += 1
            continue

        metadata, body = parse_obsidian_frontmatter(content)
        title = metadata.get("title", file_name[:-3])

        imp = compute_importance_from_metadata(metadata)
        if imp is None:
            imp = default_importance

        tags_str = metadata.get("tags", "")
        tags = extract_tags_from_content(body)
        tags.extend(extract_tags_from_content(tags_str))
        tags = list(set(tags))

        leaf = Node(
            title=title,
            content=body,
            type=NodeType.LEAF,
            parent_id=parent_id,
            importance=imp,
            tags=tags,
            source="obsidian",
        )
        leaf_id = db.create_node(leaf)
        created_nodes += 1

        # Register in lookup map for wiki-link resolution
        rel_no_ext = rel_path[:-3]
        path_node_map[rel_no_ext] = leaf.node_id
        path_node_map[rel_path] = leaf.node_id
        path_node_map[file_name[:-3]] = leaf.node_id
        path_node_map[title] = leaf.node_id

    # -- Second pass: edges from wiki-links --
    for rel_path in sorted_paths:
        full_path = md_files[rel_path]
        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            continue

        source_key = rel_path[:-3]
        source_id = path_node_map.get(source_key, path_node_map.get(rel_path))
        if source_id is None:
            source_id = path_node_map.get(rel_path.split("/")[-1][:-3])
        if source_id is None:
            continue

        links = extract_obsidian_links(content)
        for target_name in links:
            target_id = path_node_map.get(target_name)
            if target_id is None:
                target_id = path_node_map.get(f"{target_name}.md")
            if target_id is not None and target_id != source_id:
                edge = Edge(
                    source_id=source_id,
                    target_id=target_id,
                    relationship=RelationshipType.REFERENCES,
                    strength=0.5,
                )
                db.create_edge(edge)
                created_edges += 1

    return MigrationReport(
        vault_path=vault_path,
        nodes_created=created_nodes,
        edges_created=created_edges,
        files_failed=files_failed,
    )