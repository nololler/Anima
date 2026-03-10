import os
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

MEMORY_BANKS_ROOT = Path(__file__).parent.parent.parent / "memory_banks"
# backend/memory/manager.py → parent=memory, parent.parent=backend, parent.parent.parent=project root


class MemoryManager:
    def __init__(self, bank_name: str = "default"):
        self.bank_name = bank_name
        self.bank_root = MEMORY_BANKS_ROOT / bank_name
        self._ensure_structure()

    def _ensure_structure(self):
        dirs = ["static", "people", "days", "diary", "images"]
        for d in dirs:
            (self.bank_root / d).mkdir(parents=True, exist_ok=True)
        # Ensure index exists
        index_path = self.bank_root / "index.md"
        if not index_path.exists():
            index_path.write_text("# Memory Index\n\nNo entries yet.\n")
        # Ensure self.md exists
        self_path = self.bank_root / "static" / "self.md"
        if not self_path.exists():
            self_path.write_text("# Identity\n\nNo identity configured yet.\n")

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative memory path safely within the bank."""
        clean = relative_path.lstrip("/").replace("..", "")
        return self.bank_root / clean

    async def read(self, path: str) -> Optional[str]:
        full = self.resolve_path(path)
        if not full.exists():
            return None
        async with aiofiles.open(full, "r") as f:
            return await f.read()

    async def write(self, path: str, content: str) -> bool:
        full = self.resolve_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full, "w") as f:
            await f.write(content)
        return True

    async def append(self, path: str, content: str) -> bool:
        full = self.resolve_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full, "a") as f:
            await f.write("\n" + content)
        return True

    def list_files(self, folder: str = "") -> List[Dict]:
        """List files and folders at a path."""
        base = self.resolve_path(folder) if folder else self.bank_root
        if not base.exists():
            return []
        entries = []
        for item in sorted(base.iterdir()):
            entries.append({
                "name": item.name,
                "path": str(item.relative_to(self.bank_root)),
                "type": "folder" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
                "modified": item.stat().st_mtime,
            })
        return entries

    async def search(self, query: str) -> List[Dict]:
        """Keyword search across all .md files."""
        results = []
        query_lower = query.lower()
        for md_file in self.bank_root.rglob("*.md"):
            try:
                async with aiofiles.open(md_file, "r") as f:
                    content = await f.read()
                if query_lower in content.lower():
                    # Find matching lines
                    lines = [
                        {"line": i + 1, "text": line.strip()}
                        for i, line in enumerate(content.splitlines())
                        if query_lower in line.lower()
                    ]
                    results.append({
                        "path": str(md_file.relative_to(self.bank_root)),
                        "matches": lines[:5],
                    })
            except Exception:
                continue
        return results

    async def delete(self, path: str) -> bool:
        full = self.resolve_path(path)
        if full.exists() and full.is_file():
            full.unlink()
            return True
        return False

    async def read_self(self) -> str:
        return await self.read("static/self.md") or "# Identity\n\nNot yet defined.\n"

    async def write_diary(self, content: str) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"diary/{today}.md"
        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n## {timestamp}\n\n{content}\n"
        return await self.append(path, entry)

    async def read_diary(self, date: Optional[str] = None) -> Optional[str]:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return await self.read(f"diary/{date}.md")

    async def update_person(self, name: str, content: str) -> bool:
        safe_name = name.replace("/", "_").replace("..", "")
        return await self.write(f"people/{safe_name}.md", content)

    async def read_person(self, name: str) -> Optional[str]:
        safe_name = name.replace("/", "_").replace("..", "")
        return await self.read(f"people/{safe_name}.md")

    async def update_index(self, entry: str):
        await self.append("index.md", f"\n- {entry}")

    def get_bank_name(self) -> str:
        return self.bank_name

    @staticmethod
    def list_banks() -> List[str]:
        if not MEMORY_BANKS_ROOT.exists():
            return []
        return [d.name for d in MEMORY_BANKS_ROOT.iterdir() if d.is_dir()]
