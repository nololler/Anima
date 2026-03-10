import os
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

MEMORY_BANKS_ROOT = Path(__file__).parent.parent.parent / "memory_banks"


class MemoryManager:
    def __init__(self, bank_name: str = "default"):
        self.bank_name = bank_name
        self.bank_root = MEMORY_BANKS_ROOT / bank_name
        self._ensure_structure()

    def _ensure_structure(self):
        dirs = ["static", "people", "days", "diary", "images"]
        for d in dirs:
            (self.bank_root / d).mkdir(parents=True, exist_ok=True)
        index_path = self.bank_root / "index.md"
        if not index_path.exists():
            index_path.write_text("# Memory Index\n\nNo entries yet.\n")
        self_path = self.bank_root / "static" / "self.md"
        if not self_path.exists():
            self_path.write_text("# Identity\n\nNo identity configured yet.\n")
        manifest_path = self.bank_root / "images" / "manifest.md"
        if not manifest_path.exists():
            manifest_path.write_text("# Image Manifest\n\nNo images saved yet.\n")

    def resolve_path(self, relative_path: str) -> Path:
        clean = relative_path.lstrip("/").replace("..", "")
        return self.bank_root / clean

    async def read(self, path: str) -> Optional[str]:
        full = self.resolve_path(path)
        if not full.exists():
            return None
        async with aiofiles.open(full, "r", encoding="utf-8") as f:
            return await f.read()

    async def write(self, path: str, content: str) -> bool:
        full = self.resolve_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full, "w", encoding="utf-8") as f:
            await f.write(content)
        return True

    async def append(self, path: str, content: str) -> bool:
        full = self.resolve_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full, "a", encoding="utf-8") as f:
            await f.write("\n" + content)
        return True

    def list_files(self, folder: str = "") -> List[Dict]:
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
        results = []
        query_lower = query.lower()
        for md_file in self.bank_root.rglob("*.md"):
            try:
                async with aiofiles.open(md_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                if query_lower in content.lower():
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

    # ── Diary ─────────────────────────────────────────────────────────

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

    # ── Days (date-gated) ─────────────────────────────────────────────

    def get_today_day_file(self) -> str:
        """Returns the path for today's day file (creates stub filename)."""
        today = datetime.now().strftime("%Y-%m-%d")
        days_dir = self.bank_root / "days"
        # Check if a file for today already exists (may have a title suffix)
        for f in days_dir.iterdir():
            if f.name.startswith(today):
                return str(f.relative_to(self.bank_root))
        return f"days/{today}.md"

    async def write_day_entry(self, content: str, title: Optional[str] = None) -> Dict:
        """
        Date-gated day file writing.
        - If today's file exists: APPENDS content.
        - If today's file doesn't exist: CREATES it with optional title.
        - Never creates files for other dates.
        Returns {"path": ..., "action": "created"|"appended"}.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        days_dir = self.bank_root / "days"

        # Find existing today file
        existing_path = None
        for f in sorted(days_dir.iterdir()):
            if f.name.startswith(today) and f.suffix == ".md":
                existing_path = str(f.relative_to(self.bank_root))
                break

        timestamp = datetime.now().strftime("%H:%M")

        if existing_path:
            await self.append(existing_path, f"\n### {timestamp}\n{content}\n")
            return {"path": existing_path, "action": "appended"}
        else:
            # Create new file for today
            safe_title = ""
            if title:
                import re
                safe_title = "_" + re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:40]
            new_path = f"days/{today}{safe_title}.md"
            header = f"# {title or today}\n\n### {timestamp}\n{content}\n"
            await self.write(new_path, header)
            return {"path": new_path, "action": "created"}

    async def read_day(self, date: Optional[str] = None) -> Optional[str]:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        days_dir = self.bank_root / "days"
        for f in sorted(days_dir.iterdir()):
            if f.name.startswith(date):
                return await self.read(str(f.relative_to(self.bank_root)))
        return None

    # ── People ────────────────────────────────────────────────────────

    async def update_person(self, name: str, content: str) -> bool:
        safe_name = name.replace("/", "_").replace("..", "")
        return await self.write(f"people/{safe_name}.md", content)

    async def read_person(self, name: str) -> Optional[str]:
        safe_name = name.replace("/", "_").replace("..", "")
        return await self.read(f"people/{safe_name}.md")

    # ── Images ────────────────────────────────────────────────────────

    async def save_image(self, name: str, data: bytes, description: str = "", sender: str = "") -> str:
        """Save image bytes and update manifest. Returns saved path."""
        import re
        safe_name = re.sub(r"[^\w\-.]", "_", name)
        if not any(safe_name.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            safe_name += ".png"
        path = f"images/{safe_name}"
        full = self.resolve_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        # Update manifest
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n- **{safe_name}** | {timestamp} | from: {sender or 'unknown'} | {description}"
        await self.append("images/manifest.md", entry)
        return path

    async def read_image_manifest(self) -> str:
        return await self.read("images/manifest.md") or "# Image Manifest\n\nNo images.\n"

    async def list_images(self) -> List[Dict]:
        images_dir = self.bank_root / "images"
        result = []
        for f in sorted(images_dir.iterdir()):
            if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                result.append({
                    "name": f.name,
                    "path": f"images/{f.name}",
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                })
        return result

    # ── Index ─────────────────────────────────────────────────────────

    async def update_index(self, entry: str):
        await self.append("index.md", f"\n- {entry}")

    # ── Bank utilities ────────────────────────────────────────────────

    def get_bank_name(self) -> str:
        return self.bank_name

    @staticmethod
    def list_banks() -> List[str]:
        if not MEMORY_BANKS_ROOT.exists():
            return []
        return [d.name for d in sorted(MEMORY_BANKS_ROOT.iterdir()) if d.is_dir()]
